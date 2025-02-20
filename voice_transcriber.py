import discord
from discord.ext import commands
from discord.ext import voicereceive
import asyncio
import io
import speech_recognition as sr

class LiveTranscriber(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}  # Keep track of voice clients per guild

    @commands.command(name='join', help='Join voice channel and start transcribing')
    async def join(self, ctx):
        if ctx.author.voice is None:
            await ctx.send("You need to be connected to a voice channel first.")
            return
        
        channel = ctx.author.voice.channel

        if ctx.guild.id in self.voice_clients:
            await ctx.send("Already transcribing in this guild.")
            return

        voice_client = await channel.connect(cls=voicereceive.VoiceClient)
        self.voice_clients[ctx.guild.id] = voice_client
        await ctx.send(f"Connected to voice channel: {channel.name} and started transcribing.")

        voice_client.listen(self.on_voice_packet)
    
    @commands.command(name='leave', help='Leave voice channel and stop transcribing')
    async def leave(self, ctx):
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.disconnect()
            self.voice_clients.pop(ctx.guild.id, None)
            await ctx.send("Stopped transcribing and disconnected from the voice channel.")
        else:
            await ctx.send("I'm not connected to a voice channel.")

    async def on_voice_packet(self, packet):
        user = packet.user
        pcm_data = packet.decrypted_data

        # Save PCM data to a temporary WAV file
        with io.BytesIO() as wav_file:
            wav_file.write(self.pcm_to_wav(pcm_data))
            wav_file.seek(0)
            audio_data = sr.AudioFile(wav_file)
            recognizer = sr.Recognizer()
            with audio_data as source:
                audio = recognizer.record(source)
            try:
                result = recognizer.recognize_whisper(audio)
                if result.strip() == "":
                    result = "*Silence detected*"
                # Send the transcription to the text channel
                channel = user.guild.text_channels[0]  # Replace with your desired channel logic
                await channel.send(f"**{user.display_name} said:** {result}")
            except Exception as e:
                print(f"Error transcribing audio: {e}")

    def pcm_to_wav(self, pcm_data, channels=2, rate=48000):
        import wave
        with io.BytesIO() as wav_file:
            with wave.open(wav_file, 'wb') as wav:
                wav.setnchannels(channels)
                wav.setsampwidth(2)  # 2 bytes per sample (16-bit audio)
                wav.setframerate(rate)
                wav.writeframes(pcm_data)
            return wav_file.getvalue() 
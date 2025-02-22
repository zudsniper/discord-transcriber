import io
import os
import re
import sys
import functools

import discord
import speech_recognition
import pydub
from discord.ext import commands

from dotenv import load_dotenv

# Load environment variables first to determine which imports we need
load_dotenv(".env")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Replace config.ini with environment variables
TRANSCRIBE_ENGINE = os.getenv("TRANSCRIBE_ENGINE", "whisper")
TRANSCRIBE_APIKEY = os.getenv("TRANSCRIBE_APIKEY", "0")
TRANSCRIBE_AUTOMATICALLY = os.getenv("TRANSCRIBE_AUTOMATICALLY", "true").lower() == "true"
TRANSCRIBE_VMS_ONLY = os.getenv("TRANSCRIBE_VMS_ONLY", "true").lower() == "true"

# Convert comma-separated string to list of integers for admin users
ADMIN_USERS = [int(i.strip()) for i in os.getenv("ADMIN_USERS", "0").split(",") if i.strip()]
ADMIN_ROLE = int(os.getenv("ADMIN_ROLE", "0"))

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = ADMIN_ROLE != 0

# Create Bot instead of Client
bot = commands.Bot(command_prefix='!', intents=intents)

previous_transcriptions = {}

# Only import whisper-related dependencies if using local whisper
if TRANSCRIBE_ENGINE == "whisper":
	try:
		import whisper
	except ImportError:
		print("Error: Whisper dependencies not installed. Please install requirements-whisper.txt")
		print("pip install -r requirements-whisper.txt")
		sys.exit(1)

@bot.event
async def on_ready():
	print("BOT READY!")
	print("Commands ready!")

async def transcribe_message(message):
	if len(message.attachments) == 0:
		await message.reply("Transcription failed! (No Voice Message)", mention_author=False)
		return
	if TRANSCRIBE_VMS_ONLY and message.attachments[0].content_type != "audio/ogg":
		await message.reply("Transcription failed! (Attachment not a Voice Message)", mention_author=False)
		return
	
	msg = await message.reply("✨ Transcribing...", mention_author=False)
	previous_transcriptions[message.id] = msg.jump_url
	
	# Read voice file and converts it into something pydub can work with
	voice_file = await message.attachments[0].read()
	voice_file = io.BytesIO(voice_file)
	
	# Convert original .ogg file into a .wav file
	x = await bot.loop.run_in_executor(None, pydub.AudioSegment.from_file, voice_file)
	new = io.BytesIO()
	await bot.loop.run_in_executor(None, functools.partial(x.export, new, format='wav'))
	
	# Convert .wav file into speech_recognition's AudioFile format or whatever idrk
	recognizer = speech_recognition.Recognizer()
	with speech_recognition.AudioFile(new) as source:
		audio = await bot.loop.run_in_executor(None, recognizer.record, source)
	
	# Runs the file through OpenAI Whisper (or API, if configured)
	try:
		if TRANSCRIBE_ENGINE == "whisper":
			result = await bot.loop.run_in_executor(None, recognizer.recognize_whisper, audio)
		elif TRANSCRIBE_ENGINE == "api":
			if TRANSCRIBE_APIKEY == "0":
				await msg.edit("Transcription failed! (Configured to use Whisper API, but no API Key provided!)")
				return
			result = await bot.loop.run_in_executor(None, functools.partial(recognizer.recognize_whisper_api, audio, api_key=TRANSCRIBE_APIKEY))
	except Exception as e:
		await msg.edit(f"Transcription failed! Error: {str(e)}")
		return

	if result == "":
		result = "*nothing*"
	# Send results + truncate in case the transcript is longer than 1900 characters
	truncated = len(result) > 1900
	await msg.edit(content="```" + result[:1900] + ("..." if truncated else "") + "```" + (" *(truncated)*" if truncated else ""))
	print(f"full transcript: {result}")


def is_manager(input: discord.Interaction or discord.message) -> bool:
	if type(input) is discord.Interaction:
		user = input.user
	else:
		user = input.author
	
	if user.id in ADMIN_USERS:
		return True
	
	if ADMIN_ROLE != 0:
		admin = input.guild.get_role(ADMIN_ROLE)

		if user in admin.members:
			return True

	return False


@bot.event
async def on_message(message):
	if TRANSCRIBE_AUTOMATICALLY and message.flags.voice and len(message.attachments) == 1:
		await transcribe_message(message)
	# Make sure we process commands
	await bot.process_commands(message)

@bot.command(name="opensource", description="Get information about the bot's source code")
async def open_source(ctx):
	embed = discord.Embed(
    	title="Open Source",
    	description="This bot is open source! You can find the source code "
                    "[here](https://github.com/RyanCheddar/discord-voice-message-transcriber)",
    	color=0x00ff00
	)
	await ctx.send(embed=embed)
    
@bot.command(name="transcribe")
async def transcribe_command(ctx, message: discord.Message):
	if message.id in previous_transcriptions:
		await ctx.send(content=previous_transcriptions[message.id], ephemeral=True)
		return
	await ctx.send(content="Transcription started!", ephemeral=True)
	await transcribe_message(message)


if __name__ == "__main__":
	bot.run(BOT_TOKEN)

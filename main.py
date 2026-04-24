import os
import dotenv
from discord import Intents
from discord.ext import commands

dotenv.load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Game(name="!help"))


@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")


if __name__ == "__main__":
    if not BOT_TOKEN:
        print("Error: DISCORD_BOT_TOKEN not found in .env file")
        exit(1)
    bot.run(BOT_TOKEN)
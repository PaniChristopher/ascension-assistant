import os
import asyncio
import threading
import dotenv
import discord
from discord import Intents
from discord.ext import commands, tasks
from flask import Flask, request, jsonify

dotenv.load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

DISCORD_CHANNEL_ID = 1465712191964713063
WEBHOOK_PORT = 8080

intents = Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

webhook_app = Flask(__name__)
webhook_queue = asyncio.Queue()


@webhook_app.route("/webhook", methods=["POST"])
def receive_webhook():
    data = request.json
    if data:
        try:
            loop = bot.loop
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(webhook_queue.put(data), loop)
        except Exception as e:
            print(f"Queue error: {e}")
    return jsonify({"status": "ok"})


def run_webhook_server():
    webhook_app.run(host="0.0.0.0", port=WEBHOOK_PORT)


@tasks.loop(seconds=1)
async def check_queue():
    while not webhook_queue.empty():
        try:
            data = await asyncio.wait_for(webhook_queue.get(), timeout=0.1)
            channel = bot.get_channel(DISCORD_CHANNEL_ID)
            if channel and data:
                embed = discord.Embed(
                    title=data.get("title", "New Post"),
                    color=discord.Color.blue()
                )
                if "message" in data:
                    embed.add_field(name="Message", value=data["message"], inline=False)
                if "link" in data:
                    embed.add_field(name="Link", value=data["link"], inline=False)
                if "source" in data:
                    embed.set_footer(text=f"Posted on {data['source']}")
                await channel.send(embed=embed)
        except asyncio.QueueEmpty:
            break
        except Exception as e:
            print(f"Error processing webhook: {e}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Helping Ascension Esports"))
    check_queue.start()


@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")


@bot.command()
async def webhook_url(ctx):
    await ctx.send(f"```\nGeneral webhook: http://YOUR_IP:{WEBHOOK_PORT}/webhook\n\nExample POST body:\n{{\n  \"title\": \"New Post\",\n  \"message\": \"Your message\",\n  \"link\": \"https://...\",\n  \"source\": \"Instagram\"\n}}\n```")
    await channel.send(f"General webhook: http://YOUR_IP:{WEBHOOK_PORT}/webhook")
    await channel.send(f"Example POST body:")
    await channel.send("""{
  "title": "New Post",
  "message": "Your message",
  "link": "https://...",
  "source": "Instagram"
}""")
    await channel.send("```")


if __name__ == "__main__":
    if not BOT_TOKEN:
        print("Error: DISCORD_BOT_TOKEN not found in .env file")
        exit(1)
    threading.Thread(target=run_webhook_server, daemon=True).start()
    print(f"Webhook server running on port {WEBHOOK_PORT}")
    bot.run(BOT_TOKEN)
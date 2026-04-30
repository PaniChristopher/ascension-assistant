import os
import asyncio
import threading
import time
import requests
import dotenv
import discord
from discord import Intents
from discord.ext import commands, tasks
from flask import Flask, request, jsonify

dotenv.load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

DISCORD_CHANNEL_ID = 1465712191964713063
WEBHOOK_PORT = 8080

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_CREATORS = os.getenv("TWITCH_CREATORS", "").split(",")

TWITCH_ACCESS_TOKEN = None
TWITCH_TOKEN_EXPIRY = 0

intents = Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

webhook_app = Flask(__name__)
webhook_queue = asyncio.Queue()
twitch_users = {}
live_streams = {}


def get_twitch_access_token():
    global TWITCH_ACCESS_TOKEN, TWITCH_TOKEN_EXPIRY
    if TWITCH_ACCESS_TOKEN and time.time() < TWITCH_TOKEN_EXPIRY:
        return TWITCH_ACCESS_TOKEN
    
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    resp = requests.post(url, params=params)
    if resp.status_code == 200:
        data = resp.json()
        TWITCH_ACCESS_TOKEN = data["access_token"]
        TWITCH_TOKEN_EXPIRY = time.time() + data["expires_in"] - 60
        return TWITCH_ACCESS_TOKEN
    return None


def get_twitch_user_id(username):
    if username in twitch_users:
        return twitch_users[username]
    
    url = "https://api.twitch.tv/helix/users"
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {get_twitch_access_token()}"
    }
    params = {"login": username}
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        data = resp.json()
        if data["data"]:
            twitch_users[username] = data["data"][0]["id"]
            return data["data"][0]["id"]
    return None


def check_twitch_stream(user_id):
    url = "https://api.twitch.tv/helix/streams"
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {get_twitch_access_token()}"
    }
    params = {"user_id": user_id}
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        data = resp.json()
        if data["data"]:
            return data["data"][0]
    return None


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


@tasks.loop(seconds=60)
async def check_twitch():
    if not TWITCH_CREATORS or not TWITCH_CLIENT_ID:
        return
    
    for creator in TWITCH_CREATORS:
        creator = creator.strip()
        if not creator:
            continue
        
        user_id = get_twitch_user_id(creator)
        if not user_id:
            continue
        
        stream = check_twitch_stream(user_id)
        is_live = live_streams.get(creator, False)
        
        if stream and not is_live:
            live_streams[creator] = True
            channel = bot.get_channel(DISCORD_CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title=f"{creator} is LIVE on Twitch!",
                    color=discord.Color.red()
                )
                embed.add_field(name="Title", value=stream["title"], inline=False)
                embed.add_field(name="Game", value=stream["game_name"], inline=False)
                embed.add_field(name="Watch", value=f"https://twitch.tv/{creator}", inline=False)
                await channel.send(embed=embed)
        elif not stream and is_live:
            live_streams[creator] = False


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
    if TWITCH_CREATORS and TWITCH_CLIENT_ID:
        check_twitch.start()


@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")


if __name__ == "__main__":
    threading.Thread(target=run_webhook_server, daemon=True).start()
    print(f"Webhook server running on port {WEBHOOK_PORT}")
    bot.run(BOT_TOKEN)
import discord
from dotenv import load_dotenv
from discord.ext import commands, tasks
import aiohttp
import os

# Initialize bot with command prefix and all intents
bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())
latest_commit_sha = None  # To store the latest commit SHA
latest_etag = None  # To store the latest ETag received from GitHub API

# Event that runs once when the bot is ready
@bot.event
async def on_ready():
    check_github_commits.start()  # Start the task for checking GitHub commits

# Command for checking the current rate limit status
@bot.command()
async def ratelimit(ctx):
    headers = {
        'Authorization': f'token {os.getenv("GITHUB_TOKEN")}'
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(os.getenv('REPO_URL'), headers=headers) as response:
            limit = response.headers.get('X-RateLimit-Limit')
            remaining = response.headers.get('X-RateLimit-Remaining')

            # Create an embed message with the rate limit details
            embed = discord.Embed(title="GitHub API Rate Limit Status", color=discord.Color.red())
            embed.add_field(name="Limit", value=limit, inline=False)
            embed.add_field(name="Remaining", value=remaining, inline=False)
            await ctx.send(embed=embed)

# Task that runs every minute to check for new commits
@tasks.loop(minutes=1.0)
async def check_github_commits():
    global latest_commit_sha
    global latest_etag

    # Include the ETag in the header if it exists, along with the Authorization
    headers = {
        'If-None-Match': latest_etag,
        'Authorization': f'token {os.getenv("GITHUB_TOKEN")}'
    } if latest_etag else {
        'Authorization': f'token {os.getenv("GITHUB_TOKEN")}'
    }

    # Make a GET request to the GitHub API
    async with aiohttp.ClientSession() as session:
        async with session.get(os.getenv('REPO_URL'), headers=headers) as response:
            if response.status == 304:
                # No new data, so no action required
                return
            latest_etag = response.headers.get('ETag')
            data = await response.json()

    new_commit_sha = data[0]['sha']

    # If this is the first run, just store the latest commit SHA and don't post anything
    if latest_commit_sha is None:
        latest_commit_sha = new_commit_sha
        return

    # If the commit SHA has changed, post the new commit details
    if new_commit_sha != latest_commit_sha:
        commit_author = data[0]['commit']['author']['name']
        commit_message = data[0]['commit']['message']
        commit_url = data[0]['html_url']

        # Create an embed message with the commit details
        embed = discord.Embed(description=commit_message, color=discord.Color.orange())
        embed.add_field(name="Commit URL", value=commit_url)
        embed.set_footer(text=f'New commit by {commit_author}')
        
        channel = bot.get_channel(int(os.getenv('CHANNEL_ID')))  # Get the channel to post in
        await channel.send(embed=embed)  # Send the message
        latest_commit_sha = new_commit_sha

load_dotenv()  # Load the environment variables from .env file
bot.run(os.getenv('BOT_TOKEN'))  # Start the bot with your bot token

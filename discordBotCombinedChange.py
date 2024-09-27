import discord
from discord.ext import commands, tasks
import aiohttp
from bs4 import BeautifulSoup
import json
import time

# Dictionary to track sent alerts: {user_id: {server_name: last_alert_time}}
sent_alerts = {}

# Create a bot instance with both regular and slash commands
intents = discord.Intents.all()
client = commands.Bot(command_prefix='!', intents=intents)

# Load user preferences from a file
def load_preferences():
    try:
        with open('preferences.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Save user preferences to a file
def save_preferences(preferences):
    with open('preferences.json', 'w') as f:
        json.dump(preferences, f)

# This dictionary will hold user preference
user_preferences = load_preferences()

@client.event
async def on_ready():
    await client.tree.sync()  # Sync slash commands when the bot is fully ready
    print("Bud Bot Online")
    print("*******************")
    check_server_status.start()  # Start the background task

# Slash command to set alert
@client.tree.command(name="setalert", description="Set an alert when a server has a certain amount of players")
async def set_alert(interaction: discord.Interaction, server_name: str, threshold: int):
    user_id = str(interaction.user.id)
    if user_id not in user_preferences:
        user_preferences[user_id] = {}

    user_preferences[user_id][server_name] = threshold
    save_preferences(user_preferences)
    await interaction.response.send_message(f"Alert set for {server_name} at population threshold {threshold}.")

# Task to check server status every 30 minutes
@tasks.loop(minutes=30)
async def check_server_status():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://servers.moviebattles.org') as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                server_rows = soup.find_all('tr', class_='serverlistrow')

                for user_id, servers in user_preferences.items():
                    user = await client.fetch_user(user_id)
                    for keyword, threshold in servers.items():
                        for row in server_rows:
                            server_name_row = row.find_all('td')[1].text.strip()
                            player_count = int(row.find_all('td')[6].text.strip().split('/')[0])  # Extract current player count

                            # Check if the keyword is in the server name
                            if keyword.lower() in server_name_row.lower() and player_count >= threshold:
                                current_time = time.time()
                                last_alert_time = sent_alerts.get(user_id, {}).get(server_name_row)

                                if last_alert_time is None or (current_time - last_alert_time) > 1800:  # 1800 seconds = 30 minutes
                                    await user.channel.send(f"{server_name_row} is well populated with {player_count} players!")
                                    # Update the last alert time
                                    if user_id not in sent_alerts:
                                        sent_alerts[user_id] = {}
                                    sent_alerts[user_id][server_name_row] = current_time

# Slash command to stop alerts
@client.tree.command(name="stopalert", description="Stop receiving alerts")
async def stop_alert(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id in user_preferences:
        del user_preferences[user_id]
        save_preferences(user_preferences)
        await interaction.response.send_message("Your alerts have been stopped.")

# Define a slash command for server list
@client.tree.command(name="serverlist", description="Fetches the top 5 most populated servers")
async def serverlist(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://servers.moviebattles.org') as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                server_rows = soup.find_all('tr', class_='serverlistrow')[:5]

                server_list = []

                for index, row in enumerate(server_rows, start=1):
                    server_name = row.find_all('td')[1].text.strip()
                    map_name = row.find_all('td')[5].text.strip()
                    player_count = row.find_all('td')[6].text.strip()

                    server_info = f"{index}) {server_name}    {map_name}    {player_count}"
                    server_list.append(server_info)

                response_message = "Top 5 Most Populated Servers:\n" + "\n".join(server_list)
                await interaction.response.send_message(response_message)
            else:
                await interaction.response.send_message("Failed to retrieve server data.", ephemeral=True)

# Error handler for slash commands
@client.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CommandInvokeError):
        await interaction.response.send_message("There was an error executing the command.", ephemeral=True)
    else:
        await interaction.response.send_message(f"An unexpected error occurred: {error}", ephemeral=True)
        
# Basic message response
@client.event
async def on_message(message):
    contentLower = message.content.lower()
    if "bud" in contentLower:
        await message.channel.send("huh")
    await client.process_commands(message)

client.run('token')

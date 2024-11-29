import discord
from discord.ext import commands
import json
import random
import os
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Bot configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
RIOT_API_KEY = os.getenv('RIOT_API_KEY')
RIOT_API_BASE_URL = "https://na1.api.riotgames.com/lol"

# Initialize bot with explicit intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix='#', intents=intents)

# Tier points mapping
TIER_POINTS = {
    "I4": 1.0, "I3": 1.5, "I2": 2.0, "I1": 2.5,
    "B4": 3.0, "B3": 3.5, "B2": 4.0, "B1": 4.5,
    "S4": 5.0, "S3": 5.5, "S2": 6.0, "S1": 6.5,
    "G4": 7.0, "G3": 7.5, "G2": 8.0, "G1": 8.5,
    "P4": 9.0, "P3": 9.5, "P2": 10.0, "P1": 10.5,
    "E4": 11.0, "E3": 11.5, "E2": 12.0, "E1": 12.5,
    "D4": 13.0, "D3": 13.5, "D2": 14.0, "D1": 14.5,
    "M": 16.0,
    "GM": 18.0,
    "C": 20.0
}

async def get_summoner_data(summoner_name):
    """Get basic summoner data from Riot API"""
    headers = {"X-Riot-Token": RIOT_API_KEY}
    url = f"{RIOT_API_BASE_URL}/summoner/v4/summoners/by-name/{summoner_name}"
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

async def get_match_history(puuid, count=10):
    """Get recent matches for a summoner"""
    headers = {"X-Riot-Token": RIOT_API_KEY}
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count={count}"
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        match_ids = response.json()
        matches = []
        for match_id in match_ids:
            match_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
            match_response = requests.get(match_url, headers=headers)
            if match_response.status_code == 200:
                matches.append(match_response.json())
        return matches
    return None

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='leagueofflex')
async def league_flex(ctx, *args):
    if len(args) == 0:
        await ctx.send("Please provide a summoner name or team data!")
        return
    
    # Check if it's a JSON input (team balancing)
    if args[0].startswith('{'):
        try:
            # Combine all args in case JSON was split
            json_str = ' '.join(args)
            data = json.loads(json_str)
            players = data.get('players', [])
            
            if len(players) != 10:
                await ctx.send("Please provide exactly 10 players!")
                return
            
            # Calculate player scores
            player_scores = []
            for player, rank in players:
                score = TIER_POINTS.get(rank, 0)
                player_scores.append((player, score))
            
            # Sort players by score
            player_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Create balanced teams
            team1 = []
            team2 = []
            team1_score = 0
            team2_score = 0
            
            # Distribute players to balance teams
            for i, (player, score) in enumerate(player_scores):
                if team1_score <= team2_score:
                    team1.append(player)
                    team1_score += score
                else:
                    team2.append(player)
                    team2_score += score
            
            # Create response embed
            embed = discord.Embed(title="Balanced Teams", color=0x00ff00)
            embed.add_field(name="Team 1", value="\n".join(team1), inline=True)
            embed.add_field(name="Team 2", value="\n".join(team2), inline=True)
            embed.add_field(name="Team Scores", value=f"Team 1: {team1_score:.1f}\nTeam 2: {team2_score:.1f}", inline=False)
            
            await ctx.send(embed=embed)
            return
            
        except json.JSONDecodeError:
            await ctx.send("Invalid JSON format! Please check your input.")
            return
        except Exception as e:
            await ctx.send(f"Error processing team data: {str(e)}")
            return
    
    # Handle single summoner lookup
    summoner_name = args[0]
    champion_name = args[1] if len(args) > 1 else None
    
    summoner = await get_summoner_data(summoner_name)
    if not summoner:
        await ctx.send(f"Could not find summoner: {summoner_name}")
        return
    
    matches = await get_match_history(summoner['puuid'])
    if not matches:
        await ctx.send(f"Could not fetch match history for: {summoner_name}")
        return
    
    # Create response embed
    embed = discord.Embed(title=f"Summoner Profile: {summoner_name}", color=0x00ff00)
    
    # Add match history
    match_history = ""
    for match in matches:
        for participant in match['info']['participants']:
            if participant['puuid'] == summoner['puuid']:
                champion = participant['championName']
                kda = f"{participant['kills']}/{participant['deaths']}/{participant['assists']}"
                win = "Won" if participant['win'] else "Lost"
                
                if champion_name:
                    if champion.lower() == champion_name.lower():
                        match_history += f"{champion}: {kda} - {win}\n"
                else:
                    match_history += f"{champion}: {kda} - {win}\n"
    
    embed.add_field(name="Recent Matches", value=match_history if match_history else "No matches found", inline=False)
    await ctx.send(embed=embed)

# Run the bot
bot.run(DISCORD_TOKEN)
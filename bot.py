import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from itertools import combinations

# Load environment variables
load_dotenv()

# Bot configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Initialize bot with explicit intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix='#', intents=intents)

# Tier points mapping
TIER_POINTS = {
    "I4": 1.0, "I3": 1.3, "I2": 1.6, "I1": 1.9,
    "B4": 2.3, "B3": 2.7, "B2": 3.1, "B1": 3.5,
    "S4": 4.0, "S3": 4.6, "S2": 5.2, "S1": 5.8,
    "G4": 6.5, "G3": 7.2, "G2": 7.9, "G1": 8.6,
    "P4": 9.4, "P3": 10.2, "P2": 11.0, "P1": 11.8,
    "E4": 12.8, "E3": 13.8, "E2": 14.8, "E1": 15.8,
    "D4": 17.0, "D3": 18.2, "D2": 19.4, "D1": 20.6,
    "M": 23.0,  
    "GM": 27.0, 
    "C": 30.0    
}

player_pool = []

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

def format_tier_points():
    """Format tier points in a more compact way"""
    tiers = {
        "Iron": ["I4", "I3", "I2", "I1"],
        "Bronze": ["B4", "B3", "B2", "B1"],
        "Silver": ["S4", "S3", "S2", "S1"],
        "Gold": ["G4", "G3", "G2", "G1"],
        "Platinum": ["P4", "P3", "P2", "P1"],
        "Emerald": ["E4", "E3", "E2", "E1"],
        "Diamond": ["D4", "D3", "D2", "D1"],
        "Special": ["M", "GM", "C"]
    }
    
    formatted_tiers = []
    for tier_name, ranks in tiers.items():
        if tier_name == "Special":
            tier_str = "Master: 23.0 | Grandmaster: 27.0 | Challenger: 30.0"
        else:
            points = [f"{rank}: {TIER_POINTS[rank]}" for rank in ranks]
            tier_str = f"{tier_name}: {' | '.join(points)}"
        formatted_tiers.append(tier_str)
    
    return formatted_tiers

@bot.command(name='leagueofflex')
async def league_flex(ctx, *, input_text=None):
    if not input_text:
        await ctx.send("Please use `#leagueofflex help` for command information.")
        return
    
    args = input_text.split()
    command = args[0].lower()

    # Help command
    if command == 'help':
        embed = discord.Embed(title="League of Legends Team Balancer Help", color=0x00ff00)
        embed.add_field(name="Available Commands", value=(
            "1. `#leagueofflex team [player1] [rank1] [player2] [rank2] ...`\n"
            "   - Creates balanced 5v5 teams\n"
            "   - Requires exactly 10 players with their ranks\n\n"
            "2. `#leagueofflex tiers`\n"
            "   - Shows all tier point values\n\n"
            "3. `#leagueofflex help`\n"
            "   - Shows this help message\n\n"
            "4. `#join [rank]`\n"
            "   - Join the player pool for a quick match\n\n"
            "5. `#tournament [player1] [rank1] [player2] [rank2] ...`\n"
            "   - Create teams for a tournament with multiple players"
        ), inline=False)
        
        embed.add_field(name="Example Team Command", value=(
            "`#leagueofflex team Player1 D4 Player2 G1 Player3 P2 Player4 S3 Player5 B2 "
            "Player6 D2 Player7 P4 Player8 G3 Player9 S1 Player10 B4`"
        ), inline=False)
        
        embed.add_field(name="Valid Ranks", value=(
            "Iron: I4-I1\n"
            "Bronze: B4-B1\n"
            "Silver: S4-S1\n"
            "Gold: G4-G1\n"
            "Platinum: P4-P1\n"
            "Emerald: E4-E1\n"
            "Diamond: D4-D1\n"
            "Special: M (Master), GM (Grandmaster), C (Challenger)"
        ), inline=False)
        
        await ctx.send(embed=embed)
        return

    # Tiers command
    if command == 'tiers':
        embed = discord.Embed(title="League of Legends Rank Point Values", color=0x00ff00)
        for tier_str in format_tier_points():
            name, values = tier_str.split(': ', 1)
            embed.add_field(name=name, value=values, inline=False)
        await ctx.send(embed=embed)
        return

    # Team balancing command (Manual input of players)
    if command == 'team':
        args = args[1:]  # Remove 'team' from args
        if len(args) < 20:
            await ctx.send("For team balancing, provide 10 players with their ranks.\nUse `#leagueofflex help` for more information.")
            return
        
        try:
            players = []
            for i in range(0, 20, 2):
                player_name = args[i]
                player_rank = args[i+1].upper()
                if player_rank not in TIER_POINTS:
                    await ctx.send(f"Invalid rank '{player_rank}' for player '{player_name}'. Use `#leagueofflex help` to see valid ranks.")
                    return
                players.append((player_name, player_rank, TIER_POINTS[player_rank]))
            
            await create_balanced_teams(ctx, players)

        except Exception as e:
            await ctx.send("Error creating teams. Use `#leagueofflex help` for the correct format.")
            print(f"Error: {str(e)}")  # For debugging
            return

# Player Queue Command
@bot.command(name='join')
async def join(ctx, rank: str):
    rank = rank.upper()
    if rank not in TIER_POINTS:
        await ctx.send(f"Invalid rank '{rank}'. Use `#leagueofflex help` to see valid ranks.")
        return

    player_name = ctx.author.name
    player_info = (player_name, rank, TIER_POINTS[rank])

    if player_info in player_pool:
        await ctx.send(f"{player_name} is already in the queue.")
        return

    player_pool.append(player_info)
    await ctx.send(f"{player_name} joined the queue as {rank}.")

    if len(player_pool) >= 10:
        await create_balanced_teams(ctx, player_pool[:10])
        del player_pool[:10]

async def create_balanced_teams(ctx, players):
    best_diff = float('inf')
    best_team1 = None
    best_team2 = None

    for team1_indices in combinations(range(10), 5):
        team1 = [players[i] for i in team1_indices]
        team2 = [players[i] for i in range(10) if i not in team1_indices]

        team1_score = sum(player[2] for player in team1)
        team2_score = sum(player[2] for player in team2)

        diff = abs(team1_score - team2_score)
        if diff < best_diff:
            best_diff = diff
            best_team1 = team1
            best_team2 = team2

    embed = discord.Embed(title="Balanced Teams (5v5)", color=0x00ff00)

    team1_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in best_team1])
    team2_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in best_team2])

    embed.add_field(name=f"Team 1", value=team1_info, inline=True)
    embed.add_field(name=f"Team 2", value=team2_info, inline=True)
    embed.add_field(name="Balance Info", value=f"Point Difference: {best_diff:.1f} points", inline=False)

    await ctx.send(embed=embed)

# Tournament Command
@bot.command(name='tournament')
async def tournament(ctx, *, input_text=None):
    if not input_text:
        await ctx.send("Please provide players and their ranks. Example: `#leagueofflex tournament Player1 D4 Player2 G1 ...`")
        return

    args = input_text.split()
    if len(args) % 2 != 0:
        await ctx.send("Incorrect input format. Each player must have a rank. Use `#leagueofflex help` for more information.")
        return

    players = []
    for i in range(0, len(args), 2):
        player_name = args[i]
        player_rank = args[i + 1].upper()
        if player_rank not in TIER_POINTS:
            await ctx.send(f"Invalid rank '{player_rank}' for player '{player_name}'. Use `#leagueofflex help` to see valid ranks.")
            return
        players.append((player_name, player_rank, TIER_POINTS[player_rank]))

    if len(players) < 5:
        await ctx.send("Not enough players to form a single team.")
        return

    team_count = len(players) // 5
    leftover_players = len(players) % 5

    teams = []
    for i in range(team_count):
        teams.append(players[i * 5:(i + 1) * 5])

    embed = discord.Embed(title="Tournament Teams", color=0x00ff00)

    for idx, team in enumerate(teams, start=1):
        team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in team])
        embed.add_field(name=f"Team {idx}", value=team_info, inline=False)

    if leftover_players > 0:
        leftovers = players[-leftover_players:]
        leftover_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in leftovers])
        embed.add_field(name="Leftover Players", value=leftover_info, inline=False)
        embed.set_footer(text="These players need more teammates to form a complete team.")

    await ctx.send(embed=embed)

# Run the bot
bot.run(DISCORD_TOKEN)

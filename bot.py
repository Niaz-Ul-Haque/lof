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
            tier_str = "Master: 16.0 | Grandmaster: 18.0 | Challenger: 20.0"
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
            "   - Shows this help message"
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
    
    # Team balancing command
    if command == 'team':
        args = args[1:]  # Remove 'team' from args
        if len(args) < 20:
            await ctx.send("For team balancing, provide 10 players with their ranks.\nUse `#leagueofflex help` for more information.")
            return
        
        try:
            # Process players in pairs (name, rank)
            players = []
            for i in range(0, 20, 2):
                player_name = args[i]
                player_rank = args[i+1].upper()
                if player_rank not in TIER_POINTS:
                    await ctx.send(f"Invalid rank '{player_rank}' for player '{player_name}'. Use `#leagueofflex help` to see valid ranks.")
                    return
                players.append((player_name, player_rank, TIER_POINTS[player_rank]))
            
            # Sort players by score
            players.sort(key=lambda x: x[2], reverse=True)
            
            # Find the most balanced 5v5 combination
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
            
            # Calculate total scores
            team1_score = sum(player[2] for player in best_team1)
            team2_score = sum(player[2] for player in best_team2)
            
            # Create response embed
            embed = discord.Embed(title="Balanced Teams (5v5)", color=0x00ff00)
            
            # Show teams with detailed information
            team1_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in best_team1])
            team2_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in best_team2])
            
            embed.add_field(name=f"Team 1 (Total: {team1_score:.1f} pts)", value=team1_info, inline=True)
            embed.add_field(name=f"Team 2 (Total: {team2_score:.1f} pts)", value=team2_info, inline=True)
            
            # Add score difference
            embed.add_field(name="Balance Info", 
                          value=f"Point Difference: {abs(team1_score - team2_score):.1f} points",
                          inline=False)
            
            # Add tier point values at the bottom
            embed.add_field(name="Ranking System", value="\n".join(format_tier_points()), inline=False)
            
            await ctx.send(embed=embed)
            return
            
        except Exception as e:
            await ctx.send("Error creating teams. Use `#leagueofflex help` for the correct format.")
            print(f"Error: {str(e)}")  # For debugging
            return
    
    else:
        await ctx.send("Unknown command. Use `#leagueofflex help` for available commands.")

# Run the bot
bot.run(DISCORD_TOKEN)
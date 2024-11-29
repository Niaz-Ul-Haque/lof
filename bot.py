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

@bot.command(name='leagueofflex')
async def league_flex(ctx, *, input_text=None):
    if not input_text:
        await ctx.send("For team balancing use: #leagueofflex team player1 rank1 player2 rank2 ...")
        return
    
    args = input_text.split()
    
    # Check if it's a team balancing request
    if args[0].lower() == 'team':
        args = args[1:]  # Remove 'team' from args
        if len(args) < 20:  # Need 20 args for 10 players (name + rank for each)
            await ctx.send("For team balancing, provide 10 players with their ranks.\nFormat: #leagueofflex team player1 rank1 player2 rank2 ...")
            return
        
        try:
            # Process players in pairs (name, rank)
            players = []
            for i in range(0, 20, 2):
                player_name = args[i]
                player_rank = args[i+1].upper()  # Convert rank to uppercase
                if player_rank not in TIER_POINTS:
                    await ctx.send(f"Invalid rank '{player_rank}' for player '{player_name}'. Valid ranks: I4-I1, B4-B1, S4-S1, G4-G1, P4-P1, D4-D1, M, GM, C")
                    return
                players.append((player_name, player_rank, TIER_POINTS[player_rank]))
            
            # Sort players by score
            players.sort(key=lambda x: x[2], reverse=True)
            
            # Find the most balanced 5v5 combination
            best_diff = float('inf')
            best_team1 = None
            best_team2 = None
            
            # Try all possible combinations of 5 players
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
            
            # Show tier point values
            tier_info = "**Tier Point Values:**\n"
            tier_info += "\n".join([f"{tier}: {points} points" for tier, points in sorted(TIER_POINTS.items(), key=lambda x: x[1])])
            embed.add_field(name="Ranking System", value=tier_info, inline=False)
            
            # Show teams with detailed information
            team1_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in best_team1])
            team2_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in best_team2])
            
            embed.add_field(name=f"Team 1 (Total: {team1_score:.1f} pts)", value=team1_info, inline=True)
            embed.add_field(name=f"Team 2 (Total: {team2_score:.1f} pts)", value=team2_info, inline=True)
            
            # Add score difference
            embed.add_field(name="Balance Info", 
                          value=f"Point Difference: {abs(team1_score - team2_score):.1f} points",
                          inline=False)
            
            await ctx.send(embed=embed)
            return
            
        except Exception as e:
            await ctx.send(f"Error creating teams. Make sure you're using the correct format:\n#leagueofflex team player1 rank1 player2 rank2 ...")
            print(f"Error: {str(e)}")  # For debugging
            return
    
    else:
        await ctx.send("Please use the team balancing command format:\n#leagueofflex team player1 rank1 player2 rank2 ...")

# Run the bot
bot.run(DISCORD_TOKEN)
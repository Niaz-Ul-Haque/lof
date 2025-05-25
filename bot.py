import discord
from discord.ext import commands
from discord.ui import Button, View
import os
from dotenv import load_dotenv
from itertools import combinations
import random
import asyncio
import string
from datetime import datetime
from supabase import create_client, Client

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix='!lf ', intents=intents, help_command=None)

# Global variables
player_pool = []
queue_timer = None
queue_start_time = None

# Tier points and role to rank mapping
TIER_POINTS = {
    "I": 1.0,        
    "IB": 2.0,   
    "B": 3.0,    
    "BS": 4.0,   
    "S": 5.0,        
    "SG": 6.5,   
    "G": 8.0,      
    "GP": 9.5,   
    "P": 11.0,  
    "PE": 13.0, 
    "E": 15.0,   
    "ED": 17.0, 
    "D": 19.0,   
    "DM": 21.5,
    "M": 24.0,       
    "GM": 27.0,  
    "C": 30.0    
}

ROLE_TO_RANK = {
    "Iron": "I",
    "Iron-Bronze": "IB",
    "Bronze": "B",
    "Bronze-Silver": "BS",
    "Silver": "S", 
    "Silver-Gold": "SG",
    "Gold": "G",
    "Gold-Platinum": "GP",
    "Platinum": "P",
    "Platinum-Emerald": "PE",
    "Emerald": "E",
    "Emerald-Diamond": "ED",
    "Diamond": "D",
    "Diamond-Masters": "DM",
    "Master": "M",
    "Grandmaster": "GM",
    "Challenger": "C"
}

TEAM_NAMES = [
    "David's Coochies", "Driller Drug overdose", "Austin's Python", "Twasen and bumble", "Marc Carney's butt",
    "Autotune's cousin", "RIP Solace", "Silent is _____", "Wuss Squad", "Dried peen",
    "My name is Ross", "Masala Party", "Chinese Tariffs", "Shaved bootyhole", "We are racist",
]

# Color constants for better UI
BLUE_COLOR = 0x3498DB
RED_COLOR = 0xE74C3C
GREEN_COLOR = 0x2ECC71
PURPLE_COLOR = 0x9B59B6
ORANGE_COLOR = 0xE67E22
TEAL_COLOR = 0x1ABC9C

# Website to plug
WEBSITE_URL = "https://www.leagueofflex.com"

# ========================= Database Functions =========================

def generate_match_id():
    """Generate a unique 6-character match ID."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

async def create_match(team1_name, team1_players, team2_name, team2_players):
    """Create a new match in the database."""
    try:
        match_id = generate_match_id()
        
        # Ensure match_id is unique
        while True:
            existing = supabase.table('matches').select('match_id').eq('match_id', match_id).execute()
            if not existing.data:
                break
            match_id = generate_match_id()
        
        match_data = {
            'match_id': match_id,
            'team1_name': team1_name,
            'team2_name': team2_name,
            'team1_players': team1_players,
            'team2_players': team2_players,
            'winner': None,
            'created_at': datetime.now().isoformat(),
            'updated_by': None
        }
        
        result = supabase.table('matches').insert(match_data).execute()
        return match_id, True
    except Exception as e:
        print(f"Error creating match: {e}")
        return None, False

async def update_match_result(match_id, winner_team, moderator_name):
    """Update match result and player stats."""
    try:
        # Get match details
        match_result = supabase.table('matches').select('*').eq('match_id', match_id).execute()
        if not match_result.data:
            return False, "Match not found"
        
        match = match_result.data[0]
        
        # Check if this is the first time setting a result or editing an existing one
        is_first_result = match['winner'] is None
        previous_winner = match['winner']
        
        # Update match result
        update_data = {
            'winner': winner_team,
            'updated_by': moderator_name,
            'updated_at': datetime.now().isoformat()
        }
        supabase.table('matches').update(update_data).eq('match_id', match_id).execute()
        
        if is_first_result:
            # First time setting result - add wins/losses normally
            winning_players = match['team1_players'] if winner_team == 'team1' else match['team2_players']
            losing_players = match['team2_players'] if winner_team == 'team1' else match['team1_players']
            
            # Update winners
            for player in winning_players:
                await update_player_stats(player, True)
            
            # Update losers
            for player in losing_players:
                await update_player_stats(player, False)
        else:
            # Editing existing result - we need to reverse previous result and apply new one
            # Get players from previous result
            previous_winning_players = match['team1_players'] if previous_winner == 'team1' else match['team2_players']
            previous_losing_players = match['team2_players'] if previous_winner == 'team1' else match['team1_players']
            
            # Reverse previous result (subtract previous wins/losses)
            for player in previous_winning_players:
                await reverse_player_stats(player, True)
            for player in previous_losing_players:
                await reverse_player_stats(player, False)
            
            # Apply new result
            new_winning_players = match['team1_players'] if winner_team == 'team1' else match['team2_players']
            new_losing_players = match['team2_players'] if winner_team == 'team1' else match['team1_players']
            
            for player in new_winning_players:
                await update_player_stats(player, True)
            for player in new_losing_players:
                await update_player_stats(player, False)
        
        return True, "Match result updated successfully"
    except Exception as e:
        print(f"Error updating match result: {e}")
        return False, f"Error updating match: {str(e)}"

async def reverse_player_stats(player_name, was_winner):
    """Reverse player statistics (used when editing match results)."""
    try:
        # Get existing stats
        result = supabase.table('player_stats').select('*').eq('discord_username', player_name).execute()
        
        if result.data:
            current_stats = result.data[0]
            # Subtract the previous result
            new_total = max(0, current_stats['total_matches'] - 1)
            new_wins = max(0, current_stats['wins'] - (1 if was_winner else 0))
            new_losses = max(0, current_stats['losses'] - (0 if was_winner else 1))
            new_win_rate = (new_wins / new_total * 100) if new_total > 0 else 0
            
            update_data = {
                'total_matches': new_total,
                'wins': new_wins,
                'losses': new_losses,
                'win_rate': round(new_win_rate, 2)
            }
            supabase.table('player_stats').update(update_data).eq('discord_username', player_name).execute()
    except Exception as e:
        print(f"Error reversing player stats for {player_name}: {e}")

async def update_player_stats(player_name, won):
    """Update individual player statistics."""
    try:
        # Get existing stats
        result = supabase.table('player_stats').select('*').eq('discord_username', player_name).execute()
        
        if result.data:
            # Update existing player
            current_stats = result.data[0]
            new_total = current_stats['total_matches'] + 1
            new_wins = current_stats['wins'] + (1 if won else 0)
            new_losses = current_stats['losses'] + (0 if won else 1)
            new_win_rate = (new_wins / new_total) * 100 if new_total > 0 else 0
            
            update_data = {
                'total_matches': new_total,
                'wins': new_wins,
                'losses': new_losses,
                'win_rate': round(new_win_rate, 2),
                'last_played': datetime.now().isoformat()
            }
            supabase.table('player_stats').update(update_data).eq('discord_username', player_name).execute()
        else:
            # Create new player
            new_stats = {
                'discord_username': player_name,
                'total_matches': 1,
                'wins': 1 if won else 0,
                'losses': 0 if won else 1,
                'win_rate': 100.0 if won else 0.0,
                'last_played': datetime.now().isoformat()
            }
            supabase.table('player_stats').insert(new_stats).execute()
    except Exception as e:
        print(f"Error updating player stats for {player_name}: {e}")

async def get_match_details(match_id):
    """Get match details from database."""
    try:
        result = supabase.table('matches').select('*').eq('match_id', match_id).execute()
        if result.data:
            return result.data[0], True
        return None, False
    except Exception as e:
        print(f"Error getting match details: {e}")
        return None, False

async def get_player_stats(player_name):
    """Get player statistics from database."""
    try:
        result = supabase.table('player_stats').select('*').eq('discord_username', player_name).execute()
        if result.data:
            return result.data[0], True
        return None, False
    except Exception as e:
        print(f"Error getting player stats: {e}")
        return None, False

async def get_all_player_stats():
    """Get all player statistics from database."""
    try:
        result = supabase.table('player_stats').select('*').order('total_matches', desc=True).execute()
        return result.data, True
    except Exception as e:
        print(f"Error getting all player stats: {e}")
        return [], False

async def get_leaderboard():
    """Get player leaderboard sorted by win rate (minimum 3 games)."""
    try:
        result = supabase.table('player_stats').select('*').gte('total_matches', 3).order('win_rate', desc=True).limit(15).execute()
        return result.data, True
    except Exception as e:
        print(f"Error getting leaderboard: {e}")
        return [], False

# ========================= Permission Check =========================

async def check_moderator_permission(ctx):
    """Check if the user has moderator permissions."""
    allowed_roles = ["Moderators", "Admin", "Staff", "Moderator"]
    has_permission = any(role.name in allowed_roles for role in ctx.author.roles)
    
    if ctx.guild and ctx.author.id == ctx.guild.owner_id:
        has_permission = True
    
    if not has_permission:
        await ctx.send("❌ You don't have permission to update match results. This command is restricted to moderators and admins.")
    
    return has_permission

# ========================= Bot Functions =========================

async def display_queue(ctx):
    """Displays the current queue as an embed and includes a join button."""
    embed = discord.Embed(title="🎮 League of Legends Match Queue", color=BLUE_COLOR)
    
    if not player_pool:
        embed.description = "Queue is empty. Use `!lf join [name] [rank]` to join!"
    else:
        players_info = []
        for idx, player in enumerate(player_pool):
            tier_emoji = get_tier_emoji(player[1])
            players_info.append(f"`{idx+1}.` {tier_emoji} **{player[0]}** ({player[1]} - {player[2]} pts)")
        
        embed.description = "\n".join(players_info)
        
        progress = min(10, len(player_pool))
        progress_bar = create_progress_bar(progress, 10)
        
        embed.add_field(
            name="Queue Status", 
            value=f"{progress_bar}\n**{len(player_pool)}/10** players in queue", 
            inline=False
        )
        
        if queue_timer and not queue_timer.done():
            elapsed = (asyncio.get_event_loop().time() - queue_start_time)  # in seconds
            remaining_mins = max(0, (15*60 - elapsed) // 60)
            remaining_secs = max(0, (15*60 - elapsed) % 60)
            embed.add_field(
                name="⏰ Time Remaining", 
                value=f"**{int(remaining_mins)}m {int(remaining_secs)}s** until queue reset", 
                inline=False
            )
    
    embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
    
    view = QueueView(ctx)
    return embed, view

def create_progress_bar(current, maximum, length=10):
    """Creates a visual progress bar."""
    filled = round(current / maximum * length)
    empty = length - filled
    
    filled_char = "🟦"
    empty_char = "⬜"
    
    return filled_char * filled + empty_char * empty

def get_tier_emoji(tier):
    """Returns an emoji based on the player's tier."""
    tier_emojis = {
        "I": "🔘",    # Iron
        "IB": "🔘",   # Iron-Bronze
        "B": "🟤",    # Bronze
        "BS": "🟤",   # Bronze-Silver
        "S": "⚪",    # Silver
        "SG": "⚪",   # Silver-Gold
        "G": "🟡",    # Gold
        "GP": "🟡",   # Gold-Platinum
        "P": "🔵",    # Platinum
        "PE": "🔵",   # Platinum-Emerald
        "E": "🟢",    # Emerald
        "ED": "🟢",   # Emerald-Diamond
        "D": "🔷",    # Diamond
        "DM": "🔷",   # Diamond-Master
        "M": "🟣",    # Master
        "GM": "🟣",   # Grandmaster
        "C": "🔴"     # Challenger
    }
    return tier_emojis.get(tier, "❓")

async def reset_queue_timer(ctx):
    """Reset the queue after 15 minutes."""
    global player_pool, queue_timer
    
    try:
        await asyncio.sleep(15 * 60) 
        if player_pool:
            await ctx.send("⏰ Queue has been reset due to inactivity (15 minutes timer expired).")
            player_pool = []
            embed, view = await display_queue(ctx)
            await ctx.send(embed=embed, view=view)
    except asyncio.CancelledError:
        pass 
    finally:
        queue_timer = None

class QueueView(View):
    """A view for the join and leave queue buttons."""
    
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx
    
    @discord.ui.button(label="Join Queue", style=discord.ButtonStyle.green, emoji="✅")
    async def join_queue_button(self, interaction: discord.Interaction, button: Button):
        """Handles join queue button click."""
        global player_pool, queue_timer, queue_start_time
        
        member = interaction.user
        name = member.display_name
        
        for existing_player in player_pool:
            if existing_player[0].lower() == name.lower():
                await interaction.response.send_message(f"**{name}** is already in the queue. To update your rank, use `!lf leave` first, then rejoin with the correct rank.", ephemeral=True)
                return
        
        found_rank = None
        for role in member.roles:
            role_name = role.name
            if role_name in ROLE_TO_RANK:
                found_rank = ROLE_TO_RANK[role_name]
                break
        
        if found_rank is None:
            await interaction.response.send_message(
                "❌ No rank role detected. Please assign yourself a rank role or use `!lf join [name] [rank]` to specify your rank.", 
                ephemeral=True
            )
            return
        
        player_info = (name, found_rank, TIER_POINTS[found_rank])
        player_pool.append(player_info)
        
        if len(player_pool) == 1:
            queue_start_time = asyncio.get_event_loop().time()
            if queue_timer:
                queue_timer.cancel()
            queue_timer = asyncio.create_task(reset_queue_timer(self.ctx))
        
        embed, view = await display_queue(self.ctx)
        await interaction.response.send_message(f"✅ **{name}** joined the queue as **{found_rank}**.", embed=embed, view=view)
        
        if len(player_pool) >= 10:
            if queue_timer and not queue_timer.done():
                queue_timer.cancel()
                queue_timer = None
            
            teams_embed = await create_balanced_teams(player_pool[:10])
            await self.ctx.send("🎮 **Queue is full! Creating balanced teams:**", embed=teams_embed)
            del player_pool[:10]
            
            if player_pool:
                queue_start_time = asyncio.get_event_loop().time()
                queue_timer = asyncio.create_task(reset_queue_timer(self.ctx))
                remaining_embed, remaining_view = await display_queue(self.ctx)
                await self.ctx.send("**Players remaining in queue:**", embed=remaining_embed, view=remaining_view)
            
            lobby_embed = discord.Embed(
                title="🎮 Custom Game Lobby", 
                description="Click the button below to join the queue!",
                color=BLUE_COLOR
            )
            lobby_embed.add_field(name="Queue Status", value=f"{len(player_pool)}/10 players")
            lobby_embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
            
            lobby_view = QueueView(self.ctx)
            await interaction.message.edit(embed=lobby_embed, view=lobby_view)
    
    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.red, emoji="😩")
    async def leave_queue_button(self, interaction: discord.Interaction, button: Button):
        """Handles leave queue button click."""
        global player_pool
        
        member = interaction.user
        name = member.display_name
        
        player_found = False
        for i, player in enumerate(player_pool):
            if player[0].lower() == name.lower():
                del player_pool[i]
                player_found = True
                break
        
        if player_found:
            embed, view = await display_queue(self.ctx)
            await interaction.response.send_message(f"❌ **{name}** has left the queue.", embed=embed, view=view)
        else:
            await interaction.response.send_message(f"You're not currently in the queue, **{name}**.", ephemeral=True)

async def create_balanced_teams(players):
    """Create balanced 5v5 teams from a list of players and store in database."""
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

    # Generate random names for teams
    random_index1 = random.randint(0, len(TEAM_NAMES) - 1)
    random_index2 = (random_index1 + 1) % len(TEAM_NAMES)
    
    team1_name = TEAM_NAMES[random_index1]
    team2_name = TEAM_NAMES[random_index2]

    # Create match in database
    team1_players = [player[0] for player in best_team1]
    team2_players = [player[0] for player in best_team2]
    
    match_id, success = await create_match(team1_name, team1_players, team2_name, team2_players)
    
    embed = discord.Embed(title="🏆 Balanced Teams (5v5)", color=PURPLE_COLOR)
    
    team1_score = sum(player[2] for player in best_team1)
    team2_score = sum(player[2] for player in best_team2)

    # Format team members with emojis
    team1_info = []
    for player in best_team1:
        tier_emoji = get_tier_emoji(player[1])
        team1_info.append(f"{tier_emoji} **{player[0]}** ({player[1]} - {player[2]} pts)")
    
    team2_info = []
    for player in best_team2:
        tier_emoji = get_tier_emoji(player[1])
        team2_info.append(f"{tier_emoji} **{player[0]}** ({player[1]} - {player[2]} pts)")

    embed.add_field(name=f"🔵 Team A: {team1_name} ({team1_score:.1f} pts)", value="\n".join(team1_info), inline=True)
    embed.add_field(name=f"🔴 Team B: {team2_name} ({team2_score:.1f} pts)", value="\n".join(team2_info), inline=True)
    embed.add_field(name="⚖️ Balance Info", value=f"Point Difference: **{best_diff:.1f}** points", inline=False)

    if success and match_id:
        embed.add_field(
            name="🎮 **MATCH ID**", 
            value=f"**`{match_id}`**\n*Moderators: Use this ID to update results*", 
            inline=False
        )
        embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
    else:
        embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")

    return embed

# ========================= Bot Commands and Events =========================

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    activity = discord.Game(name="League of Flex | !lf information")
    await bot.change_presence(activity=activity)

@bot.command(name='lobby')
async def start_lobby(ctx):
    """Start a custom game lobby with a join button."""
    embed = discord.Embed(
        title="🎮 Custom Game Lobby", 
        description="Click the button below to join the queue!",
        color=BLUE_COLOR
    )
    
    embed.add_field(name="Queue Status", value=f"{len(player_pool)}/10 players")
    
    if queue_timer and not queue_timer.done() and queue_start_time:
        elapsed = (asyncio.get_event_loop().time() - queue_start_time)  # in seconds
        remaining_mins = max(0, (15*60 - elapsed) // 60)
        remaining_secs = max(0, (15*60 - elapsed) % 60)
        embed.add_field(
            name="⏰ Time Remaining", 
            value=f"**{int(remaining_mins)}m {int(remaining_secs)}s** until queue reset",
            inline=False
        )
    
    embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
    view = QueueView(ctx)
    
    lobby_message = await ctx.send(embed=embed, view=view)
    
    if player_pool:
        queue_embed, queue_view = await display_queue(ctx)
        await ctx.send("Current queue:", embed=queue_embed, view=queue_view)

@bot.command(name='information')
async def help_command(ctx):
    """Displays the information message with all available commands."""
    embed = discord.Embed(title="🎮 League of Legends Team Balancer Help", color=TEAL_COLOR)

    commands_text = (
        "**Basic Commands:**\n"
        "1. `!lf team [player1] [rank1] [player2] [rank2] ...`\n"
        "   - Creates balanced 5v5 teams with randomized team names\n"
        "   - Requires exactly 10 players with their ranks\n\n"
        "2. `!lf tiers`\n"
        "   - Shows all tier point values\n\n"
        "3. `!lf join`\n"
        "   - Join the player queue using your Discord name and rank role\n"
        "   - You can also use `!lf join [name] [rank]` to specify a different name or rank\n\n"
        "4. `!lf leave`\n"
        "   - Leave the queue (use this to rejoin with correct rank if needed)\n\n"
        "5. `!lf queue`\n"
        "   - Shows the current queue status\n\n"
        "6. `!lf queueclear`\n"
        "   - Clears the current queue and cancels the timer\n\n"
        "7. `!lf lobby`\n"
        "   - Start a custom game lobby with join/leave buttons\n\n"
    )
    
    match_commands = (
        "**Match & Stats Commands:**\n"
        "8. `!lf result [match_id] [teama/teamb]` *(Moderators only)*\n"
        "   - Update match result (e.g., `!lf result ABC123 teama`)\n\n"
        "9. `!lf edit [match_id] [teama/teamb]` *(Moderators only)*\n"
        "   - Edit/change an existing match result\n\n"
        "10. `!lf match [match_id]`\n"
        "   - Show details of a specific match\n\n"
        "11. `!lf stats [player_name]`\n"
        "   - Show player's win/loss statistics\n\n"
        "12. `!lf players`\n"
        "   - Show all players and their statistics\n\n"
        "13. `!lf leaderboard`\n"
        "   - Show top players by win rate (min 3 games)\n\n"
        "14. `!lf clear players`\n"
        "   - Clear the player queue\n\n"
        "15. `!lf information`\n"
        "   - Shows this help message\n"
    )

    embed.add_field(name="Commands", value=commands_text, inline=False)
    embed.add_field(name="More Commands", value=match_commands, inline=False)

    # Create a visual representation of the rank tiers with emojis
    ranks_info = ""
    for tier_name, ranks in {
        "Iron": "I", "Iron-Bronze": "IB", "Bronze": "B", "Bronze-Silver": "BS",
        "Silver": "S", "Silver-Gold": "SG", "Gold": "G", "Gold-Platinum": "GP",
        "Platinum": "P", "Platinum-Emerald": "PE", "Emerald": "E", "Emerald-Diamond": "ED",
        "Diamond": "D", "Diamond-Masters": "DM", "Master": "M", "Grandmaster": "GM", "Challenger": "C"
    }.items():
        emoji = get_tier_emoji(ranks)
        ranks_info += f"{emoji} **{tier_name}** ({ranks}): {TIER_POINTS[ranks]} Points\n"
    
    embed.add_field(name="Valid Ranks", value=ranks_info, inline=False)
    embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")

    await ctx.send(embed=embed)

@bot.command(name='tiers')
async def tiers_command(ctx):
    """Displays the tier points."""
    embed = discord.Embed(title="⚔️ League of Legends Rank Point Values", color=ORANGE_COLOR)
    
    # Create a visual representation of the tier points with emojis
    for tier_name, ranks in {
        "Iron": "I", "Iron-Bronze": "IB", "Bronze": "B", "Bronze-Silver": "BS",
        "Silver": "S", "Silver-Gold": "SG", "Gold": "G", "Gold-Platinum": "GP",
        "Platinum": "P", "Platinum-Emerald": "PE", "Emerald": "E", "Emerald-Diamond": "ED",
        "Diamond": "D", "Diamond-Masters": "DM", "Master": "M", "Grandmaster": "GM", "Challenger": "C"
    }.items():
        emoji = get_tier_emoji(ranks)
        embed.add_field(
            name=f"{emoji} {tier_name} ({ranks})", 
            value=f"**{TIER_POINTS[ranks]}** Points", 
            inline=True
        )
    
    embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
    await ctx.send(embed=embed)

@bot.command(name='players')
async def show_all_players(ctx):
    """Show all players and their statistics."""
    players_data, found = await get_all_player_stats()
    
    if not found or not players_data:
        await ctx.send("❌ No player statistics found. No matches have been played yet.")
        return
    
    embed = discord.Embed(
        title="👥 All Players Statistics",
        description=f"Total players: **{len(players_data)}**",
        color=BLUE_COLOR
    )
    
    # Group players into chunks for better display
    players_per_field = 10
    total_players = len(players_data)
    
    for i in range(0, total_players, players_per_field):
        chunk = players_data[i:i + players_per_field]
        field_name = f"Players {i+1}-{min(i+players_per_field, total_players)}"
        
        player_lines = []
        for player in chunk:
            # Win rate emoji
            win_rate = player['win_rate']
            if win_rate >= 70:
                wr_emoji = "🔥"
            elif win_rate >= 50:
                wr_emoji = "👍"
            else:
                wr_emoji = "📉"
            
            player_lines.append(
                f"**{player['discord_username']}**: {player['wins']}W-{player['losses']}L "
                f"({player['win_rate']}% {wr_emoji})"
            )
        
        embed.add_field(
            name=field_name,
            value="\n".join(player_lines),
            inline=True
        )
    
    embed.set_footer(text=f"Use !lf stats [player] for detailed stats | {WEBSITE_URL}")
    await ctx.send(embed=embed)

@bot.command(name='leaderboard', aliases=['lb', 'top'])
async def show_leaderboard(ctx):
    """Show top players by win rate (minimum 3 games)."""
    leaderboard_data, found = await get_leaderboard()
    
    if not found or not leaderboard_data:
        await ctx.send("❌ No leaderboard data found. Players need at least 3 games to appear on the leaderboard.")
        return
    
    embed = discord.Embed(
        title="🏆 Leaderboard - Top Players",
        description="*Minimum 3 games required*",
        color=PURPLE_COLOR
    )
    
    # Create leaderboard entries
    leaderboard_lines = []
    for idx, player in enumerate(leaderboard_data):
        # Position emoji
        if idx == 0:
            position = "🥇"
        elif idx == 1:
            position = "🥈"
        elif idx == 2:
            position = "🥉"
        else:
            position = f"`{idx+1}.`"
        
        # Win rate emoji
        win_rate = player['win_rate']
        if win_rate >= 70:
            wr_emoji = "🔥"
        elif win_rate >= 50:
            wr_emoji = "👍"
        else:
            wr_emoji = "📉"
        
        leaderboard_lines.append(
            f"{position} **{player['discord_username']}** - {player['win_rate']}% {wr_emoji}\n"
            f"    ↳ {player['wins']}W-{player['losses']}L ({player['total_matches']} games)"
        )
    
    # Split into fields if too many players
    if len(leaderboard_lines) <= 10:
        embed.add_field(
            name="Rankings",
            value="\n\n".join(leaderboard_lines),
            inline=False
        )
    else:
        # Split into two fields
        mid_point = len(leaderboard_lines) // 2
        embed.add_field(
            name="Top Rankings (1-8)",
            value="\n\n".join(leaderboard_lines[:mid_point]),
            inline=True
        )
        embed.add_field(
            name="Rankings (9-15)",
            value="\n\n".join(leaderboard_lines[mid_point:]),
            inline=True
        )
    
    embed.set_footer(text=f"Use !lf stats [player] for detailed stats | {WEBSITE_URL}")
    await ctx.send(embed=embed)

@bot.command(name='join')
async def join_queue(ctx, name=None, rank=None):
    """
    Allows a player to join the matchmaking queue.
    If no name is provided, uses the Discord username.
    If no rank is provided, attempts to detect from Discord roles.
    """
    global player_pool, queue_timer, queue_start_time
    
    if name is None:
        name = ctx.author.display_name
    
    player_idx = None
    for idx, existing_player in enumerate(player_pool):
        if existing_player[0].lower() == name.lower():
            player_idx = idx
            break
            
    if player_idx is not None:
        if rank is not None:
            rank = rank.upper()
            if rank not in TIER_POINTS:
                await ctx.send(f"❌ Invalid rank '**{rank}**'. Use `!lf information` to see valid ranks.")
                return
            
            del player_pool[player_idx]
            player_info = (name, rank, TIER_POINTS[rank])
            player_pool.append(player_info)
            
            embed, view = await display_queue(ctx)
            await ctx.send(f"✅ Updated **{name}**'s rank to **{rank}**.", embed=embed, view=view)
            return
        else:
            await ctx.send(f"**{name}** is already in the queue. To update your rank, use `!lf leave` first, then rejoin with the correct rank.")
            return
    
    if rank is not None:
        rank = rank.upper()
        if rank not in TIER_POINTS:
            await ctx.send(f"❌ Invalid rank '**{rank}**'. Use `!lf information` to see valid ranks.")
            return
    else:
        found_rank = None
        for role in ctx.author.roles:
            role_name = role.name
            if role_name in ROLE_TO_RANK:
                found_rank = ROLE_TO_RANK[role_name]
                break
        
        if found_rank is None:
            await ctx.send("❌ No rank role detected. Please assign yourself a rank role or use `!lf join [name] [rank]` to specify your rank.")
            return
        
        rank = found_rank
    
    player_info = (name, rank, TIER_POINTS[rank])
    player_pool.append(player_info)
    
    if len(player_pool) == 1:
        queue_start_time = asyncio.get_event_loop().time()
        if queue_timer:
            queue_timer.cancel()
        queue_timer = asyncio.create_task(reset_queue_timer(ctx))
    
    embed, view = await display_queue(ctx)
    await ctx.send(f"✅ **{name}** joined the queue as **{rank}**.", embed=embed, view=view)

    if len(player_pool) >= 10:
        if queue_timer and not queue_timer.done():
            queue_timer.cancel()
            queue_timer = None
        
        teams_embed = await create_balanced_teams(player_pool[:10])
        await ctx.send("🎮 **Queue is full! Creating balanced teams:**", embed=teams_embed)
        del player_pool[:10]
        
        if player_pool:
            queue_start_time = asyncio.get_event_loop().time()
            queue_timer = asyncio.create_task(reset_queue_timer(ctx))
            remaining_embed, remaining_view = await display_queue(ctx)
            await ctx.send("**Players remaining in queue:**", embed=remaining_embed, view=remaining_view)

@bot.command(name='leave')
async def leave_queue(ctx, name=None):
    """
    Allows a player to leave the matchmaking queue.
    If no name is provided, uses the Discord username.
    """
    global player_pool
    
    if name is None:
        name = ctx.author.display_name
    
    player_found = False
    for i, player in enumerate(player_pool):
        if player[0].lower() == name.lower():
            del player_pool[i]
            player_found = True
            break
    
    if player_found:
        embed, view = await display_queue(ctx)
        await ctx.send(f"❌ **{name}** has left the queue.", embed=embed, view=view)
    else:
        await ctx.send(f"**{name}** is not currently in the queue.")

@bot.command(name='queueclear')
async def clear_queue(ctx):
    """Clears the current queue and cancels the timer."""
    global player_pool, queue_timer
    
    if not player_pool:
        await ctx.send("Queue is already empty.")
        return
    
    player_count = len(player_pool)
    player_pool = []
    
    if queue_timer and not queue_timer.done():
        queue_timer.cancel()
        queue_timer = None
    
    await ctx.send(f"🧹 Queue cleared. Removed **{player_count}** player(s).")
    embed, view = await display_queue(ctx)
    await ctx.send(embed=embed, view=view)

@bot.command(name='queue')
async def show_queue(ctx):
    """Shows the current queue and creates one if it doesn't exist."""
    try:
        embed = discord.Embed(title="🎮 League of Legends Match Queue", color=BLUE_COLOR)
        
        if not player_pool:
            embed.description = "Queue is empty. Use `!lf join [name] [rank]` to join!"
        else:
            players_info = []
            for idx, player in enumerate(player_pool):
                tier_emoji = get_tier_emoji(player[1])
                players_info.append(f"`{idx+1}.` {tier_emoji} **{player[0]}** ({player[1]} - {player[2]} pts)")
            
            embed.description = "\n".join(players_info)
            
            progress = min(10, len(player_pool))
            progress_bar = create_progress_bar(progress, 10)
            
            embed.add_field(
                name="Queue Status", 
                value=f"{progress_bar}\n**{len(player_pool)}/10** players in queue", 
                inline=False
            )
            
            if queue_timer and not queue_timer.done():
                elapsed = (asyncio.get_event_loop().time() - queue_start_time)  # in seconds
                remaining_mins = max(0, (15*60 - elapsed) // 60)
                remaining_secs = max(0, (15*60 - elapsed) % 60)
                embed.add_field(
                    name="⏰ Time Remaining", 
                    value=f"**{int(remaining_mins)}m {int(remaining_secs)}s** until queue reset", 
                    inline=False
                )
        
        embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
        
        view = QueueView(ctx)
        await ctx.send(embed=embed, view=view)
    except Exception as e:
        print(f"Error in queue command: {str(e)}")
        await ctx.send(f"❌ An error occurred with the queue command: {str(e)}")

@bot.command(name='team')
async def team_balance(ctx, *, input_text=None):
    """Creates balanced teams based on provided players and ranks."""
    if not input_text:
        await ctx.send("Please use `!lf information` for command information.")
        return

    args = input_text.split()
    if len(args) < 20:
        await ctx.send("For team balancing, provide 10 players with their ranks.\nUse `!lf information` for more information.")
        return

    try:
        players = []
        for i in range(0, 20, 2):
            player_name = args[i]
            player_rank = args[i+1].upper()
            if player_rank not in TIER_POINTS:
                await ctx.send(f"❌ Invalid rank '**{player_rank}**' for player '**{player_name}**'. Use `!lf information` to see valid ranks.")
                return
            players.append((player_name, player_rank, TIER_POINTS[player_rank]))

        teams_embed = await create_balanced_teams(players)
        await ctx.send(embed=teams_embed)
    except Exception as e:
        await ctx.send("❌ Error creating teams. Use `!lf information` for the correct format.")
        print(f"Error: {str(e)}") 

@bot.command(name='clear')
async def clear_players(ctx):
    """Clears the player queue."""
    global player_pool, queue_timer
    
    if not player_pool:
        await ctx.send("Queue is already empty.")
        return
    
    player_count = len(player_pool)
    player_pool = []
    
    if queue_timer and not queue_timer.done():
        queue_timer.cancel()
        queue_timer = None
    
    await ctx.send(f"🧹 Player queue has been cleared. Removed **{player_count}** player(s).")

# ========================= Match Result Commands =========================

@bot.command(name='result')
async def update_result(ctx, match_id=None, winner=None):
    """Update match result. Usage: !lf result [match_id] [teama/teamb]"""
    if not await check_moderator_permission(ctx):
        return
    
    if not match_id or not winner:
        await ctx.send("❌ Usage: `!lf result [match_id] [teama/teamb]`\nExample: `!lf result ABC123 teama`")
        return
    
    winner = winner.lower()
    if winner not in ['teama', 'teamb', 'team1', 'team2']:
        await ctx.send("❌ Winner must be 'teama' or 'teamb'")
        return
    
    # Convert team1/team2 to teama/teamb for consistency
    if winner == 'team1':
        winner = 'teama'
    elif winner == 'team2':
        winner = 'teamb'
    
    # Convert to database format (team1/team2)
    db_winner = 'team1' if winner == 'teama' else 'team2'
    
    success, message = await update_match_result(match_id.upper(), db_winner, ctx.author.display_name)
    
    if success:
        # Get match details for announcement
        match_data, found = await get_match_details(match_id.upper())
        if found:
            winning_team_name = match_data['team1_name'] if db_winner == 'team1' else match_data['team2_name']
            
            embed = discord.Embed(
                title="🏆 Match Result Updated!",
                description=f"**{winning_team_name}** wins!",
                color=GREEN_COLOR
            )
            embed.add_field(name="Match ID", value=match_id.upper(), inline=True)
            embed.add_field(name="Updated by", value=ctx.author.display_name, inline=True)
            embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
            
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"✅ {message}")
    else:
        await ctx.send(f"❌ {message}")

@bot.command(name='edit')
async def edit_result(ctx, match_id=None, winner=None):
    """Edit/change an existing match result. Usage: !lf edit [match_id] [teama/teamb]"""
    if not await check_moderator_permission(ctx):
        return
    
    if not match_id or not winner:
        await ctx.send("❌ Usage: `!lf edit [match_id] [teama/teamb]`\nExample: `!lf edit ABC123 teamb`")
        return
    
    winner = winner.lower()
    if winner not in ['teama', 'teamb', 'team1', 'team2']:
        await ctx.send("❌ Winner must be 'teama' or 'teamb'")
        return
    
    # Convert team1/team2 to teama/teamb for consistency
    if winner == 'team1':
        winner = 'teama'
    elif winner == 'team2':
        winner = 'teamb'
    
    # Convert to database format (team1/team2)
    db_winner = 'team1' if winner == 'teama' else 'team2'
    
    # Check if match exists first
    match_data, found = await get_match_details(match_id.upper())
    if not found:
        await ctx.send("❌ Match not found")
        return
    
    if match_data['winner'] is None:
        await ctx.send("❌ This match has no result to edit. Use `!lf result` instead.")
        return
    
    success, message = await update_match_result(match_id.upper(), db_winner, ctx.author.display_name)
    
    if success:
        winning_team_name = match_data['team1_name'] if db_winner == 'team1' else match_data['team2_name']
        
        embed = discord.Embed(
            title="✏️ Match Result Edited!",
            description=f"**{winning_team_name}** now wins!",
            color=ORANGE_COLOR
        )
        embed.add_field(name="Match ID", value=match_id.upper(), inline=True)
        embed.add_field(name="Updated by", value=ctx.author.display_name, inline=True)
        embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
        
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ {message}")

@bot.command(name='match')
async def show_match(ctx, match_id=None):
    """Show details of a specific match. Usage: !lf match [match_id]"""
    if not match_id:
        await ctx.send("❌ Usage: `!lf match [match_id]`\nExample: `!lf match ABC123`")
        return
    
    match_data, found = await get_match_details(match_id.upper())
    if not found:
        await ctx.send("❌ Match not found")
        return
    
    embed = discord.Embed(
        title=f"🎮 Match Details: {match_id.upper()}",
        color=BLUE_COLOR
    )
    
    # Team A info
    team1_players = "\n".join([f"• **{player}**" for player in match_data['team1_players']])
    embed.add_field(
        name=f"🔵 Team A: {match_data['team1_name']}",
        value=team1_players,
        inline=True
    )
    
    # Team B info
    team2_players = "\n".join([f"• **{player}**" for player in match_data['team2_players']])
    embed.add_field(
        name=f"🔴 Team B: {match_data['team2_name']}",
        value=team2_players,
        inline=True
    )
    
    # Match status
    if match_data['winner']:
        winner_name = match_data['team1_name'] if match_data['winner'] == 'team1' else match_data['team2_name']
        winner_team = "Team A" if match_data['winner'] == 'team1' else "Team B"
        status_value = f"🏆 **{winner_team}: {winner_name}** won!"
        if match_data['updated_by']:
            status_value += f"\nUpdated by: {match_data['updated_by']}"
    else:
        status_value = "⏳ Pending result"
    
    embed.add_field(name="Match Status", value=status_value, inline=False)
    
    # Timestamps
    created_date = datetime.fromisoformat(match_data['created_at'].replace('Z', '+00:00'))
    embed.add_field(name="Created", value=created_date.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
    
    if match_data.get('updated_at'):
        updated_date = datetime.fromisoformat(match_data['updated_at'].replace('Z', '+00:00'))
        embed.add_field(name="Completed", value=updated_date.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
    
    embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
    await ctx.send(embed=embed)

@bot.command(name='stats')
async def show_stats(ctx, *, player_name=None):
    """Show player statistics. Usage: !lf stats [player_name]"""
    if not player_name:
        player_name = ctx.author.display_name
    
    stats, found = await get_player_stats(player_name)
    if not found:
        await ctx.send(f"❌ No statistics found for **{player_name}**. They haven't played any tracked matches yet.")
        return
    
    embed = discord.Embed(
        title=f"📊 Player Statistics: {player_name}",
        color=PURPLE_COLOR
    )
    
    # Basic stats
    embed.add_field(name="Total Matches", value=f"**{stats['total_matches']}**", inline=True)
    embed.add_field(name="Wins", value=f"**{stats['wins']}** 🏆", inline=True)
    embed.add_field(name="Losses", value=f"**{stats['losses']}** ❌", inline=True)
    
    # Win rate with visual bar
    win_rate = stats['win_rate']
    if win_rate >= 70:
        wr_emoji = "🔥"
        wr_color = "🟢"
    elif win_rate >= 50:
        wr_emoji = "👍"
        wr_color = "🟡"
    else:
        wr_emoji = "📉"
        wr_color = "🔴"
    
    embed.add_field(
        name="Win Rate",
        value=f"{wr_color} **{win_rate}%** {wr_emoji}",
        inline=True
    )
    
    # Last played
    if stats.get('last_played'):
        last_played = datetime.fromisoformat(stats['last_played'].replace('Z', '+00:00'))
        embed.add_field(
            name="Last Played",
            value=last_played.strftime("%Y-%m-%d"),
            inline=True
        )
    
    embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
    await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    """Listen for specific phrases and respond with a custom message."""
    # Don't respond to bot messages to avoid loops
    if message.author.bot:
        return
        
    content = message.content.upper()
    customs_phrases = ["WHERE ARE CUSTOMS", "WHERE THE CUSTOMS", "WHERE ARE THE CUSTOMS", "WHERE CUSTOMS"]
    
    if any(phrase in content for phrase in customs_phrases):
        response = "Bro, just type in '!lf queue' to start a custom lobby and invite your friends. Also, please don't write that anymore; I have work to do as well."
        await message.channel.send(response)
    
    # Process commands - this is necessary so that normal commands still work
    await bot.process_commands(message)

# Run the bot
bot.run(DISCORD_TOKEN)
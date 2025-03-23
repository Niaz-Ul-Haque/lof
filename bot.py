import discord
from discord.ext import commands
from discord.ui import Button, View, Select
import os
from dotenv import load_dotenv
from itertools import combinations
import math
import random
import asyncio
import datetime

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix='!lf ', intents=intents, help_command=None)
global player_pool, queue_timer, queue_start_time

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
    "Diamond-Master": "DM",
    "Master": "M",
    "Grandmaster": "GM",
    "Challenger": "C"
}

player_pool = []
tournaments = {}
queue_timer = None
queue_start_time = None

TEAM_NAMES = [
    "Sasquatch Squad", "Viking Vandals", "Pirate Pythons", "Ninja Nachos", "Zombie Zebras",
    "Wacky Wombats", "Grumpy Geese", "Mad Hooligans", "Crying Cowboys", "Reckless Rhinos",
    "Bumbling Buccaneers", "Sneaky Sasquatches", "Crazy Cacti", "Drunken Dragons", "Grouchy Gnomes",
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
            
            teams_embed = create_balanced_teams(player_pool[:10])
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
    
    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.red, emoji="( 👁️ ͜ʖ 👁️ )")
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
    
    # try:
    #     await lobby_message.pin()
    # except discord.HTTPException:
    #     await ctx.send("Note: I couldn't pin the lobby message. For best visibility, an admin should pin it manually.")
    
    if player_pool:
        queue_embed, queue_view = await display_queue(ctx)
        await ctx.send("Current queue:", embed=queue_embed, view=queue_view)

def format_tier_points():
    """Format tier points in a more compact way."""
    tiers = {
        "Iron": ["I"],
        "Iron-Bronze": ["IB"],
        "Bronze": ["B"],
        "Bronze-Silver": ["BS"],
        "Silver": ["S"],
        "Silver-Gold": ["SG"],
        "Gold": ["G"],
        "Gold-Platinum": ["GP"],
        "Platinum": ["P"],
        "Platinum-Emerald": ["PE"],
        "Emerald": ["E"],
        "Emerald-Diamond": ["ED"],
        "Diamond": ["D"],
        "Diamond-Master": ["DM"],
        "Master": ["M"],
        "Grandmaster": ["GM"],
        "Challenger": ["C"]
    }

    formatted_tiers = []
    for tier_name, ranks in tiers.items():
        if tier_name in ["Master", "Grandmaster", "Challenger"]:
            tier_str = f"{tier_name}: {TIER_POINTS[ranks[0]]}"
        else:
            points = [f"{rank}: {TIER_POINTS[rank]}" for rank in ranks]
            tier_str = f"{tier_name}: {' | '.join(points)}"
        formatted_tiers.append(tier_str)

    return formatted_tiers

def create_balanced_teams(players):
    """Create balanced 5v5 teams from a list of players."""
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

    embed.add_field(name=f"🔵 {team1_name} ({team1_score:.1f} pts)", value="\n".join(team1_info), inline=True)
    embed.add_field(name=f"🔴 {team2_name} ({team2_score:.1f} pts)", value="\n".join(team2_info), inline=True)
    embed.add_field(name="⚖️ Balance Info", value=f"Point Difference: **{best_diff:.1f}** points", inline=False)

    embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
    return embed

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    activity = discord.Game(name="League of Flex | !lf information")
    await bot.change_presence(activity=activity)

@bot.command(name='information')
async def help_command(ctx):
    """Displays the information message with all available commands."""
    embed = discord.Embed(title="🎮 League of Legends Team Balancer Help", color=TEAL_COLOR)

    commands_part1 = (
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
        "7. `!lf clear [option]`\n"
        "    - Clear specific data. Options: players, teams, tournaments, matches, all\n\n"
        "8. `!lf information`\n"
        "    - Shows this help message\n"
    )

    embed.add_field(name="Available Commands", value=commands_part1, inline=False)

    # Create a visual representation of the rank tiers with emojis
    ranks_info = ""
    for tier_name, ranks in {
        "Iron": "I", "Iron-Bronze": "IB", "Bronze": "B", "Bronze-Silver": "BS",
        "Silver": "S", "Silver-Gold": "SG", "Gold": "G", "Gold-Platinum": "GP",
        "Platinum": "P", "Platinum-Emerald": "PE", "Emerald": "E", "Emerald-Diamond": "ED",
        "Diamond": "D", "Diamond-Master": "DM", "Master": "M", "Grandmaster": "GM", "Challenger": "C"
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
        "Diamond": "D", "Diamond-Master": "DM", "Master": "M", "Grandmaster": "GM", "Challenger": "C"
    }.items():
        emoji = get_tier_emoji(ranks)
        embed.add_field(
            name=f"{emoji} {tier_name} ({ranks})", 
            value=f"**{TIER_POINTS[ranks]}** Points", 
            inline=True
        )
    
    embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
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
        
        teams_embed = create_balanced_teams(player_pool[:10])
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
    embed, view = await display_queue(ctx)
    await ctx.send(embed=embed, view=view)

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

        teams_embed = create_balanced_teams(players)
        await ctx.send(embed=teams_embed)
    except Exception as e:
        await ctx.send("❌ Error creating teams. Use `!lf information` for the correct format.")
        print(f"Error: {str(e)}") 

@bot.group(name='clear', invoke_without_command=True)
async def clear(ctx):
    """Base command for clearing data."""
    await ctx.send("Please specify what to clear. Options: players, teams, tournaments, matches, all")

@clear.command(name='players')
async def clear_players(ctx):
    """Clears the player queue."""
    global player_pool, queue_timer
    player_pool = []
    if queue_timer and not queue_timer.done():
        queue_timer.cancel()
        queue_timer = None
    await ctx.send("🧹 Player queue has been cleared.")

@clear.command(name='teams')
async def clear_teams(ctx):
    """Clears all tournament teams."""
    global tournaments
    for tournament in tournaments.values():
        tournament.teams = []
    await ctx.send("🧹 All tournament teams have been cleared.")

@clear.command(name='all')
async def clear_all(ctx):
    """Clears all data including players, teams, tournaments, and matches."""
    global player_pool, tournaments, queue_timer
    player_pool = []
    tournaments = {}
    if queue_timer and not queue_timer.done():
        queue_timer.cancel()
        queue_timer = None
    await ctx.send("🧹 All data has been cleared.")

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

bot.run(DISCORD_TOKEN)
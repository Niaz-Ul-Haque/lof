import discord
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput
import os
from dotenv import load_dotenv
from itertools import combinations
import math
import random
import asyncio
import datetime
import uuid
import json

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix='!lf ', intents=intents, help_command=None)

# Global variables
player_pool = []
tournaments = {}
active_tournament = None
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

# Tournament constants
TOURNAMENT_PHASE = {
    "REGISTRATION": "Registration Open",
    "TEAMS_GENERATED": "Teams Generated",
    "IN_PROGRESS": "Tournament In Progress",
    "COMPLETED": "Tournament Completed"
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

# ========================= Original Bot Functions =========================

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
        "Diamond-Masters": ["DM"],
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

# ========================= Tournament Data Models =========================

class Tournament:
    def __init__(self, name, creator_id):
        self.id = str(uuid.uuid4())[:8]  # Short ID for easier reference
        self.name = name
        self.creator_id = creator_id
        self.participants = []  # List of (name, rank, points) tuples
        self.teams = []  # List of Team objects
        self.matches = []  # List of Match objects
        self.created_at = datetime.datetime.now()
        self.phase = TOURNAMENT_PHASE["REGISTRATION"]
        self.winner = None
    
    def add_participant(self, name, rank):
        # Check if name already exists
        for p in self.participants:
            if p[0].lower() == name.lower():
                return False, f"Player {name} is already in the tournament"
        
        # Add participant
        self.participants.append((name, rank, TIER_POINTS[rank]))
        return True, f"Added {name} ({rank}) to tournament {self.name}"
    
    def remove_participant(self, name):
        for i, participant in enumerate(self.participants):
            if participant[0].lower() == name.lower():
                del self.participants[i]
                return True, f"Removed {name} from tournament {self.name}"
        
        return False, f"Player {name} not found in tournament"
    
    def generate_teams(self):
        if len(self.participants) < 40:
            return False, f"Need 40 participants to generate teams (currently {len(self.participants)})"
        
        participants = self.participants.copy()
        
        # Sort participants by their tier points in descending order
        participants.sort(key=lambda x: x[2], reverse=True)
        
        # Seed distribution (S-curve seeding)
        # This will distribute top players across teams
        team_assignments = [[] for _ in range(8)]
        
        # Snake draft pattern: 0,1,2,3,4,5,6,7,7,6,5,4,3,2,1,0,0,1...
        snake_order = list(range(8)) + list(range(7, -1, -1))
        snake_order = snake_order * 3  # For 5 players per team
        snake_order = snake_order[:40]  # Limit to 40 players
        
        for i, team_idx in enumerate(snake_order):
            if i < len(participants):
                team_assignments[team_idx].append(participants[i])
        
        # Create team objects
        self.teams = []
        random.shuffle(TEAM_NAMES)  # Shuffle team names
        
        for i, players in enumerate(team_assignments):
            # Take first 8 team names
            team_name = TEAM_NAMES[i % len(TEAM_NAMES)]
            team = Team(team_name, players)
            self.teams.append(team)
        
        # Generate initial matches for quarterfinals
        self.generate_bracket()
        
        # Update tournament phase
        self.phase = TOURNAMENT_PHASE["TEAMS_GENERATED"]
        
        return True, f"Generated 8 teams for tournament {self.name}"
    
    def generate_bracket(self):
        # Clear existing matches
        self.matches = []
        
        # Create quarterfinal matches (4 matches)
        for i in range(0, 8, 2):
            match = Match(
                id=f"QF{i//2+1}",
                team1=self.teams[i],
                team2=self.teams[i+1],
                stage="Quarterfinals",
                match_number=i//2+1,
                best_of=1
            )
            self.matches.append(match)
        
        # Create semifinal matches (2 matches)
        for i in range(2):
            match = Match(
                id=f"SF{i+1}",
                team1=None,  # Will be filled after quarterfinals
                team2=None,
                stage="Semifinals",
                match_number=i+1,
                best_of=1
            )
            self.matches.append(match)
        
        # Create final match
        final_match = Match(
            id="F1",
            team1=None,  # Will be filled after semifinals
            team2=None,
            stage="Finals",
            match_number=1,
            best_of=3  # Finals are BO3
        )
        self.matches.append(final_match)
        
        # Update tournament phase
        self.phase = TOURNAMENT_PHASE["IN_PROGRESS"]
        
        return True
    
    def update_match_result(self, match_id, winner_id, score1=None, score2=None):
        match = next((m for m in self.matches if m.id == match_id), None)
        if not match:
            return False, f"Match {match_id} not found"
        
        winner_team = next((t for t in self.teams if t.id == winner_id), None)
        if not winner_team:
            return False, f"Team {winner_id} not found"
        
        if winner_team != match.team1 and winner_team != match.team2:
            return False, f"Team {winner_team.name} is not part of this match"
        
        # Update match result
        match.winner = winner_team
        if score1 is not None and score2 is not None:
            match.score = (score1, score2)
        
        # Advance winner to next stage
        if match.stage == "Quarterfinals":
            # Find corresponding semifinal match
            sf_index = (match.match_number - 1) // 2
            sf_match = next((m for m in self.matches if m.id == f"SF{sf_index+1}"), None)
            
            if sf_match:
                if match.match_number % 2 == 1:  # 1st or 3rd quarterfinal
                    sf_match.team1 = winner_team
                else:  # 2nd or 4th quarterfinal
                    sf_match.team2 = winner_team
        
        elif match.stage == "Semifinals":
            # Advance to finals
            final_match = next((m for m in self.matches if m.id == "F1"), None)
            
            if final_match:
                if match.match_number == 1:
                    final_match.team1 = winner_team
                else:
                    final_match.team2 = winner_team
        
        elif match.stage == "Finals":
            # Tournament completed
            self.winner = winner_team
            self.phase = TOURNAMENT_PHASE["COMPLETED"]
        
        match.completed = True
        return True, f"Updated match {match_id}: {winner_team.name} wins"

class Team:
    def __init__(self, name, players):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.players = players
        self.score = sum(player[2] for player in players)
    
    def get_formatted_players(self):
        result = []
        for player in self.players:
            tier_emoji = get_tier_emoji(player[1])
            result.append(f"{tier_emoji} **{player[0]}** ({player[1]} - {player[2]} pts)")
        return result

class Match:
    def __init__(self, id, team1, team2, stage, match_number, best_of):
        self.id = id
        self.team1 = team1
        self.team2 = team2
        self.stage = stage
        self.match_number = match_number
        self.best_of = best_of
        self.winner = None
        self.score = None  # Tuple of (team1_score, team2_score)
        self.completed = False

# ========================= Tournament UI Components =========================

class TeamSelectionView(View):
    def __init__(self, ctx, tournament, match_id):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.tournament = tournament
        self.match_id = match_id
        self.match = next((m for m in tournament.matches if m.id == match_id), None)
        
        if not self.match or not self.match.team1 or not self.match.team2:
            return
        
        # Add buttons for each team
        self.add_item(discord.ui.Button(
            label=f"{self.match.team1.name}",
            style=discord.ButtonStyle.primary,
            custom_id=f"team_{self.match.team1.id}"
        ))
        
        self.add_item(discord.ui.Button(
            label=f"{self.match.team2.name}",
            style=discord.ButtonStyle.danger,
            custom_id=f"team_{self.match.team2.id}"
        ))
    
    async def interaction_check(self, interaction):
        if interaction.data["custom_id"].startswith("team_"):
            team_id = interaction.data["custom_id"].replace("team_", "")
            
            # Create modal for score input
            modal = ScoreInputModal(self.tournament, self.match_id, team_id)
            await interaction.response.send_modal(modal)
            return True
        
        return False

class ScoreInputModal(Modal):
    def __init__(self, tournament, match_id, winner_id):
        super().__init__(title="Enter Match Score")
        self.tournament = tournament
        self.match_id = match_id
        self.winner_id = winner_id
        
        self.match = next((m for m in tournament.matches if m.id == match_id), None)
        
        # Add text inputs for scores
        self.team1_score = TextInput(
            label=f"{self.match.team1.name} Score",
            placeholder="0",
            required=True,
            max_length=1
        )
        self.add_item(self.team1_score)
        
        self.team2_score = TextInput(
            label=f"{self.match.team2.name} Score",
            placeholder="0",
            required=True,
            max_length=1
        )
        self.add_item(self.team2_score)
    
    async def on_submit(self, interaction):
        try:
            score1 = int(self.team1_score.value)
            score2 = int(self.team2_score.value)
            
            # Validate scores
            if self.winner_id == self.match.team1.id and score1 <= score2:
                await interaction.response.send_message("Error: Winner's score must be higher", ephemeral=True)
                return
            
            if self.winner_id == self.match.team2.id and score2 <= score1:
                await interaction.response.send_message("Error: Winner's score must be higher", ephemeral=True)
                return
            
            # Update match result
            success, message = self.tournament.update_match_result(
                self.match_id, 
                self.winner_id,
                score1,
                score2
            )
            
            if success:
                embed = create_match_embed(self.match)
                await interaction.response.send_message(f"✅ {message}", embed=embed)
            else:
                await interaction.response.send_message(f"❌ {message}", ephemeral=True)
        
        except ValueError:
            await interaction.response.send_message("Please enter valid numbers for scores", ephemeral=True)

# ========================= Tournament Helper Functions =========================

async def check_tournament_admin_permission(ctx):
    """Check if the user has permission to manage tournaments."""
    # List of roles that can manage tournaments
    allowed_roles = ["Moderators", "Admin", "Staff", "Moderator"]
    
    # Check if the user has any of the allowed roles
    has_permission = any(role.name in allowed_roles for role in ctx.author.roles)
    
    # Server owner always has permission
    if ctx.guild and ctx.author.id == ctx.guild.owner_id:
        has_permission = True
    
    # If user doesn't have permission, send a message
    if not has_permission:
        await ctx.send("❌ You don't have permission to manage tournaments. This command is restricted to moderators and admins.")
    
    return has_permission

def create_tournament_teams_embeds(tournament):
    """Creates embeds for tournament teams."""
    embeds = []
    
    # Create separate embeds for each team pair (2 teams per embed)
    for i in range(0, len(tournament.teams), 2):
        embed = discord.Embed(
            title=f"🏆 Tournament Teams: {tournament.name}",
            color=PURPLE_COLOR
        )
        
        # Add first team
        team1 = tournament.teams[i]
        team1_players = team1.get_formatted_players()
        embed.add_field(
            name=f"Team {i+1}: {team1.name} ({team1.score:.1f} pts) [ID: {team1.id}]",
            value="\n".join(team1_players),
            inline=True
        )
        
        # Add second team if exists
        if i + 1 < len(tournament.teams):
            team2 = tournament.teams[i+1]
            team2_players = team2.get_formatted_players()
            embed.add_field(
                name=f"Team {i+2}: {team2.name} ({team2.score:.1f} pts) [ID: {team2.id}]",
                value="\n".join(team2_players),
                inline=True
            )
        
        embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
        embeds.append(embed)
    
    return embeds

def create_tournament_matches_embed(tournament):
    """Creates embed for tournament matches."""
    embed = discord.Embed(
        title=f"🏆 Tournament Matches: {tournament.name}",
        description=f"Tournament Phase: {tournament.phase}",
        color=PURPLE_COLOR
    )
    
    # Group matches by stage
    stages = {}
    for match in tournament.matches:
        if match.stage not in stages:
            stages[match.stage] = []
        stages[match.stage].append(match)
    
    # Add matches by stage
    for stage, matches in stages.items():
        matches_info = []
        
        for match in matches:
            team1_name = match.team1.name if match.team1 else "TBD"
            team2_name = match.team2.name if match.team2 else "TBD"
            
            if match.winner:
                if match.score:
                    score_str = f" ({match.score[0]}-{match.score[1]})"
                else:
                    score_str = ""
                status = f"✓ {match.winner.name} won{score_str}"
            else:
                status = "Pending"
            
            matches_info.append(f"**{match.id}**: {team1_name} vs {team2_name} - {status}")
        
        embed.add_field(
            name=stage,
            value="\n".join(matches_info),
            inline=False
        )
    
    if tournament.winner:
        embed.add_field(
            name="🎉 Tournament Winner",
            value=f"**{tournament.winner.name}**",
            inline=False
        )
    
    embed.set_footer(text=f"Use `!lf tournament update [match_id]` to update match results")
    return embed

def create_match_embed(match):
    """Creates embed for a specific match."""
    # Define colors for different stages
    stage_colors = {
        "Quarterfinals": 0x3498DB,  # Blue
        "Semifinals": 0x9B59B6,    # Purple
        "Finals": 0xF1C40F        # Gold
    }
    
    color = stage_colors.get(match.stage, PURPLE_COLOR)
    
    embed = discord.Embed(
        title=f"🏆 {match.stage} - Match {match.id}",
        description=f"Best of {match.best_of}",
        color=color
    )
    
    # Team 1 info
    if match.team1:
        team1_players = match.team1.get_formatted_players()
        embed.add_field(
            name=f"🔵 {match.team1.name} ({match.team1.score:.1f} pts)",
            value="\n".join(team1_players),
            inline=True
        )
    else:
        embed.add_field(name="🔵 TBD", value="To be determined", inline=True)
    
    # Team 2 info
    if match.team2:
        team2_players = match.team2.get_formatted_players()
        embed.add_field(
            name=f"🔴 {match.team2.name} ({match.team2.score:.1f} pts)",
            value="\n".join(team2_players),
            inline=True
        )
    else:
        embed.add_field(name="🔴 TBD", value="To be determined", inline=True)
    
    # Match result
    if match.winner:
        if match.score:
            score_str = f" ({match.score[0]}-{match.score[1]})"
        else:
            score_str = ""
        
        embed.add_field(
            name="Match Result",
            value=f"✓ **{match.winner.name}** won{score_str}",
            inline=False
        )
    
    embed.set_footer(text=f"Update this match with: !lf tournament update {match.id}")
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
    
    # try:
    #     await lobby_message.pin()
    # except discord.HTTPException:
    #     await ctx.send("Note: I couldn't pin the lobby message. For best visibility, an admin should pin it manually.")
    
    if player_pool:
        queue_embed, queue_view = await display_queue(ctx)
        await ctx.send("Current queue:", embed=queue_embed, view=queue_view)

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

    commands_tournament = (
        "9. `!lf tournament create [name]`\n"
        "   - Create a new tournament\n\n"
        "10. `!lf tournament add [name] [rank]`\n"
        "   - Add a player to the tournament\n\n"
        "11. `!lf tournament help`\n"
        "   - Show all tournament commands\n"
    )
    
    embed.add_field(name="Tournament Commands", value=commands_tournament, inline=False)

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

# ========================= Tournament Commands =========================

@bot.group(name='tournament', aliases=['t', 'tourney'], invoke_without_command=True)
async def tournament(ctx):
    """Base command for tournament management."""
    await ctx.send("Please use a subcommand: create, add, remove, generate, teams, matches, update, clear, info, active")

@tournament.command(name='create')
async def tournament_create(ctx, *, name=None):
    """Creates a new tournament."""
    # Check if user has permission
    if not await check_tournament_admin_permission(ctx):
        return
    
    global active_tournament
    
    if not name:
        await ctx.send("❌ Please provide a tournament name: `!lf tournament create [name]`")
        return
    
    tournament = Tournament(name, ctx.author.id)
    tournaments[tournament.id] = tournament
    active_tournament = tournament.id
    
    embed = discord.Embed(
        title=f"🏆 Tournament Created: {tournament.name}",
        description=f"Tournament ID: `{tournament.id}`\nUse `!lf tournament add [name] [rank]` to add participants",
        color=PURPLE_COLOR
    )
    embed.add_field(name="Status", value=tournament.phase, inline=True)
    embed.add_field(name="Participants", value="0/40", inline=True)
    embed.add_field(name="Created By", value=ctx.author.mention, inline=True)
    embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
    
    await ctx.send(embed=embed)

@tournament.command(name='add')
async def tournament_add(ctx, name=None, rank=None):
    """Adds a player to the active tournament."""
    # Check if user has permission
    if not await check_tournament_admin_permission(ctx):
        return
    
    global active_tournament
    
    if not active_tournament or active_tournament not in tournaments:
        await ctx.send("❌ No active tournament. Create one with `!lf tournament create [name]`")
        return
    
    tournament = tournaments[active_tournament]
    
    if tournament.phase != TOURNAMENT_PHASE["REGISTRATION"]:
        await ctx.send(f"❌ Cannot add participants. Tournament is in {tournament.phase} phase.")
        return
    
    if not name:
        await ctx.send("❌ Please provide a player name: `!lf tournament add [name] [rank]`")
        return
    
    if not rank:
        await ctx.send("❌ Please provide a player rank: `!lf tournament add [name] [rank]`")
        return
    
    rank = rank.upper()
    if rank not in TIER_POINTS:
        await ctx.send(f"❌ Invalid rank '**{rank}**'. Use `!lf information` to see valid ranks.")
        return
    
    success, message = tournament.add_participant(name, rank)
    
    if success:
        participants_count = len(tournament.participants)
        await ctx.send(f"✅ {message} ({participants_count}/40 participants)")
        
        if participants_count >= 40:
            await ctx.send("🎮 **You now have 40 participants!** Use `!lf tournament generate` to create teams and matches")
    else:
        await ctx.send(f"❌ {message}")

@tournament.command(name='addmany')
async def tournament_add_many(ctx, *, player_data=None):
    """Adds multiple players to the active tournament.
    Format: name1 rank1, name2 rank2, name3 rank3, ..."""
    # Check if user has permission
    if not await check_tournament_admin_permission(ctx):
        return
    
    global active_tournament
    
    if not active_tournament or active_tournament not in tournaments:
        await ctx.send("❌ No active tournament. Create one with `!lf tournament create [name]`")
        return
    
    tournament = tournaments[active_tournament]
    
    if tournament.phase != TOURNAMENT_PHASE["REGISTRATION"]:
        await ctx.send(f"❌ Cannot add participants. Tournament is in {tournament.phase} phase.")
        return
    
    if not player_data:
        await ctx.send("❌ Please provide player data in format: `name1 rank1, name2 rank2, ...`")
        return
    
    # Split by commas to get each player's data
    player_entries = player_data.split(',')
    added_count = 0
    errors = []
    
    for entry in player_entries:
        parts = entry.strip().split()
        if len(parts) < 2:
            errors.append(f"Invalid entry: {entry} (missing rank)")
            continue
        
        # Last part is the rank, everything before is the name
        rank = parts[-1].upper()
        name = ' '.join(parts[:-1])
        
        if rank not in TIER_POINTS:
            errors.append(f"Invalid rank '{rank}' for player '{name}'")
            continue
        
        success, message = tournament.add_participant(name, rank)
        if success:
            added_count += 1
        else:
            errors.append(message)
    
    # Report results
    response = f"✅ Added {added_count} players to the tournament."
    if errors:
        response += f"\n❌ Errors ({len(errors)}):\n" + "\n".join(errors)
    
    participants_count = len(tournament.participants)
    response += f"\n\nTotal participants: {participants_count}/40"
    
    if participants_count >= 40:
        response += "\n🎮 **You now have 40 participants!** Use `!lf tournament generate` to create teams and matches"
    
    await ctx.send(response)
    
@tournament.command(name='remove')
async def tournament_remove(ctx, *, name=None):
    """Removes a player from the active tournament."""
    # Check if user has permission
    if not await check_tournament_admin_permission(ctx):
        return
    
    global active_tournament
    
    if not active_tournament or active_tournament not in tournaments:
        await ctx.send("❌ No active tournament. Create one with `!lf tournament create [name]`")
        return
    
    tournament = tournaments[active_tournament]
    
    if tournament.phase != TOURNAMENT_PHASE["REGISTRATION"]:
        await ctx.send(f"❌ Cannot remove participants. Tournament is in {tournament.phase} phase.")
        return
    
    if not name:
        await ctx.send("❌ Please provide a player name: `!lf tournament remove [name]`")
        return
    
    success, message = tournament.remove_participant(name)
    
    if success:
        participants_count = len(tournament.participants)
        await ctx.send(f"✅ {message} ({participants_count}/40 participants)")
    else:
        await ctx.send(f"❌ {message}")

@tournament.command(name='generate')
async def tournament_generate(ctx):
    """Generates balanced teams and bracket for the active tournament."""
    # Check if user has permission
    if not await check_tournament_admin_permission(ctx):
        return
    
    global active_tournament
    
    if not active_tournament or active_tournament not in tournaments:
        await ctx.send("❌ No active tournament. Create one with `!lf tournament create [name]`")
        return
    
    tournament = tournaments[active_tournament]
    
    if tournament.phase != TOURNAMENT_PHASE["REGISTRATION"]:
        await ctx.send(f"❌ Teams have already been generated. Tournament is in {tournament.phase} phase.")
        return
    
    success, message = tournament.generate_teams()
    
    if success:
        await ctx.send(f"✅ {message}")
        
        # Send teams info
        teams_embeds = create_tournament_teams_embeds(tournament)
        for embed in teams_embeds:
            await ctx.send(embed=embed)
        
        # Send matches info
        matches_embed = create_tournament_matches_embed(tournament)
        await ctx.send(embed=matches_embed)
    else:
        await ctx.send(f"❌ {message}")

@tournament.command(name='teams')
async def tournament_teams(ctx):
    """Shows all teams in the active tournament."""
    global active_tournament
    
    if not active_tournament or active_tournament not in tournaments:
        await ctx.send("❌ No active tournament. Create one with `!lf tournament create [name]`")
        return
    
    tournament = tournaments[active_tournament]
    
    if not tournament.teams:
        await ctx.send("❌ Teams have not been generated yet. Use `!lf tournament generate` to create teams.")
        return
    
    teams_embeds = create_tournament_teams_embeds(tournament)
    for embed in teams_embeds:
        await ctx.send(embed=embed)

@tournament.command(name='matches')
async def tournament_matches(ctx):
    """Shows all matches in the active tournament."""
    global active_tournament
    
    if not active_tournament or active_tournament not in tournaments:
        await ctx.send("❌ No active tournament. Create one with `!lf tournament create [name]`")
        return
    
    tournament = tournaments[active_tournament]
    
    if not tournament.matches:
        await ctx.send("❌ Matches have not been generated yet. Use `!lf tournament generate` to create matches.")
        return
    
    matches_embed = create_tournament_matches_embed(tournament)
    await ctx.send(embed=matches_embed)

@tournament.command(name='match')
async def tournament_match(ctx, match_id=None):
    """Shows details for a specific match."""
    global active_tournament
    
    if not active_tournament or active_tournament not in tournaments:
        await ctx.send("❌ No active tournament. Create one with `!lf tournament create [name]`")
        return
    
    tournament = tournaments[active_tournament]
    
    if not match_id:
        await ctx.send("❌ Please provide a match ID: `!lf tournament match [match_id]`")
        return
    
    match = next((m for m in tournament.matches if m.id == match_id), None)
    if not match:
        await ctx.send(f"❌ Match {match_id} not found")
        return
    
    embed = create_match_embed(match)
    await ctx.send(embed=embed)

@tournament.command(name='update')
async def tournament_update(ctx, match_id=None):
    """Updates the result of a match."""
    # Check if user has permission
    if not await check_tournament_admin_permission(ctx):
        return
    
    global active_tournament
    
    if not active_tournament or active_tournament not in tournaments:
        await ctx.send("❌ No active tournament. Create one with `!lf tournament create [name]`")
        return
    
    tournament = tournaments[active_tournament]
    
    if not match_id:
        await ctx.send("❌ Please provide a match ID: `!lf tournament update [match_id]`")
        return
    
    match = next((m for m in tournament.matches if m.id == match_id), None)
    if not match:
        await ctx.send(f"❌ Match {match_id} not found")
        return
    
    if not match.team1 or not match.team2:
        await ctx.send(f"❌ Teams for match {match_id} are not set yet")
        return
    
    if match.completed:
        await ctx.send(f"❌ Match {match_id} is already completed")
        return
    
    # Show team selection view
    embed = create_match_embed(match)
    embed.add_field(name="Update Result", value="Select the winning team below:", inline=False)
    
    view = TeamSelectionView(ctx, tournament, match_id)
    await ctx.send(embed=embed, view=view)

@tournament.command(name='clear')
async def tournament_clear(ctx):
    """Clears the active tournament."""
    # Check if user has permission
    if not await check_tournament_admin_permission(ctx):
        return
    
    global active_tournament
    
    if not active_tournament or active_tournament not in tournaments:
        await ctx.send("❌ No active tournament to clear")
        return
    
    del tournaments[active_tournament]
    active_tournament = None
    
    await ctx.send("🧹 Active tournament has been cleared")

@tournament.command(name='active')
async def tournament_active(ctx, tournament_id=None):
    """Sets the active tournament or shows current active tournament."""
    # Check if user has permission for setting active tournament
    if tournament_id and not await check_tournament_admin_permission(ctx):
        return
    
    global active_tournament
    
    if tournament_id:
        if tournament_id in tournaments:
            active_tournament = tournament_id
            tournament = tournaments[active_tournament]
            await ctx.send(f"✅ Active tournament set to: **{tournament.name}** (ID: `{tournament.id}`)")
        else:
            await ctx.send(f"❌ Tournament with ID `{tournament_id}` not found")
    else:
        if active_tournament and active_tournament in tournaments:
            tournament = tournaments[active_tournament]
            await ctx.send(f"🏆 Current active tournament: **{tournament.name}** (ID: `{tournament.id}`)")
        else:
            await ctx.send("❌ No active tournament set")

@tournament.command(name='list')
async def tournament_list(ctx):
    """Lists all tournaments."""
    if not tournaments:
        await ctx.send("❌ No tournaments created yet")
        return
    
    embed = discord.Embed(
        title="🏆 All Tournaments",
        description=f"Total tournaments: {len(tournaments)}",
        color=PURPLE_COLOR
    )
    
    for tournament_id, tournament in tournaments.items():
        active_marker = "✅ " if tournament_id == active_tournament else ""
        embed.add_field(
            name=f"{active_marker}{tournament.name} (ID: {tournament_id})",
            value=f"Phase: {tournament.phase}\nTeams: {len(tournament.teams)}\nParticipants: {len(tournament.participants)}/40",
            inline=False
        )
    
    embed.set_footer(text=f"Use `!lf tournament active [id]` to set the active tournament")
    await ctx.send(embed=embed)

@tournament.command(name='info')
async def tournament_info(ctx):
    """Shows information about the active tournament."""
    global active_tournament
    
    if not active_tournament or active_tournament not in tournaments:
        await ctx.send("❌ No active tournament. Create one with `!lf tournament create [name]`")
        return
    
    tournament = tournaments[active_tournament]
    
    embed = discord.Embed(
        title=f"🏆 Tournament: {tournament.name}",
        description=f"ID: `{tournament.id}`",
        color=PURPLE_COLOR
    )
    
    embed.add_field(name="Status", value=tournament.phase, inline=True)
    embed.add_field(name="Participants", value=f"{len(tournament.participants)}/40", inline=True)
    embed.add_field(name="Teams", value=len(tournament.teams), inline=True)
    
    if tournament.winner:
        embed.add_field(name="Winner", value=f"🎉 **{tournament.winner.name}**", inline=False)
    
    # If in registration phase, show recent participants
    if tournament.phase == TOURNAMENT_PHASE["REGISTRATION"] and tournament.participants:
        recent_participants = tournament.participants[-5:]  # Show last 5 added
        participants_list = []
        
        for p in recent_participants:
            tier_emoji = get_tier_emoji(p[1])
            participants_list.append(f"{tier_emoji} **{p[0]}** ({p[1]} - {p[2]} pts)")
        
        embed.add_field(
            name="Recent Participants",
            value="\n".join(participants_list),
            inline=False
        )
    
    embed.set_footer(text=f"Created at: {tournament.created_at.strftime('%Y-%m-%d %H:%M')}")
    await ctx.send(embed=embed)

@tournament.command(name='help')
async def tournament_help(ctx):
    """Shows help for tournament commands."""
    embed = discord.Embed(
        title="🏆 Tournament Commands Help",
        description="Manage tournaments with the following commands:",
        color=TEAL_COLOR
    )
    
    commands = [
        ("`!lf tournament create [name]`", "Create a new tournament and set it as active"),
        ("`!lf tournament add [name] [rank]`", "Add a player to the active tournament"),
        ("`!lf tournament remove [name]`", "Remove a player from the active tournament"),
        ("`!lf tournament generate`", "Generate balanced teams and bracket for the active tournament"),
        ("`!lf tournament teams`", "Show all teams in the active tournament"),
        ("`!lf tournament matches`", "Show all matches in the active tournament"),
        ("`!lf tournament match [match_id]`", "Show details for a specific match"),
        ("`!lf tournament update [match_id]`", "Update the result of a match"),
        ("`!lf tournament clear`", "Clear the active tournament"),
        ("`!lf tournament active [tournament_id]`", "Set the active tournament"),
        ("`!lf tournament list`", "List all tournaments"),
        ("`!lf tournament info`", "Show information about the active tournament"),
        ("`!lf tournament help`", "Show this help message")
    ]
    
    for cmd, desc in commands:
        embed.add_field(name=cmd, value=desc, inline=False)
    
    embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
    await ctx.send(embed=embed)

# Run the bot
bot.run(DISCORD_TOKEN)
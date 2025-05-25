
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import os
from dotenv import load_dotenv
from itertools import combinations
import random
import asyncio
import string
from datetime import datetime
import json
import urllib.parse
import re

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

# Channel IDs for cross-posting
RESULTS_CHANNEL_NAME = "✅︱customs-results"
LEADERBOARD_CHANNEL_NAME = "📊︱customs-leaderboard"

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

# Server mapping for OP.GG regions
OPGG_SERVERS = {
    'NA': 'na',
    'EUW': 'euw',
    'EUNE': 'eune', 
    'KR': 'kr',
    'JP': 'jp',
    'OCE': 'oce',
    'BR': 'br',
    'LAS': 'las',
    'LAN': 'lan',
    'RU': 'ru',
    'TR': 'tr',
    'SEA': 'sg',  # Singapore for SEA
    'TH': 'th',
    'TW': 'tw',
    'VN': 'vn',
    'PH': 'ph'
}

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

async def create_match(team1_name, team1_players, team2_name, team2_players, team1_user_ids=None, team2_user_ids=None):
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
            'team1_user_ids': team1_user_ids or [],
            'team2_user_ids': team2_user_ids or [],
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
            winning_user_ids = match.get('team1_user_ids', []) if winner_team == 'team1' else match.get('team2_user_ids', [])
            losing_user_ids = match.get('team2_user_ids', []) if winner_team == 'team1' else match.get('team1_user_ids', [])
            
            # Update winners
            for i, player in enumerate(winning_players):
                user_id = winning_user_ids[i] if i < len(winning_user_ids) else None
                await update_player_stats(player, True, user_id)
            
            # Update losers
            for i, player in enumerate(losing_players):
                user_id = losing_user_ids[i] if i < len(losing_user_ids) else None
                await update_player_stats(player, False, user_id)
        else:
            # Editing existing result - we need to reverse previous result and apply new one
            # Get players from previous result
            previous_winning_players = match['team1_players'] if previous_winner == 'team1' else match['team2_players']
            previous_losing_players = match['team2_players'] if previous_winner == 'team1' else match['team1_players']
            previous_winning_user_ids = match.get('team1_user_ids', []) if previous_winner == 'team1' else match.get('team2_user_ids', [])
            previous_losing_user_ids = match.get('team2_user_ids', []) if previous_winner == 'team1' else match.get('team1_user_ids', [])
            
            # Reverse previous result
            for i, player in enumerate(previous_winning_players):
                user_id = previous_winning_user_ids[i] if i < len(previous_winning_user_ids) else None
                await reverse_player_stats(player, True, user_id)
            for i, player in enumerate(previous_losing_players):
                user_id = previous_losing_user_ids[i] if i < len(previous_losing_user_ids) else None
                await reverse_player_stats(player, False, user_id)
            
            # Apply new result
            new_winning_players = match['team1_players'] if winner_team == 'team1' else match['team2_players']
            new_losing_players = match['team2_players'] if winner_team == 'team1' else match['team1_players']
            new_winning_user_ids = match.get('team1_user_ids', []) if winner_team == 'team1' else match.get('team2_user_ids', [])
            new_losing_user_ids = match.get('team2_user_ids', []) if winner_team == 'team1' else match.get('team1_user_ids', [])
            
            for i, player in enumerate(new_winning_players):
                user_id = new_winning_user_ids[i] if i < len(new_winning_user_ids) else None
                await update_player_stats(player, True, user_id)
            for i, player in enumerate(new_losing_players):
                user_id = new_losing_user_ids[i] if i < len(new_losing_user_ids) else None
                await update_player_stats(player, False, user_id)
        
        return True, "Match result updated successfully"
    except Exception as e:
        print(f"Error updating match result: {e}")
        return False, f"Error updating match: {str(e)}"

async def reverse_player_stats(player_name, was_winner, user_id=None):
    """Reverse player statistics (used when editing match results)."""
    try:
        # Try to find by user_id first, then by username
        if user_id:
            result = supabase.table('player_stats').select('*').eq('discord_user_id', user_id).execute()
        else:
            result = supabase.table('player_stats').select('*').eq('discord_username', player_name).execute()
        
        if result.data:
            current_stats = result.data[0]
            # Subtract the previous result
            new_total = max(0, current_stats['total_matches'] - 1)
            new_wins = max(0, current_stats['wins'] - (1 if was_winner else 0))
            new_losses = max(0, current_stats['losses'] - (0 if was_winner else 1))
            new_win_rate = (new_wins / new_total * 100) if new_total > 0 else 0
            
            # Reverse recent form
            current_form = current_stats.get('recent_form', '')
            new_recent_form = current_form[:-1] if current_form else ''
            
            update_data = {
                'total_matches': new_total,
                'wins': new_wins,
                'losses': new_losses,
                'win_rate': round(new_win_rate, 2),
                'recent_form': new_recent_form
            }
            
            if user_id:
                supabase.table('player_stats').update(update_data).eq('discord_user_id', user_id).execute()
            else:
                supabase.table('player_stats').update(update_data).eq('discord_username', player_name).execute()
    except Exception as e:
        print(f"Error reversing player stats for {player_name}: {e}")

async def update_player_stats(player_name, won, user_id=None):
    """Update individual player statistics."""
    try:
        # Try to find by user_id first, then by username
        if user_id:
            result = supabase.table('player_stats').select('*').eq('discord_user_id', user_id).execute()
        else:
            result = supabase.table('player_stats').select('*').eq('discord_username', player_name).execute()
        
        if result.data:
            # Update existing player
            current_stats = result.data[0]
            new_total = current_stats['total_matches'] + 1
            new_wins = current_stats['wins'] + (1 if won else 0)
            new_losses = current_stats['losses'] + (0 if won else 1)
            new_win_rate = (new_wins / new_total) * 100 if new_total > 0 else 0
            
            # Update recent form (last 5 games)
            current_form = current_stats.get('recent_form', '')
            new_form_char = 'W' if won else 'L'
            new_recent_form = (current_form + new_form_char)[-5:]  # Keep only last 5
            
            # Update streaks
            current_streak = current_stats.get('current_streak', 0)
            streak_type = current_stats.get('streak_type', '')
            longest_win_streak = current_stats.get('longest_win_streak', 0)
            
            if won:
                if streak_type == 'WIN':
                    current_streak += 1
                else:
                    current_streak = 1
                    streak_type = 'WIN'
                longest_win_streak = max(longest_win_streak, current_streak)
            else:
                if streak_type == 'LOSS':
                    current_streak += 1
                else:
                    current_streak = 1
                    streak_type = 'LOSS'
            
            update_data = {
                'total_matches': new_total,
                'wins': new_wins,
                'losses': new_losses,
                'win_rate': round(new_win_rate, 2),
                'last_played': datetime.now().isoformat(),
                'recent_form': new_recent_form,
                'current_streak': current_streak,
                'streak_type': streak_type,
                'longest_win_streak': longest_win_streak,
                'display_name': player_name
            }
            
            if user_id:
                update_data['discord_user_id'] = user_id
            
            if user_id:
                supabase.table('player_stats').update(update_data).eq('discord_user_id', user_id).execute()
            else:
                supabase.table('player_stats').update(update_data).eq('discord_username', player_name).execute()
        else:
            # Create new player
            new_stats = {
                'discord_username': player_name,
                'discord_user_id': user_id,
                'display_name': player_name,
                'total_matches': 1,
                'wins': 1 if won else 0,
                'losses': 0 if won else 1,
                'win_rate': 100.0 if won else 0.0,
                'last_played': datetime.now().isoformat(),
                'recent_form': 'W' if won else 'L',
                'current_streak': 1,
                'streak_type': 'WIN' if won else 'LOSS',
                'longest_win_streak': 1 if won else 0
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

async def get_player_stats(player_name_or_id):
    """Get player statistics from database by name or user ID."""
    try:
        # Try by user ID first if it's a number
        if str(player_name_or_id).isdigit():
            result = supabase.table('player_stats').select('*').eq('discord_user_id', int(player_name_or_id)).execute()
            if result.data:
                return result.data[0], True
        
        # Try by username
        result = supabase.table('player_stats').select('*').eq('discord_username', player_name_or_id).execute()
        if result.data:
            return result.data[0], True
        
        # Try by display name
        result = supabase.table('player_stats').select('*').eq('display_name', player_name_or_id).execute()
        if result.data:
            return result.data[0], True
        
        return None, False
    except Exception as e:
        print(f"Error getting player stats: {e}")
        return None, False

async def get_all_player_stats(order_by='total_matches'):
    """Get all player statistics from database."""
    try:
        valid_orders = ['total_matches', 'wins', 'losses', 'win_rate']
        if order_by not in valid_orders:
            order_by = 'total_matches'
        
        result = supabase.table('player_stats').select('*').order(order_by, desc=True).execute()
        return result.data, True
    except Exception as e:
        print(f"Error getting all player stats: {e}")
        return [], False

async def get_leaderboard(order_by='total_matches', min_games=3):
    """Get player leaderboard sorted by specified criteria."""
    try:
        valid_orders = ['total_matches', 'wins', 'losses', 'win_rate']
        if order_by not in valid_orders:
            order_by = 'total_matches'
        
        result = supabase.table('player_stats').select('*').gte('total_matches', min_games).order(order_by, desc=True).limit(15).execute()
        return result.data, True
    except Exception as e:
        print(f"Error getting leaderboard: {e}")
        return [], False

async def merge_player_accounts(old_player, new_player):
    """Merge two player accounts together."""
    try:
        # Get both player stats
        old_result = supabase.table('player_stats').select('*').eq('discord_username', old_player).execute()
        new_result = supabase.table('player_stats').select('*').eq('discord_username', new_player).execute()
        
        if not old_result.data:
            return False, f"Player {old_player} not found"
        
        old_stats = old_result.data[0]
        
        if new_result.data:
            # Merge into existing new player
            new_stats = new_result.data[0]
            merged_stats = {
                'total_matches': old_stats['total_matches'] + new_stats['total_matches'],
                'wins': old_stats['wins'] + new_stats['wins'],
                'losses': old_stats['losses'] + new_stats['losses'],
                'longest_win_streak': max(old_stats.get('longest_win_streak', 0), new_stats.get('longest_win_streak', 0))
            }
            merged_stats['win_rate'] = (merged_stats['wins'] / merged_stats['total_matches'] * 100) if merged_stats['total_matches'] > 0 else 0
            
            # Update new player with merged stats
            supabase.table('player_stats').update(merged_stats).eq('discord_username', new_player).execute()
        else:
            # Rename old player to new player
            supabase.table('player_stats').update({'discord_username': new_player, 'display_name': new_player}).eq('discord_username', old_player).execute()
        
        # Delete old player record
        if new_result.data:  # Only delete if we merged into existing player
            supabase.table('player_stats').delete().eq('discord_username', old_player).execute()
        
        return True, f"Successfully merged {old_player} into {new_player}"
    except Exception as e:
        print(f"Error merging players: {e}")
        return False, f"Error merging players: {str(e)}"

def get_display_name(player_data):
    """Helper function to get the correct display name for a player."""
    display_name = player_data.get('display_name')
    # Handle both None and "None" string cases
    if not display_name or display_name == "None" or display_name.strip() == "":
        return player_data.get('discord_username', 'Unknown')
    return display_name


async def get_daily_server_stats():
    """Get server statistics for today."""
    try:
        today = datetime.now().date()
        today_start = f"{today}T00:00:00"
        today_end = f"{today}T23:59:59"
        
        # Get matches played today
        matches_today = supabase.table('matches').select('*').gte('created_at', today_start).lte('created_at', today_end).execute()
        completed_matches_today = [m for m in matches_today.data if m['winner'] is not None]
        
        # Get total stats
        total_players = supabase.table('player_stats').select('discord_username').execute()
        total_matches = supabase.table('matches').select('match_id').execute()
        
        return {
            'matches_today': len(matches_today.data),
            'completed_today': len(completed_matches_today),
            'total_players': len(total_players.data),
            'total_matches': len(total_matches.data)
        }, True
    except Exception as e:
        print(f"Error getting daily stats: {e}")
        return {}, False

# ========================= NEW DATABASE FUNCTIONS FOR HEAD-TO-HEAD =========================

async def get_head_to_head_stats(player1, player2):
    """Get head-to-head statistics between two players."""
    try:
        # Get all matches where both players participated
        all_matches = supabase.table('matches').select('*').not_.is_('winner', 'null').execute()
        
        head_to_head = {
            'total_matches': 0,
            'player1_wins': 0,
            'player2_wins': 0,
            'recent_matches': []
        }
        
        for match in all_matches.data:
            team1_players = match.get('team1_players', [])
            team2_players = match.get('team2_players', [])
            
            # Check if both players are in this match
            player1_in_team1 = any(p.lower() == player1.lower() for p in team1_players)
            player1_in_team2 = any(p.lower() == player1.lower() for p in team2_players)
            player2_in_team1 = any(p.lower() == player2.lower() for p in team1_players)
            player2_in_team2 = any(p.lower() == player2.lower() for p in team2_players)
            
            # They played against each other
            if (player1_in_team1 and player2_in_team2) or (player1_in_team2 and player2_in_team1):
                head_to_head['total_matches'] += 1
                
                winner = match['winner']
                if (player1_in_team1 and winner == 'team1') or (player1_in_team2 and winner == 'team2'):
                    head_to_head['player1_wins'] += 1
                    result = f"{player1} won"
                else:
                    head_to_head['player2_wins'] += 1
                    result = f"{player2} won"
                
                head_to_head['recent_matches'].append({
                    'match_id': match['match_id'],
                    'date': match['created_at'],
                    'result': result
                })
        
        # Sort recent matches by date (most recent first) and keep last 5
        head_to_head['recent_matches'].sort(key=lambda x: x['date'], reverse=True)
        head_to_head['recent_matches'] = head_to_head['recent_matches'][:5]
        
        return head_to_head, True
    except Exception as e:
        print(f"Error getting head-to-head stats: {e}")
        return {}, False

async def get_most_played_with(player_name):
    """Get players this person has played with most often as teammates."""
    try:
        # Get all matches where this player participated
        all_matches = supabase.table('matches').select('*').execute()
        
        teammate_counts = {}
        
        for match in all_matches.data:
            # Parse team players - they might be stored as JSON strings
            team1_players = match.get('team1_players', [])
            team2_players = match.get('team2_players', [])
            
            # If they're strings, parse them as JSON
            if isinstance(team1_players, str):
                try:
                    team1_players = json.loads(team1_players)
                except json.JSONDecodeError:
                    team1_players = []
            
            if isinstance(team2_players, str):
                try:
                    team2_players = json.loads(team2_players)
                except json.JSONDecodeError:
                    team2_players = []
            
            # Ensure they're lists and filter out None values
            team1_players = [p for p in (team1_players or []) if p is not None and str(p).strip()]
            team2_players = [p for p in (team2_players or []) if p is not None and str(p).strip()]
            
            # Find which team the player was on
            player_team = None
            if any(str(p).lower() == str(player_name).lower() for p in team1_players):
                player_team = team1_players
            elif any(str(p).lower() == str(player_name).lower() for p in team2_players):
                player_team = team2_players
            
            if player_team:
                # Count all other players on the same team as teammates
                for teammate in player_team:
                    if teammate and str(teammate).lower() != str(player_name).lower():
                        teammate_counts[str(teammate)] = teammate_counts.get(str(teammate), 0) + 1
        
        # Sort by count and return top 10
        sorted_teammates = sorted(teammate_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return sorted_teammates, True
    except Exception as e:
        print(f"Error getting most played with: {e}")
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

def check_moderator_permission_interaction(interaction):
    """Check if the user has moderator permissions for interactions."""
    allowed_roles = ["Moderators", "Admin", "Staff", "Moderator"]
    has_permission = any(role.name in allowed_roles for role in interaction.user.roles)
    
    if interaction.guild and interaction.user.id == interaction.guild.owner_id:
        has_permission = True
    
    return has_permission

# ========================= UI Components =========================

class MatchResultView(View):
    """View for match result buttons in the results channel."""
    
    def __init__(self, match_id, team1_name, team2_name):
        super().__init__(timeout=None)
        self.match_id = match_id
        self.team1_name = team1_name
        self.team2_name = team2_name
    
    @discord.ui.button(label="Team A Won", style=discord.ButtonStyle.primary, emoji="🔵")
    async def team_a_won(self, interaction: discord.Interaction, button: Button):
        if not check_moderator_permission_interaction(interaction):
            await interaction.response.send_message("❌ You need moderator permissions to update match results.", ephemeral=True)
            return
        
        success, message = await update_match_result(self.match_id, 'team1', interaction.user.display_name)
        
        if success:
            embed = discord.Embed(
                title="🏆 Match Result Updated!",
                description=f"**Team A: {self.team1_name}** wins!",
                color=GREEN_COLOR
            )
            embed.add_field(name="Match ID", value=self.match_id, inline=True)
            embed.add_field(name="Updated by", value=interaction.user.display_name, inline=True)
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)
    
    @discord.ui.button(label="Team B Won", style=discord.ButtonStyle.danger, emoji="🔴")
    async def team_b_won(self, interaction: discord.Interaction, button: Button):
        if not check_moderator_permission_interaction(interaction):
            await interaction.response.send_message("❌ You need moderator permissions to update match results.", ephemeral=True)
            return
        
        success, message = await update_match_result(self.match_id, 'team2', interaction.user.display_name)
        
        if success:
            embed = discord.Embed(
                title="🏆 Match Result Updated!",
                description=f"**Team B: {self.team2_name}** wins!",
                color=GREEN_COLOR
            )
            embed.add_field(name="Match ID", value=self.match_id, inline=True)
            embed.add_field(name="Updated by", value=interaction.user.display_name, inline=True)
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)

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
        
        player_info = (name, found_rank, TIER_POINTS[found_rank], member.id)
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
            
            teams_embed, match_id = await create_balanced_teams(player_pool[:10])
            await self.ctx.send("🎮 **Queue is full! Creating balanced teams:**", embed=teams_embed)
            
            # Post to results channel if it exists
            if match_id:
                await post_to_results_channel(self.ctx.guild, teams_embed, match_id)
            
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
    team1_user_ids = [player[3] if len(player) > 3 else None for player in best_team1]
    team2_user_ids = [player[3] if len(player) > 3 else None for player in best_team2]
    
    match_id, success = await create_match(team1_name, team1_players, team2_name, team2_players, team1_user_ids, team2_user_ids)
    
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

    return embed, match_id

async def post_to_results_channel(guild, embed, match_id):
    """Post match teams to the results channel with result buttons."""
    try:
        # Try multiple channel name variations
        possible_names = ["✅︱customs-results", "customs-results", "✅customs-results", "results"]
        results_channel = None
        
        for name in possible_names:
            results_channel = discord.utils.get(guild.channels, name=name)
            if results_channel:
                break
        
        if results_channel:
            # Get team names from embed
            team1_name = "Team A"
            team2_name = "Team B"
            for field in embed.fields:
                if "Team A:" in field.name:
                    team1_name = field.name.split("Team A: ")[1].split(" (")[0]
                elif "Team B:" in field.name:
                    team2_name = field.name.split("Team B: ")[1].split(" (")[0]
            
            # Create result embed
            result_embed = discord.Embed(
                title="🎮 Match Created - Report Results",
                description=f"**Match ID:** `{match_id}`",
                color=BLUE_COLOR
            )
            
            # Copy team information
            for field in embed.fields:
                if "Team A:" in field.name or "Team B:" in field.name or "Balance Info" in field.name:
                    result_embed.add_field(name=field.name, value=field.value, inline=field.inline)
            
            result_embed.add_field(
                name="📝 How to Report Results",
                value="**Moderators:** Click the button below for the winning team",
                inline=False
            )
            
            view = MatchResultView(match_id, team1_name, team2_name)
            await results_channel.send(embed=result_embed, view=view)
    except Exception as e:
        print(f"Error posting to results channel: {e}")

# ========================= Auto Leaderboard Task =========================


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    activity = discord.Game(name="League of Flex | !lf information")
    await bot.change_presence(activity=activity)
    if not auto_leaderboard.is_running():
        auto_leaderboard.start()

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

@tasks.loop(hours=3)
async def auto_leaderboard():
    """Automatically post leaderboard every 3 hours."""
    try:
        for guild in bot.guilds:
            # Try multiple channel name variations
            possible_names = ["📊︱customs-leaderboard", "customs-leaderboard", "📊customs-leaderboard", "leaderboard"]
            leaderboard_channel = None
            
            for name in possible_names:
                leaderboard_channel = discord.utils.get(guild.channels, name=name)
                if leaderboard_channel:
                    break
            
            if leaderboard_channel:
                # Get leaderboard data
                leaderboard_data, found = await get_leaderboard('total_matches', 1)
                daily_stats, stats_found = await get_daily_server_stats()
                
                if found and leaderboard_data:
                    embed = discord.Embed(
                        title="🏆 Server Leaderboard",
                        description="*Auto-updated every 3 hours*",
                        color=PURPLE_COLOR
                    )
                    
                    # Add daily stats
                    if stats_found:
                        stats_text = (
                            f"🎮 **Today's Activity:**\n"
                            f"• Matches Created: {daily_stats.get('matches_today', 0)}\n"
                            f"• Matches Completed: {daily_stats.get('completed_today', 0)}\n"
                            f"• Total Players: {daily_stats.get('total_players', 0)}\n"
                            f"• Total Matches: {daily_stats.get('total_matches', 0)}"
                        )
                        embed.add_field(name="📊 Server Stats", value=stats_text, inline=False)
                    
                    # Create leaderboard entries (top 10)
                    leaderboard_lines = []
                    for idx, player in enumerate(leaderboard_data[:10]):
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
                        
                        # Recent form
                        recent_form = player.get('recent_form', '')
                        form_display = f" [{recent_form}]" if recent_form else ""
                        
                        # Use the helper function to get display name
                        display_name = get_display_name(player)
                        
                        leaderboard_lines.append(
                            f"{position} **{display_name}** - {player['total_matches']} games\n"
                            f"    ↳ {player['wins']}W-{player['losses']}L ({player['win_rate']}% {wr_emoji}){form_display}"
                        )
                    
                    embed.add_field(
                        name="🏆 Top Players (by matches played)",
                        value="\n\n".join(leaderboard_lines),
                        inline=False
                    )
                    
                    embed.set_footer(text=f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} | {WEBSITE_URL}")
                    
                    # Try to edit the last message, or send new one
                    try:
                        messages_found = False
                        async for message in leaderboard_channel.history(limit=20):
                            if message.author == bot.user and message.embeds and "Server Leaderboard" in message.embeds[0].title:
                                await message.edit(embed=embed)
                                messages_found = True
                                break
                        
                        if not messages_found:
                            await leaderboard_channel.send(embed=embed)
                    except Exception as edit_error:
                        print(f"Error editing leaderboard message: {edit_error}")
                        await leaderboard_channel.send(embed=embed)
                else:
                    print(f"No leaderboard data found for guild {guild.name}")
            else:
                print(f"Leaderboard channel not found in guild {guild.name}")
    except Exception as e:
        print(f"Error in auto leaderboard task: {e}")

@auto_leaderboard.before_loop
async def before_auto_leaderboard():
    """Wait for the bot to be ready before starting the auto leaderboard task."""
    await bot.wait_until_ready()

# ========================= Bot Commands and Events =========================


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
        embed, view = await display_queue(ctx)
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
            players.append((player_name, player_rank, TIER_POINTS[player_rank], None))  # No user ID for manual teams

        teams_embed, match_id = await create_balanced_teams(players)
        await ctx.send(embed=teams_embed)
        
        # Post to results channel
        if match_id:
            await post_to_results_channel(ctx.guild, teams_embed, match_id)
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


# ========================= Bot Commands and Events =========================

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
        "11. `!lf stats [player_name]` or `!lf stats me`\n"
        "   - Show player's win/loss statistics\n\n"
        "12. `!lf players`\n"
        "   - Show all players and their statistics\n\n"
        "13. `!lf leaderboard [type]`\n"
        "   - Show leaderboards: matches, wins, losses, winrate\n"
        "   - Default: `!lf leaderboard` (by matches played)\n\n"
        "14. `!lf merge [old_player] [new_player]` *(Moderators only)*\n"
        "   - Merge two player accounts together\n\n"
        "15. `!lf clear players`\n"
        "   - Clear the player queue\n\n"
        "16. `!lf information`\n"
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
            player_info = (name, rank, TIER_POINTS[rank], ctx.author.id)
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
    
    player_info = (name, rank, TIER_POINTS[rank], ctx.author.id)
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
        
        teams_embed, match_id = await create_balanced_teams(player_pool[:10])
        await ctx.send("🎮 **Queue is full! Creating balanced teams:**", embed=teams_embed)
        
        # Post to results channel
        if match_id:
            await post_to_results_channel(ctx.guild, teams_embed, match_id)
        
        del player_pool[:10]
        
        if player_pool:
            queue_start_time = asyncio.get_event_loop().time()
            queue_timer = asyncio.create_task(reset_queue_timer(ctx))
            remaining_embed, remaining_view = await display_queue(ctx)
            await ctx.send("**Players remaining in queue:**", embed=remaining_embed, view=remaining_view)

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
    """Show player statistics. Usage: !lf stats [player_name] or !lf stats me"""
    if not player_name or player_name.lower() == 'me':
        player_name = ctx.author.display_name
        # Also try with user ID for better matching
        player_id = ctx.author.id
        stats, found = await get_player_stats(player_id)
        if not found:
            stats, found = await get_player_stats(player_name)
    else:
        stats, found = await get_player_stats(player_name)
    
    if not found:
        await ctx.send(f"❌ No statistics found for **{player_name}**. They haven't played any tracked matches yet.")
        return
    
    # Use the helper function to get display name
    display_name = get_display_name(stats)
    
    embed = discord.Embed(
        title=f"📊 Player Statistics: {display_name}",
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

    recent_form = stats.get('recent_form', '')
    if recent_form:
        form_display = ' - '.join(recent_form)
        embed.add_field(
            name="Recent Form",
            value=f"`{form_display}`",
            inline=True
        )
    
    # Streaks
    current_streak = stats.get('current_streak', 0)
    streak_type = stats.get('streak_type', '')
    longest_win_streak = stats.get('longest_win_streak', 0)
    
    if current_streak > 0:
        streak_emoji = "🔥" if streak_type == 'WIN' else "❄️"
        embed.add_field(
            name="Current Streak",
            value=f"{streak_emoji} **{current_streak}** {streak_type.lower()}{'s' if current_streak > 1 else ''}",
            inline=True
        )
    
    if longest_win_streak > 0:
        embed.add_field(
            name="Best Win Streak",
            value=f"🏆 **{longest_win_streak}** wins",
            inline=True
        )
    
    # Most played with teammates
    teammates, found_teammates = await get_most_played_with(display_name)
    if found_teammates and teammates:
        top_teammates = teammates[:3]  # Show top 3
        teammates_text = []
        for teammate, count in top_teammates:
            teammates_text.append(f"**{teammate}** ({count} games)")
        
        embed.add_field(
            name="Top Teammates",
            value="\n".join(teammates_text),
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

@bot.command(name='players')
async def show_all_players(ctx):
    """Show all players and their statistics."""
    players_data, found = await get_all_player_stats('total_matches')
    
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
            
            # Use the helper function to get display name
            display_name = get_display_name(player)
            
            recent_form = player.get('recent_form', '')
            form_display = f" [{recent_form}]" if recent_form else ""
            
            player_lines.append(
                f"**{display_name}**: {player['wins']}W-{player['losses']}L "
                f"({player['win_rate']}% {wr_emoji}){form_display}"
            )
        
        embed.add_field(
            name=field_name,
            value="\n".join(player_lines),
            inline=True
        )
    
    embed.set_footer(text=f"Use !lf stats [player] for detailed stats | {WEBSITE_URL}")
    await ctx.send(embed=embed)


@bot.command(name='headtohead', aliases=['h2h', 'vs'])
async def head_to_head(ctx, player1=None, player2=None):
    """Show head-to-head statistics between two players. Usage: !lf headtohead [player1] [player2]"""
    if not player1 or not player2:
        await ctx.send("❌ Usage: `!lf headtohead [player1] [player2]`\nExample: `!lf headtohead PlayerA PlayerB`")
        return
    
    # If one player is "me", replace with the command user's name
    if player1.lower() == 'me':
        player1 = ctx.author.display_name
    if player2.lower() == 'me':
        player2 = ctx.author.display_name
    
    if player1.lower() == player2.lower():
        await ctx.send("❌ You can't compare a player against themselves!")
        return
    
    h2h_stats, found = await get_head_to_head_stats(player1, player2)
    
    if not found or h2h_stats['total_matches'] == 0:
        await ctx.send(f"❌ No head-to-head matches found between **{player1}** and **{player2}**.")
        return
    
    embed = discord.Embed(
        title=f"⚔️ Head-to-Head: {player1} vs {player2}",
        color=ORANGE_COLOR
    )
    
    # Overall stats
    embed.add_field(
        name="Total Matches",
        value=f"**{h2h_stats['total_matches']}**",
        inline=True
    )
    
    embed.add_field(
        name=f"{player1} Wins",
        value=f"**{h2h_stats['player1_wins']}** 🏆",
        inline=True
    )
    
    embed.add_field(
        name=f"{player2} Wins", 
        value=f"**{h2h_stats['player2_wins']}** 🏆",
        inline=True
    )
    
    # Win rate
    player1_winrate = (h2h_stats['player1_wins'] / h2h_stats['total_matches'] * 100) if h2h_stats['total_matches'] > 0 else 0
    player2_winrate = (h2h_stats['player2_wins'] / h2h_stats['total_matches'] * 100) if h2h_stats['total_matches'] > 0 else 0
    
    if player1_winrate > player2_winrate:
        leading = f"🔥 **{player1}** leads with {player1_winrate:.1f}% win rate"
    elif player2_winrate > player1_winrate:
        leading = f"🔥 **{player2}** leads with {player2_winrate:.1f}% win rate"
    else:
        leading = "🤝 **Perfectly tied!**"
    
    embed.add_field(name="Current Leader", value=leading, inline=False)
    
    # Recent matches
    if h2h_stats['recent_matches']:
        recent_text = []
        for match in h2h_stats['recent_matches']:
            date = datetime.fromisoformat(match['date'].replace('Z', '+00:00'))
            recent_text.append(f"`{match['match_id']}` - {match['result']} ({date.strftime('%m/%d')})")
        
        embed.add_field(
            name="Recent Matches",
            value="\n".join(recent_text),
            inline=False
        )
    
    embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
    await ctx.send(embed=embed)

@bot.command(name='leaderboard', aliases=['lb', 'top'])
async def show_leaderboard(ctx, leaderboard_type='matches'):
    """Show leaderboards by different criteria. Usage: !lf leaderboard [matches/wins/losses/winrate]"""
    
    # Map user input to database columns
    type_mapping = {
        'matches': 'total_matches',
        'wins': 'wins', 
        'losses': 'losses',
        'winrate': 'win_rate',
        'wr': 'win_rate'
    }
    
    if leaderboard_type.lower() not in type_mapping:
        await ctx.send("❌ Invalid leaderboard type. Use: `matches`, `wins`, `losses`, or `winrate`")
        return
    
    order_by = type_mapping[leaderboard_type.lower()]
    min_games = 3 if leaderboard_type.lower() in ['winrate', 'wr'] else 1
    
    leaderboard_data, found = await get_leaderboard(order_by, min_games)
    
    if not found or not leaderboard_data:
        min_text = f" (min {min_games} games)" if min_games > 1 else ""
        await ctx.send(f"❌ No leaderboard data found{min_text}.")
        return
    
    # Set title based on type
    titles = {
        'total_matches': 'Most Matches Played',
        'wins': 'Most Wins', 
        'losses': 'Most Losses',
        'win_rate': 'Highest Win Rate'
    }
    
    embed = discord.Embed(
        title=f"🏆 Leaderboard - {titles[order_by]}",
        description=f"*Minimum {min_games} games required*" if min_games > 1 else "",
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
        
        # Recent form
        recent_form = player.get('recent_form', '')
        form_display = f" [{recent_form}]" if recent_form else ""
        
        # Use the helper function to get display name
        display_name = get_display_name(player)
        
        # Different display based on leaderboard type
        if order_by == 'total_matches':
            main_stat = f"{player[order_by]} games"
        elif order_by == 'win_rate':
            main_stat = f"{player[order_by]}% {wr_emoji}"
        else:
            main_stat = f"{player[order_by]} {order_by}"
        
        leaderboard_lines.append(
            f"{position} **{display_name}** - {main_stat}\n"
            f"    ↳ {player['wins']}W-{player['losses']}L ({player['total_matches']} games){form_display}"
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
@bot.command(name='merge')
async def merge_players(ctx, old_player=None, new_player=None):
    """Merge two player accounts. Usage: !lf merge [old_player] [new_player]"""
    if not await check_moderator_permission(ctx):
        return
    
    if not old_player or not new_player:
        await ctx.send("❌ Usage: `!lf merge [old_player] [new_player]`\nExample: `!lf merge oldname newname`")
        return
    
    success, message = await merge_player_accounts(old_player, new_player)
    
    if success:
        embed = discord.Embed(
            title="🔄 Players Merged Successfully!",
            description=message,
            color=GREEN_COLOR
        )
        embed.add_field(name="Merged by", value=ctx.author.display_name, inline=True)
        embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ {message}")

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

@bot.command(name='teammates')
async def show_teammates(ctx, *, player_name=None):
    """Show who a player has played with most often. Usage: !lf teammates [player_name]"""
    if not player_name or player_name.lower() == 'me':
        player_name = ctx.author.display_name
    
    teammates, found = await get_most_played_with(player_name)
    
    if not found or not teammates:
        await ctx.send(f"❌ No teammate data found for **{player_name}**.")
        return
    
    embed = discord.Embed(
        title=f"🤝 Most Played With: {player_name}",
        description="Players you've teamed up with most often",
        color=GREEN_COLOR
    )
    
    # Top teammates
    teammate_lines = []
    for idx, (teammate, count) in enumerate(teammates):
        if idx == 0:
            position = "🥇"
        elif idx == 1:
            position = "🥈"
        elif idx == 2:
            position = "🥉"
        else:
            position = f"`{idx+1}.`"
        
        teammate_lines.append(f"{position} **{teammate}** - {count} games together")
    
    # Split into two columns if more than 5 teammates
    if len(teammate_lines) <= 5:
        embed.add_field(
            name="Top Teammates",
            value="\n".join(teammate_lines),
            inline=False
        )
    else:
        mid_point = len(teammate_lines) // 2
        embed.add_field(
            name="Top Teammates (1-5)",
            value="\n".join(teammate_lines[:mid_point]),
            inline=True
        )
        embed.add_field(
            name="More Teammates (6-10)",
            value="\n".join(teammate_lines[mid_point:]),
            inline=True
        )
    
    embed.set_footer(text=f"Visit {WEBSITE_URL} for more League of Flex features!")
    await ctx.send(embed=embed)


def convert_hashtag_to_dash(name):
    """Convert hashtag format to OP.GG dash format (e.g., 4444#He11 -> 4444-he11)."""
    if '#' in name:
        parts = name.split('#', 1)  # Split on first hashtag only
        if len(parts) == 2:
            base_name = parts[0].strip()
            hashtag_part = parts[1].strip().lower()  # Convert hashtag to lowercase
            return f"{base_name}-{hashtag_part}"
    return name

def parse_summoner_names(text):
    """Parse summoner names from text, handling quotes and hashtags."""
    names = []
    current_name = ""
    in_quotes = False
    i = 0
    
    while i < len(text):
        char = text[i]
        
        if char == '"' and not in_quotes:
            # Start of quoted name
            in_quotes = True
        elif char == '"' and in_quotes:
            # End of quoted name
            in_quotes = False
            if current_name.strip():
                # Convert hashtag to dash format for OP.GG
                clean_name = convert_hashtag_to_dash(current_name.strip())
                if clean_name:
                    names.append(clean_name)
            current_name = ""
        elif char == ' ' and not in_quotes:
            # Space outside quotes - end of current name
            if current_name.strip():
                # Convert hashtag to dash format for OP.GG
                clean_name = convert_hashtag_to_dash(current_name.strip())
                if clean_name:
                    names.append(clean_name)
            current_name = ""
        else:
            # Regular character
            current_name += char
        
        i += 1
    
    # Handle last name if any
    if current_name.strip():
        clean_name = convert_hashtag_to_dash(current_name.strip())
        if clean_name:
            names.append(clean_name)
    
    return names

def parse_summoner_names_for_multi(text):
    """Parse summoner names for multi-search, preserving hashtags."""
    names = []
    current_name = ""
    in_quotes = False
    i = 0
    
    while i < len(text):
        char = text[i]
        
        if char == '"' and not in_quotes:
            # Start of quoted name
            in_quotes = True
        elif char == '"' and in_quotes:
            # End of quoted name
            in_quotes = False
            if current_name.strip():
                # Keep hashtags for multi-search
                names.append(current_name.strip())
            current_name = ""
        elif char == ' ' and not in_quotes:
            # Space outside quotes - end of current name
            if current_name.strip():
                # Keep hashtags for multi-search
                names.append(current_name.strip())
            current_name = ""
        else:
            # Regular character
            current_name += char
        
        i += 1
    
    # Handle last name if any
    if current_name.strip():
        names.append(current_name.strip())
    
    return names

def parse_server_and_names(input_text, for_multi_search=False):
    """Parse server and summoner names from input text, handling quotes and hashtags."""
    if not input_text:
        return 'na', []
    
    # Check for SERVER= syntax
    server_match = re.match(r'SERVER=(\w+)\s+(.+)', input_text.strip())
    if server_match:
        server_code = server_match.group(1).upper()
        names_text = server_match.group(2)
        
        # Validate server
        if server_code in OPGG_SERVERS:
            server = OPGG_SERVERS[server_code]
            if for_multi_search:
                names = parse_summoner_names_for_multi(names_text)
            else:
                names = parse_summoner_names(names_text)
            return server, names
        else:
            # Invalid server, treat whole thing as names
            if for_multi_search:
                names = parse_summoner_names_for_multi(input_text)
            else:
                names = parse_summoner_names(input_text)
            return 'na', names
    else:
        # No server specified, use NA as default
        if for_multi_search:
            names = parse_summoner_names_for_multi(input_text)
        else:
            names = parse_summoner_names(input_text)
        return 'na', names

@bot.command(name='riot')
async def riot_stats(ctx, *, input_text=None):
    """Show OP.GG stats for League players. Usage: !lf riot [names...] or !lf riot SERVER=KR [names...]"""
    if not input_text:
        server_list = ", ".join(OPGG_SERVERS.keys())
        await ctx.send(f"❌ Usage: `!lf riot [summoner_name]` or `!lf riot SERVER=KR [summoner_name]`\n"
                      f"**Examples:**\n"
                      f"• `!lf riot Faker`\n"
                      f"• `!lf riot \"TSM Bjergsen\"`\n"
                      f"• `!lf riot 4444#He11` (becomes 4444-he11)\n"
                      f"• `!lf riot SERVER=KR Faker`\n"
                      f"• `!lf riot SERVER=EUW Caps Perkz \"G2 Jankos\"`\n"
                      f"• `!lf riot SERVER=NA \"TSM Bjergsen#NA1\" \"C9 Blaber\"`\n\n"
                      f"**📝 Name Format Tips:**\n"
                      f"• Use quotes for names with spaces: `\"TSM Bjergsen\"`\n"
                      f"• Hashtags become dashes: `4444#He11` → `4444-he11`\n"
                      f"• Mix quoted and unquoted names: `Faker \"TSM Bjergsen\" Caps`\n\n"
                      f"**Available servers:** {server_list}")
        return
    
    # Check if this is a multi-search first
    temp_server, temp_names = parse_server_and_names(input_text, for_multi_search=True)
    is_multi_search = len(temp_names) > 1
    
    if is_multi_search:
        # Multi-search - preserve hashtags
        server, summoner_names = parse_server_and_names(input_text, for_multi_search=True)
        
        if len(summoner_names) > 10:
            await ctx.send("❌ Maximum 10 players allowed for multi-search.")
            return
        
        # Clean and encode summoner names - remove spaces but preserve hashtags
        clean_names = [name.replace(" ", "") for name in summoner_names]
        encoded_names = [urllib.parse.quote(name) for name in clean_names]
        
        # Create OP.GG multi-search URL with properly encoded commas
        names_param = "%2C".join(encoded_names)
        opgg_url = f"https://{server}.op.gg/multisearch/{server}?summoners={names_param}"
        
        embed = discord.Embed(
            title=f"📊 Multi-Player Stats Lookup",
            description=f"Comparing {len(summoner_names)} players on OP.GG",
            color=PURPLE_COLOR
        )
        
        # Display the players being searched
        player_list = "\n".join([f"• **{name}**" for name in summoner_names])
        embed.add_field(
            name=f"🎮 Players ({len(summoner_names)})",
            value=player_list,
            inline=True
        )
        
        embed.add_field(
            name="📈 Multi-Search Features:",
            value="• Side-by-side comparison\n• Rank comparison\n• Recent performance\n• Head-to-head analysis",
            inline=True
        )
        
        # Show server info
        server_display = next((k for k, v in OPGG_SERVERS.items() if v == server), server.upper())
        embed.add_field(
            name="🌍 Server:",
            value=f"**{server_display}**",
            inline=True
        )
        
        embed.add_field(
            name="🔗 View Comparison",
            value=f"[Compare All Players on OP.GG]({opgg_url})",
            inline=False
        )
        
        embed.set_footer(text=f"Stats powered by OP.GG | {WEBSITE_URL}")
        await ctx.send(embed=embed)
    
    else:
        # Single search - convert hashtags to dashes
        server, summoner_names = parse_server_and_names(input_text, for_multi_search=False)
        
        if not summoner_names:
            await ctx.send("❌ No summoner names provided.")
            return
        
        summoner_name = summoner_names[0]
        # Remove spaces but keep dashes from hashtag conversion
        clean_name = summoner_name.replace(" ", "")
        encoded_name = urllib.parse.quote(clean_name)
        opgg_url = f"https://{server}.op.gg/summoners/{server}/{encoded_name}"
        
        embed = discord.Embed(
            title=f"📊 League Stats: {summoner_name}",
            description=f"Click the link below to view detailed stats on OP.GG",
            color=BLUE_COLOR
        )
        
        embed.add_field(
            name="🔗 OP.GG Profile",
            value=f"[View {summoner_name}'s Stats]({opgg_url})",
            inline=False
        )
        
        embed.add_field(
            name="📈 What you'll find:",
            value="• Rank & LP\n• Recent match history\n• Champion statistics\n• Win rates & KDA",
            inline=True
        )
        
        embed.add_field(
            name="🎮 Recent Games:",
            value="• Last 20 matches\n• Performance trends\n• Champion performance\n• Build analysis",
            inline=True
        )
        
        # Show server info
        server_display = next((k for k, v in OPGG_SERVERS.items() if v == server), server.upper())
        embed.add_field(
            name="🌍 Server:",
            value=f"**{server_display}**",
            inline=True
        )
        
        embed.set_footer(text=f"Stats powered by OP.GG | {WEBSITE_URL}")
        await ctx.send(embed=embed)

@bot.command(name='riot-meta')
async def riot_meta(ctx, server='NA'):
    """Show current meta information from OP.GG. Usage: !lf riot-meta [server]"""
    server = server.upper()
    
    if server not in OPGG_SERVERS:
        server_list = ", ".join(OPGG_SERVERS.keys())
        await ctx.send(f"❌ Invalid server. Available servers: {server_list}")
        return
    
    server_code = OPGG_SERVERS[server]
    
    embed = discord.Embed(
        title=f"📊 League Meta Information - {server}",
        description="Current patch meta, tier lists, and analytics",
        color=GREEN_COLOR
    )
    
    # Meta links - OP.GG uses region parameter format
    champions_url = f"https://op.gg/lol/champions?region={server_code}"
    statistics_url = f"https://op.gg/lol/statistics/champions?region={server_code}"
    
    embed.add_field(
        name="🏆 Champion Tier List",
        value=f"[View Current Tier List]({champions_url})\n*Win rates, pick rates, ban rates by role*",
        inline=False
    )
    
    embed.add_field(
        name="📈 Champion Statistics",
        value=f"[Detailed Champion Analytics]({statistics_url})\n*Performance trends, builds, runes*",
        inline=False
    )
    
    embed.add_field(
        name="🎮 What you'll find:",
        value="• Current patch tier lists\n• Champion win/pick/ban rates\n• Role-specific meta\n• Build recommendations\n• Rune optimization",
        inline=True
    )
    
    embed.add_field(
        name="📊 Analytics Available:",
        value="• Performance by rank\n• Regional differences\n• Patch trends\n• Pro play influence\n• Counter matchups",
        inline=True
    )
    
    embed.set_footer(text=f"Meta data powered by OP.GG | {WEBSITE_URL}")
    await ctx.send(embed=embed)

@bot.command(name='riot-patch')
async def riot_patch(ctx):
    """Show current patch notes and updates."""
    
    embed = discord.Embed(
        title="🔄 League of Legends Patch Information",
        description="Latest patch notes and game updates",
        color=ORANGE_COLOR
    )
    
    # OP.GG doesn't host patch notes, but we can link to official sources
    patch_notes_url = "https://www.leagueoflegends.com/en-us/news/tags/patch-notes/"
    surrender_url = "https://www.surrenderat20.net/"
    opgg_news_url = "https://op.gg/news"
    
    embed.add_field(
        name="📋 Official Patch Notes",
        value=f"[Riot Games Patch Notes]({patch_notes_url})\n*Official champion changes, item updates, bug fixes*",
        inline=False
    )
    
    embed.add_field(
        name="📰 Surrender@20",
        value=f"[PBE Updates & News]({surrender_url})\n*Early patch previews, upcoming changes*",
        inline=False
    )
    
    embed.add_field(
        name="📊 OP.GG News",
        value=f"[Meta Impact Analysis]({opgg_news_url})\n*How patches affect the meta and statistics*",
        inline=False
    )
    
    embed.add_field(
        name="🎯 Patch Impact:",
        value="• Champion balance changes\n• Item adjustments\n• New features\n• Bug fixes\n• Meta shifts",
        inline=True
    )
    
    embed.add_field(
        name="📈 Track Changes:",
        value="• Win rate impacts\n• Pick/ban shifts\n• Build adaptations\n• Role meta changes\n• Pro play effects",
        inline=True
    )
    
    embed.set_footer(text=f"Patch info from official sources | {WEBSITE_URL}")
    await ctx.send(embed=embed)

@bot.command(name='riot-esports')
async def riot_esports(ctx, region='WORLD'):
    """Show esports/pro match information. Usage: !lf riot-esports [region]"""
    
    region = region.upper()
    valid_regions = ['WORLD', 'LCS', 'LEC', 'LCK', 'LPL', 'MSI', 'WORLDS']
    
    embed = discord.Embed(
        title=f"🏆 League Esports - {region}",
        description="Professional League of Legends matches and tournaments",
        color=RED_COLOR
    )
    
    # Esports links
    lolesports_url = "https://lolesports.com/"
    opgg_esports_url = "https://op.gg/esports"
    
    embed.add_field(
        name="🎮 Official Esports",
        value=f"[LoL Esports Hub]({lolesports_url})\n*Official matches, schedules, standings*",
        inline=False
    )
    
    embed.add_field(
        name="📊 Esports Analytics",
        value=f"[OP.GG Esports Stats]({opgg_esports_url})\n*Pro player stats, team performance, meta analysis*",
        inline=False
    )
    
    embed.add_field(
        name="🏟️ Available Leagues:",
        value="• **LCS** (North America)\n• **LEC** (Europe)\n• **LCK** (Korea)\n• **LPL** (China)\n• **MSI** (Mid-Season)\n• **WORLDS** (World Championship)",
        inline=True
    )
    
    embed.add_field(
        name="📈 Pro Analytics:",
        value="• Player performance\n• Team statistics\n• Champion priority\n• Draft analysis\n• Tournament results",
        inline=True
    )
    
    embed.set_footer(text=f"Esports data from official sources | {WEBSITE_URL}")
    await ctx.send(embed=embed)

# Run the bot
bot.run(DISCORD_TOKEN)
    
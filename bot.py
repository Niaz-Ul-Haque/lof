import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from itertools import combinations
import math
import random

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

# Updated Tier Points Mapping
TIER_POINTS = {
    "I": 1.0,     # Iron
    "IB": 2.0,    # Iron-Bronze
    "B": 3.0,     # Bronze
    "BS": 4.0,    # Bronze-Silver
    "S": 5.0,     # Silver
    "SG": 6.5,    # Silver-Gold
    "G": 8.0,     # Gold
    "GP": 9.5,    # Gold-Platinum
    "P": 11.0,    # Platinum
    "PE": 13.0,   # Platinum-Emerald
    "E": 15.0,    # Emerald
    "ED": 17.0,   # Emerald-Diamond
    "D": 19.0,    # Diamond
    "DM": 21.5,   # Diamond-Master
    "M": 24.0,    # Master
    "GM": 27.0,   # Grandmaster
    "C": 30.0     # Challenger
}

player_pool = []
tournaments = {}

class Tournament:
    def __init__(self, name, teams, commentators=None, staffs=None):
        self.name = name
        self.teams = teams  # List of teams (each team is a dict with 'name' and 'players')
        self.matches = []   # List of matches in the brackets
        self.commentators = commentators or []  # Max 2 commentators
        self.staffs = staffs or []  # Additional staff members
        self.create_brackets()

    def create_brackets(self):
        """Create initial matches based on teams, balancing first matches as much as possible."""
        team_scores = [(idx, sum(player[2] for player in team['players'])) for idx, team in enumerate(self.teams)]
        team_scores.sort(key=lambda x: x[1])
        num_teams = len(self.teams)
        self.matches = []
        total_rounds = math.ceil(math.log2(num_teams))
        bracket_size = 2 ** total_rounds
        byes = bracket_size - num_teams
        match_num = 1
        for idx in range(0, num_teams, 2):
            team1_idx = team_scores[idx][0]
            team2_idx = team_scores[idx + 1][0] if idx + 1 < num_teams else None
            self.matches.append({
                'round': 1,
                'match_num': match_num,
                'team1': team1_idx,
                'team2': team2_idx,
                'winner': None
            })
            match_num += 1

    def report_match_result(self, match_num, winning_team_idx):
        """Update the match result and advance the tournament if necessary."""
        for match in self.matches:
            if match['match_num'] == match_num and match['round'] == self.get_current_round():
                match['winner'] = winning_team_idx
                break
        else:
            return False  # Match not found

        # Proceed to next round if all matches in the current round are completed
        if all(m['winner'] is not None for m in self.matches if m['round'] == self.get_current_round()):
            self.advance_to_next_round()
        return True

    def get_current_round(self):
        """Determine the current round based on matches."""
        rounds = [m['round'] for m in self.matches]
        return max(rounds) if rounds else 0

    def advance_to_next_round(self):
        """Create matches for the next round based on winners of the current round."""
        winners = [m['winner'] for m in self.matches if m['round'] == self.get_current_round()]
        next_round = self.get_current_round() + 1
        num_winners = len(winners)
        new_matches = []
        match_num = 1
        for i in range(0, num_winners, 2):
            team1_idx = winners[i]
            if i + 1 < num_winners:
                team2_idx = winners[i + 1]
            else:
                team2_idx = None
            new_matches.append({
                'round': next_round,
                'match_num': match_num,
                'team1': team1_idx,
                'team2': team2_idx,
                'winner': None
            })
            match_num += 1
        self.matches.extend(new_matches)

    def display_brackets(self):
        """Return an embed representing the current brackets."""
        embed = discord.Embed(title=f"Tournament Brackets: {self.name}", color=0x00ff00)
        rounds = set(m['round'] for m in self.matches)
        for rnd in sorted(rounds):
            matches_in_round = [m for m in self.matches if m['round'] == rnd]
            value = ""
            for m in matches_in_round:
                team1_name = f"Team {m['team1'] + 1}: {self.teams[m['team1']]['name']}" if m['team1'] is not None else "TBD"
                team2_name = f"Team {m['team2'] + 1}: {self.teams[m['team2']]['name']}" if m['team2'] is not None else "Bye"
                winner_name = f"Team {m['winner'] + 1}: {self.teams[m['winner']]['name']}" if m['winner'] is not None else "In Progress"
                value += f"Match {m['match_num']}: {team1_name} vs {team2_name} - Winner: {winner_name}\n"
            embed.add_field(name=f"Round {rnd}", value=value, inline=False)
        return embed

    def update_team_name(self, team_number, new_name):
        """Update the name of a team."""
        if 0 <= team_number < len(self.teams):
            self.teams[team_number]['name'] = new_name
            return True
        return False

    def clear_all(self):
        """Clear all data from the tournament."""
        self.teams.clear()
        self.matches.clear()
        self.commentators.clear()
        self.staffs.clear()

# Utility Functions
def create_balanced_teams(players):
    """Create balanced 5v5 teams with fixed names 'Team 1' and 'Team 2'."""
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

    embed.add_field(name="Team 1", value=team1_info, inline=True)
    embed.add_field(name="Team 2", value=team2_info, inline=True)
    embed.add_field(name="Balance Info", value=f"Point Difference: {best_diff:.1f} points", inline=False)

    return embed

# Commands
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='help')
async def help_command(ctx):
    """Display help for all commands."""
    embed = discord.Embed(title="League of Legends Team Balancer Help", color=0x00ff00)
    embed.add_field(name="Available Commands", value=(
        "1. `#help`\n   - Show this help message\n\n"
        "2. `#leagueofflex join [name] [rank]`\n   - Add a player to the matchmaking pool\n\n"
        "3. `#leagueofflex team [player1 rank1 ...]`\n   - Generate balanced 5v5 teams\n\n"
        "4. `#leagueofflex tiers`\n   - Show all ranks and their associated point values\n\n"
        "5. `#leagueofflex tournament create [name] [player1 rank1 ...]`\n   - Create a tournament\n\n"
        "6. `#leagueofflex tournament help [name]`\n   - Show detailed tournament info\n\n"
        "7. `#leagueofflex tournament players [name]`\n   - List all players in a tournament\n\n"
        "8. `#leagueofflex tournament brackets [name]`\n   - Show tournament brackets\n\n"
        "9. `#leagueofflex tournament update_team [name] [team_number] [new_name]`\n   - Update team name\n\n"
        "10. `#leagueofflex clear`\n   - Clear all data (tournaments, players, matches)"
    ), inline=False)
    embed.add_field(name="Rank Info", value="Ranks: I, IB, B, BS, S, SG, G, GP, P, PE, E, ED, D, DM, M, GM, C", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='tiers')
async def tiers_command(ctx):
    """Display the tier system and associated points."""
    embed = discord.Embed(title="League of Legends Rank Point Values", color=0x00ff00)
    for tier, points in TIER_POINTS.items():
        embed.add_field(name=tier, value=f"{points} points", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='clear')
async def clear_command(ctx):
    """Clear all tournaments, teams, players, and matches."""
    player_pool.clear()
    tournaments.clear()
    await ctx.send("All data cleared: tournaments, teams, players, and matches.")

@bot.command(name='tournament_help')
async def tournament_help(ctx, tournament_name=None):
    """Show detailed information about a specific tournament."""
    if not tournament_name:
        await ctx.send("Please specify a tournament name. Example: `#tournament_help [tournament_name]`")
        return

    tournament = tournaments.get(tournament_name)
    if not tournament:
        await ctx.send(f"Tournament '{tournament_name}' not found.")
        return

    # Create an embed to display the information
    embed = discord.Embed(title=f"Tournament: {tournament_name}", color=0x00ff00)

    # Add general information
    embed.add_field(name="Tournament Organizer", value="League of Flex Bot", inline=False)
    embed.add_field(name="Number of Teams", value=len(tournament.teams), inline=True)

    # Add staff and commentators
    staff_names = ", ".join(tournament.staffs) if tournament.staffs else "None"
    commentator_names = ", ".join(tournament.commentators) if tournament.commentators else "None"
    embed.add_field(name="Staff Members", value=staff_names, inline=True)
    embed.add_field(name="Commentators", value=commentator_names, inline=True)

    # Add teams and players
    for idx, team in enumerate(tournament.teams):
        team_name = team['name']
        players_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in team['players']])
        embed.add_field(name=f"Team {idx + 1}: {team_name}", value=players_info, inline=False)

    # Add current match bracket info
    if tournament.matches:
        brackets = "\n".join([
            f"Match {match['match_num']}: {tournament.teams[match['team1']]['name']} vs "
            f"{tournament.teams[match['team2']]['name'] if match['team2'] is not None else 'Bye'}"
            for match in tournament.matches
        ])
        embed.add_field(name="Current Brackets", value=brackets, inline=False)
    else:
        embed.add_field(name="Current Brackets", value="No matches available yet.", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='tournament_players')
async def tournament_players(ctx, tournament_name=None):
    """Show all players in a tournament, sorted by their rank tier."""
    if not tournament_name:
        await ctx.send("Please specify a tournament name. Example: `#tournament_players [tournament_name]`")
        return

    tournament = tournaments.get(tournament_name)
    if not tournament:
        await ctx.send(f"Tournament '{tournament_name}' not found.")
        return

    # Gather all players from all teams
    all_players = []
    for team in tournament.teams:
        all_players.extend(team['players'])

    # Sort players by their rank points
    sorted_players = sorted(all_players, key=lambda x: TIER_POINTS[x[1]])

    # Format the output
    embed = discord.Embed(title=f"Players in Tournament: {tournament_name}", color=0x00ff00)
    rank_info = "\n".join([f"{player[0]} - {player[1]} ({TIER_POINTS[player[1]]} pts)" for player in sorted_players])

    if rank_info:
        embed.add_field(name="Players (Sorted by Rank)", value=rank_info, inline=False)
    else:
        embed.add_field(name="Players", value="No players found.", inline=False)

    await ctx.send(embed=embed)

# Run the bot
bot.run(DISCORD_TOKEN)

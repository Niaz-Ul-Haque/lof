import discord
from discord.ext import commands
from discord.ui import Button, View, Select
import os
from dotenv import load_dotenv
from itertools import combinations
import math
import random
import json
import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('tournament_bot')

# Load environment variables
load_dotenv()

# Bot configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN not found in environment variables")

# Initialize bot with explicit intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix='!lf ', intents=intents)

# Updated Tier points mapping
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

# Updated Team Names
TEAM_NAMES = [
    "Sasquatch Squad", "Viking Vandals", "Pirate Pythons", "Ninja Nachos", "Zombie Zebras",
    "Wacky Wombats", "Grumpy Geese", "Mad Hooligans", "Crying Cowboys", "Reckless Rhinos",
    "Bumbling Buccaneers", "Sneaky Sasquatches", "Crazy Cacti", "Drunken Dragons", "Grouchy Gnomes",
    "Laughing Llamas", "Pouting Penguins", "Silly Sharks", "Angry Alpacas", "Mischievous Monkeys",
    "Furious Ferrets", "Boisterous Bears", "Cantankerous Camels", "Rowdy Raccoons", "Troubled Turtles",
    "Grim Griffins", "Moody Meerkats", "Jaded Jaguars", "Perky Porcupines", "Restless Ravers"
]

# Global state (with proper typing)
player_pool: List[Tuple[str, str, float]] = []
tournaments: Dict[str, 'Tournament'] = {}

@dataclass
class Player:
    name: str
    rank: str
    points: float

    @staticmethod
    def from_input(name: str, rank: str) -> 'Player':
        rank = rank.upper()
        if rank not in TIER_POINTS:
            raise ValueError(f"Invalid rank: {rank}")
        return Player(name=name, rank=rank, points=TIER_POINTS[rank])

class Tournament:
    def __init__(self, name: str, teams: List[Dict], commentators: Optional[List[str]] = None, staff: Optional[List[str]] = None):
        self.name = name
        self.teams = teams
        self.matches = []
        self.commentators = commentators if commentators else []
        self.staff = staff if staff else []
        self.create_brackets()
    
    def save_to_file(self) -> None:
        """Save tournament data to a JSON file."""
        try:
            tournament_data = {
                'name': self.name,
                'teams': self.teams,
                'matches': self.matches,
                'commentators': self.commentators,
                'staff': self.staff
            }
            with open(f'tournament_{self.name}.json', 'w') as f:
                json.dump(tournament_data, f)
        except Exception as e:
            logger.error(f"Failed to save tournament data: {e}")
            raise

    @classmethod
    def load_from_file(cls, name: str) -> 'Tournament':
        """Load tournament data from a JSON file."""
        try:
            with open(f'tournament_{name}.json', 'r') as f:
                data = json.load(f)
                return cls(
                    name=data['name'],
                    teams=data['teams'],
                    commentators=data['commentators'],
                    staff=data['staff']
                )
        except FileNotFoundError:
            logger.error(f"Tournament file not found: {name}")
            raise
        except Exception as e:
            logger.error(f"Failed to load tournament data: {e}")
            raise

    def create_brackets(self) -> None:
        """Create initial matches based on teams, balancing first matches."""
        try:
            team_scores = [(idx, sum(player[2] for player in team['players'])) 
                          for idx, team in enumerate(self.teams)]
            team_scores.sort(key=lambda x: x[1])
            num_teams = len(self.teams)
            
            # Calculate number of rounds needed
            total_rounds = math.ceil(math.log2(num_teams))
            bracket_size = 2 ** total_rounds
            
            # Create initial matches
            match_num = 1
            for idx in range(0, num_teams, 2):
                self.matches.append({
                    'round': 1,
                    'match_num': match_num,
                    'team1': team_scores[idx][0],
                    'team2': team_scores[idx + 1][0] if idx + 1 < num_teams else None,
                    'winner': None
                })
                match_num += 1
        except Exception as e:
            logger.error(f"Error creating brackets: {e}")
            raise

    def report_match_result(self, match_num: int, winning_team_idx: int) -> bool:
        """Update match result and advance tournament if necessary."""
        try:
            current_round = self.get_current_round()
            match = next((m for m in self.matches 
                         if m['match_num'] == match_num and m['round'] == current_round), None)
            
            if not match:
                return False
                
            match['winner'] = winning_team_idx
            
            # Check if round is complete
            if all(m['winner'] is not None 
                   for m in self.matches if m['round'] == current_round):
                self.advance_to_next_round()
            
            self.save_to_file()  # Save after updating
            return True
        except Exception as e:
            logger.error(f"Error reporting match result: {e}")
            return False

    def get_current_round(self) -> int:
        """Determine the current round based on matches."""
        return max((m['round'] for m in self.matches), default=0)

    def advance_to_next_round(self) -> None:
        """Create matches for the next round based on winners."""
        try:
            current_round = self.get_current_round()
            winners = [m['winner'] for m in self.matches 
                      if m['round'] == current_round]
            
            next_round = current_round + 1
            match_num = 1
            
            new_matches = []
            for i in range(0, len(winners), 2):
                new_matches.append({
                    'round': next_round,
                    'match_num': match_num,
                    'team1': winners[i],
                    'team2': winners[i + 1] if i + 1 < len(winners) else None,
                    'winner': None
                })
                match_num += 1
                
            self.matches.extend(new_matches)
            self.save_to_file()  # Save after updating
        except Exception as e:
            logger.error(f"Error advancing tournament: {e}")
            raise

    def display_brackets(self) -> discord.Embed:
        """Return an embed representing the current brackets."""
        try:
            embed = discord.Embed(
                title=f"Tournament Brackets: {self.name}", 
                color=0x00ff00
            )
            
            rounds = sorted(set(m['round'] for m in self.matches))
            for rnd in rounds:
                matches_in_round = [m for m in self.matches if m['round'] == rnd]
                value = ""
                
                for m in matches_in_round:
                    team1_name = (f"Team {m['team1'] + 1}: {self.teams[m['team1']]['name']}" 
                                if m['team1'] is not None else "TBD")
                    team2_name = (f"Team {m['team2'] + 1}: {self.teams[m['team2']]['name']}" 
                                if m['team2'] is not None else "Bye")
                    winner_name = (f"Team {m['winner'] + 1}: {self.teams[m['winner']]['name']}" 
                                 if m['winner'] is not None else "In Progress")
                    
                    value += f"Match {m['match_num']}: {team1_name} vs {team2_name} - Winner: {winner_name}\n"
                
                embed.add_field(name=f"Round {rnd}", value=value, inline=False)
            
            return embed
        except Exception as e:
            logger.error(f"Error displaying brackets: {e}")
            raise

    def update_member(self, team_number: int, old_member_name: str, 
                     new_member_name: str, new_member_rank: str) -> bool:
        """Update a member in a team."""
        try:
            team_idx = team_number - 1
            if not 0 <= team_idx < len(self.teams):
                return False
                
            team = self.teams[team_idx]['players']
            for idx, player in enumerate(team):
                if player[0].lower() == old_member_name.lower():
                    if new_member_rank.upper() not in TIER_POINTS:
                        return False
                    team[idx] = (new_member_name, 
                               new_member_rank.upper(), 
                               TIER_POINTS[new_member_rank.upper()])
                    self.save_to_file()  # Save after updating
                    return True
            return False
        except Exception as e:
            logger.error(f"Error updating member: {e}")
            return False

    def update_team_name(self, team_number: int, new_name: str) -> bool:
        """Update the name of a team."""
        try:
            team_idx = team_number - 1
            if not 0 <= team_idx < len(self.teams):
                return False
            self.teams[team_idx]['name'] = new_name
            self.save_to_file()  # Save after updating
            return True
        except Exception as e:
            logger.error(f"Error updating team name: {e}")
            return False

class TeamConfirmationView(View):
    def __init__(self, teams: List[Dict], original_players: List[Tuple[str, str, float]]):
        super().__init__(timeout=60)
        self.teams = teams
        self.original_players = original_players

    @discord.ui.button(label="Confirm Teams", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="Teams Confirmed!", 
            description="Teams have been successfully confirmed.", 
            color=0x00ff00
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="Regenerate Teams", style=discord.ButtonStyle.red)
    async def regenerate(self, interaction: discord.Interaction, button: Button):
        embed, view = create_balanced_teams(self.original_players)
        await interaction.response.edit_message(embed=embed, view=view)
        self.stop()

# Command error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing required argument: {error.param}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"Invalid argument provided: {str(error)}")
    else:
        logger.error(f"Command error: {error}")
        await ctx.send(f"An error occurred: {str(error)}")

# Bot event handlers
@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')

# Helper functions
def format_tier_points() -> List[str]:
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

    return [
        f"{tier_name}: {' | '.join(f'{rank}: {TIER_POINTS[rank]}' for rank in ranks)}"
        for tier_name, ranks in tiers.items()
    ]

def create_balanced_teams(players: List[Tuple[str, str, float]]) -> Tuple[discord.Embed, TeamConfirmationView]:
    """Create balanced 5v5 teams from a list of players."""
    try:
        if len(players) != 10:
            raise ValueError("Exactly 10 players required for team balancing")

        best_diff = float('inf')
        best_teams = None

        for team1_indices in combinations(range(10), 5):
            team1 = [players[i] for i in team1_indices]
            team2 = [players[i] for i in range(10) if i not in team1_indices]

            team1_score = sum(player[2] for player in team1)
            team2_score = sum(player[2] for player in team2)

            diff = abs(team1_score - team2_score)
            if diff < best_diff:
                best_diff = diff
                best_teams = (team1, team2)

        team1_name = "Team 1"
        team2_name = "Team 2"

        embed = discord.Embed(title="Balanced Teams (5v5)", color=0x00ff00)

        team1_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in best_teams[0]])
        team2_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in best_teams[1]])

        embed.add_field(name=team1_name, value=team1_info, inline=True)
        embed.add_field(name=team2_name, value=team2_info, inline=True)
        embed.add_field(name="Balance Info", value=f"Point Difference: {best_diff:.1f} points", inline=False)

        view = TeamConfirmationView(teams=[team1_name, team2_name], original_players=players)
        return embed, view
    except Exception as e:
        logger.error(f"Error creating balanced teams: {e}")
        raise

def create_balanced_tournament_teams(players: List[Tuple[str, str, float]]) -> List[Dict]:
    """Create balanced teams for a tournament."""
    try:
        team_size = 5
        num_teams = len(players) // team_size
        
        if not num_teams:
            raise ValueError("Not enough players to form teams")
            
        if num_teams > len(TEAM_NAMES):
            raise ValueError("Not enough team names available")

        teams = []
        team_points = []
        available_team_names = TEAM_NAMES.copy()
        random.shuffle(available_team_names)

        # Initialize teams
        for _ in range(num_teams):
            teams.append({'name': available_team_names.pop(), 'players': []})
            team_points.append(0)

        # Sort players by skill and distribute
        players_sorted = sorted(players, key=lambda x: x[2], reverse=True)
        for player in players_sorted:
            min_team_idx = team_points.index(min(team_points))
            if len(teams[min_team_idx]['players']) < team_size:
                teams[min_team_idx]['players'].append(player)
                team_points[min_team_idx] += player[2]

        return teams
    except Exception as e:
        logger.error(f"Error creating tournament teams: {e}")
        raise

# Bot commands
@bot.command(name='help')
async def help_command(ctx):
    """Displays the help message with all available commands."""
    embed = discord.Embed(title="League of Legends Team Balancer Help", color=0x00ff00)
    
    commands_info = {
        "Basic Commands": {
            "!lf help": "Shows this help message",
            "!lf tiers": "Shows all tier point values",
            "!lf join [name] [rank]": "Join the player queue for a quick match",
            "!lf team [player1] [rank1] [player2] [rank2] ...": "Creates balanced 5v5 teams"
        },
        "Tournament Commands": {
            "!lf tournament create [name] [players...]": "Create a new tournament",
            "!lf tournament brackets [name]": "Display tournament brackets",
            "!lf tournament teams [name]": "Display tournament teams",
            "!lf tournament report [name] [match] [winner]": "Report match results",
            "!lf tournament update_member [details...]": "Update team member",
            "!lf tournament update_name [details...]": "Update team name",
            "!lf tournament add_commentator [details...]": "Add commentator",
            "!lf tournament remove_commentator [details...]": "Remove commentator",
            "!lf tournament add_staff [details...]": "Add staff member",
            "!lf tournament remove_staff [details...]": "Remove staff member"
        },
        "Management Commands": {
            "!lf clear players": "Clear player queue",
            "!lf clear teams": "Clear all teams",
            "!lf clear tournaments": "Clear all tournaments",
            "!lf clear matches": "Clear all matches",
            "!lf clear all": "Clear all data"
        }
    }

    for category, commands in commands_info.items():
        commands_text = "\n".join([f"{cmd}: {desc}" for cmd, desc in commands.items()])
        embed.add_field(name=category, value=commands_text, inline=False)

    # Add valid ranks information
    embed.add_field(name="Valid Ranks", value="\n".join(format_tier_points()), inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='tiers')
async def tiers_command(ctx):
    """Displays the tier points."""
    embed = discord.Embed(title="League of Legends Rank Point Values", color=0x00ff00)
    for tier_str in format_tier_points():
        name, values = tier_str.split(': ', 1)
        embed.add_field(name=name, value=values, inline=False)
    await ctx.send(embed=embed)

@bot.command(name='join')
async def join_queue(ctx, name: str, rank: str):
    """Allows a player to join the matchmaking queue."""
    try:
        player = Player.from_input(name, rank)
        player_info = (player.name, player.rank, player.points)

        if player_info in player_pool:
            await ctx.send(f"{name} is already in the queue.")
            return

        player_pool.append(player_info)
        await ctx.send(f"{name} joined the queue as {rank}.")

        if len(player_pool) >= 10:
            embed, view = create_balanced_teams(player_pool[:10])
            await ctx.send(embed=embed, view=view)
            del player_pool[:10]
    except ValueError as e:
        await ctx.send(str(e))
    except Exception as e:
        logger.error(f"Error in join queue: {e}")
        await ctx.send("An error occurred while joining the queue.")

@bot.command(name='team')
async def team_balance(ctx, *, input_text: str = None):
    """Creates balanced teams based on provided players and ranks."""
    if not input_text:
        await ctx.send("Please use `!lf help` for command information.")
        return

    try:
        args = input_text.split()
        if len(args) < 20:
            await ctx.send("For team balancing, provide 10 players with their ranks.")
            return

        players = []
        for i in range(0, 20, 2):
            player = Player.from_input(args[i], args[i+1])
            players.append((player.name, player.rank, player.points))

        embed, view = create_balanced_teams(players)
        await ctx.send(embed=embed, view=view)

    except ValueError as e:
        await ctx.send(str(e))
    except Exception as e:
        logger.error(f"Error in team balance: {e}")
        await ctx.send("An error occurred while creating teams.")

# Tournament commands group
@bot.group(name='tournament', invoke_without_command=True)
async def tournament(ctx):
    """Base command for tournament operations."""
    await ctx.send("Please use a subcommand. Use `!lf help` for more information.")

@tournament.command(name='create')
async def tournament_create(ctx, tournament_name: str, *args):
    """Creates a new tournament."""
    try:
        if tournament_name in tournaments:
            await ctx.send(f"Tournament '{tournament_name}' already exists.")
            return

        # Parse players and roles
        players = []
        commentators = []
        staff = []
        i = 0
        
        while i < len(args):
            arg = args[i].lower()
            if arg.startswith(('commentator', 'staff')):
                break
            if i + 1 >= len(args):
                await ctx.send("Invalid player format. Need both name and rank.")
                return
            
            player = Player.from_input(args[i], args[i+1])
            players.append((player.name, player.rank, player.points))
            i += 2

        # Parse commentators and staff
        while i < len(args):
            if args[i].lower().startswith('commentator'):
                if len(commentators) >= 2:
                    await ctx.send("Maximum of 2 commentators allowed.")
                    return
                commentators.append(args[i+1])
                i += 2
            elif args[i].lower().startswith('staff'):
                staff.append(args[i+1])
                i += 2
            else:
                await ctx.send(f"Unrecognized role: {args[i]}")
                return

        teams = create_balanced_tournament_teams(players)
        tournament_obj = Tournament(tournament_name, teams, commentators, staff)
        tournaments[tournament_name] = tournament_obj

        # Show teams
        embed = discord.Embed(title=f"Tournament Teams: {tournament_name}", color=0x00ff00)
        for idx, team in enumerate(teams):
            team_points = sum(player[2] for player in team['players'])
            team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" 
                                 for player in team['players']])
            embed.add_field(
                name=f"Team {idx + 1}: {team['name']} - {team_points:.1f} pts",
                value=team_info,
                inline=False
            )
        
        if commentators:
            embed.add_field(name="Commentators", value=", ".join(commentators), inline=False)
        if staff:
            embed.add_field(name="Staff", value=", ".join(staff), inline=False)
        
        await ctx.send(embed=embed)
        
        # Show brackets
        brackets_embed = tournament_obj.display_brackets()
        await ctx.send(embed=brackets_embed)

    except ValueError as e:
        await ctx.send(str(e))
    except Exception as e:
        logger.error(f"Error creating tournament: {e}")
        await ctx.send("An error occurred while creating the tournament.")

# Additional tournament commands
@tournament.command(name='brackets')
async def tournament_brackets(ctx, tournament_name: str):
    """Displays the brackets of a tournament."""
    try:
        tournament_obj = tournaments.get(tournament_name)
        if not tournament_obj:
            await ctx.send(f"Tournament '{tournament_name}' not found.")
            return
        
        embed = tournament_obj.display_brackets()
        await ctx.send(embed=embed)
    except Exception as e:
        logger.error(f"Error displaying brackets: {e}")
        await ctx.send("An error occurred while displaying the brackets.")

@tournament.command(name='report')
async def tournament_report(ctx, tournament_name: str, match_number: int, winning_team_number: int):
    """Reports the result of a match."""
    try:
        tournament_obj = tournaments.get(tournament_name)
        if not tournament_obj:
            await ctx.send(f"Tournament '{tournament_name}' not found.")
            return

        if winning_team_number < 1 or winning_team_number > len(tournament_obj.teams):
            await ctx.send("Invalid winning team number.")
            return

        winning_team_idx = winning_team_number - 1
        success = tournament_obj.report_match_result(match_number, winning_team_idx)
        
        if success:
            await ctx.send(
                f"Updated match {match_number} with winner Team {winning_team_number}: "
                f"{tournament_obj.teams[winning_team_idx]['name']}."
            )
            embed = tournament_obj.display_brackets()
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"Failed to update match {match_number}.")
    except Exception as e:
        logger.error(f"Error reporting match result: {e}")
        await ctx.send("An error occurred while reporting the match result.")

# Clear commands
@bot.group(name='clear', invoke_without_command=True)
async def clear(ctx):
    """Base command for clearing data."""
    await ctx.send("Please specify what to clear. Options: players, teams, tournaments, matches, all")

@clear.command(name='players')
async def clear_players(ctx):
    """Clears the player queue."""
    try:
        global player_pool
        player_pool = []
        await ctx.send("Player queue has been cleared.")
    except Exception as e:
        logger.error(f"Error clearing players: {e}")
        await ctx.send("An error occurred while clearing players.")

@clear.command(name='teams')
async def clear_teams(ctx):
    """Clears all tournament teams."""
    try:
        for tournament in tournaments.values():
            tournament.teams = []
            tournament.save_to_file()
        await ctx.send("All tournament teams have been cleared.")
    except Exception as e:
        logger.error(f"Error clearing teams: {e}")
        await ctx.send("An error occurred while clearing teams.")

@clear.command(name='tournaments')
async def clear_tournaments(ctx):
    """Clears all tournaments."""
    try:
        global tournaments
        tournaments = {}
        await ctx.send("All tournaments have been cleared.")
    except Exception as e:
        logger.error(f"Error clearing tournaments: {e}")
        await ctx.send("An error occurred while clearing tournaments.")

@clear.command(name='matches')
async def clear_matches(ctx):
    """Clears all matches in all tournaments."""
    try:
        for tournament in tournaments.values():
            tournament.matches = []
            tournament.save_to_file()
        await ctx.send("All matches in all tournaments have been cleared.")
    except Exception as e:
        logger.error(f"Error clearing matches: {e}")
        await ctx.send("An error occurred while clearing matches.")

@clear.command(name='all')
async def clear_all(ctx):
    """Clears all data including players, teams, tournaments, and matches."""
    try:
        global player_pool, tournaments
        player_pool = []
        tournaments = {}
        await ctx.send("All data has been cleared.")
    except Exception as e:
        logger.error(f"Error clearing all data: {e}")
        await ctx.send("An error occurred while clearing data.")

@tournament.command(name='teams')
async def tournament_teams(ctx, tournament_name: str):
    """Displays the teams of a tournament."""
    try:
        tournament_obj = tournaments.get(tournament_name)
        if not tournament_obj:
            await ctx.send(f"Tournament '{tournament_name}' not found.")
            return
            
        embed = discord.Embed(title=f"Tournament Teams: {tournament_name}", color=0x00ff00)
        
        for idx, team in enumerate(tournament_obj.teams):
            team_name = team['name']
            team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" 
                                 for player in team['players']])
            team_points = sum(player[2] for player in team['players'])
            embed.add_field(
                name=f"Team {idx + 1}: {team_name} - {team_points:.1f} pts",
                value=team_info,
                inline=False
            )
            
        if tournament_obj.commentators:
            embed.add_field(name="Commentators", value=", ".join(tournament_obj.commentators), inline=False)
        if tournament_obj.staff:
            embed.add_field(name="Staff", value=", ".join(tournament_obj.staff), inline=False)
            
        await ctx.send(embed=embed)
    except Exception as e:
        logger.error(f"Error displaying teams: {e}")
        await ctx.send("An error occurred while displaying teams.")

@tournament.command(name='update_member')
async def tournament_update_member(ctx, tournament_name: str, team_number: int, 
                                 old_member_name: str, new_member_name: str, new_member_rank: str):
    """Updates a member in a tournament team."""
    try:
        tournament_obj = tournaments.get(tournament_name)
        if not tournament_obj:
            await ctx.send(f"Tournament '{tournament_name}' not found.")
            return

        new_member_rank = new_member_rank.upper()
        if new_member_rank not in TIER_POINTS:
            await ctx.send(f"Invalid rank '{new_member_rank}'. Use `!lf help` to see valid ranks.")
            return

        success = tournament_obj.update_member(team_number, old_member_name, new_member_name, new_member_rank)
        
        if success:
            await ctx.send(f"Updated Team {team_number}: Replaced '{old_member_name}' with '{new_member_name}' ({new_member_rank}).")
            # Display updated teams
            embed = discord.Embed(title=f"Tournament Teams: {tournament_name}", color=0x00ff00)
            for idx, team in enumerate(tournament_obj.teams):
                team_name = team['name']
                team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" 
                                     for player in team['players']])
                team_points = sum(player[2] for player in team['players'])
                embed.add_field(
                    name=f"Team {idx + 1}: {team_name} - {team_points:.1f} pts",
                    value=team_info,
                    inline=False
                )
            await ctx.send(embed=embed)
        else:
            await ctx.send("Failed to update member. Please check the team number and member name.")
    except Exception as e:
        logger.error(f"Error updating member: {e}")
        await ctx.send("An error occurred while updating the team member.")

@tournament.command(name='add_commentator')
async def tournament_add_commentator(ctx, tournament_name: str, commentator_name: str):
    """Adds a commentator to an existing tournament."""
    try:
        tournament_obj = tournaments.get(tournament_name)
        if not tournament_obj:
            await ctx.send(f"Tournament '{tournament_name}' not found.")
            return
            
        if len(tournament_obj.commentators) >= 2:
            await ctx.send("Maximum of 2 commentators allowed.")
            return
            
        if commentator_name in tournament_obj.commentators:
            await ctx.send(f"Commentator '{commentator_name}' is already in the tournament.")
            return
            
        tournament_obj.commentators.append(commentator_name)
        tournament_obj.save_to_file()
        
        await ctx.send(f"Added commentator '{commentator_name}' to tournament '{tournament_name}'.")
        await tournament_teams(ctx, tournament_name)
    except Exception as e:
        logger.error(f"Error adding commentator: {e}")
        await ctx.send("An error occurred while adding the commentator.")

@tournament.command(name='remove_commentator')
async def tournament_remove_commentator(ctx, tournament_name: str, commentator_name: str):
    """Removes a commentator from an existing tournament."""
    try:
        tournament_obj = tournaments.get(tournament_name)
        if not tournament_obj:
            await ctx.send(f"Tournament '{tournament_name}' not found.")
            return
            
        if commentator_name not in tournament_obj.commentators:
            await ctx.send(f"Commentator '{commentator_name}' is not in the tournament.")
            return
            
        tournament_obj.commentators.remove(commentator_name)
        tournament_obj.save_to_file()
        
        await ctx.send(f"Removed commentator '{commentator_name}' from tournament '{tournament_name}'.")
        await tournament_teams(ctx, tournament_name)
    except Exception as e:
        logger.error(f"Error removing commentator: {e}")
        await ctx.send("An error occurred while removing the commentator.")

@tournament.command(name='add_staff')
async def tournament_add_staff(ctx, tournament_name: str, staff_name: str):
    """Adds a staff member to an existing tournament."""
    try:
        tournament_obj = tournaments.get(tournament_name)
        if not tournament_obj:
            await ctx.send(f"Tournament '{tournament_name}' not found.")
            return
            
        if staff_name in tournament_obj.staff:
            await ctx.send(f"Staff member '{staff_name}' is already in the tournament.")
            return
            
        tournament_obj.staff.append(staff_name)
        tournament_obj.save_to_file()
        
        await ctx.send(f"Added staff member '{staff_name}' to tournament '{tournament_name}'.")
        await tournament_teams(ctx, tournament_name)
    except Exception as e:
        logger.error(f"Error adding staff: {e}")
        await ctx.send("An error occurred while adding the staff member.")

@tournament.command(name='remove_staff')
async def tournament_remove_staff(ctx, tournament_name: str, staff_name: str):
    """Removes a staff member from an existing tournament."""
    try:
        tournament_obj = tournaments.get(tournament_name)
        if not tournament_obj:
            await ctx.send(f"Tournament '{tournament_name}' not found.")
            return
            
        if staff_name not in tournament_obj.staff:
            await ctx.send(f"Staff member '{staff_name}' is not in the tournament.")
            return
            
        tournament_obj.staff.remove(staff_name)
        tournament_obj.save_to_file()
        
        await ctx.send(f"Removed staff member '{staff_name}' from tournament '{tournament_name}'.")
        await tournament_teams(ctx, tournament_name)
    except Exception as e:
        logger.error(f"Error removing staff: {e}")
        await ctx.send("An error occurred while removing the staff member.")

@tournament.command(name='update_name')
async def tournament_update_name(ctx, tournament_name: str, team_number: int, new_team_name: str):
    """Updates the name of a team in a tournament."""
    try:
        tournament_obj = tournaments.get(tournament_name)
        if not tournament_obj:
            await ctx.send(f"Tournament '{tournament_name}' not found.")
            return

        success = tournament_obj.update_team_name(team_number, new_team_name)
        
        if success:
            await ctx.send(f"Updated Team {team_number} name to '{new_team_name}'.")
            await tournament_teams(ctx, tournament_name)
        else:
            await ctx.send("Failed to update team name. Please check the team number.")
    except Exception as e:
        logger.error(f"Error updating team name: {e}")
        await ctx.send("An error occurred while updating the team name.")

# Run the bot
if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

# --------------------------------------------
# --------------------------------------------
# --------------------------------------------
# --------------------------------------------
# --------------------------------------------
# --------------------------------------------
# --------------------------------------------
# --------------------------------------------
# --------------------------------------------
# --------------------------------------------


# ### **Comprehensive Test Commands for Your Enhanced Discord Bot**

# To thoroughly test all functionalities of your Discord bot, below are a series of test commands using real professional League of Legends (LoL) player names and a variety of ranks ranging from Iron to Challenger. These commands will help ensure that each feature operates as intended, providing a robust and seamless experience.

# ---

# #### **1. Help Command**

# **Purpose**: Verify that the help command displays all available commands and their descriptions correctly.

# **Command**:
# ```
# !lf help
# ```

# **Expected Response**:
# An embedded message detailing all available commands, their usage, and valid ranks.

# ---

# #### **2. Tiers Command**

# **Purpose**: Check if the bot correctly displays all tier point values.

# **Command**:
# ```
# !lf tiers
# ```

# **Expected Response**:
# An embedded message listing all tiers with their corresponding point values in the updated format.

# ---

# #### **3. Join Queue Commands**

# **Purpose**: Test adding players to the matchmaking queue using the `join` command.

# **Commands**:
# ```
# !lf join Faker M
# !lf join Uzi C
# !lf join Doublelift GM
# !lf join Caps P
# !lf join Bjergsen DM
# !lf join Doinb S
# !lf join Perkz SG
# !lf join Chovy G
# !lf join TheShy G
# !lf join Rookie DM
# !lf join JackeyLove C
# !lf join Caps P
# !lf join ShowMaker DM
# !lf join Khan GM
# !lf join Knight GM
# !lf join Rookie DM
# !lf join Jankos GM
# !lf join Nuguri G
# !lf join Humanoid S
# !lf join Impact DM
# !lf join U.N.O C
# ```

# **Explanation**:
# - Each `join` command adds a professional player to the matchmaking queue with varying ranks.

# **Expected Response**:
# For each `join` command, the bot should acknowledge the player joining the queue. Once the player pool reaches 10 players, the bot will generate balanced teams interactively using buttons for confirmation or regeneration.

# ---

# #### **4. Team Balancing Command**

# **Purpose**: Manually create balanced teams with a specific set of players.

# **Command**:
# ```
# !lf team Faker M Uzi C Doublelift GM Caps P Bjergsen DM Doinb S Perkz SG
# ```

# **Explanation**:
# - This command creates balanced teams using 10 professional players with diverse ranks.

# **Expected Response**:
# An embedded message displaying "Team 1" and "Team 2" with the respective players and their ranks. Interactive buttons for "Confirm Teams" and "Regenerate Teams" should appear below the embed.

# ---

# #### **5. Tournament Creation Command**

# **Purpose**: Create a tournament with 60 players to test the team-making functionality.

# **Note**: Ensure that this command is entered as a single message in Discord. If Discord's character limit is exceeded, consider splitting the command into multiple lines or messages.

# **Command**:
# ```
# !lf tournament create ProLeague2024 \
# Faker M Uzi C Doublelift GM Caps P Bjergsen DM Doinb S Perkz SG Chovy G TheShy G \
# Rookie DM JackeyLove C ShowMaker DM Khan GM Knight GM Jankos GM Nuguri G Humanoid S \
# Impact DM U.N.O C Tiger WM Caps P \
# Faker M Uzi C Doublelift GM Caps P Bjergsen DM Doinb S Perkz SG Chovy G TheShy G \
# Rookie DM JackeyLove C ShowMaker DM Khan GM Knight GM Jankos GM Nuguri G Humanoid S \
# Impact DM U.N.O C Tiger WM Caps P \
# Faker M Uzi C Doublelift GM Caps P Bjergsen DM Doinb S Perkz SG Chovy G TheShy G \
# Rookie DM JackeyLove C ShowMaker DM Khan GM Knight GM Jankos GM Nuguri G Humanoid S \
# Impact DM U.N.O C Tiger WM Caps P \
# Faker M Uzi C Doublelift GM Caps P Bjergsen DM Doinb S Perkz SG Chovy G TheShy G \
# Rookie DM JackeyLove C ShowMaker DM Khan GM Knight GM Jankos GM Nuguri G Humanoid S \
# Impact DM U.N.O C Tiger WM Caps P \
# Commentator1 John Commentator2 Jane Staff1 Alice Staff2 Bob
# ```

# **Explanation**:
# - **Tournament Name**: `ProLeague2024`
# - **Players**: 60 players with varying ranks (M, C, GM, P, DM, S, SG, G)
#   - **Sample Players**: Faker, Uzi, Doublelift, Caps, Bjergsen, Doinb, Perkz, Chovy, TheShy, Rookie, JackeyLove, ShowMaker, Khan, Knight, Jankos, Nuguri, Humanoid, Impact, U.N.O, Tiger, WM
# - **Commentators**: John, Jane
# - **Staff Members**: Alice, Bob

# **Expected Response**:
# 1. An embedded message listing all 12 teams with their respective players and total points.
# 2. A separate embedded message displaying the tournament brackets, showing initial matchups.

# **Note**: Due to the repetition in player names for demonstration purposes, ensure to replace duplicates with unique names or additional pro players to accurately simulate a real tournament.

# ---

# #### **6. Tournament Brackets Display Command**

# **Purpose**: Display the current brackets of a specific tournament.

# **Command**:
# ```
# !lf tournament brackets ProLeague2024
# ```

# **Expected Response**:
# An embedded message showing the tournament brackets, detailing each round, match numbers, team names, and winners (if any matches have been reported).

# ---

# #### **7. Reporting Match Results Command**

# **Purpose**: Report the outcome of a specific match within a tournament.

# **Command**:
# ```
# !lf tournament report ProLeague2024 1 2
# ```

# **Explanation**:
# - `ProLeague2024`: Name of the tournament.
# - `1`: Match number to report.
# - `2`: Winning team number (e.g., Team 2).

# **Expected Response**:
# A confirmation message stating that Match 1 has been updated with the winner as Team 2. The updated tournament brackets should also be displayed, reflecting the new result.

# ---

# #### **8. Displaying Tournament Teams Command**

# **Purpose**: View all teams participating in a specific tournament.

# **Command**:
# ```
# !lf tournament teams ProLeague2024
# ```

# **Expected Response**:
# An embedded message listing all teams in "ProLeague2024" along with their players and total points. If commentators and staff were added during creation, they will also be displayed.

# ---

# #### **9. Updating a Tournament Team Member Command**

# **Purpose**: Update a member within a specific team in a tournament.

# **Command**:
# ```
# !lf tournament update_member ProLeague2024 3 Uzi Faker S
# ```

# **Explanation**:
# - `ProLeague2024`: Name of the tournament.
# - `3`: Team number to update.
# - `Uzi`: Existing member's name to be replaced.
# - `Faker`: New member's name.
# - `S`: New member's rank.

# **Expected Response**:
# A confirmation message indicating that "Uzi" has been replaced with "Faker (S)" in Team 3. An updated list of teams with their players and points should also be displayed.

# ---

# #### **10. Updating a Tournament Team Name Command**

# **Purpose**: Change the name of a specific team within a tournament.

# **Command**:
# ```
# !lf tournament update_name ProLeague2024 5 "Viking Vandals"
# ```

# **Explanation**:
# - `ProLeague2024`: Name of the tournament.
# - `5`: Team number to rename.
# - `"Viking Vandals"`: New team name.

# **Expected Response**:
# A confirmation message stating that Team 5 has been renamed to "Viking Vandals". An updated list of teams with their new names and current players should also be displayed.

# ---

# #### **11. Clearing Data Commands**

# **Purpose**: Test the data clearing functionalities to ensure they work as expected.

# **a. Clear Player Queue**

# **Command**:
# ```
# !lf clear players
# ```

# **Expected Response**:
# A message confirming that the player queue has been cleared.

# ---

# **b. Clear All Tournaments**

# **Command**:
# ```
# !lf clear tournaments
# ```

# **Expected Response**:
# A message confirming that all tournaments have been cleared.

# ---

# **c. Clear All Data**

# **Command**:
# ```
# !lf clear all
# ```

# **Expected Response**:
# A message confirming that all data (players, teams, tournaments, matches) has been cleared.

# ---

# #### **12. Interactive UI Elements Test**

# **Purpose**: Verify that interactive buttons for confirming or regenerating teams are functioning correctly.

# **Steps**:

# 1. **Generate Teams**:
#    - Use the `join` command to add 10 players, triggering the interactive buttons.
#    ```
#    !lf join Faker M
#    !lf join Uzi C
#    !lf join Doublelift GM
#    !lf join Caps P
#    !lf join Bjergsen DM
#    !lf join Doinb S
#    !lf join Perkz SG
#    !lf join Chovy G
#    !lf join TheShy G
#    !lf join Rookie DM
#    ```

# 2. **Interact with Buttons**:
#    - **Confirm Teams**:
#      - Click the "Confirm Teams" button.
#      - **Expected Outcome**: The embed updates to show that teams have been confirmed, and the buttons are removed.

#    - **Regenerate Teams**:
#      - Click the "Regenerate Teams" button.
#      - **Expected Outcome**: The bot regenerates the teams, displays the new team composition, and presents the buttons again for confirmation or further regeneration.

# 3. **Timeout Handling**:
#    - If no interaction occurs within 60 seconds, the buttons will become inactive.
#    - **Expected Outcome**: After timeout, the embed remains as is without interactive elements.

# ---

# ### **Automated Tournament Test Command with 60 Players**

# To streamline the process of creating a tournament with 60 players, use the following command. This command includes 60 players with varying ranks, two commentators, and two staff members. Ensure that you input this as a single message in Discord.

# **Command**:
# ```
# !lf tournament create ProLeague2024 \
# Faker M Uzi C Doublelift GM Caps P Bjergsen DM Doinb S Perkz SG Chovy G TheShy G \
# Rookie DM JackeyLove C ShowMaker DM Khan GM Knight GM Jankos GM Nuguri G Humanoid S \
# Impact DM U.N.O C Tiger WM Caps P Faker M Uzi C Doublelift GM Caps P Bjergsen DM \
# Doinb S Perkz SG Chovy G TheShy G Rookie DM JackeyLove C ShowMaker DM Khan GM \
# Knight GM Jankos GM Nuguri G Humanoid S Impact DM U.N.O C Tiger WM Caps P Faker M \
# Uzi C Doublelift GM Caps P Bjergsen DM Doinb S Perkz SG Chovy G TheShy G Rookie DM \
# JackeyLove C ShowMaker DM Khan GM Knight GM Jankos GM Nuguri G Humanoid S Impact DM \
# U.N.O C Tiger WM Caps P Commentator1 John Commentator2 Jane Staff1 Alice Staff2 Bob
# ```

# **Explanation**:
# - **Tournament Name**: `ProLeague2024`
# - **Players**: 60 players with varying ranks (M, C, GM, P, DM, S, SG, G)
#   - **Sample Players**: Faker, Uzi, Doublelift, Caps, Bjergsen, Doinb, Perkz, Chovy, TheShy, Rookie, JackeyLove, ShowMaker, Khan, Knight, Jankos, Nuguri, Humanoid, Impact, U.N.O, Tiger, WM
# - **Commentators**: John, Jane
# - **Staff Members**: Alice, Bob

# **Steps**:
# 1. **Execute the Command**: Paste the entire command into your Discord server where the bot is active.
# 2. **Bot Response**:
#    - An embedded message listing all 12 teams with their respective players and total points.
#    - A separate embedded message displaying the tournament brackets, showing initial matchups.

# **Note**: Ensure that player names are unique to accurately simulate a real tournament. Replace duplicates with additional pro players if necessary.

# ---

# ### **Additional Test Commands for Comprehensive Coverage**

# To thoroughly test all functionalities, here are additional commands you can use:

# #### **a. Confirm and Regenerate Teams**

# After generating teams using the `join` or `team` commands, interact with the buttons to confirm or regenerate teams.

# **Steps**:

# 1. **Generate Teams**:
#    ```
#    !lf join Faker M
#    !lf join Uzi C
#    !lf join Doublelift GM
#    !lf join Caps P
#    !lf join Bjergsen DM
#    !lf join Doinb S
#    !lf join Perkz SG
#    !lf join Chovy G
#    !lf join TheShy G
#    !lf join Rookie DM
#    ```
#    - This will generate "Team 1" and "Team 2" with the first 10 players.

# 2. **Interact with Buttons**:
#    - **Confirm Teams**: Click the "Confirm Teams" button to finalize the teams.
#    - **Regenerate Teams**: Click the "Regenerate Teams" button to create a new set of balanced teams.

# **Expected Outcomes**:
# - **Confirm Teams**: The embed updates to show confirmation, and the buttons are removed.
# - **Regenerate Teams**: New teams are generated and displayed with the interactive buttons reappearing for further confirmation or regeneration.

# ---

# #### **b. Update a Team Member**

# **Command**:
# ```
# !lf tournament update_member ProLeague2024 3 Uzi Faker S
# ```

# **Explanation**:
# - `ProLeague2024`: Name of the tournament.
# - `3`: Team number to update.
# - `Uzi`: Existing member to be replaced.
# - `Faker`: New member's name.
# - `S`: New member's rank.

# **Expected Response**:
# A confirmation message indicating that "Uzi" has been replaced with "Faker (S)" in Team 3. An updated list of teams with their players and points should also be displayed.

# ---

# #### **c. Update a Team Name**

# **Command**:
# ```
# !lf tournament update_name ProLeague2024 5 "Viking Vandals"
# ```

# **Explanation**:
# - `ProLeague2024`: Name of the tournament.
# - `5`: Team number to rename.
# - `"Viking Vandals"`: New team name.

# **Expected Response**:
# A confirmation message stating that Team 5 has been renamed to "Viking Vandals". An updated list of teams with their new names and current players should also be displayed.

# ---

# #### **d. Clear Specific Data**

# **Commands**:

# - **Clear Player Queue**:
#   ```
#   !lf clear players
#   ```
#   **Expected Response**: "Player queue has been cleared."

# - **Clear All Tournaments**:
#   ```
#   !lf clear tournaments
#   ```
#   **Expected Response**: "All tournaments have been cleared."

# - **Clear All Data**:
#   ```
#   !lf clear all
#   ```
#   **Expected Response**: "All data has been cleared."

# ---

# ### **Verifying Interactive UI Elements**

# To ensure that the interactive UI elements (buttons) are functioning correctly, follow these steps:

# 1. **Generate Teams**:
#    - Use the `join` command to add 10 players, triggering the interactive buttons.
#    ```
#    !lf join Faker M
#    !lf join Uzi C
#    !lf join Doublelift GM
#    !lf join Caps P
#    !lf join Bjergsen DM
#    !lf join Doinb S
#    !lf join Perkz SG
#    !lf join Chovy G
#    !lf join TheShy G
#    !lf join Rookie DM
#    ```

# 2. **Interact with Buttons**:
#    - **Confirm Teams**:
#      - Click the "Confirm Teams" button.
#      - **Expected Outcome**: The embed updates to show that teams have been confirmed, and the buttons disappear.

#    - **Regenerate Teams**:
#      - Click the "Regenerate Teams" button.
#      - **Expected Outcome**: The bot regenerates the teams, displays the new team composition, and presents the buttons again for confirmation or further regeneration.

# 3. **Timeout Handling**:
#    - If no interaction occurs within 60 seconds, the buttons will become inactive.
#    - **Expected Outcome**: After timeout, the embed remains as is without interactive elements.

# ---

# ### **Final Notes**

# By executing the above test commands, you can comprehensively verify that all functionalities of your Discord bot are operational. Ensure that each command behaves as expected and interact with the UI elements to confirm their proper functionality.

# If you encounter any issues or unexpected behaviors during testing, consider reviewing the bot's code for potential bugs or inconsistencies. Additionally, ensure that the bot has the necessary permissions in your Discord server to execute commands and interact with users effectively.

# Feel free to reach out if you need further assistance or encounter any challenges during testing!
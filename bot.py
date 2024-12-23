import discord
from discord.ext import commands
from discord.ui import Button, View, Select
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
bot = commands.Bot(command_prefix='!lf ', intents=intents, help_command=None)

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

player_pool = []
tournaments = {}

# Updated Team Names with Funny and Country-Related (Dark Humor)
TEAM_NAMES = [
    "Sasquatch Squad", "Viking Vandals", "Pirate Pythons", "Ninja Nachos", "Zombie Zebras",
    "Wacky Wombats", "Grumpy Geese", "Mad Hooligans", "Crying Cowboys", "Reckless Rhinos",
    "Bumbling Buccaneers", "Sneaky Sasquatches", "Crazy Cacti", "Drunken Dragons", "Grouchy Gnomes",
    "Laughing Llamas", "Pouting Penguins", "Silly Sharks", "Angry Alpacas", "Mischievous Monkeys",
    "Furious Ferrets", "Boisterous Bears", "Cantankerous Camels", "Rowdy Raccoons", "Troubled Turtles",
    "Grim Griffins", "Moody Meerkats", "Jaded Jaguars", "Perky Porcupines", "Restless Ravers"
]

class Tournament:
    def __init__(self, name, teams, commentators=None, staff=None):
        self.name = name
        self.teams = teams  # List of teams (each team is a dict with 'name' and 'players')
        self.matches = []   # List of matches in the brackets
        self.commentators = commentators if commentators else []
        self.staff = staff if staff else []
        self.create_brackets()
    
    def create_brackets(self):
        """Create initial matches based on teams, balancing first matches as much as possible."""
        team_scores = [(idx, sum(player[2] for player in team['players'])) for idx, team in enumerate(self.teams)]
        team_scores.sort(key=lambda x: x[1])
        num_teams = len(self.teams)
        self.matches = []
        # Calculate number of rounds needed
        total_rounds = math.ceil(math.log2(num_teams))
        # Pad teams to make the number a power of 2
        bracket_size = 2 ** total_rounds
        byes = bracket_size - num_teams
        # Assign byes to top teams
        match_num = 1
        for idx in range(0, num_teams, 2):
            team1_idx = team_scores[idx][0]
            if idx + 1 < num_teams:
                team2_idx = team_scores[idx + 1][0]
            else:
                team2_idx = None
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
            # Match not found
            return False
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
                team1_name = f"Team {m['team1'] +1}: {self.teams[m['team1']]['name']}" if m['team1'] is not None else "TBD"
                team2_name = f"Team {m['team2'] +1}: {self.teams[m['team2']]['name']}" if m['team2'] is not None else "Bye"
                winner_name = f"Team {m['winner'] +1}: {self.teams[m['winner']]['name']}" if m['winner'] is not None else "In Progress"
                value += f"Match {m['match_num']}: {team1_name} vs {team2_name} - Winner: {winner_name}\n"
            embed.add_field(name=f"Round {rnd}", value=value, inline=False)
        return embed

    def update_member(self, team_number, old_member_name, new_member_name, new_member_rank):
        """Update a member in a team."""
        team_idx = team_number - 1
        if team_idx < 0 or team_idx >= len(self.teams):
            return False
        team = self.teams[team_idx]['players']
        for idx, player in enumerate(team):
            if player[0].lower() == old_member_name.lower():
                if new_member_rank.upper() not in TIER_POINTS:
                    return False
                team[idx] = (new_member_name, new_member_rank.upper(), TIER_POINTS[new_member_rank.upper()])
                return True
        return False

    def get_team_info(self, team_idx):
        """Return the team information."""
        team = self.teams[team_idx]
        team_name = team['name']
        players = team['players']
        team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in players])
        return team_name, team_info

    def get_all_teams_info(self):
        """Return information for all teams."""
        info = ""
        for idx, team in enumerate(self.teams):
            team_name, team_info = self.get_team_info(idx)
            info += f"{team_name}:\n{team_info}\n\n"
        return info

    def add_commentator(self, commentator_name):
        """Add a commentator to the tournament."""
        if len(self.commentators) >= 2:
            return False
        if commentator_name in self.commentators:
            return False
        self.commentators.append(commentator_name)
        return True

    def remove_commentator(self, commentator_name):
        """Remove a commentator from the tournament."""
        if commentator_name in self.commentators:
            self.commentators.remove(commentator_name)
            return True
        return False

    def add_staff(self, staff_name):
        """Add a staff member to the tournament."""
        if staff_name in self.staff:
            return False
        self.staff.append(staff_name)
        return True

    def remove_staff(self, staff_name):
        """Remove a staff member from the tournament."""
        if staff_name in self.staff:
            self.staff.remove(staff_name)
            return True
        return False

    def update_team_name(self, team_number, new_name):
        """Update the name of a team."""
        team_idx = team_number -1
        if team_idx < 0 or team_idx >= len(self.teams):
            return False
        self.teams[team_idx]['name'] = new_name
        return True

class TeamConfirmationView(View):
    """A view for confirming or regenerating teams."""

    def __init__(self, teams, original_players):
        super().__init__(timeout=60)  # Timeout after 60 seconds
        self.teams = teams
        self.original_players = original_players

    @discord.ui.button(label="Regenerate Teams", style=discord.ButtonStyle.red)
    async def regenerate(self, interaction: discord.Interaction, button: Button):
        """Handles team regeneration."""
        embed, view = create_balanced_teams(self.original_players)
        await interaction.response.edit_message(embed=embed, view=view)
        self.stop()

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

    # Generate all possible combinations for team1
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

    team1_name = "Team 1"
    team2_name = "Team 2"

    embed = discord.Embed(title="Balanced Teams (5v5)", color=0x00ff00)

    team1_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in best_team1])
    team2_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in best_team2])

    embed.add_field(name=f"{team1_name}", value=team1_info, inline=True)
    embed.add_field(name=f"{team2_name}", value=team2_info, inline=True)
    embed.add_field(name="Balance Info", value=f"Point Difference: {best_diff:.1f} points", inline=False)

    view = TeamConfirmationView(teams=[team1_name, team2_name], original_players=players)
    embed.set_footer(text="The teams should be balanced as much as possible. If not, please regenerate the teams using the button below.")
    return embed, view

def create_balanced_tournament_teams(players):
    """Create balanced teams for a tournament."""
    team_size = 5
    num_teams = len(players) // team_size
    teams = []
    team_points = []
    players_sorted = sorted(players, key=lambda x: x[2], reverse=True)
    available_team_names = TEAM_NAMES.copy()
    random.shuffle(available_team_names)
    for _ in range(num_teams):
        teams.append({'name': available_team_names.pop(), 'players': []})
        team_points.append(0)
    for player in players_sorted:
        # Assign to the team with the lowest total points
        min_team_idx = team_points.index(min(team_points))
        if len(teams[min_team_idx]['players']) < team_size:
            teams[min_team_idx]['players'].append(player)
            team_points[min_team_idx] += player[2]
    return teams

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='helpme')
async def help_command(ctx):
    """Displays the helpme message with all available commands."""
    embed = discord.Embed(title="League of Legends Team Balancer Help", color=0x00ff00)

    # First half of commands
    commands_part1 = (
        "1. `!lf team [player1] [rank1] [player2] [rank2] ...`\n"
        "   - Creates balanced 5v5 teams named 'Team 1' and 'Team 2'\n"
        "   - Requires exactly 10 players with their ranks\n\n"
        "2. `!lf tiers`\n"
        "   - Shows all tier point values\n\n"
        "3. `!lf join [name] [rank]`\n"
        "   - Join the player queue for a quick match\n\n"
        "4. `!lf tournament create [tournament_name] [player1] [rank1] ... [commentator1] [commentator2] [staff1] [staff2]`\n"
        "   - Create teams for a tournament with multiple players, optionally adding up to 2 commentators and staff\n\n"
        "5. `!lf tournament add_commentator [tournament_name] [commentator_name]`\n"
        "   - Add a commentator to an existing tournament (max 2)\n\n"
        "6. `!lf tournament remove_commentator [tournament_name] [commentator_name]`\n"
        "   - Remove a commentator from an existing tournament\n\n"
        "7. `!lf tournament add_staff [tournament_name] [staff_name]`\n"
        "   - Add a staff member to an existing tournament\n\n"
    )

    # Second half of commands
    commands_part2 = (
        "8. `!lf tournament remove_staff [tournament_name] [staff_name]`\n"
        "   - Remove a staff member from an existing tournament\n\n"
        "9. `!lf tournament report [tournament_name] [match_number] [winning_team_number]`\n"
        "   - Report match results and update brackets\n\n"
        "10. `!lf tournament brackets [tournament_name]`\n"
        "    - Display the current tournament brackets\n\n"
        "11. `!lf tournament teams [tournament_name]`\n"
        "    - Display the teams in the tournament\n\n"
        "12. `!lf tournament update_member [tournament_name] [team_number] [old_member_name] [new_member_name] [new_member_rank]`\n"
        "    - Update a member in a tournament team\n\n"
        "13. `!lf tournament update_name [tournament_name] [team_number] [new_team_name]`\n"
        "    - Update the name of a team in the tournament\n\n"
        "14. `!lf clear [option]`\n"
        "    - Clear specific data. Options: players, teams, tournaments, matches, all\n\n"
        "15. `!lf helpme`\n"
        "    - Shows this help message\n"
    )

    embed.add_field(name="Available Commands (1/2)", value=commands_part1, inline=False)
    embed.add_field(name="Available Commands (2/2)", value=commands_part2, inline=False)

    # Ranks are short enough to fit in one field
    ranks_info = (
        "Iron: I - 1.0 Points\n"
        "Iron-Bronze: IB - 2.0 Points\n"
        "Bronze: B - 3.0 Points\n"
        "Bronze-Silver: BS - 4.0 Points\n"
        "Silver: S - 5.0 Points\n"
        "Silver-Gold: SG - 6.5 Points\n"
        "Gold: G - 8.0 Points\n"
        "Gold-Platinum: GP - 9.5 Points\n"
        "Platinum: P - 11.0 Points\n"
        "Platinum-Emerald: PE - 13.0 Points\n"
        "Emerald: E - 15.0 Points\n"
        "Emerald-Diamond: ED - 17.0 Points\n"
        "Diamond: D - 19.0 Points\n"
        "Diamond-Master: DM - 21.5 Points\n"
        "Master: M - 24.0 Points\n"
        "Grandmaster: GM - 27.0 Points\n"
        "Challenger: C - 30.0 Points"
    )
    embed.add_field(name="Valid Ranks", value=ranks_info, inline=False)

    await ctx.send(embed=embed)

@bot.command(name='tiers')
async def tiers_command(ctx):
    """Displays the tier points."""
    embed = discord.Embed(title="League of Legends Rank Point Values", color=0x00ff00)
    for tier_str in format_tier_points():
        if ': ' in tier_str:
            name, values = tier_str.split(': ', 1)
            embed.add_field(name=name, value=values, inline=False)
    await ctx.send(embed=embed)

@bot.command(name='join')
async def join_queue(ctx, name: str, rank: str):
    """Allows a player to join the matchmaking queue."""
    rank = rank.upper()
    if rank not in TIER_POINTS:
        await ctx.send(f"Invalid rank '{rank}'. Use `!lf help` to see valid ranks.")
        return

    player_info = (name, rank, TIER_POINTS[rank])
    if player_info in player_pool:
        await ctx.send(f"{name} is already in the queue.")
        return

    player_pool.append(player_info)
    await ctx.send(f"{name} joined the queue as {rank}.")

    if len(player_pool) >= 10:
        embed, view = create_balanced_teams(player_pool[:10])
        await ctx.send(embed=embed, view=view)
        del player_pool[:10]

@bot.command(name='team')
async def team_balance(ctx, *, input_text=None):
    """Creates balanced teams based on provided players and ranks."""
    if not input_text:
        await ctx.send("Please use `!lf help` for command information.")
        return

    args = input_text.split()
    if len(args) < 20:
        await ctx.send("For team balancing, provide 10 players with their ranks.\nUse `!lf help` for more information.")
        return

    try:
        players = []
        for i in range(0, 20, 2):
            player_name = args[i]
            player_rank = args[i+1].upper()
            if player_rank not in TIER_POINTS:
                await ctx.send(f"Invalid rank '{player_rank}' for player '{player_name}'. Use `!lf help` to see valid ranks.")
                return
            players.append((player_name, player_rank, TIER_POINTS[player_rank]))

        embed, view = create_balanced_teams(players)
        await ctx.send(embed=embed, view=view)
    except Exception as e:
        await ctx.send("Error creating teams. Use `!lf help` for the correct format.")
        print(f"Error: {str(e)}")  # For debugging

@bot.group(name='tournament', invoke_without_command=True)
async def tournament(ctx):
    """Base command for tournament operations."""
    await ctx.send("Please use a subcommand. Use `!lf help` for more information.")

@tournament.command(name='create')
async def tournament_create(ctx, tournament_name: str, *args):
    """
    Creates a new tournament.
    Format: !lf tournament create [tournament_name] [player1] [rank1] ... [commentator1] [commentator2] [staff1] [staff2]
    Commentators and staff are optional.
    """
    required_player_args = 10 * 2  # 10 players, each with name and rank
    if len(args) < required_player_args:
        await ctx.send("Please provide a tournament name and at least 10 players with their ranks.\nUse `!lf help` for more information.")
        return

    # Extract players
    players = []
    i = 0
    while i +1 < len(args):
        if args[i].lower().startswith(('commentator', 'staff')):
            break
        player_name = args[i]
        player_rank = args[i+1].upper()
        if player_rank not in TIER_POINTS:
            await ctx.send(f"Invalid rank '{player_rank}' for player '{player_name}'. Use `!lf help` to see valid ranks.")
            return
        players.append((player_name, player_rank, TIER_POINTS[player_rank]))
        i += 2

    if len(players) <5:
        await ctx.send("Not enough players to form a single team.")
        return

    # Remaining args could be commentators and staff
    commentators = []
    staff = []
    while i < len(args):
        if args[i].lower().startswith('commentator'):
            if len(commentators) >=2:
                await ctx.send("Maximum of 2 commentators allowed.")
                return
            if i +1 >= len(args):
                await ctx.send("Please provide a name for the commentator.")
                return
            commentators.append(args[i+1])
            i +=2
        elif args[i].lower().startswith('staff'):
            if i +1 >= len(args):
                await ctx.send("Please provide a name for the staff member.")
                return
            staff.append(args[i+1])
            i +=2
        else:
            await ctx.send(f"Unrecognized role '{args[i]}'. Use `!lf help` for more information.")
            return

    # Create teams
    teams = create_balanced_tournament_teams(players)
    # Create Tournament instance
    tournament_obj = Tournament(tournament_name, teams, commentators, staff)
    tournaments[tournament_name] = tournament_obj

    # Display teams and their members with team points
    embed = discord.Embed(title=f"Tournament Teams: {tournament_name}", color=0x00ff00)
    for idx, team in enumerate(teams):
        team_name = team['name']
        team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in team['players']])
        team_points = sum(player[2] for player in team['players'])
        embed.add_field(name=f"Team {idx +1}: {team_name} - {team_points:.1f} pts", value=team_info, inline=False)
    if commentators:
        embed.add_field(name="Commentators", value=", ".join(commentators), inline=False)
    if staff:
        embed.add_field(name="Staff", value=", ".join(staff), inline=False)
    await ctx.send(embed=embed)

    # Also display the brackets
    embed = tournament_obj.display_brackets()
    await ctx.send(embed=embed)

@tournament.command(name='add_commentator')
async def tournament_add_commentator(ctx, tournament_name: str, commentator_name: str):
    """
    Adds a commentator to an existing tournament.
    Format: !lf tournament add_commentator [tournament_name] [commentator_name]
    """
    tournament_obj = tournaments.get(tournament_name)
    if not tournament_obj:
        await ctx.send(f"Tournament '{tournament_name}' not found.")
        return
    success = tournament_obj.add_commentator(commentator_name)
    if success:
        await ctx.send(f"Commentator '{commentator_name}' has been added to tournament '{tournament_name}'.")
        # Update tournament embed
        embed = discord.Embed(title=f"Tournament Teams: {tournament_name}", color=0x00ff00)
        for idx, team in enumerate(tournament_obj.teams):
            team_name = team['name']
            team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in team['players']])
            team_points = sum(player[2] for player in team['players'])
            embed.add_field(name=f"Team {idx +1}: {team_name} - {team_points:.1f} pts", value=team_info, inline=False)
        if tournament_obj.commentators:
            embed.add_field(name="Commentators", value=", ".join(tournament_obj.commentators), inline=False)
        if tournament_obj.staff:
            embed.add_field(name="Staff", value=", ".join(tournament_obj.staff), inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"Failed to add commentator '{commentator_name}'. They may already be added or the limit of 2 commentators has been reached.")

@tournament.command(name='remove_commentator')
async def tournament_remove_commentator(ctx, tournament_name: str, commentator_name: str):
    """
    Removes a commentator from an existing tournament.
    Format: !lf tournament remove_commentator [tournament_name] [commentator_name]
    """
    tournament_obj = tournaments.get(tournament_name)
    if not tournament_obj:
        await ctx.send(f"Tournament '{tournament_name}' not found.")
        return
    success = tournament_obj.remove_commentator(commentator_name)
    if success:
        await ctx.send(f"Commentator '{commentator_name}' has been removed from tournament '{tournament_name}'.")
        # Update tournament embed
        embed = discord.Embed(title=f"Tournament Teams: {tournament_name}", color=0x00ff00)
        for idx, team in enumerate(tournament_obj.teams):
            team_name = team['name']
            team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in team['players']])
            team_points = sum(player[2] for player in team['players'])
            embed.add_field(name=f"Team {idx +1}: {team_name} - {team_points:.1f} pts", value=team_info, inline=False)
        if tournament_obj.commentators:
            embed.add_field(name="Commentators", value=", ".join(tournament_obj.commentators), inline=False)
        if tournament_obj.staff:
            embed.add_field(name="Staff", value=", ".join(tournament_obj.staff), inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"Failed to remove commentator '{commentator_name}'. They may not be part of the tournament.")

@tournament.command(name='add_staff')
async def tournament_add_staff(ctx, tournament_name: str, staff_name: str):
    """
    Adds a staff member to an existing tournament.
    Format: !lf tournament add_staff [tournament_name] [staff_name]
    """
    tournament_obj = tournaments.get(tournament_name)
    if not tournament_obj:
        await ctx.send(f"Tournament '{tournament_name}' not found.")
        return
    success = tournament_obj.add_staff(staff_name)
    if success:
        await ctx.send(f"Staff member '{staff_name}' has been added to tournament '{tournament_name}'.")
        # Update tournament embed
        embed = discord.Embed(title=f"Tournament Teams: {tournament_name}", color=0x00ff00)
        for idx, team in enumerate(tournament_obj.teams):
            team_name = team['name']
            team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in team['players']])
            team_points = sum(player[2] for player in team['players'])
            embed.add_field(name=f"Team {idx +1}: {team_name} - {team_points:.1f} pts", value=team_info, inline=False)
        if tournament_obj.commentators:
            embed.add_field(name="Commentators", value=", ".join(tournament_obj.commentators), inline=False)
        if tournament_obj.staff:
            embed.add_field(name="Staff", value=", ".join(tournament_obj.staff), inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"Failed to add staff member '{staff_name}'. They may already be added.")

@tournament.command(name='remove_staff')
async def tournament_remove_staff(ctx, tournament_name: str, staff_name: str):
    """
    Removes a staff member from an existing tournament.
    Format: !lf tournament remove_staff [tournament_name] [staff_name]
    """
    tournament_obj = tournaments.get(tournament_name)
    if not tournament_obj:
        await ctx.send(f"Tournament '{tournament_name}' not found.")
        return
    success = tournament_obj.remove_staff(staff_name)
    if success:
        await ctx.send(f"Staff member '{staff_name}' has been removed from tournament '{tournament_name}'.")
        # Update tournament embed
        embed = discord.Embed(title=f"Tournament Teams: {tournament_name}", color=0x00ff00)
        for idx, team in enumerate(tournament_obj.teams):
            team_name = team['name']
            team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in team['players']])
            team_points = sum(player[2] for player in team['players'])
            embed.add_field(name=f"Team {idx +1}: {team_name} - {team_points:.1f} pts", value=team_info, inline=False)
        if tournament_obj.commentators:
            embed.add_field(name="Commentators", value=", ".join(tournament_obj.commentators), inline=False)
        if tournament_obj.staff:
            embed.add_field(name="Staff", value=", ".join(tournament_obj.staff), inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"Failed to remove staff member '{staff_name}'. They may not be part of the tournament.")

@tournament.command(name='report')
async def tournament_report(ctx, tournament_name: str, match_number: int, winning_team_number: int):
    """
    Reports the result of a match.
    Format: !lf tournament report [tournament_name] [match_number] [winning_team_number]
    """
    tournament_obj = tournaments.get(tournament_name)
    if not tournament_obj:
        await ctx.send(f"Tournament '{tournament_name}' not found.")
        return
    if winning_team_number <1 or winning_team_number > len(tournament_obj.teams):
        await ctx.send("Invalid winning team number.")
        return
    winning_team_idx = winning_team_number -1
    success = tournament_obj.report_match_result(match_number, winning_team_idx)
    if success:
        await ctx.send(f"Updated match {match_number} with winner Team {winning_team_number}: {tournament_obj.teams[winning_team_idx]['name']}.")
        # Display updated brackets
        embed = tournament_obj.display_brackets()
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"Failed to update match {match_number}.")

@tournament.command(name='brackets')
async def tournament_brackets(ctx, tournament_name: str):
    """
    Displays the brackets of a tournament.
    Format: !lf tournament brackets [tournament_name]
    """
    tournament_obj = tournaments.get(tournament_name)
    if not tournament_obj:
        await ctx.send(f"Tournament '{tournament_name}' not found.")
        return
    embed = tournament_obj.display_brackets()
    await ctx.send(embed=embed)

@tournament.command(name='teams')
async def tournament_teams(ctx, tournament_name: str):
    """
    Displays the teams of a tournament.
    Format: !lf tournament teams [tournament_name]
    """
    tournament_obj = tournaments.get(tournament_name)
    if not tournament_obj:
        await ctx.send(f"Tournament '{tournament_name}' not found.")
        return
    embed = discord.Embed(title=f"Tournament Teams: {tournament_name}", color=0x00ff00)
    for idx, team in enumerate(tournament_obj.teams):
        team_name = team['name']
        team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in team['players']])
        team_points = sum(player[2] for player in team['players'])
        embed.add_field(name=f"Team {idx +1}: {team_name} - {team_points:.1f} pts", value=team_info, inline=False)
    if tournament_obj.commentators:
        embed.add_field(name="Commentators", value=", ".join(tournament_obj.commentators), inline=False)
    if tournament_obj.staff:
        embed.add_field(name="Staff", value=", ".join(tournament_obj.staff), inline=False)
    await ctx.send(embed=embed)

@tournament.command(name='update_member')
async def tournament_update_member(ctx, tournament_name: str, team_number: int, old_member_name: str, new_member_name: str, new_member_rank: str):
    """
    Updates a member in a tournament team.
    Format: !lf tournament update_member [tournament_name] [team_number] [old_member_name] [new_member_name] [new_member_rank]
    """
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
            team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in team['players']])
            team_points = sum(player[2] for player in team['players'])
            embed.add_field(name=f"Team {idx +1}: {team_name} - {team_points:.1f} pts", value=team_info, inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("Failed to update member.")

@tournament.command(name='update_name')
async def tournament_update_name(ctx, tournament_name: str, team_number: int, new_team_name: str):
    """
    Updates the name of a team in a tournament.
    Format: !lf tournament update_name [tournament_name] [team_number] [new_team_name]
    """
    tournament_obj = tournaments.get(tournament_name)
    if not tournament_obj:
        await ctx.send(f"Tournament '{tournament_name}' not found.")
        return
    success = tournament_obj.update_team_name(team_number, new_team_name)
    if success:
        await ctx.send(f"Updated Team {team_number} name to '{new_team_name}'.")
        # Display updated teams
        embed = discord.Embed(title=f"Tournament Teams: {tournament_name}", color=0x00ff00)
        for idx, team in enumerate(tournament_obj.teams):
            team_name = team['name']
            team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in team['players']])
            team_points = sum(player[2] for player in team['players'])
            embed.add_field(name=f"Team {idx +1}: {team_name} - {team_points:.1f} pts", value=team_info, inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("Failed to update team name.")

@bot.group(name='clear', invoke_without_command=True)
async def clear(ctx):
    """Base command for clearing data."""
    await ctx.send("Please specify what to clear. Options: players, teams, tournaments, matches, all")

@clear.command(name='players')
async def clear_players(ctx):
    """Clears the player queue."""
    global player_pool
    player_pool = []
    await ctx.send("Player queue has been cleared.")

@clear.command(name='teams')
async def clear_teams(ctx):
    """Clears all tournament teams."""
    global tournaments
    for tournament in tournaments.values():
        tournament.teams = []
    await ctx.send("All tournament teams have been cleared.")

@clear.command(name='tournaments')
async def clear_tournaments(ctx):
    """Clears all tournaments."""
    global tournaments
    tournaments = {}
    await ctx.send("All tournaments have been cleared.")

@clear.command(name='matches')
async def clear_matches(ctx):
    """Clears all matches in all tournaments."""
    global tournaments
    for tournament in tournaments.values():
        tournament.matches = []
    await ctx.send("All matches in all tournaments have been cleared.")

@clear.command(name='all')
async def clear_all(ctx):
    """Clears all data including players, teams, tournaments, and matches."""
    global player_pool, tournaments
    player_pool = []
    tournaments = {}
    await ctx.send("All data has been cleared.")

# Run the bot
bot.run(DISCORD_TOKEN)



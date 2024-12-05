import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from itertools import combinations
import math

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
    "M": 23.0,  # Master
    "GM": 27.0, # Grandmaster
    "C": 30.0   # Challenger
}

player_pool = []
tournaments = {}

class Tournament:
    def __init__(self, name, teams):
        self.name = name
        self.teams = teams  # List of teams
        self.matches = []   # List of matches in the brackets
        self.create_brackets()

    def create_brackets(self):
        """Create initial matches based on teams, balancing first matches as much as possible."""
        team_scores = [(idx, sum(player[2] for player in team)) for idx, team in enumerate(self.teams)]
        team_scores.sort(key=lambda x: x[1])
        num_teams = len(self.teams)
        self.matches = []
        # Calculate number of rounds needed
        total_rounds = math.ceil(math.log2(num_teams))
        # Pad teams to make the number a power of 2
        bracket_size = 2 ** total_rounds
        byes = bracket_size - num_teams
        # Assign byes to top teams
        for idx, (team_idx, _) in enumerate(team_scores):
            if idx < byes:
                # Team gets a bye to next round
                self.matches.append({
                    'round': 1,
                    'match_num': idx + 1,
                    'team1': team_idx,
                    'team2': None,
                    'winner': team_idx
                })
            else:
                # Team plays in first round
                opponent_idx = team_scores[byes + (idx - byes)][0]
                self.matches.append({
                    'round': 1,
                    'match_num': idx + 1,
                    'team1': team_idx,
                    'team2': opponent_idx,
                    'winner': None
                })
                break  # Only pair one match at a time for balancing

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
        for i in range(0, num_winners, 2):
            if i + 1 < num_winners:
                new_matches.append({
                    'round': next_round,
                    'match_num': i // 2 + 1,
                    'team1': winners[i],
                    'team2': winners[i + 1],
                    'winner': None
                })
            else:
                # Odd number of teams; team gets a bye
                new_matches.append({
                    'round': next_round,
                    'match_num': i // 2 + 1,
                    'team1': winners[i],
                    'team2': None,
                    'winner': winners[i]
                })
        self.matches.extend(new_matches)

    def display_brackets(self):
        """Return an embed representing the current brackets."""
        embed = discord.Embed(title=f"Tournament Brackets: {self.name}", color=0x00ff00)
        rounds = set(m['round'] for m in self.matches)
        for rnd in sorted(rounds):
            matches_in_round = [m for m in self.matches if m['round'] == rnd]
            value = ""
            for m in matches_in_round:
                team1_name = f"Team {m['team1'] + 1}"
                team2_name = f"Team {m['team2'] + 1}" if m['team2'] is not None else "Bye"
                winner = f"Winner: Team {m['winner'] + 1}" if m['winner'] is not None else "In Progress"
                value += f"Match {m['match_num']}: {team1_name} vs {team2_name} - {winner}\n"
            embed.add_field(name=f"Round {rnd}", value=value, inline=False)
        return embed

    def update_member(self, team_number, old_member_name, new_member_name, new_member_rank):
        """Update a member in a team."""
        team_idx = team_number - 1
        if team_idx < 0 or team_idx >= len(self.teams):
            return False
        team = self.teams[team_idx]
        for idx, player in enumerate(team):
            if player[0] == old_member_name:
                if new_member_rank.upper() not in TIER_POINTS:
                    return False
                team[idx] = (new_member_name, new_member_rank.upper(), TIER_POINTS[new_member_rank.upper()])
                return True
        return False

    def get_team_info(self, team_idx):
        """Return the team information."""
        team = self.teams[team_idx]
        team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in team])
        return team_info

    def get_all_teams_info(self):
        """Return information for all teams."""
        info = ""
        for idx, team in enumerate(self.teams):
            team_info = self.get_team_info(idx)
            info += f"Team {idx + 1}:\n{team_info}\n\n"
        return info

def format_tier_points():
    """Format tier points in a more compact way."""
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

def create_balanced_teams(ctx, players):
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

    embed = discord.Embed(title="Balanced Teams (5v5)", color=0x00ff00)

    team1_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in best_team1])
    team2_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in best_team2])

    embed.add_field(name=f"Team 1", value=team1_info, inline=True)
    embed.add_field(name=f"Team 2", value=team2_info, inline=True)
    embed.add_field(name="Balance Info", value=f"Point Difference: {best_diff:.1f} points", inline=False)

    return embed

def create_balanced_tournament_teams(players):
    """Create balanced teams for a tournament."""
    team_size = 5
    num_teams = len(players) // team_size
    teams = [[] for _ in range(num_teams)]
    team_points = [0] * num_teams
    players_sorted = sorted(players, key=lambda x: x[2], reverse=True)
    for player in players_sorted:
        # Assign to the team with the lowest total points
        min_team_idx = team_points.index(min(team_points))
        if len(teams[min_team_idx]) < team_size:
            teams[min_team_idx].append(player)
            team_points[min_team_idx] += player[2]
    return teams

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

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
            "4. `#leagueofflex join [name] [rank]`\n"
            "   - Join the player queue for a quick match\n\n"
            "5. `#leagueofflex tournament create [tournament_name] [player1] [rank1] ...`\n"
            "   - Create teams for a tournament with multiple players\n\n"
            "6. `#leagueofflex tournament report [tournament_name] [match_number] [winning_team_number]`\n"
            "   - Report match results and update brackets\n\n"
            "7. `#leagueofflex tournament brackets [tournament_name]`\n"
            "   - Display the current tournament brackets\n\n"
            "8. `#leagueofflex tournament teams [tournament_name]`\n"
            "   - Display the teams in the tournament\n\n"
            "9. `#leagueofflex tournament update_member [tournament_name] [team_number] [old_member_name] [new_member_name] [new_member_rank]`\n"
            "   - Update a member in a tournament team"
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

    # Join command
    if command == 'join':
        args = args[1:]  # Remove 'join' from args
        if len(args) != 2:
            await ctx.send("Please provide a name and rank. Example: `#leagueofflex join Player1 D4`")
            return
        player_name = args[0]
        rank = args[1].upper()
        if rank not in TIER_POINTS:
            await ctx.send(f"Invalid rank '{rank}'. Use `#leagueofflex help` to see valid ranks.")
            return

        player_info = (player_name, rank, TIER_POINTS[rank])

        if player_info in player_pool:
            await ctx.send(f"{player_name} is already in the queue.")
            return

        player_pool.append(player_info)
        await ctx.send(f"{player_name} joined the queue as {rank}.")

        if len(player_pool) >= 10:
            embed = create_balanced_teams(ctx, player_pool[:10])
            await ctx.send(embed=embed)
            del player_pool[:10]
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

            embed = create_balanced_teams(ctx, players)
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send("Error creating teams. Use `#leagueofflex help` for the correct format.")
            print(f"Error: {str(e)}")  # For debugging
            return

    # Tournament commands
    if command == 'tournament':
        if len(args) < 2:
            await ctx.send("Please provide a subcommand. Use `#leagueofflex help` for more information.")
            return
        subcommand = args[1].lower()
        if subcommand == 'create':
            # Create a new tournament
            args = args[2:]  # Remove 'tournament' and 'create' from args
            if len(args) < 3:
                await ctx.send("Please provide a tournament name and players. Example: `#leagueofflex tournament create Tourney1 Player1 D4 Player2 G1 ...`")
                return
            tournament_name = args[0]
            args = args[1:]
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
            # Create teams
            teams = create_balanced_tournament_teams(players)
            # Create Tournament instance
            tournament = Tournament(tournament_name, teams)
            tournaments[tournament_name] = tournament
            # Display teams and their members with team points
            embed = discord.Embed(title=f"Tournament Teams: {tournament_name}", color=0x00ff00)
            for idx, team in enumerate(teams):
                team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in team])
                team_points = sum(player[2] for player in team)
                embed.add_field(name=f"Team {idx +1} - {team_points:.1f} pts", value=team_info, inline=False)
            await ctx.send(embed=embed)
            # Also display the brackets
            embed = tournament.display_brackets()
            await ctx.send(embed=embed)
            return
        elif subcommand == 'report':
            # Report match result
            args = args[2:]  # Remove 'tournament' and 'report' from args
            if len(args) != 3:
                await ctx.send("Usage: `#leagueofflex tournament report [tournament_name] [match_number] [winning_team_number]`")
                return
            tournament_name = args[0]
            match_number = int(args[1])
            winning_team_number = int(args[2])
            tournament = tournaments.get(tournament_name)
            if not tournament:
                await ctx.send(f"Tournament '{tournament_name}' not found.")
                return
            success = tournament.report_match_result(match_number, winning_team_number -1)
            if success:
                await ctx.send(f"Updated match {match_number} with winner Team {winning_team_number}.")
                # Display updated brackets
                embed = tournament.display_brackets()
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"Failed to update match {match_number}.")
            return
        elif subcommand == 'brackets':
            # Display brackets
            args = args[2:]  # Remove 'tournament' and 'brackets' from args
            if len(args) !=1:
                await ctx.send("Usage: `#leagueofflex tournament brackets [tournament_name]`")
                return
            tournament_name = args[0]
            tournament = tournaments.get(tournament_name)
            if not tournament:
                await ctx.send(f"Tournament '{tournament_name}' not found.")
                return
            embed = tournament.display_brackets()
            await ctx.send(embed=embed)
            return
        elif subcommand == 'teams':
            # Display teams
            args = args[2:]  # Remove 'tournament' and 'teams' from args
            if len(args) !=1:
                await ctx.send("Usage: `#leagueofflex tournament teams [tournament_name]`")
                return
            tournament_name = args[0]
            tournament = tournaments.get(tournament_name)
            if not tournament:
                await ctx.send(f"Tournament '{tournament_name}' not found.")
                return
            embed = discord.Embed(title=f"Tournament Teams: {tournament_name}", color=0x00ff00)
            for idx, team in enumerate(tournament.teams):
                team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in team])
                team_points = sum(player[2] for player in team)
                embed.add_field(name=f"Team {idx +1} - {team_points:.1f} pts", value=team_info, inline=False)
            await ctx.send(embed=embed)
            return
        elif subcommand == 'update_member':
            # Update member in a team
            args = args[2:]  # Remove 'tournament' and 'update_member' from args
            if len(args) != 5:
                await ctx.send("Usage: `#leagueofflex tournament update_member [tournament_name] [team_number] [old_member_name] [new_member_name] [new_member_rank]`")
                return
            tournament_name = args[0]
            team_number = int(args[1])
            old_member_name = args[2]
            new_member_name = args[3]
            new_member_rank = args[4]
            tournament = tournaments.get(tournament_name)
            if not tournament:
                await ctx.send(f"Tournament '{tournament_name}' not found.")
                return
            success = tournament.update_member(team_number, old_member_name, new_member_name, new_member_rank)
            if success:
                await ctx.send(f"Updated Team {team_number}: replaced '{old_member_name}' with '{new_member_name}' ({new_member_rank}).")
                # Display updated teams
                embed = discord.Embed(title=f"Tournament Teams: {tournament_name}", color=0x00ff00)
                for idx, team in enumerate(tournament.teams):
                    team_info = "\n".join([f"{player[0]} ({player[1]} - {player[2]} pts)" for player in team])
                    team_points = sum(player[2] for player in team)
                    embed.add_field(name=f"Team {idx +1} - {team_points:.1f} pts", value=team_info, inline=False)
                await ctx.send(embed=embed)
            else:
                await ctx.send("Failed to update member.")
            return
        else:
            await ctx.send("Invalid subcommand for tournament. Use `#leagueofflex help` for more information.")
            return

# Run the bot
bot.run(DISCORD_TOKEN)

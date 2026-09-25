from .models import Game, HeadToHeadSummary, RecordSplit, VenueSplit


def head_to_head_games(games: list[Game], team_a: str, team_b: str) -> list[Game]:
    """All meetings between the two teams, oldest first."""
    matches = [g for g in games if {g.home_team, g.away_team} == {team_a, team_b}]
    return sorted(matches, key=lambda g: (g.season, g.week))


def avg_combined_points(games: list[Game]) -> float | None:
    if not games:
        return None
    return sum(g.combined_points for g in games) / len(games)


def historical_over_rate(games: list[Game], threshold: float) -> float | None:
    """Fraction of these games whose combined score exceeded threshold."""
    if not games:
        return None
    overs = sum(1 for g in games if g.combined_points > threshold)
    return overs / len(games)


def build_head_to_head(games: list[Game], team_a: str, team_b: str) -> HeadToHeadSummary:
    all_games = head_to_head_games(games, team_a, team_b)
    longest_team, longest_len, current_team, current_len = _streaks(all_games)

    return HeadToHeadSummary(
        team_a=team_a,
        team_b=team_b,
        all_time=_record_split("all-time", all_games, team_a, team_b),
        last_10=_record_split("last 10", all_games[-10:], team_a, team_b),
        last_20=_record_split("last 20", all_games[-20:], team_a, team_b),
        team_a_venue_splits=_venue_splits(all_games, team_a),
        team_b_venue_splits=_venue_splits(all_games, team_b),
        longest_streak_team=longest_team,
        longest_streak_len=longest_len,
        current_streak_team=current_team,
        current_streak_len=current_len,
        avg_combined_points=avg_combined_points(all_games),
    )


def _record_split(label: str, games: list[Game], team_a: str, team_b: str) -> RecordSplit:
    team_a_wins = sum(1 for g in games if g.winner == team_a)
    team_b_wins = sum(1 for g in games if g.winner == team_b)
    ties = sum(1 for g in games if g.winner is None)

    # "Average margin of victory" -- only counts games that team actually won,
    # not the scoring differential across every meeting.
    a_margins = [g.margin_for(team_a) for g in games if g.winner == team_a]
    b_margins = [g.margin_for(team_b) for g in games if g.winner == team_b]

    return RecordSplit(
        label=label,
        games=len(games),
        team_a_wins=team_a_wins,
        team_b_wins=team_b_wins,
        ties=ties,
        avg_margin_team_a=(sum(a_margins) / len(a_margins)) if a_margins else None,
        avg_margin_team_b=(sum(b_margins) / len(b_margins)) if b_margins else None,
    )


def _venue_splits(games: list[Game], team: str) -> dict[str, VenueSplit]:
    # Unlike RecordSplit's margin, this is the average scoring margin across
    # every game at that venue (can be negative) -- the question here is "how
    # do they play there", not "how big are their wins there".
    by_venue: dict[str, list[Game]] = {}
    for g in games:
        by_venue.setdefault(g.venue_for(team), []).append(g)

    splits = {}
    for venue, venue_games in by_venue.items():
        wins = sum(1 for g in venue_games if g.winner == team)
        losses = sum(1 for g in venue_games if g.winner is not None and g.winner != team)
        ties = sum(1 for g in venue_games if g.winner is None)
        margins = [g.margin_for(team) for g in venue_games]
        splits[venue] = VenueSplit(
            venue=venue,
            wins=wins,
            losses=losses,
            ties=ties,
            avg_margin=(sum(margins) / len(margins)) if margins else None,
        )
    return splits


def _streaks(games_sorted: list[Game]) -> tuple[str | None, int, str | None, int]:
    """(longest_streak_team, longest_streak_len, current_streak_team, current_streak_len).

    A tie breaks any streak in progress.
    """
    longest_team, longest_len = None, 0
    running_team, running_len = None, 0

    for g in games_sorted:
        winner = g.winner
        if winner is not None and winner == running_team:
            running_len += 1
        elif winner is not None:
            running_team, running_len = winner, 1
        else:
            running_team, running_len = None, 0

        if running_len > longest_len:
            longest_team, longest_len = running_team, running_len

    if not games_sorted or games_sorted[-1].winner is None:
        return longest_team, longest_len, None, 0

    current_team = games_sorted[-1].winner
    current_len = 0
    for g in reversed(games_sorted):
        if g.winner != current_team:
            break
        current_len += 1

    return longest_team, longest_len, current_team, current_len

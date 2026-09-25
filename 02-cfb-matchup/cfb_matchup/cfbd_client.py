import sys

import cfbd
from cfbd.rest import ApiException

from .models import Game


def _client(api_key: str) -> cfbd.ApiClient:
    return cfbd.ApiClient(cfbd.Configuration(access_token=api_key))


def fetch_team_games(api_key: str, team: str, seasons: list[int]) -> list[Game]:
    """Every completed game a team played in each of the given seasons."""
    games: list[Game] = []
    with _client(api_key) as client:
        games_api = cfbd.GamesApi(client)
        for year in seasons:
            try:
                raw_games = games_api.get_games(year=year, team=team)
            except ApiException as e:
                print(f"  (couldn't fetch {year} games for {team}: {e})", file=sys.stderr)
                continue
            for g in raw_games:
                if not g.completed or g.home_points is None or g.away_points is None:
                    continue
                games.append(
                    Game(
                        season=g.season,
                        week=g.week or 0,
                        date=str(g.start_date) if g.start_date else "",
                        home_team=g.home_team,
                        away_team=g.away_team,
                        home_score=g.home_points,
                        away_score=g.away_points,
                        neutral_site=bool(g.neutral_site),
                    )
                )
    return games


def fetch_recent_universe(api_key: str, team_a: str, team_b: str, seasons: list[int]) -> list[Game]:
    """team_a's and team_b's own recent games, plus every recent game played
    by anyone they faced -- that second layer is what strength-of-schedule
    and common-opponent comparisons need, since those ask "how good is the
    team that beat them", not just "how did they do."
    """
    games = fetch_team_games(api_key, team_a, seasons) + fetch_team_games(api_key, team_b, seasons)

    opponents = set()
    for g in games:
        if g.home_team in (team_a, team_b):
            opponents.add(g.away_team)
        if g.away_team in (team_a, team_b):
            opponents.add(g.home_team)
    opponents -= {team_a, team_b}

    for opponent in opponents:
        games += fetch_team_games(api_key, opponent, seasons)

    seen = set()
    unique_games = []
    for g in games:
        key = (g.season, g.week, g.home_team, g.away_team)
        if key not in seen:
            seen.add(key)
            unique_games.append(g)
    return unique_games


def fetch_sp_rating(api_key: str, team: str, year: int) -> float | None:
    """Bill Connelly's SP+ overall rating, an established outside opinion to
    blend with our own recency-weighted calc (see power_rating.py). None if
    unavailable for that team/year rather than raising -- it's an optional
    input, not a required one.
    """
    with _client(api_key) as client:
        ratings_api = cfbd.RatingsApi(client)
        try:
            results = ratings_api.get_sp(year=year, team=team)
        except ApiException as e:
            print(f"  (couldn't fetch SP+ rating for {team} {year}: {e})", file=sys.stderr)
            return None
    return results[0].rating if results else None

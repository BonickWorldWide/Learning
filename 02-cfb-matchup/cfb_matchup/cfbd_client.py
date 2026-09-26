import sys
import time

import cfbd
from cfbd.rest import ApiException

from .models import Game

# CFBD's free tier rate-limits request bursts, not just an hourly total --
# fetching a team's games one season at a time (the h2h fetch alone used to
# be 50+ sequential calls by default) triggers a 429 reliably without pacing.
# These numbers were tuned against a real 429 from a live run, not guessed.
REQUEST_DELAY_SECONDS = 0.5
MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 3.0


class QuotaExceededError(Exception):
    """The account's *monthly* call allowance is gone, not a burst limit --
    retrying does nothing until the quota resets, so this must never go
    through the same retry-with-backoff path a 429 burst limit does."""


def _client(api_key: str) -> cfbd.ApiClient:
    return cfbd.ApiClient(cfbd.Configuration(access_token=api_key))


def _is_quota_exceeded(e: ApiException) -> bool:
    body = e.body
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    return "quota" in (body or "").lower()


def _call_with_retry(fn, *args, **kwargs):
    """Retries on a burst 429 with a growing backoff. A monthly-quota 429
    looks identical at the HTTP level but must not be retried -- a real
    run hit this and burned four retries (up to 9s each) on every single
    one of ~100 calls before finally failing, when the very first response
    already said "Monthly call quota exceeded." Any other ApiException is
    re-raised immediately too -- that's a real error, not a rate limit, and
    retrying it would just waste time before failing anyway."""
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except ApiException as e:
            if e.status == 429 and _is_quota_exceeded(e):
                raise QuotaExceededError(
                    "CollegeFootballData.com's monthly call quota is used up for this API "
                    "key. This is not a burst rate limit -- it will not clear up by waiting "
                    "or retrying. It resets at the start of next month, or get a second free "
                    "key at https://collegefootballdata.com/key ."
                ) from e
            if e.status != 429 or attempt == MAX_RETRIES - 1:
                raise
            wait = RETRY_BACKOFF_SECONDS * (attempt + 1)
            print(f"  (rate limited, waiting {wait:.0f}s...)", file=sys.stderr)
            time.sleep(wait)


def _map_games(raw_games) -> list[Game]:
    games = []
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


def fetch_team_games(api_key: str, team: str, seasons: list[int]) -> list[Game]:
    """Every completed game a team played in each of the given seasons.

    Kept for callers that genuinely need one team's full schedule; h2h and
    recent-context fetching (below) no longer use this, because it costs one
    API call per season and both of those needs can be answered far more
    cheaply.
    """
    games: list[Game] = []
    with _client(api_key) as client:
        games_api = cfbd.GamesApi(client)
        for i, year in enumerate(seasons):
            if i > 0:
                time.sleep(REQUEST_DELAY_SECONDS)
            try:
                raw_games = _call_with_retry(games_api.get_games, year=year, team=team)
            except ApiException as e:
                print(f"  (couldn't fetch {year} games for {team}: {e})", file=sys.stderr)
                continue
            games.extend(_map_games(raw_games))
    return games


def fetch_h2h_games(
    api_key: str, team_a: str, team_b: str, min_year: int | None = None, max_year: int | None = None
) -> list[Game]:
    """Every meeting between these two teams, in **one** API call.

    This used to be `fetch_team_games(team_a, <50 seasons>)` -- one call per
    season just to filter for the ~5 that were actually against team_b. CFBD
    has a dedicated matchup endpoint that returns exactly the games in
    common, which is what a real run needed all along.
    """
    with _client(api_key) as client:
        teams_api = cfbd.TeamsApi(client)
        try:
            matchup = _call_with_retry(
                teams_api.get_matchup, team1=team_a, team2=team_b, min_year=min_year, max_year=max_year
            )
        except ApiException as e:
            print(f"  (couldn't fetch matchup history for {team_a} vs {team_b}: {e})", file=sys.stderr)
            return []

    games = []
    for g in matchup.games:
        if g.home_score is None or g.away_score is None:
            continue
        games.append(
            Game(
                season=g.season,
                week=g.week or 0,
                date=g.var_date or "",
                home_team=g.home_team,
                away_team=g.away_team,
                home_score=g.home_score,
                away_score=g.away_score,
                neutral_site=bool(g.neutral_site),
            )
        )
    return sorted(games, key=lambda g: (g.season, g.week))


def fetch_season_games(api_key: str, year: int) -> list[Game]:
    """Every completed game in a season, one API call -- the efficient way
    to gather what a backtest needs (every team, not just two), instead of
    fetching team by team.
    """
    with _client(api_key) as client:
        games_api = cfbd.GamesApi(client)
        try:
            raw_games = _call_with_retry(games_api.get_games, year=year)
        except ApiException as e:
            print(f"  (couldn't fetch {year} season: {e})", file=sys.stderr)
            return []
    return _map_games(raw_games)


def fetch_recent_universe(api_key: str, team_a: str, team_b: str, seasons: list[int]) -> list[Game]:
    """team_a's and team_b's own recent games, plus every recent game played
    by anyone they faced -- that second layer is what strength-of-schedule
    and common-opponent comparisons need, since those ask "how good is the
    team that beat them", not just "how did they do."

    This pulls **whole seasons** (one API call per season, via
    `fetch_season_games`) rather than one call per team -- it used to fetch
    team_a, team_b, and then *every distinct opponent either of them
    faced*, each for every season, which was 20-50+ calls for a single
    report and is exactly what emptied a real account's monthly quota. A
    whole season is one call and already contains every one of those teams'
    games; filtering down to the ones that matter is free.
    """
    all_games: list[Game] = []
    for i, year in enumerate(seasons):
        if i > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
        all_games.extend(fetch_season_games(api_key, year))

    opponents = set()
    for g in all_games:
        if g.home_team in (team_a, team_b):
            opponents.add(g.away_team)
        if g.away_team in (team_a, team_b):
            opponents.add(g.home_team)
    opponents -= {team_a, team_b}

    relevant = {team_a, team_b} | opponents
    return [g for g in all_games if g.home_team in relevant or g.away_team in relevant]


def fetch_sp_rating(api_key: str, team: str, year: int) -> float | None:
    """Bill Connelly's SP+ overall rating, an established outside opinion to
    blend with our own recency-weighted calc (see power_rating.py). None if
    unavailable for that team/year rather than raising -- it's an optional
    input, not a required one.
    """
    with _client(api_key) as client:
        ratings_api = cfbd.RatingsApi(client)
        try:
            results = _call_with_retry(ratings_api.get_sp, year=year, team=team)
        except ApiException as e:
            print(f"  (couldn't fetch SP+ rating for {team} {year}: {e})", file=sys.stderr)
            return None
    return results[0].rating if results else None

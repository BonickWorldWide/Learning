# 01 · Fantasy Lineup Advisor

For each QB/RB/WR/TE on your roster and their real-life opponent this week,
shows:

1. **Player vs. opponent (career)** — every game that player has played
   against this specific opponent: games played, PPG in this matchup vs.
   their career PPG, and the key stats for their position (targets,
   receptions, yards, TDs, carries or attempts).
2. **Team vs. opponent (last 3–5 seasons)** — how the player's *team* has
   performed against this opponent regardless of roster: run/pass split,
   rush vs. pass yards, points scored, and which positions got the volume.
3. **Start/sit recommendation** — your rostered players at each position,
   ranked by their matchup-specific edge, with a one-line reason for each
   call — plus explicit "Start A over B: ..." lines.

Small samples (fewer than 3 meetings) are flagged for both the player and
the team sections. Head-coach and starting-QB changes since the historical
games are detected automatically. No projected points anywhere — that's
what your ESPN app is already for.

## Your roster is a file you edit, not an account you connect

`roster.json` is a plain list of names you type in once and update as your
team changes:

```json
[
  { "name": "Josh Allen", "position": "QB", "slot": "QB" },
  { "name": "Bijan Robinson", "position": "RB", "slot": "RB" }
]
```

`slot` is just a label for "starting" vs `"BE"` (bench) — it doesn't affect
the analysis, since this tool ranks by position, not by your current
lineup. Copy `roster.example.json` to `roster.json` and fill in your own.

Your current NFL team and this week's opponent are both looked up
automatically — you never type those in, so a trade mid-season doesn't
leave stale data sitting in a file you forgot to update.

There's no ESPN account, league ID, or login involved anywhere in this
tool. That was a deliberate choice, not just a simpler one: an earlier
version pulled your roster live from the ESPN API, and it turned out to be
a dead end for two independent reasons — the ESPN fantasy app doesn't give
you a shareable roster link on iPad (screenshot only), and separately, the
sandboxed environment this was built in couldn't reach ESPN's API host at
all (a network policy block, not fixable from inside the tool). Typing
your roster into a file sidesteps both problems at once, and it's not
really a downside — you already know your own roster.

## Data sources (both free, no signup)

- **[`nfl_data_py`](https://pypi.org/project/nfl-data-py/)** — weekly
  player stats (targets, carries, yards, TDs, attempts) going back to 1999.
- **[`nflverse`](https://github.com/nflverse/nflverse-data)'s schedule
  data** — final scores, and (this is the useful surprise) **head coach and
  starting QB for every game**, which is what makes the coach/QB continuity
  check automatic instead of something you'd have to track by hand.
- **`nflverse`'s weekly roster snapshots** — which team a player is actually
  on, per week. This is what resolves a name typed into `roster.json` to a
  current team (and catches a mid-season trade) without needing any other
  account or API.

**What's *not* automatic:** offensive coordinator changes. There's no free
public dataset of OC history, so that one stays a human judgment call — the
README won't pretend otherwise.

## What this teaches

- **Working with a real, messy data source.** The raw data doesn't hand you
  "fumbles lost" as one field (it's three: sack/rushing/receiving, summed in
  `nfl_data.py`), team abbreviations disagree between different providers for
  relocated franchises (`teams.py` normalizes them), and matching a typed-in
  name to real roster data needs real care, not a naive comparison. This is
  what real data work looks like — half of it is reconciling sources that
  don't quite agree, or names that aren't spelled quite the way you expect.
- **Name matching is never as simple as it looks.** `rosters.py`'s
  `latest_team_for_player` went through real bugs found by testing it
  against an actual roster: a name typed with "Jr." against data that
  doesn't have it (or the reverse — both happen), and a substring check
  that only worked in one direction. It tries exact match, then a
  suffix-blind match, then substring, in that order — each one only a
  fallback for the one before it, so a looser match never overrides a
  tighter one that already succeeded.
- **Separating I/O from logic, at a bigger scale than project 01's.** Every
  computational module (`scoring.py`, `player_history.py`,
  `team_tendencies.py`, `continuity.py`, `recommend.py`, `rosters.py`,
  `schedule.py`) is a pure function over a `pandas.DataFrame` — no network,
  fully unit-tested with small synthetic DataFrames. Only `nfl_data.py`
  touches the network. `report.py` and `manual_roster.py` are the seams
  that wire pure logic to real data.
- **Local caching.** Downloading years of stats on every run would be slow
  and unfriendly to the free data source — `nfl_data.py` caches each
  season to a local Parquet file (`.cache/`, git-ignored) and only
  re-fetches with `--refresh-data`.
- **Explaining a ranking, not just producing one.** `recommend.py` doesn't
  output a black-box score — every ranked player gets a plain-English
  reason built from the same numbers you can see in sections 1 and 2.
- **A season that's still being played is a real edge case, not a bug.**
  `get_weekly_stats` used to crash outright because the current season's
  stats file doesn't exist until the season is further along. Now it skips
  the missing season with a note — the exact case that matters most for a
  live start/sit decision has to degrade gracefully, not error out.
- **A network you don't control can simply say no.** The ESPN path is gone
  from this codebase entirely, not just unused — when an external
  dependency turns out to be unreachable for reasons outside your control,
  the fix isn't a workaround bolted on top, it's removing the dependency.

## Setup

```bash
cd 01-fantasy-lineup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json   # scoring/lookback settings — optional, has defaults
cp roster.example.json roster.json   # your actual roster
```

Then edit `roster.json` with your real players, and optionally `config.json`:

- `"scoring"` — `"ppr"` (default), `"half_ppr"`, or `"standard"`. Computed
  from raw stats using standard scoring weights — close to most leagues,
  but not a guaranteed exact match for a league's custom rules.
- `"player_seasons_lookback"` — how many seasons count as "career" for the
  player-vs-opponent section. Default 10.
- `"team_seasons_lookback"` — how many seasons for the team-vs-opponent
  section. Default 5, matching the 3–5 season ask this was built for.
- `"year"` — the season to run the report for. Default 2026.

## Usage

```bash
python -m fantasy_lineup matchups                # this week's report
python -m fantasy_lineup --week 5 matchups        # a specific week
python -m fantasy_lineup matchups --refresh-data  # bypass the local cache
```

Global flags (`--week`, `--refresh-data`) go *before* `matchups` on the
command line — that's an argparse subcommand quirk, not a choice.

The first run downloads and caches up to 10 seasons of stats, which takes
a while — later runs reuse the cache and are fast.

## Running the tests

```bash
pytest
```

Every pure module has its own test file, built on small hand-written
DataFrames rather than real downloaded data — the tests run in well under a
second and never touch the network. `nfl_data.py` (the stats download +
cache) is the only untested file: it needs the real network to exercise
for real, so it's kept as thin as possible instead.

## Where to take this next

- **Ranking is currently single-signal** — it sorts by the player's own
  matchup delta and uses team tendency only as supporting text in the
  reason, never as part of the ranking itself. A more sophisticated version
  could blend the two, but that starts trading away explainability for a
  fuzzier "AI-ish" score, which is exactly what this was built to avoid.
- **QB continuity uses the most recent *played* game of the season**, which
  can occasionally catch a backup who started a meaningless week 18 game.
  Worth a smarter heuristic (e.g. most starts this season, not just most
  recent) if that turns out to matter often.
- **A manual OC-change note field** in `config.json` (per team) would close
  the one gap automatic detection can't reach.

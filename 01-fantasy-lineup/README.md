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

## Two ways to get your roster in

**`--roster`** (recommended) — reads `roster.json`, a plain list of names
you type in once and update as your team changes. No ESPN account, no
league ID, no cookies, and no dependency on network access actually
reaching ESPN's servers (a real constraint in some sandboxed
environments — ESPN's fantasy API was flatly unreachable from the one this
was developed in, which is exactly why this mode exists). Your current NFL
team and this week's opponent are both looked up automatically — you never
type those in, so a trade mid-season doesn't leave stale data sitting in a
file you forgot to update.

```json
[
  { "name": "Josh Allen", "position": "QB", "slot": "QB" },
  { "name": "Bijan Robinson", "position": "RB", "slot": "RB" }
]
```

`slot` is just a label for "starting" vs `"BE"` (bench) — it doesn't affect
the analysis, since this tool ranks by position, not by your current
lineup. Copy `roster.example.json` to `roster.json` and fill in your own.

**The ESPN API path** (`client.py`, no flag) — pulls your roster live from
your real league. More convenient *if* your network can actually reach
`fantasy.espn.com`. See below for its setup.

Both paths produce identically-shaped reports — `manual_roster.py` and
`client.py` both just build a list of `PlayerWeek`s, and everything
downstream (`report.py` onward) has no idea which one supplied them.

## Data sources (both free, no signup)

- **[`nfl_data_py`](https://pypi.org/project/nfl-data-py/)** — weekly
  player stats (targets, carries, yards, TDs, attempts) going back to 1999.
- **[`nflverse`](https://github.com/nflverse/nflverse-data)'s schedule
  data** — final scores, and (this is the useful surprise) **head coach and
  starting QB for every game**, which is what makes the coach/QB continuity
  check automatic instead of something you'd have to track by hand.
- **`nflverse`'s weekly roster snapshots** — which team a player is actually
  on, per week. Used by `--roster` mode to resolve a typed-in name to a
  current team (and catch a mid-season trade) without needing ESPN at all.

ESPN's player IDs and nflverse's player IDs are different systems, so
matching between them goes through a public ID crosswalk table rather than
matching on name strings (name matching breaks on suffixes, hyphens, and
two players sharing an abbreviated name).

**What's *not* automatic:** offensive coordinator changes. There's no free
public dataset of OC history, so that one stays a human judgment call — the
README won't pretend otherwise.

## What this teaches

- **Working with a real, messy data source.** The raw data doesn't hand you
  "fumbles lost" as one field (it's three: sack/rushing/receiving, summed in
  `nfl_data.py`), team abbreviations disagree between ESPN and nflverse for
  relocated franchises (`teams.py` normalizes them), and a player match
  needs a proper ID crosswalk, not name-guessing. This is what real data
  work looks like — half of it is reconciling sources that don't quite
  agree.
- **Name matching is never as simple as it looks.** `rosters.py`'s
  `latest_team_for_player` went through three real bugs found by testing it
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
  fully unit-tested with small synthetic DataFrames. Only `nfl_data.py` and
  `client.py` touch the network. `report.py` and `manual_roster.py` are the
  seams that wire pure logic to real data — and the reason `--roster` mode
  was a small addition rather than a rewrite: everything past "get a list
  of `PlayerWeek`s" didn't need to change at all.
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

## Setup

```bash
cd 01-fantasy-lineup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

`config.json` holds scoring/lookback settings either way. For `--roster`
mode, that's all you need — also copy `roster.example.json` to
`roster.json` and fill in your players; `league_id`/`team_id`/cookies can
stay blank. The rest of this section is only for the ESPN API path.

### 1. `league_id` and `team_id`

Open your league in the ESPN Fantasy app or at fantasy.espn.com, go to
**your team**, and look at the URL (or "share" link). It looks like:

```
https://fantasy.espn.com/football/team?leagueId=123456&teamId=4
```

`leagueId` → `league_id`, `teamId` → `team_id` in `config.json`.

### 2. `espn_s2` and `swid` — only if your league is private

Try leaving these blank first and run `matchups` (below). If it works,
you're done — your league is public. If you get an authentication error,
ESPN needs proof you're logged in, via two cookies from your browser
session.

On an iPad, Safari won't let you type `javascript:` straight into the
address bar (it's blocked as a security measure), so it has to go through a
bookmark:

1. Bookmark any page (e.g. fantasy.espn.com itself), then open
   **Bookmarks → Edit** on it and replace its URL entirely with:
   `javascript:document.title=document.cookie;` — save it.
2. Log into fantasy.espn.com in Safari, navigate to your league, then open
   your bookmarks list and tap that bookmark. It rewrites the page's tab
   title to your cookies — tap the tab-switcher / long-press the title area
   to read the full text.
3. Look for `espn_s2=...` and `SWID=...` in it (SWID looks like
   `{ABC-123-...}`, curly braces included) and copy each value into
   `config.json`.

If that doesn't surface them (some cookies are marked "http-only" and
genuinely can't be read this way), the reliable fallback is doing this once
from a laptop's browser dev tools (Application/Storage tab → Cookies →
`espn.com`) — you only need to do it once, and the values are long-lived.

**Never paste these cookie values into our chat** — they're session
credentials for your ESPN login. Put them straight into `config.json`,
which never leaves your machine (it's git-ignored).

### 3. Scoring and lookback windows (optional)

`config.json` also has:

- `"scoring"` — `"ppr"` (default), `"half_ppr"`, or `"standard"`. Computed
  from raw stats using standard scoring weights — close to most ESPN
  leagues, but not a guaranteed exact match for a league's custom rules.
- `"player_seasons_lookback"` — how many seasons count as "career" for the
  player-vs-opponent section. Default 10.
- `"team_seasons_lookback"` — how many seasons for the team-vs-opponent
  section. Default 5, matching the 3–5 season ask this was built for.

## Usage

```bash
python -m fantasy_lineup --roster matchups          # manual roster.json, this week
python -m fantasy_lineup matchups                   # ESPN API, this week
python -m fantasy_lineup --roster --week 5 matchups # a specific week
python -m fantasy_lineup --roster matchups --refresh-data  # bypass the local cache
```

Global flags (`--roster`, `--week`, `--refresh-data`) go *before* `matchups`
on the command line — that's an argparse subcommand quirk, not a choice.

The first run downloads and caches up to 10 seasons of stats, which takes
a while — later runs reuse the cache and are fast.

## Running the tests

```bash
pytest
```

Every pure module has its own test file, built on small hand-written
DataFrames rather than real downloaded data — the tests run in well under a
second and never touch the network. `client.py` (ESPN) and `nfl_data.py`
(the stats download + cache) are the only untested files, for the same
reason as project 01: they need real credentials/network to exercise for
real, so they're kept as thin as possible instead.

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

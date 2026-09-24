# 02 · Fantasy Lineup Advisor

Pulls your real ESPN fantasy football roster and tells you:

- **`roster`** — everyone on your team, starters and bench, with their
  opponent this week and ESPN's own projected points (ESPN's projections
  already bake in matchup strength, so this is your "who's good against what"
  view).
- **`lineup`** — specific swap suggestions: any bench player projected to
  outscore a starter in a slot they're eligible for.

## What this teaches

- **Working with a third-party API wrapper** (`espn_api`) instead of raw
  HTTP — the same shape as most real-world "talk to some external data
  source" code you'll write.
- **Separating I/O from logic.** `recommend.py` is pure — it takes a list of
  players and returns swap suggestions, no network involved, so it's fully
  unit-testable. `client.py` is the only file that talks to ESPN. This split
  is the single most useful habit in this whole project: it's *why*
  `test_recommend.py` can run in milliseconds with no internet connection.
- **A boundary-mapping function** (`player_from_box_player` in `client.py`)
  — converting a third-party library's object into your own simple shape,
  defensively (`getattr` with defaults), because a library's exact fields
  can change between versions but your own code shouldn't crash over it.
- **Keeping secrets out of git.** `config.json` holds your real league ID
  and (if needed) private session cookies — it's git-ignored. Only
  `config.example.json`, a template with fake values, is committed.

## Setup

```bash
cd 02-fantasy-lineup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

Then edit `config.json`:

### 1. `league_id` and `team_id`

Open your league in the ESPN Fantasy app or at fantasy.espn.com, go to
**your team**, and look at the URL (or "share" link). It looks like:

```
https://fantasy.espn.com/football/team?leagueId=123456&teamId=4
```

`leagueId` → `league_id`, `teamId` → `team_id` in `config.json`.

### 2. `espn_s2` and `swid` — only if your league is private

Try leaving these blank first and run `roster` (below). If it works, you're
done — your league is public. If you get an authentication error, ESPN
needs proof you're logged in, via two cookies from your browser session.

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

## Usage

```bash
python -m fantasy_lineup roster          # see everyone + this week's matchups
python -m fantasy_lineup lineup          # get swap suggestions
python -m fantasy_lineup --week 5 lineup # a specific week
```

## Running the tests

```bash
pytest
```

These test `recommend.py`'s logic and `client.py`'s mapping function only —
nothing here hits the network or needs your real config, which is the point
of keeping I/O separate from logic.

## Where to take this next

- The swap logic is **greedy by roster order**, not a true optimal
  assignment — a bench player only ever fills the first slot it's
  considered for. Worth learning about the assignment problem / Hungarian
  algorithm if you want to make this provably optimal.
- Pull in recent performance trend (last 3 games vs. season average)
  alongside the single-week projection.
- Factor in `injury_status` — right now a questionable/doubtful player isn't
  treated any differently from a healthy one.

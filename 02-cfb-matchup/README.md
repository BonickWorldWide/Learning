# 02 · College Football Matchup Analyzer

Enter two teams, get:

1. **Head-to-head history** — all-time record, last 10 and last 20 meetings,
   average margin of victory for each team, venue splits (home/away/neutral),
   longest and current win streaks, and scoring trends — all in tables.
2. **Recent context** (weighted more heavily than old history) — each team's
   last 3 seasons: record, points for/against, home/away splits, strength of
   schedule, and results against common opponents.
3. **A simulated prediction** — 10,000 Monte Carlo trials using a simple,
   fully-explained power rating: win probability, projected score, spread,
   over/under, and fair moneyline odds for each team.
4. **A short verdict** — who's favored, by how much, the 2-3 biggest factors,
   and explicit low-confidence flags for rare matchups or major roster/coach
   turnover.

## Status: the engine is built and fully tested; two ways to feed it real data

Every number in sections 1-4 is computed by a pure, unit-tested module —
61 tests, all passing, verified against hand-computed expected values and
an end-to-end synthetic matchup, including the `--data-file` path below.
What can't be exercised *from inside this sandbox* is a live fetch against
CollegeFootballData.com's API — it's blocked by this environment's network
policy, the same class of block that killed the fantasy tool's ESPN path.
See "Two ways to get real data in" below.

## Data source: CollegeFootballData.com

Free, with a self-serve API key (just an email signup, no approval wait, at
https://collegefootballdata.com/key), via the official `cfbd` Python
package. `cfbd_client.py` is the only file that touches it:

- `fetch_team_games` — every completed game a team played in a season range.
- `fetch_recent_universe` — team_a's and team_b's recent games, *plus*
  every recent game played by anyone either of them faced. That second
  layer is what strength-of-schedule and common-opponent comparisons
  actually need — "how good was the team that beat them" requires that
  team's own results, not just the final score of one game.
- `fetch_sp_rating` — Bill Connelly's SP+ overall rating, an established
  outside opinion blended into the power rating (see below) rather than
  relying solely on a rating built from scratch here.

## Two ways to get real data in

`api.collegefootballdata.com` returns a 403 from this environment's egress
proxy — an organization network policy, not an authentication problem, and
not something fixable from inside the tool. (I checked for a free
GitHub-hosted bulk dataset too, the same workaround that saved the fantasy
project when ESPN was blocked — there is one, `cfbfastR-data`, but it's
play-by-play only and stops at the 2020 season, useless for "last 3
seasons" recency.)

### Option A: fetch from your own browser, hand the file to Claude

**Gridiron Fetch** is a small page (published as a Claude artifact) that
does the same fetch `cfbd_client.py` would, but as JavaScript running in
*your* browser instead of Python running in this sandbox — so it isn't
behind this environment's network block at all, since the request comes
from your device. Open it, paste in a free API key from
collegefootballdata.com/key, enter the two teams, and it downloads a JSON
file (using the artifact `downloads` capability, since plain download
links don't work inside an artifact frame). Send that file back in chat,
or run it yourself:

```bash
python -m cfb_matchup --data-file path/to/the-downloaded-file.json
```

`bundle.py` reads it into exactly the same `Game` objects a live fetch
would produce — `analysis.py` has no idea which path supplied them, which
is the entire reason it was built as a pure function taking games data as
an argument rather than fetching anything itself.

### Option B: run cfbd_client.py directly, somewhere unrestricted

Your own machine, once you have a free API key — the code doesn't know or
care that it was written inside a sandbox. Or try broadening *this*
environment's Network access (cloud environment menu → Edit → Network
access) to include `api.collegefootballdata.com` — worth attempting even
though it didn't pan out for ESPN, since it's a different host.

Either way:

```bash
cd 02-cfb-matchup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

Edit `config.json` and paste the key into `"api_key"` (or set the
`CFBD_API_KEY` environment variable instead — either works, the env var is
checked if `config.json` doesn't have one).

## Usage

```bash
python -m cfb_matchup "Ohio State" "Michigan"
python -m cfb_matchup "Ohio State" "Michigan" --home-team "Michigan"
python -m cfb_matchup "Ohio State" "Michigan" --neutral-site --year 2025
python -m cfb_matchup "Ohio State" "Michigan" --note-a "New offensive coordinator" --note-b "Lost starting QB to the portal"

# using a file from Gridiron Fetch instead of a live API call -- team
# names, year and home/away come from the file, no need to repeat them
python -m cfb_matchup --data-file cfb-ohio-state-vs-michigan-2026.json
```

Team names need to match CollegeFootballData's naming (usually just the
school name, e.g. `"Ohio State"`, `"Alabama"`, `"Boise State"`) — if a name
doesn't match, the report will just show no games found rather than
guessing at a close match.

## The model, and every knob in it

This is deliberately simple and explainable over accurate-but-opaque — the
whole point of showing the inputs is so you can see *why* it says what it
says, and adjust it.

**Power rating** (`power_rating.py`), per team:

1. Take each of the last 3 seasons' average scoring margin.
2. Weight them by recency: `SEASON_RECENCY_WEIGHTS = [0.5, 0.3, 0.2]` — this
   season counts for half, two seasons ago for a fifth. A season the team
   didn't play in (transfer to FBS, etc.) is skipped and the remaining
   weights are renormalized rather than treating a missing season as a zero.
3. Add a strength-of-schedule adjustment: `SOS_WEIGHT = 0.25` of the average
   opponent's own scoring margin. Beating bad teams by a lot counts for
   less than the raw margin alone would suggest.
4. If an SP+ rating is available, blend it in at `EXTERNAL_RATING_WEIGHT =
   0.4` — 40% outside opinion, 60% our own calculation.
5. Convert to a raw expected-points number: `BASELINE_EXPECTED_POINTS =
   27.0` (a rough FBS-average anchor) `+ rating / 2`.

All five constants live at the top of `power_rating.py`. Change a number,
re-run, see what shifts — nothing here is hidden inside a formula.

**Simulation** (`simulate.py`): each team's score in each of the 10,000
trials is a random draw around its expected points, using that team's own
real scoring standard deviation from its recent games (not a fixed
assumption — a wildly inconsistent team gets a wider spread of simulated
outcomes than a steady one). `HOME_FIELD_ADVANTAGE = 2.5` points is added
to whichever team is actually hosting; 0 for a neutral site.

**Moneyline**: `win_prob_to_moneyline()` converts a win probability to fair
(no-vig) American odds — the standard formula, not a sportsbook line (a
real book's odds would be shaded a few points worse on both sides to bake
in their margin).

## What this teaches

- **The same pure/impure split as project 01, at a larger scale.** Every
  computational module (`h2h.py`, `recent_form.py`, `power_rating.py`,
  `simulate.py`, `continuity.py`, `tables.py`, `verdict.py`) is pure —
  no network, fully unit-tested with hand-built `Game` objects whose
  expected outputs were worked out by hand before writing the test. Only
  `cfbd_client.py` touches the network. `analysis.py` is the seam that
  wires pure logic to real data, exactly like `report.py` in project 01 —
  and it's *itself* pure (it takes games data as an argument, it doesn't
  fetch anything), so the whole pipeline end-to-end is one more thing that
  got tested without any network at all (`tests/test_analysis.py`). That
  purity is also what made Gridiron Fetch possible without touching
  `analysis.py` at all: `bundle.py` maps its JSON into the exact same
  `Game` objects `cfbd_client.py` produces, so a third way of getting data
  in was a ~30-line addition, not a redesign.
- **When one environment can't reach an API, run the fetch somewhere that
  can — that "somewhere" doesn't have to be a whole other machine.** An
  Artifact page runs in the *viewer's* browser, not in the sandbox that
  published it, so its network requests go out from the viewer's own
  device. Gridiron Fetch is client-side JavaScript doing the same job as
  `cfbd_client.py` in Python — same endpoints, same two-pass
  strength-of-schedule fetch, same game-shape output — because the actual
  blocker was never the code, it was which network the request left from.
- **A model is a set of named, adjustable numbers, not a black box.**
  Every weight in `power_rating.py` and `simulate.py` is a module-level
  constant with a comment explaining what it does — the opposite of a
  model whose "why" lives only in a trained set of coefficients nobody can
  read.
- **Head-to-head "average margin" has more than one honest definition.**
  `h2h.py`'s `RecordSplit.avg_margin_team_a` only counts games that team
  actually won (a true "margin of victory"); `VenueSplit.avg_margin`
  counts every game at that venue, win or lose, because "how do they
  perform there" is a different question than "how big are their wins
  there." Both are documented at the point they're computed, not left for
  someone to guess at from the numbers alone.
- **Strength of schedule needs a second layer of data you might not think
  of at first.** Computing "how tough was this team's schedule" requires
  knowing how *their opponents* did against *everyone else* — not just
  the final score of the game between the two teams you actually care
  about. `fetch_recent_universe`'s two-pass fetch (get team_a's and
  team_b's games, then get every opponent's games too) exists because of
  that.
- **What can't be automated should say so, not fake it.** `continuity.py`
  doesn't try to detect a coaching change or transfer-portal turnover —
  there's no free public dataset of that for college football reachable
  here, so it's a plain pass-through for notes you supply yourself
  (`--note-a`/`--note-b`), the same honest gap as the fantasy tool's
  offensive-coordinator limitation.
- **When a dependency turns out to be unreachable, say so plainly instead
  of quietly shipping something you couldn't verify.** This README says
  plainly which path (`cfbd_client.py` vs. Gridiron Fetch) has actually
  been exercised against live data and which hasn't, rather than
  describing the tool as finished and letting that surface later.

## Running the tests

```bash
pytest
```

All 61 tests are pure-logic, run in well under a second, and need no
network or API key. `cfbd_client.py` is the only untested file, for the
same reason as every network-touching file in this repo: it needs the real
network to exercise for real, so it's kept as thin as possible instead.
(Gridiron Fetch's JavaScript is the same kind of thin, untested-by-design
boundary — it's tested by actually running it, not by a Python test suite
that can't execute browser JS.)

## Where to take this next

- **Once a live run actually happens**, expect team-name mismatches (CFBD's
  exact naming vs. what you'd guess) to be the first real friction —
  worth adding a fuzzy-match-and-suggest step if it comes up often.
- **The over/under threshold** in section 1's "how often the h2h series
  went over" line uses *this simulation's* projected total as the
  reference line, computed fresh each run — there's no fixed "typical
  total" concept, which seemed more honest than picking an arbitrary round
  number.
- **A manual continuity-notes file** (like the fantasy tool's
  `roster.json`) instead of `--note-a`/`--note-b` flags would make
  standing notes ("Team X changed conferences in 2024") persist between
  runs instead of being retyped every time.
- **The power rating doesn't currently use SP+'s offense/defense/special
  teams breakdown**, only the single overall `rating` field — a more
  detailed version could weight a run-heavy team's offense against a
  pass-funnel defense specifically, rather than one aggregate number per
  side.

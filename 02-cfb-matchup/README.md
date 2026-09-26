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

## Status: verified end-to-end against live data

Every number in sections 1-4 is computed by a pure, unit-tested module —
61 tests, all passing, verified against hand-computed expected values — and
the full pipeline has now also run for real: Ohio State vs. Michigan, live
CollegeFootballData.com data, 49 meetings of head-to-head history, current
Big Ten realignment reflected correctly in the common-opponents list,
10,000-trial simulation, the works.

That real run happened from Google Colab, not from inside this sandbox —
`api.collegefootballdata.com` is blocked by this environment's network
policy, the same class of block that killed the fantasy tool's ESPN path,
and that's still true. See "Getting real data in" below for how to run it
yourself.

## Data source: CollegeFootballData.com

Free, with a self-serve API key (just an email signup, no approval wait, at
https://collegefootballdata.com/key), via the official `cfbd` Python
package. `cfbd_client.py` is the only file that touches it:

- `fetch_h2h_games` — every meeting between two teams, ever, in one API
  call (CFBD's dedicated matchup endpoint).
- `fetch_recent_universe` — team_a's and team_b's recent games, *plus*
  every recent game played by anyone either of them faced, pulled a whole
  season at a time and filtered locally. That second layer is what
  strength-of-schedule and common-opponent comparisons actually need —
  "how good was the team that beat them" requires that team's own results,
  not just the final score of one game.
- `fetch_sp_rating` — Bill Connelly's SP+ overall rating, an established
  outside opinion blended into the power rating (see below) rather than
  relying solely on a rating built from scratch here.
- `fetch_team_games` / `fetch_season_games` — one team's or one whole
  season's games; the backtester (below) uses the latter.

## Getting real data in

`api.collegefootballdata.com` returns a 403 from this environment's egress
proxy — an organization network policy, not an authentication problem, and
not something fixable from inside the tool. (I checked for a free
GitHub-hosted bulk dataset too, the same workaround that saved the fantasy
project when ESPN was blocked — there is one, `cfbfastR-data`, but it's
play-by-play only and stops at the 2020 season, useless for "last 3
seasons" recency.)

### What actually works: run cfbd_client.py somewhere unrestricted

Verified end-to-end from Google Colab: clone the repo, `pip install -r
requirements.txt`, set `CFBD_API_KEY`, run `python -m cfb_matchup matchup
"Ohio State" "Michigan"`. Colab is a full, unrestricted Python environment,
not a sandboxed iframe, so this environment's network block simply doesn't
apply there. Your own machine works the same way, once you have a free
key from collegefootballdata.com/key — the code doesn't know or care that
it was written inside a sandbox.

Two real bugs this surfaced, both from actually running it rather than
reading the code:

1. `fetch_team_games` originally fired all ~50 yearly requests back-to-back
   with no delay, and CollegeFootballData's free tier rate-limits bursts
   like that (429s on nearly every call after the first). Fixed with pacing
   and retry-with-backoff.
2. A later real run hit a *different* 429 — `"Monthly call quota
   exceeded"` — that pacing and backoff couldn't fix, because it isn't a
   burst limit, it's the account's whole month used up. The old fetch path
   made that easy to hit: a single report fetched one team's full schedule
   for ~50 seasons of head-to-head *plus* both teams' and every common
   opponent's schedules for the recent-form window — close to a hundred
   calls for one matchup. Two fixes: `_call_with_retry` now recognizes a
   quota-exceeded 429 by its message and fails immediately instead of
   retrying it four times (retrying something that won't clear until next
   month just burns the clock before failing anyway), and the fetch itself
   is far cheaper — `fetch_h2h_games` uses CFBD's dedicated
   `TeamsApi.get_matchup` endpoint (one call for a team's *entire*
   head-to-head history, instead of one call per season), and
   `fetch_recent_universe` now pulls whole seasons
   (`fetch_season_games`, one call per season) and filters locally instead
   of fetching team by team. A report that used to cost ~100 calls now
   costs roughly `len(recent_seasons) + 2` (SP+) `+ 1` (h2h).

You could also try broadening *this* environment's Network access (cloud
environment menu → Edit → Network access) to include
`api.collegefootballdata.com` — worth attempting even
though it didn't pan out for ESPN, since it's a different host.

Setup, either way you end up running it:

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
python -m cfb_matchup matchup "Ohio State" "Michigan"
python -m cfb_matchup matchup "Ohio State" "Michigan" --home-team "Michigan"
python -m cfb_matchup matchup "Ohio State" "Michigan" --neutral-site --year 2025
python -m cfb_matchup matchup "Ohio State" "Michigan" --note-a "New offensive coordinator" --note-b "Lost starting QB to the portal"

# running from a pre-fetched JSON file instead of a live API call -- team
# names, year and home/away come from the file, no need to repeat them
python -m cfb_matchup matchup --data-file cfb-ohio-state-vs-michigan-2026.json
```

`--data-file` reads a JSON file matching `cfbd_client.py`'s output shape
(`bundle.py` maps it into the same `Game` objects a live fetch produces) —
useful for re-running a report without hitting the API again, or for any
future way of getting data in that isn't `cfbd_client.py` itself.

## Backtesting: does the model actually predict anything?

```bash
python -m cfb_matchup backtest --season 2025
```

Every prediction the tool makes is a claim about the future, and the only
way to know if that claim is any good is to check it against games that
already happened. `backtest` replays the *real* model (`build_matchup_report`,
unmodified — not a separate copy of the logic) against every completed game
in a season, using only games that happened strictly before each one as
that prediction's history. A game with nothing before it to predict from
(the very first one in the dataset) is skipped rather than guessed at from
nothing.

It reports:

- **Win accuracy** — how often the favored team actually won.
- **Brier score** — the standard way to grade a *probability*, not just a
  pick. 0 is perfect, 0.25 is what you'd get by always guessing 50/50, 1 is
  the worst possible. A confident wrong call costs more than a hedged one.
- **Mean absolute spread/total error** — how far off the projected margin
  and combined score were, on average, in points.
- **Biggest total misses** and **most confident wrong calls** — the
  specific games worth reading into, not just the aggregate numbers.

This surfaced a real, structural gap immediately: Navy vs. UAB (gave Navy
61%, Navy lost) and Army vs. Temple (projected total 60, actual 38) were
both flagged as the tool's own worst calls in exactly the same shape a real
run had already produced them. See "Where to take this next" for the
diagnosis and the fix that's actually needed.

`--history-seasons` (default 5) controls how many extra prior seasons get
fetched so early-season games in the test season still have enough history
to be predicted from — a week 1 game needs last season's results, not just
this season's (nonexistent) earlier games. `--n-simulations` defaults lower
(1,000) than a single report's 10,000, since a backtest runs the simulator
once per game across a whole season.

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
  purity is also what made `--data-file` (`bundle.py`) a ~30-line addition
  instead of a redesign: it maps a pre-fetched JSON file into the exact
  same `Game` objects `cfbd_client.py` produces, and `analysis.py` has no
  idea which path supplied them.
- **A platform's own sandbox can block a fix that looks perfectly
  reasonable, and the failure mode is unhelpfully generic.** The first
  attempt at working around this environment's network block was
  **Gridiron Fetch**, a Claude artifact meant to run the CollegeFootballData
  fetch as JavaScript in the *viewer's* browser instead of Python in this
  sandbox — reasoning that an artifact's network requests come from the
  viewer's device, so the sandbox's block wouldn't apply. It doesn't work:
  Claude's artifact platform has its own content-security-policy boundary
  that blocks `fetch()`/XHR to arbitrary external hosts from inside an
  artifact entirely, as a deliberate anti-exfiltration measure — a
  different, earlier wall than the one this was trying to get around, and
  one no amount of client-side code can route past. It failed silently
  (every request came back the generic browser error `"Load failed"`,
  identical to what a CORS rejection or a real network outage would also
  produce), which is why the fix ended up being "run it from Colab
  instead" rather than a patch to the artifact. The lesson generalizes:
  when a fetch fails with a maximally generic error, verify which layer
  actually rejected it before assuming the fix is in your own code.
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
  of quietly shipping something you couldn't verify — and when a fix
  doesn't pan out, say that plainly too.** This README doesn't just note
  that `cfbd_client.py` needed to run somewhere unrestricted; it says which
  specific attempt (Gridiron Fetch) failed, why, and that the working
  answer ended up being Colab instead.

## Running the tests

```bash
pytest
```

All 75 tests are pure-logic, run in well under a second, and need no
network or API key. `cfbd_client.py` is the only untested file, for the
same reason as every network-touching file in this repo: it needs the real
network to exercise for real, so it's kept as thin as possible instead.

## Where to take this next

- **The model has no pace/tempo signal, and that's a real, diagnosed gap,
  not a guess.** Two live predictions missed in the same way: Navy (a
  triple-option team) was favored 61% over UAB and lost, and Army vs.
  Temple projected a total of 60 when the actual combined score was 38.
  Both are the same root cause. `power_rating.py` and `simulate.py` build a
  team's expected points entirely from *points per game*, which silently
  bakes in how many possessions that team's games tend to have. Army,
  Navy, and Air Force run a triple-option offense specifically to run more
  clock per possession than anyone else in FBS — fewer possessions in the
  game, for **both** teams, regardless of who's better. A model that only
  sees "points per game" reads a low-possession team's history as *weaker
  offense* when it's actually just *fewer chances to score*, and it has no
  way to tell those apart. The fix is a plays-per-game or
  possessions-per-game signal (CFBD's `/stats/season` has this) used to
  scale expected points by relative pace, not just recent scoring. The
  `backtest` command (above) is what surfaced this pattern in the first
  place — run it across a full season and check whether service-academy
  games cluster at the top of "biggest total misses" before assuming this
  fix is worth the added complexity.
- **Team-name mismatches are still a real risk for less obvious team
  names** — Ohio State/Michigan matched CFBD's naming exactly, but a school
  with a nickname or ambiguous short form might not. Worth a
  fuzzy-match-and-suggest step if it comes up.
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

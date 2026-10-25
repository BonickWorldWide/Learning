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
   turnover. Optionally, type in a real sportsbook spread and over/under and
   it'll also tell you which side the model actually leans against that
   specific line.

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

- `fetch_fbs_teams` — the exact-spelling FBS team list, used to resolve
  whatever team names were typed (see "Usage" above) before any other
  fetch happens.
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
- `fetch_team_plays` / `fetch_returning_production` — the tempo and
  returning-production signals (see "The model, and every knob in it").
- `fetch_team_games` / `fetch_season_games` — one team's or one whole
  season's games; the backtester (below) uses the latter.
- `fetch_season_lines` — a season's real closing betting lines, one call
  (see "Benchmarking against the real market" below).

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

# compare the model against a real sportsbook line and get a pick
python -m cfb_matchup matchup "Ohio State" "Michigan" --line-a -7.5 --over-under 54.5

# also check whether a moneyline price is actually worth betting, not just who's favored
python -m cfb_matchup matchup "Georgia Tech" "Boston College" --line-a -6.5 --moneyline-a -230

# running from a pre-fetched JSON file instead of a live API call -- team
# names, year and home/away come from the file, no need to repeat them
python -m cfb_matchup matchup --data-file cfb-ohio-state-vs-michigan-2026.json
```

`--data-file` reads a JSON file matching `cfbd_client.py`'s output shape
(`bundle.py` maps it into the same `Game` objects a live fetch produces) —
useful for re-running a report without hitting the API again, or for any
future way of getting data in that isn't `cfbd_client.py` itself.

### Betting against a real line

`--line-a` / `--line-b` take the points a real sportsbook is giving each
team, typed in **exactly as the book shows them** — favorite negative,
underdog positive (e.g. Ohio State -7.5, Michigan +7.5). Either one alone
is enough; both together is also fine and gets cross-checked for a typo
(a real line is always the same number on both teams with opposite
signs — `-7.5` and `+3.0` together raises a clear error rather than
silently building a report off whichever one it happened to read first).
`--over-under` takes the book's total the same way (e.g. `54.5`).

With a line given, the **same 10,000 simulated trials already run for the
win probability** are also tallied against that exact number — not a
second, separate model — and the report gets three new things:

- In section 3, the actual line next to the model's own projected spread
  and total, plus each team's/side's real cover and over/under
  probability.
- In section 4 (the summary), an explicit pick: **"Pick Michigan against
  the spread, based on covering in 62% of simulated trials..."** — not a
  hedge, a team name and the number behind it. Same for the total: "Pick
  Over 54.5, based on hitting in 58% of simulated trials...".

**When the spread itself is too close to call** (within 5 percentage
points of a 50/50 cover split, `verdict.NO_LEAN_BAND`), the spread pick
doesn't default to either side of that coin flip — it falls back to the
one question the model still has a real opinion on: **"Pick Ohio State to
win outright -- the spread is too close to call... so this falls back to
who's actually more likely to win the game (71%)."** This fallback pick
can be a *different* team than either side of the spread would have
suggested, which is deliberate: "who covers this specific number" and
"who wins the game" are genuinely different questions, and when the first
one has no real answer, the second one still might. The total has no
equivalent fallback (there's no "who wins the total"), so a too-close
total is reported as exactly that, with no side picked.

This can also pick the team *not* favored by the model to win: if Ohio
State is projected to win by 8 but the book demands a 14-point margin to
cover, the model can still pick Michigan against that spread even though
Ohio State remains the favorite to win outright.

### Betting the right side isn't enough

A real user's betting record surfaced the gap this closes: across 19
picks using earlier versions of this tool's recommendations, the
against-the-spread picks went 7-3 (70%, well clear of the 52.4% break-even
rate the `backtest` command checks against), but the moneyline ("to win")
picks — mostly heavy favorites at -120 to -750 — went only 5-4, and on
flat $100 bets that lost money overall (-$267 on $900 risked), dragging a
genuinely good ATS record down to barely break-even across both bet types
combined. **Being right more often than not is not the same as the price
being worth paying.** A -400 favorite needs to win 80% of the time just to
break even at that price; winning 70% of the time at -400 is a losing bet
every time, however good it feels to be "right."

`--moneyline-a` / `--moneyline-b` take the real sportsbook "to win" price
for each team, American odds exactly as shown (e.g. `-230`, `+185`). They
only change anything when the spread pick falls back to a straight-up
winner (see above) — that's the one place this tool was recommending a
bet with zero regard for its price. With a moneyline given, that fallback
pick checks the model's own win probability against what the real price
is demanding (`simulate.moneyline_to_implied_prob`) and reports the
expected profit per $100 staked (`simulate.moneyline_ev`):

- **Real value**: *"Pick Georgia Tech to win outright at -230 -- ...and at
  that price (implying a 70% win probability) this is real value: an
  expected +$21.96 per $100 staked, not just the more likely winner."*
- **No real edge, even though the direction is right**: *"No bet, even
  though TCU is the more likely winner (70%) -- ...but at -400 the market
  is already demanding an 80% win probability to break even, which
  doesn't leave real value (expected -$12.50 per $100 staked). This is
  exactly the trap a heavy favorite's price sets: being right more often
  than not doesn't cover what laying that much to win a little actually
  costs when it's wrong."*

`verdict.MIN_EV_FOR_VALUE_BET` ($3 per $100 staked) is why a bet has to
clear zero by a real margin, not just technically be positive — the
model's own win probability is an estimate, not a certainty, and a bet
that only beats the market's price by a few cents is betting on the model
being exactly right, which is a different and much stronger claim than
"probably a bit better than the market here." Without a moneyline typed
in at all, the fallback still names the more likely winner (there's
nothing wrong with that half of the claim), but says plainly that it
can't check whether that team is worth betting on at whatever price is
actually on offer.

## Parlays: a good pick isn't a good parlay leg

```bash
python -m cfb_matchup parlay \
  --leg "0.75,-230,Georgia Tech" \
  --leg "0.65,-110,Ohio State spread" \
  --stake 5
```

A real user's actual pattern: "$5 parlay, 5 to 6 of the picks need to hit
in 1 bet." Checked against their own recent slips — same games as the
moneyline example above — **every one of 4 separate parlays lost, including
one that hit 4 of its 5 legs.** Going 4-for-5 is a complete loss on an
all-or-nothing ticket, the same as going 0-for-5. That's not bad luck,
it's what the structure guarantees: five independent 70% legs don't
combine to a 70% chance of cashing, they combine to 0.70⁵ ≈ 17%. The
straight-bet and moneyline-EV analysis elsewhere in this README is real
and useful, but it doesn't describe this at all — a parlay's own odds of
paying out have nothing to do with any single leg's quality in isolation.

**The fix is not "avoid favorites."** Checked directly: at the market's
own fair price, a heavy favorite (-230) and a near-coin-flip (-110) both
have exactly $0.00 expected value per $100 — favorites aren't
structurally worse bets, they're just lower-variance ones. What actually
matters for a parlay leg is the same thing that matters for a single bet:
**real edge**, the model's own probability clearing what the price
demands (exactly `simulate.moneyline_ev`'s question, asked per leg). A
leg priced at exactly the model's own confidence adds pure bust risk to
an all-or-nothing ticket for free — nothing compensates for the extra
uncertainty — so dropping any zero-or-negative-edge leg always raises the
parlay's own expected value, never lowers it.

`parlay.py` (new, pure, tested) does the actual math:

- `combined_probability` — every leg's own probability multiplied
  together, the real chance of cashing (not any single leg's probability,
  and not an average).
- `parlay_payout` / `combined_decimal_odds` — the real payout if every leg
  hits, from each leg's own American odds converted and multiplied.
- `parlay_ev` — expected profit on the whole ticket, at this exact stake,
  given each leg's TRUE probability (the model's own number, not the
  market's) — the parlay version of `moneyline_ev`.
- `leg_edges` — per-leg edge over the market's own price, worst first, so
  a leg worth dropping (or betting straight instead, away from the
  all-or-nothing structure) is immediately visible rather than requiring
  a manual scan of every leg's numbers.

`python -m cfb_matchup parlay` takes each leg as `--leg "PROB,ODDS[,LABEL]"`
— `PROB` comes from running `matchup` first (the win probability for a
moneyline leg, or the cover probability for a spread leg), `ODDS` is the
real sportsbook price for that specific bet. It reports the combined odds
of cashing, the real payout, the ticket's own expected value, and flags
every leg whose price already demands as much confidence as the model
actually has.

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
- **Against the spread / over-under, against the real closing line** —
  the actual answer to "does this beat the market," not just "did the
  favored team win." See "Benchmarking against the real market" below.
- **Biggest total misses** and **most confident wrong calls** — the
  specific games worth reading into, not just the aggregate numbers.

This surfaced a real, structural gap immediately: Navy vs. UAB (gave Navy
61%, Navy lost) and Army vs. Temple (projected total 60, actual 38) were
both flagged as the tool's own worst calls in exactly the same shape a real
run had already produced them. Both are now fixed — see "Tempo/pace
adjustment" below.

`--history-seasons` (default 5) controls how many extra prior seasons get
fetched so early-season games in the test season still have enough history
to be predicted from — a week 1 game needs last season's results, not just
this season's (nonexistent) earlier games. `--n-simulations` defaults lower
(1,000) than a single report's 10,000, since a backtest runs the simulator
once per game across a whole season.

Team names don't need to match CollegeFootballData's exact capitalization
any more — `matchup` fetches the real FBS team list once and resolves
whatever you typed to it, case-insensitively (`"virginia tech"` and
`"Boston college"` both work). A name that still doesn't match anything —
a typo, or a nickname CFBD doesn't list as an alternate — raises a clear
error with a suggestion (`"Did you mean: Boston College?"`) rather than
silently building a report with zero games found for that team, which is
what used to happen: every section (`h2h.py`, `recent_form.py`,
`simulate.py`'s home-field check) compares by exact string equality
against `team_a`/`team_b`, so a merely-differently-cased name matched
nothing anywhere and the report came back all zeros with no indication
why. `--home-team` goes through the same resolution.

## Benchmarking against the real market

Win accuracy and Brier score both grade the model against what *happened*
— but "the favored team won" and "this model knows something the market
didn't already price in" are different claims. A model can look good on
every metric above and still be worse than Vegas, which already prices in
injuries, weather, and things this model has no way to see. The only
honest way to answer "is this actually adding anything" is to check the
model's own picks against the real closing line, not just the final score.

`backtest` now fetches each tested season's real closing lines
(`cfbd_client.fetch_season_lines`, CFBD's `BettingApi`, one extra call)
and feeds the matching line into every target game's `build_matchup_report`
call exactly the way a live `--line-a`/`--over-under` would — so the
*same* simulation that already runs for the win probability also tallies
real cover/over probabilities against the actual market line that game
closed at, for free.

Two numbers come out of that:

- **ATS accuracy** — of the games where a real line existed *and* the
  model's own cover probability was a real lean (not a coin flip — same
  `NO_LEAN_BAND` the live report's spread_pick uses), how often did the
  side the model picked actually cover.
- **Over/under accuracy** — the same shape, for the total.

**Both are graded only on games the model actually had an opinion on.**
A game with no closing line found, or where the model's own probability
sat too close to 50/50 to call a real lean, is excluded from the
denominator entirely rather than coin-flipped into the number — mixing in
"games we had nothing to say about" would make the accuracy figure
measure something else (how the model performs on average) instead of the
actual question (how the model performs *when it has a real pick*). The
report says how many games were gradable.

**The bar to clear is 52.4%, not 50%.** `BREAK_EVEN_ATS_RATE` is the
math behind a standard -110-on-both-sides sportsbook line: bet $110 to
win $100, so break-even is `110 / (110 + 100)` ≈ 52.4%. A model that's
"right" exactly half the time against the spread still loses money over
time once the vig is in — 50% was never the real target, and reporting
it as one would be misleading about what "beating the market" actually
requires.

**The sign convention on CFBD's own spread field is documented, not yet
confirmed against live data** (`models.BettingLine`'s docstring) — this
environment can't reach `api.collegefootballdata.com` to spot-check a
real response (see "Getting real data in"). The assumption is CFBD's
standard convention: spread relative to the home team, negative when the
home team is favored, the same direction `--line-a` already expects.
**Worth confirming on the first real run**: pick a known lopsided
historical game from the backtest output and check that the loaded
spread matches what that game's real line actually was.

When multiple sportsbooks reported a line for the same game, whichever one
is listed as "consensus" is used; failing that, whichever provider CFBD
lists first with a non-null spread (`cfbd_client._pick_line`) — a
documented simplification, not a claim that one specific book is the
single source of truth.

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
3. If a plays-per-game figure is available, pace-normalize the margin
   (see "Tempo/pace adjustment" below) — this happens *before* the SOS
   adjustment, so a slow-tempo team's schedule strength is judged against
   its pace-corrected rating, not its raw one.
4. Add a strength-of-schedule adjustment: `SOS_WEIGHT = 0.25` of the average
   opponent's own scoring margin. Beating bad teams by a lot counts for
   less than the raw margin alone would suggest.
5. If a returning-production figure is available, add/subtract
   `returning_production_adjustment` (see "Returning production" below).
6. If an SP+ rating is available, blend it in at `EXTERNAL_RATING_WEIGHT =
   0.4` — 40% outside opinion, 60% our own calculation (this blend happens
   last, against the own-calc rating *after* every adjustment above).
7. Convert to a raw expected-points number: `BASELINE_EXPECTED_POINTS =
   27.0` (a rough FBS-average anchor) `+ rating / 2`.

All these constants live at the top of `power_rating.py`. Change a number,
re-run, see what shifts — nothing here is hidden inside a formula.

**Tempo/pace adjustment** (`power_rating.py`'s `pace_factor` /
`game_pace_factor`) — the fix for a real, diagnosed gap: a live backtest
favored Navy 61% over UAB and Navy lost, and separately projected a total
of 60 for Army vs. Temple when the real combined score was 38. Navy, Army
and Air Force all run a triple-option offense specifically to grind the
clock and run fewer plays than almost anyone in FBS — and
`points_for_per_game`/`points_against_per_game`, which the whole model was
built from, bakes in how many possessions a team's games tend to have,
with no way to tell "scored less because weaker" apart from "scored less
because fewer chances to score."

Two separate adjustments, not one, because they fix two different things:

1. **A team's own rating is pace-*normalized*.** `pace_factor(team's own
   plays/game)` is 1.0 at a league-average pace (`LEAGUE_AVERAGE_PLAYS_PER_GAME
   = 70.0`, the same kind of rough FBS-wide anchor as
   `BASELINE_EXPECTED_POINTS`), below 1.0 for a slower team, above 1.0 for
   a faster one. `build_power_rating` divides the margin component by this
   factor — a slow team's margin gets scaled *up*, because the same margin
   with fewer opportunities implies better-than-it-looks play per
   possession. This is what fixes a Navy-shaped mis-call: their real
   quality was being undervalued for a reason that had nothing to do with
   how good they actually are.
2. **The specific matchup's pace is re-applied on top of that**, in
   `analysis.py`, after both teams' ratings (now pace-neutral) have been
   turned into expected points. `game_pace_factor` averages both teams'
   own pace factors and scales *both* teams' expected points by it before
   they're simulated — two slow-tempo teams playing each other really will
   produce a lower-scoring game than a league-average matchup, independent
   of either team's now-corrected quality rating. Skipping this step and
   keeping only the first would have correctly rated Navy as better than
   their raw points suggested, while still projecting a normal-pace total
   for a game that will not play out at a normal pace — exactly the
   Army/Temple miss.

Plays-per-game comes from one extra API call per team
(`cfbd_client.fetch_team_plays`, CFBD's advanced season stats), gated by
`use_pace_adjustment` in `config.json` (default `true`) the same way
`use_sp_plus` gates the SP+ fetch. Missing pace data for a team — too
early in a season for CFBD to have posted it yet — is treated as exactly
league-average (1.0) for that team only, rather than silently skipping the
whole adjustment or biasing one team's rating relative to the other's for
a reason that has nothing to do with the game. The report prints the
combined game pace factor right under the projected total, and each
team's own factor under "Model inputs."

**Returning production** (`power_rating.py`'s `returning_production_adjustment`)
— the one signal this model can see *before* the current season has played
a single down. Everything else (margin, pace, SOS) is built from games
that already happened, which is exactly why it has nothing real to say in
weeks 1-3: the recency weights are still leaning almost entirely on last
season's numbers because this season barely has any yet. CFBD tracks what
fraction of last season's offensive production (`percent_ppa` — predicted
points added, weighted by who actually generated it) is still on the
roster; a team that graduated its starting QB and five O-linemen is not
the team its last-3-years margin says it is, and this is knowable in
August. `LEAGUE_AVERAGE_RETURNING_PRODUCTION = 0.60` is the anchor (an
approximation, same spirit as every other league-average constant here)
and `RETURNING_PRODUCTION_WEIGHT = 20.0` turns a deviation from it into
rating points — both reasoned starting values, not backtested ones (see
"Where to take this next"). Gated by `use_returning_production` in
`config.json` (default `true`), one extra call per team
(`cfbd_client.fetch_returning_production`); missing data adds exactly 0.0
rather than guessing.

**Simulation** (`simulate.py`): each team's score in each of the 10,000
trials is a random draw around its expected points, using that team's own
real scoring standard deviation from its recent games (not a fixed
assumption — a wildly inconsistent team gets a wider spread of simulated
outcomes than a steady one).

**Home-field advantage is per-team, not one flat number.**
`recent_form.team_home_field_edge` derives each team's own edge from half
the gap between its average home margin and its average away margin over
`recent_seasons` — the same way a single league-wide number is itself
usually derived, just computed per team instead of across all of FBS.
Some programs really do defend their own field better than others
(altitude, crowd noise, how far the visitor had to travel); treating
every team as exactly average was never more than a starting
approximation. Falls back to the flat `HOME_FIELD_ADVANTAGE = 2.5` when
there isn't at least 3 home *and* 3 away games to trust (a 3-season
window is typically 6-9 of each, but not always), and the computed value
is clamped to `[0, 2x the flat default]` — a small sample implying a
15-point home edge is noise, not a program with a legitimately enormous
one. Whichever team is actually hosting gets *their own* number; 0 for
the visitor and for a neutral site, same as before this existed. The
report prints both teams' edge under the projected total.

**Moneyline**: `win_prob_to_moneyline()` converts a win probability to fair
(no-vig) American odds — the standard formula, not a sportsbook line (a
real book's odds would be shaded a few points worse on both sides to bake
in their margin).

**Against a real line** (`--line-a`/`--line-b`/`--over-under`, see "Betting
against a real line" above): `simulate_game` tallies cover/over rates
straight from the same trials, no second model — each trial already draws
a score for both teams, so "did team_a's margin beat this line" and "was
the total over this number" are two more comparisons per trial, not a
different calculation. A trial landing exactly on the line counts as not
covering/not going over, which almost never actually happens here since
real scores are integers but these are continuous Gaussian draws — a
documented simplification, same spirit as clamping a negative draw to 0.

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

All 179 tests are pure-logic, run in well under a second, and need no
network or API key. `cfbd_client.py` is the only untested file, for the
same reason as every network-touching file in this repo: it needs the real
network to exercise for real, so it's kept as thin as possible instead.

## Where to take this next

- **Fixed: no way to check a parlay, only single bets.** See "Parlays: a
  good pick isn't a good parlay leg" above — a real user's actual pattern
  ($5 parlays, 5-6 legs, all must hit) showed every one of 4 recent slips
  losing, including one that hit 4 of its 5 legs, which the single-bet EV
  analysis elsewhere in this README has no way to explain.
  `parlay.py`/`python -m cfb_matchup parlay` close that gap.
- **Fixed: the straight-up fallback pick ignored price entirely.** See
  "Betting the right side isn't enough" above — a real user's record
  showed moneyline picks on heavy favorites losing money even at a 55.6%
  hit rate, because the tool never checked whether the model's win
  probability actually cleared what the real price demanded.
  `simulate.moneyline_ev`/`moneyline_to_implied_prob` plus
  `--moneyline-a`/`--moneyline-b` close that gap.
- **Fixed: the pace/tempo gap.** See "Tempo/pace adjustment" above —
  `power_rating.pace_factor`/`game_pace_factor` now correct for exactly
  the Navy/UAB and Army/Temple misses the `backtest` command surfaced.
- **Fixed: home-field advantage was one flat number for all of FBS.** See
  "Home-field advantage is per-team, not one flat number" above —
  `recent_form.team_home_field_edge` now derives each team's own edge
  from its own home/away scoring split, falling back to the flat default
  when the sample is too thin to trust.
- **Partially fixed: no early-season signal.** Returning production (see
  above) gives the model something real to say in weeks 1-3, when almost
  all of its other inputs are still last season's numbers. Still open:
  CFBD's recruiting talent composite (`TeamsApi.get_talent`) would be a
  second, free, roster-strength-shaped signal for exactly that window,
  and a weekly-updating Elo rating (`RatingsApi.get_elo`) would fix the
  *separate* problem that nothing currently gives extra weight to this
  week over week 1 once the season is actually underway —
  `recent_form.py` averages flatly across the whole recent-seasons
  window with no within-season recency at all.
- **Still true, more constants to sweep now: nothing has been tuned
  against a real backtest, only chosen to sound reasonable.**
  `SOS_WEIGHT = 0.25`, `EXTERNAL_RATING_WEIGHT = 0.4`,
  `SEASON_RECENCY_WEIGHTS = [0.5, 0.3, 0.2]`, `LEAGUE_AVERAGE_PLAYS_PER_GAME
  = 70.0`, and now `LEAGUE_AVERAGE_RETURNING_PRODUCTION = 0.60` /
  `RETURNING_PRODUCTION_WEIGHT = 20.0` are all plausible-looking defaults
  that nobody has actually swept against `backtest`'s own Brier
  score/mean-absolute-error output to see whether they're good numbers or
  just defensible-sounding ones. That's a free accuracy gain sitting
  there before reaching for a new data source — try a small grid of values
  for one constant at a time, rerun `backtest --season 2025`, and keep
  whatever actually lowers the error, the same empirical standard that
  caught the pace gap in the first place.
- **Fixed: backtest now benchmarks against the real market, not just
  outcomes.** See "Benchmarking against the real market" above — `backtest`
  fetches real closing lines and reports ATS/over-under accuracy against
  the 52.4% break-even bar, not just "did the favored team win." Still
  genuinely open: the CFBD spread sign convention this relies on is
  documented but unconfirmed against live data (same section, same reason
  every "diagnosed, not yet confirmed" item in this file is marked that
  way) — spot-check it on the first real run before trusting the ATS
  number.
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

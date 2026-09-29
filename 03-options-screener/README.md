# 03 · Options Screener

Two screens over a watchlist of tickers:

1. **Cheap, near-the-money contracts** — calls and puts trading close to
   the stock's current price, at a low absolute premium. A cheap,
   high-leverage way to play a name close to breakeven.
2. **"Bound to pop" candidates** — far out-of-the-money calls, picked by
   delta, on stocks whose recent momentum, news sentiment and options
   volume all lean bullish. Lottery tickets, screened rather than guessed.

Plus a one-ticker deep dive (`analyze`) that shows the full breakdown
behind either screen for a single name, and `discover`, which scans the
S&P 500 instead of requiring a hand-picked watchlist -- see "Finding
candidates automatically" below.

**This is a research/screening tool, not a trading system.** It doesn't
place orders, hold positions, or know anything about your account — it
surfaces candidates and the reasoning behind them so you can decide.
Options can expire worthless; nothing here is investment advice.

## Status

The whole analysis engine is pure, unit-tested (70 tests, hand-verified
against a textbook Black-Scholes reference case). `yfinance` itself is
blocked from inside this environment by the same network policy that
blocked CollegeFootballData.com and ESPN for the other two projects here
(see "Getting real data in"), but `discover` has now run for real from
Colab — see "Real bugs this surfaced" below for what that turned up.

## The model, and every knob in it

Deliberately simple and explainable, same principle as the CFB tool: every
score is a sum of named, visible parts, not a trained model you have to
trust blind.

### Cheap, near-the-money screen

`moneyness.find_cheap_near_money(contracts, spot, band_pct, max_premium)` —
keeps any call or put within `band_pct` of the current price (default 5%,
either side) priced at or under `max_premium` (default $2.00), sorted
cheapest first. No signal, no scoring — just "close to the money and
cheap." Each result carries its own Black-Scholes Greeks so you can see
its delta before deciding.

### "Bound to pop" screen

`screener.build_pop_candidate` scores each ticker 0-1 as an equal-weighted
average of whichever signals are available, each independently visible in
the report:

- **Momentum** (`momentum.py`) — three simple technical reads: 20-day
  return, 14-day RSI, and whether the price is above its 50-day average.
  Each one votes bullish (1), bearish (0), or neutral (0.5); the score is
  the average of whichever ones have enough history to compute.
- **Sentiment** (`sentiment.py`) — a small, hand-curated positive/negative
  word list run against recent headlines (from `yfinance`'s news feed for
  that ticker) *and*, if filings are turned on (see "Financial reports"
  below), recent 8-K filing text scored by the exact same lexicon rather
  than a separate mechanism. Not a trained NLP model — a few dozen words
  anyone can read (`POSITIVE_WORDS` / `NEGATIVE_WORDS`), on purpose —
  explainable over clever. A ticker with fewer than 3 headlines total is
  flagged `low_confidence` rather than silently trusted.
- **Unusual options volume** (`volume_signal.py`) — today's call volume
  against standing open interest. A ratio at or above 1.0 means today's
  volume alone exceeds everyone who already held a position — the classic
  "someone new just showed up" signal, computed straight from the option
  chain with no history needed.
- **Financial growth** (`financials.py`, optional) — real reported
  year-over-year revenue and EPS growth from SEC filings, not another
  keyword guess. Only counted when `include_filings` is on (see below);
  when it's off, the score stays a three-way average exactly as before.

Once a ticker has a score, its **actual contracts** are picked separately:
every call whose Black-Scholes delta falls in the configured band (default
0.10–0.30 — solidly out of the money) and whose premium is at or under a
cap (default $1.00). A ticker can score well with nothing picked (nothing
cheap enough today) — that's a real, useful answer, not a bug.

`rank_pop_candidates` then keeps only tickers at or above a score
threshold (default 0.6), sorted best first.

### Delta and the other Greeks

`greeks.py` is a from-scratch Black-Scholes implementation (stdlib `math`
only, no dependency) — delta, gamma, theta, vega and fair value, given
spot, strike, days to expiry, implied volatility and a risk-free rate. It's
verified in `test_greeks.py` against the standard textbook reference case
(Hull's), so the formulas aren't just "looked right."

Deliberate simplifications, documented rather than hidden:

- **No dividend yield.** Standard for a short-dated equity option screen;
  it would matter for a long-dated option on a high dividend payer, which
  isn't what either screen here is looking at.
- **A constant risk-free rate** (`risk_free_rate` in config, default
  4.5%), not a live Treasury yield.
- **IV comes from `yfinance`**, which Yahoo itself computes and reports per
  contract — this tool doesn't derive its own from bid/ask, it takes the
  market's.

## Financial reports (SEC EDGAR), and why they split into two signals

**Off by default.** Turn it on with two keys in `config.json`:

```json
{
  "include_filings": true,
  "edgar_contact_email": "you@example.com"
}
```

Two very different documents both count as "financial reports," and they
feed the model in two different ways:

- **8-K filings** — short, event-triggered disclosures (earnings releases,
  M&A, executive departures, guidance changes). Close enough to "news" that
  `edgar_client.fetch_recent_8k_texts` pulls the plain text of the most
  recent few and hands it straight to the *same* `sentiment.py` lexicon
  that already scores headlines — one scorer, two sources, no new
  mechanism to build or trust.
- **10-Q/10-K filings** — the full quarterly/annual reports. Far too long
  and dense to keyword-scan usefully (often 50-200 pages, mostly legal
  boilerplate), but SEC EDGAR exposes the actual numbers a company reported
  as structured data (XBRL), not just prose. `financials.py` pulls revenue
  and diluted EPS and computes real year-over-year growth — comparing the
  same fiscal quarter a year apart (`Q3 FY2025` vs. `Q3 FY2024`), never
  quarter-over-quarter, so a seasonal business isn't misread as growing or
  shrinking just because one quarter is bigger than the last by design.
  This is a genuine quantitative signal, not another lexicon guess, and
  it's why filings split into two files (`edgar_client.py` fetches,
  `financials.py` computes) instead of one.

Revenue is reported under different XBRL tags depending on when and how a
company filed (`Revenues`, then `RevenueFromContractWithCustomerExcludingAssessedTax`,
then the older `SalesRevenueNet`) — `edgar_client.py` tries each in order
and uses the first with any data, the same defensive-fallback pattern
`fetch_news_headlines` already uses for Yahoo's own schema changes.

**Why this is opt-in, and why a contact email is required at all:** SEC's
fair-access policy requires every request to identify a real requester by
name and email in the `User-Agent` header, and will block requests that
don't — a stricter, explicitly-published version of the same thing that
got Wikipedia's default `urllib` User-Agent a 403 earlier in this project.
There's no key to apply for the way there is for CollegeFootballData; there
is a header you're expected to set honestly instead. Leaving
`include_filings` on with `edgar_contact_email` blank prints a warning
and sends a placeholder — functional for a quick look, but not something
to rely on, and not something to leave in place if you're actually going
to use this regularly.

**Not yet run against live data.** Like everything else in this project,
`edgar_client.py` is written against SEC EDGAR's documented endpoint
shapes but hasn't been exercised against a real response — this sandbox
can't reach `sec.gov` either (confirmed, not assumed: a real proxy 403,
same as Yahoo and Wikipedia). Try it from Colab and report back what
actually comes back; CFBD, Yahoo and Wikipedia all needed at least one
real-data fix apiece the first time they were actually run.

## Finding candidates automatically

```bash
python -m options_screener discover
python -m options_screener discover --top-n 30
```

`watchlist.json` only ever contains tickers you already typed in. `discover`
scans the S&P 500 instead — but a full-depth scan of 500 tickers (option
chain + history + news, each) is 3,000+ requests, which risks Yahoo
throttling or blocking a scraping library with no official rate-limit tier
to fall back on. So it runs in two stages instead of one:

1. **Cheap prefilter** — every S&P 500 ticker, but only price history and
   news (`discover.prefilter_score`, momentum + sentiment, equal-weighted,
   no option chain fetched at all). Two requests per ticker.
2. **Expensive stage** — only the top `--top-n` tickers (default 15) from
   the prefilter go on to a full option-chain fetch and the same
   `build_pop_candidate` scoring `screen` uses, so the printed report is
   identical in shape to `screen`'s.

`market_data.fetch_sp500_tickers` pulls the constituent list straight from
Wikipedia's own table — always current, no bundled list here to drift out
of date as the index is reconstituted. A ticker with a dot in its symbol
(`BRK.B`) is rewritten with a hyphen (`BRK-B`), which is the form Yahoo
Finance actually uses; the raw Wikipedia spelling would fail to look the
ticker up at all.

A small pause between prefilter requests (`REQUEST_DELAY_SECONDS`, 0.2s)
is a precaution against exactly the kind of burst that got a real 429 out
of CollegeFootballData's API in the CFB tool — Yahoo has no published limit
to tune against, so this hasn't been verified as necessary, only as
prudent. Scanning all ~500 tickers takes several minutes in practice
(a real run measured about 7) — that's the pacing plus ~500 sequential
round trips, not a hang.

### Real bugs this surfaced

Three, all from actually running `discover` in Colab rather than from
reading the code:

1. `pandas.read_html` handed the Wikipedia URL directly gets a 403,
   because it (like a lot of sites) rejects the generic User-Agent
   Python's `urllib` sends by default — nothing to do with this sandbox's
   own network block, since Colab has no such block and hit it too. Fixed
   by fetching the page ourselves with a browser-like `User-Agent` first,
   then handing pandas the HTML directly instead of the URL.
2. Every single one of the first real shortlist (15 real tickers) failed
   with `cannot convert float NaN to integer`. A contract with no trades
   that day comes back from `yfinance` with `volume`/`openInterest` as
   `NaN`, not `None` -- and `NaN or 0` never falls through to `0`, because
   `NaN` is truthy in Python. `option_rows.py` (new, pure, tested) replaces
   that pattern with an explicit NaN-or-None check for every field, and
   treats a missing implied volatility as "skip this contract" rather than
   faking a `0`, which would otherwise tell the model this contract has
   literally no time value -- a real, wrong claim, not a harmless default.
3. The next real run came back with every printed delta showing `+0.00` or
   `-0.00`, and zero of 15 shortlisted tickers found a single "bound to
   pop" contract. `fetch_option_chain` pulls the nearest 4 expiries with no
   floor on how close they can be, and several of those nearest expiries
   were only 2-3 days out. At that range delta collapses toward 0 or 1
   within a percent or two of the strike (`test_screener.py` and
   `test_moneyness.py` now assert this directly, and it checks out against
   the textbook Black-Scholes case too: at 3 days, a name needs 45%+ IV just
   to reach 0.13 delta a few percent out of the money; at 21 days the same
   distance lands comfortably in a normal 0.10-0.30 band across ordinary
   IV levels). So both screens were being flooded with contracts that were
   only "cheap"/low-delta because they were about to expire, not because
   they were a good setup -- and the 0.10-0.30 delta band for a 2-3 day
   contract is a sliver of strikes that mostly don't exist or cost more
   than the premium cap on a $150-280 stock. Fixed with `min_days_to_expiry`
   (config, default 7), applied in both `moneyness.find_cheap_near_money`
   and `screener.build_pop_candidate` before any scoring or picking
   happens. Delta is also now printed to 4 decimal places instead of 2 --
   the old 2-decimal display was hiding genuinely different (if all
   small) numbers behind an identical-looking `0.00`.

## Data source: yfinance (no key, no approval wait)

`yfinance` scrapes Yahoo Finance's own endpoints — no API key, no signup,
no rate-limit tier to pick. `market_data.py` is the only file that touches
it:

- `fetch_option_chain` — calls, puts and the spot price for the nearest
  few expiries (`DEFAULT_MAX_EXPIRIES`, 4) — one request per expiry, since
  `yfinance` has no bulk endpoint. Row-by-row cleanup (missing/`NaN`
  fields) is `option_rows.py`, pure and tested, deliberately kept out of
  this file.
- `fetch_price_history` — a year of daily closes, what `momentum.py` needs.
- `fetch_news_headlines` — recent headline titles. Yahoo's news response
  shape has changed across `yfinance` versions (a flat `title` key, then a
  nested `content.title`); this tries both rather than assuming one, so a
  future schema change means fewer headlines found, not a crash.
- `fetch_sp500_tickers` — the S&P 500 constituent list, from Wikipedia
  rather than a bundled file; used by `discover` (above).

## Getting real data in

Same story as the CFB tool: this sandbox's network policy returns a 403
for Yahoo Finance's endpoints, confirmed by actually trying it (`curl: (7)
CONNECT tunnel failed, response 403`), not assumed. `market_data.py` has
never been exercised against a real response from in here.

**What should work**, following the exact pattern that was verified for
the CFB tool: run it from Google Colab, or your own machine — both are
full, unrestricted Python environments this network policy doesn't apply
to. No API key setup needed this time, which makes it simpler than the CFB
tool's Colab flow:

```bash
!git clone https://github.com/BonickWorldWide/learning.git
%cd learning/03-options-screener
!pip install -q -r requirements.txt
!cp watchlist.example.json watchlist.json
!python -m options_screener screen
```

**Verified against live data**: `discover` has now run for real from Colab
and surfaced two real bugs, both fixed — see "Real bugs this surfaced"
above. `screen` and `analyze` are written against the same `market_data.py`
and haven't individually hit a real run yet, so the same caveat applies to
them: the first real run may still surface something new, the way it did
for `discover` twice already.

## Data freshness, and when to actually run this

**It runs fine at any hour — 1am included — but what it returns is frozen
at the last close outside market hours**, not live:

- **Prices and option quotes** (bid/ask, last price) are whatever Yahoo
  last recorded when the market closed. At 1am that's the previous
  session's close; nothing moves again until the market reopens.
- **Open interest** is a once-a-day figure everywhere, not just here --
  exchanges settle and publish it once per session, so it isn't extra
  stale specifically at 1am.
- **Momentum** (`momentum.py`'s RSI, 20-day return, 50-day SMA) only ever
  uses *completed* daily closes, so it's identical whether you run at 1am
  or at noon the next day -- it only changes once a new session finishes.
- **News sentiment** isn't tied to market hours at all; overnight headlines
  still show up.
- **Implied volatility** is derived from the last quote, so it's frozen the
  same way prices are.

**Run it during market hours if you're deciding what to actually buy right
now.** Two things specifically depend on it:

1. The bid/ask a "cheap near-the-money" pick or a delta-band pick shows you
   is only the price you could actually transact at while the market is
   open. A price from last night's close may simply not be there anymore
   at the open -- stocks gap.
2. **Unusual volume** (`volume_signal.py`) is a running total that
   accumulates through the session. Checking right after the open can
   under-count a signal that only becomes "unusual" by the afternoon; a
   check late in the trading day sees a more complete picture, though real
   activity can also show up right at the open and be genuinely worth
   seeing early.

Running it at 1am (or any time outside market hours) is still a
legitimate way to use it -- it's exactly what shows you where things stood
at the last close, which is a reasonable way to decide what to look at
before the market opens. Just don't expect the specific premium it quotes
to still be sitting there once trading resumes.

## Usage

```bash
cd 03-options-screener
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp watchlist.example.json watchlist.json   # edit with your own tickers
cp config.example.json config.json          # optional, defaults are sane

python -m options_screener screen           # scans your whole watchlist
python -m options_screener discover         # scans the S&P 500 instead
python -m options_screener analyze AAPL     # full breakdown for one ticker
pytest
```

`watchlist.json` and `config.json` are gitignored, same as the fantasy
tool's `roster.json` — personal, not committed.

## Config knobs (`config.json`)

| key | default | meaning |
|---|---|---|
| `near_money_band_pct` | 0.05 | how close to spot counts as "near the money" |
| `cheap_max_premium` | 2.00 | ceiling for the cheap-contract screen |
| `pop_delta_min` / `pop_delta_max` | 0.10 / 0.30 | the delta band a "bound to pop" pick must fall in |
| `pop_max_premium` | 1.00 | ceiling for a "bound to pop" pick |
| `pop_min_score` | 0.6 | minimum composite score to rank in `screen` |
| `risk_free_rate` | 0.045 | constant rate fed into Black-Scholes |
| `min_days_to_expiry` | 7 | excludes contracts closer to expiry than this from both screens |
| `include_filings` | false | turns on SEC EDGAR fetching (8-K sentiment + 10-Q/10-K growth) |
| `edgar_contact_email` | `""` | your real contact email, required by SEC's fair-access policy when `include_filings` is on |

## Running the tests

```bash
pytest
```

All 92 tests are pure-logic, run in well under a second, and need no
network. `market_data.py` and `edgar_client.py` are the only untested
files, for the same reason as every network-touching file in this repo:
they need the real network to exercise for real, so they're kept as thin
as possible instead — all the actual logic (Greeks, momentum, sentiment
scoring, growth calculation) lives in pure, tested modules they call into.

## Where to take this next

- **Puts, symmetrically.** "Bound to pop" only looks at calls; a bearish
  mirror (momentum/sentiment/volume all leaning down, far-OTM puts by
  delta) is the same engine pointed the other way.
- **An earnings-date signal.** The original scope discussed an "upcoming
  known catalyst" signal (earnings, FDA dates) and deliberately shelved it
  for v1 — `yfinance` exposes `earnings_dates`, so it's a fourth component
  away rather than a new data source.
- **Backtesting**, same idea as the CFB tool's `backtest` command: replay
  the screen against historical options data and see whether a high score
  actually preceded a pop. Real historical options chains (not just stock
  price history) are harder to get for free than CFBD's game history was,
  so this needs its own data-source research before it's worth building.

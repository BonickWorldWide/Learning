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

The whole analysis engine is pure, unit-tested (63 tests, hand-verified
against a textbook Black-Scholes reference case), and has never touched
live data from inside this environment — `yfinance` (the data source, see
below) is blocked by the same network policy that blocked
CollegeFootballData.com and ESPN for the other two projects here. See
"Getting real data in."

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
average of three signals, each independently visible in the report:

- **Momentum** (`momentum.py`) — three simple technical reads: 20-day
  return, 14-day RSI, and whether the price is above its 50-day average.
  Each one votes bullish (1), bearish (0), or neutral (0.5); the score is
  the average of whichever ones have enough history to compute.
- **Sentiment** (`sentiment.py`) — a small, hand-curated positive/negative
  word list run against recent headlines (from `yfinance`'s news feed for
  that ticker), not a trained NLP model. It's a few dozen words anyone can
  read (`POSITIVE_WORDS` / `NEGATIVE_WORDS`), on purpose — explainable over
  clever. A ticker with fewer than 3 headlines is flagged
  `low_confidence` rather than silently trusted.
- **Unusual options volume** (`volume_signal.py`) — today's call volume
  against standing open interest. A ratio at or above 1.0 means today's
  volume alone exceeds everyone who already held a position — the classic
  "someone new just showed up" signal, computed straight from the option
  chain with no history needed.

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
prudent.

## Data source: yfinance (no key, no approval wait)

`yfinance` scrapes Yahoo Finance's own endpoints — no API key, no signup,
no rate-limit tier to pick. `market_data.py` is the only file that touches
it:

- `fetch_option_chain` — calls, puts and the spot price for the nearest
  few expiries (`DEFAULT_MAX_EXPIRIES`, 4) — one request per expiry, since
  `yfinance` has no bulk endpoint.
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

**This has not actually been run against live data yet** — say so plainly,
same as the CFB tool's own status before its first real Colab run. The
engine is unit-tested and the `yfinance` calls are written against its
documented response shapes, but the first real run may well surface a real
bug the way the CFB tool's rate-limiting and team-name-matching bugs were
found — by actually running it, not by reading the code. Report back what
happens.

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

## Running the tests

```bash
pytest
```

All 63 tests are pure-logic, run in well under a second, and need no
network. `market_data.py` is the only untested file, for the same reason
as every network-touching file in this repo: it needs the real network to
exercise for real, so it's kept as thin as possible instead.

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

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

**Every dollar figure is the total cost of one contract, never a bare
per-share quote.** A real user read a printed "$1.65" as the total cost of
one contract when it actually meant $165 (options are quoted per share but
always trade 100 shares at a time) — every screen and every config knob
now works in, and prints, the number you'd actually pay
(`OptionContract.total_cost`; see "A real bug" under Config knobs below).
`screen`/`discover` also lead with a **TOP PICKS** section — the
highest-scoring tickers that actually have a qualifying contract, each
with a one-line plain-English reason (`_rationale` in `cli.py`) — instead
of leaving you to compare fifteen per-ticker blocks yourself.

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
either side) priced at or under `max_premium` (a **per-share** price —
`config.py` converts the human-facing `cheap_max_contract_cost` for you,
see "Config knobs" below), sorted cheapest first. No signal, no scoring —
just "close to the money and cheap." Each result carries its own
Black-Scholes Greeks so you can see its delta before deciding, and every
printed line shows both the per-share price and the actual dollar cost of
one contract.

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
chain + price history + news, each) is thousands of requests, which risks
Yahoo throttling or blocking a scraping library with no official
rate-limit tier to fall back on. So it runs in two stages instead of one:

1. **Cheap prefilter** — every S&P 500 ticker, but only price history
   (`discover.prefilter_score`, momentum + affordability, no news and no
   option chain fetched at all). **One** request per ticker.
2. **Expensive stage** — only the top `--top-n` tickers (default 15) from
   the prefilter go on to a full option-chain fetch, real multi-source news,
   and the same `build_pop_candidate` scoring `screen` uses, so the printed
   report is identical in shape to `screen`'s.

**Sentiment isn't part of the prefilter at all**, which is a real design
change, not an oversight — see "Real bugs this surfaced" below for why: a
neutral sentiment score adds the exact same constant to every ticker, so
it can never change *which* tickers make the shortlist, only how expensive
getting there is. `discover.prefilter_score(momentum)` treats a missing
sentiment as neutral explicitly, so the ranking math is identical to
before, just without paying for a fetch that couldn't have changed the
outcome.

**Affordability *is* part of the prefilter**, and for the opposite reason:
unlike sentiment, a stock's price *can* change the ranking without ever
fetching an option chain, because Black-Scholes prices scale predictably
with the underlying price. `discover.affordability_score` estimates —
from the last close plus an assumed 35% IV — roughly what a contract in
the configured delta band would cost, and folds that in alongside
momentum. This is what stops the shortlist from being entirely $200-400+
mega-caps whose options can never fit a real cost cap while cheaper
stocks that could produce an actual pick never get considered — see "Real
bugs this surfaced" #9.

`market_data.fetch_sp500_tickers` pulls the constituent list straight from
Wikipedia's own table — always current, no bundled list here to drift out
of date as the index is reconstituted. A ticker with a dot in its symbol
(`BRK.B`) is rewritten with a hyphen (`BRK-B`), which is the form Yahoo
Finance actually uses; the raw Wikipedia spelling would fail to look the
ticker up at all. The same table's "Security" column gives a ticker →
company name map, threaded through to the expensive stage's news fetch
(see "News sources" below) for a much better Google News query than a
bare, sometimes single-letter ticker.

A pause between prefilter requests (`REQUEST_DELAY_SECONDS`, 0.5s) plus a
longer breather every `COOLDOWN_EVERY_N` tickers (100, 15s) are precautions
against exactly the kind of burst that got a real 429 out of
CollegeFootballData's API in the CFB tool — Yahoo has no published limit to
tune against, so neither is verified to actually clear a real throttle,
only sensible to try. That pacing now protects a much lighter loop than it
originally did (one plain GET per ticker, not up to four sequential
requests plus a retry sleep — see "Real bugs this surfaced"), so it hasn't
been loosened even though it's arguably being overly cautious for the
current, smaller request per ticker.

### Real bugs this surfaced

Nine, all from actually running `discover` in Colab rather than from
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
4. **Diagnosed, not yet confirmed or fixed.** After the `min_days_to_expiry`
   fix, a run with 10-17 day contracts *still* showed near-zero deltas
   (`+0.0000`) for options only 3-5% out of the money -- which shouldn't
   happen at that range for any realistic implied volatility. Checked
   directly: for one of the actual contracts printed (JNJ, $285 call, 10
   days, ~4.8% OTM), IV would need to be under about 8% to produce a delta
   that small — implausibly low for one stock, and this pattern held
   identically across 15 completely different companies (mega-cap pharma,
   cybersecurity growth names, hospitals) at once, which a real IV
   difference between them wouldn't produce. There's no unit conversion or
   scaling applied to `impliedVolatility` anywhere in this codebase between
   `yfinance` and `black_scholes_greeks`, so the leading (but *unconfirmed*
   -- said plainly, not verified) hypothesis is that Yahoo's own computed
   IV is unreliable for exactly this class of contract: thin,
   near-the-money, low-premium, likely not traded recently, which is what
   the cheap screen deliberately selects for. Rather than build a fix on a
   guess, the cheap and picked-contract report lines now also print the
   raw `impliedVolatility` value directly (`iv 12.3%`), so the next real
   run shows the actual number instead of requiring another round of
   inference. If it confirms implausibly low IVs, the real fix is
   probably deriving IV independently from the bid/ask midpoint (a reverse
   Black-Scholes solve) rather than trusting Yahoo's own figure --
   but that's a real amount of work, worth doing only once the cause is
   confirmed rather than assumed.

   **Update, largely resolved:** the next real run (with a raised premium
   cap, so it wasn't only picking the very cheapest/most-expiring-soon
   contracts) printed entirely realistic IVs across 15 different names --
   27.7% for ABBV, 48.6% for AMD, 21.3% for AAPL, 84.9% for BE -- each
   sensibly matching how volatile that kind of stock actually is. So the
   earlier near-zero deltas were mostly a symptom of the `min_days_to_expiry`
   bug (#3) and a too-tight cost cap compounding each other, not a
   separate IV data-quality problem. A narrower version of the original
   oddity is still visible on two specific tickers (AES and TECH showed
   2.6-8% IV on long-dated, deep-illiquid, dollar-cheap strikes) --
   consistent with the original hypothesis, just isolated to genuinely
   thin contracts rather than universal. Not worth a reverse-BS-solver for
   two names; worth watching for if it recurs more broadly.
5. `discover`'s prefilter loop hit `yfinance`'s own internal
   `"Failed to retrieve the news and received faulty response instead."`
   for roughly the back half of the S&P 500 (alphabetically T onward),
   all starting midway through the same run -- the classic shape of a
   burst throttle after some request-count threshold, not scattered bad
   luck per ticker. That message comes from inside `yfinance` itself (a
   swallowed JSON-decode failure, logged rather than raised), so
   `fetch_news_headlines`'s own `except Exception` never even saw
   anything to catch -- `get_news()` just quietly returned an empty list.
   Separately, tickers fetched *before* that block (including AAPL, one of
   the most continuously covered stocks that exists) also came back with
   zero usable headlines and no error at all -- implausible as "genuinely
   no news," and not explained by the throttle since they ran before it
   started. Rather than guess which of "throttled," "really no news," or
   "title-extraction silently matching nothing" was happening for which
   ticker, `fetch_news_headlines` now: retries once after a real pause
   when zero articles come back, and prints the raw article count plus the
   first article's actual keys whenever articles *are* returned but zero
   titles are extracted from them -- so the next run reports which
   explanation is real instead of requiring another guess. Pacing was also
   raised (`REQUEST_DELAY_SECONDS` 0.2s → 0.5s) and a periodic longer pause
   added (`COOLDOWN_EVERY_N` 100 tickers, `COOLDOWN_SECONDS` 15s) --
   neither is verified to actually clear a throttle Yahoo doesn't publish
   the shape of, only sensible to try given the same lesson already
   learned once with CollegeFootballData's API.

   **Update: it wasn't (just) a throttle.** `analyze AAPL` run completely
   in isolation -- no 500-ticker burst beforehand at all -- still came back
   with zero news articles after the retry. That rules out load as the
   sole explanation. Reading `yfinance`'s own `data.py`: `get_news()` sends
   an authenticated **POST** that needs a Yahoo session cookie + crumb,
   while `option_chain()` and `history()` (which worked fine for AAPL in
   the same run, real option data and all) are plain **GET**s that don't
   need one. Crumb/cookie acquisition for Yahoo's newer endpoints is a
   widely-reported pain point with `yfinance` generally, not something
   specific to this code. `fetch_news_headlines` now falls back to Yahoo's
   older RSS feed (`YAHOO_RSS_URL`, `_fetch_rss_headlines`) when
   `get_news()` comes back empty -- a plain, unauthenticated GET that
   doesn't touch that session machinery at all, so it's a structurally
   different path rather than a second attempt at the same one. Also
   unverified against live data -- Yahoo's RSS feeds have been trimmed back
   before and may not exist for every ticker.
6. **A real, isolated test settled it.** `analyze AAPL` run completely
   alone -- no 500-ticker burst beforehand -- still came back with zero
   news articles after the retry. That ruled out load as the *sole*
   explanation for #5 (the throttle finding still likely explains the
   mid-run block; this is a second, independent gap it doesn't cover).
   Added a further fallback and a genuinely different kind of source --
   see "News sources: three free fallbacks plus one paid option" below.
7. **A real timing report -- "12 minutes, 200 tickers in" -- traced the
   discover prefilter's slowness to two compounding causes, both fixed.**
   First, the retry in #5/#6 was designed for a *transient* throttle;
   #6 already showed the real cause is a structural auth problem
   (`get_news()` needs a Yahoo cookie + crumb), which a 2-second wait can't
   fix. That retry was firing on nearly every one of 500+ tickers --
   ~1000 seconds (500 × 2s) of guaranteed-wasted time, never once
   confirmed to help. Removed rather than shortened, since there was no
   evidence any delay there changes the outcome. Second, and bigger: the
   prefilter was fetching **full four-source news** for every one of ~500
   tickers just to compute a ranking that news couldn't actually change --
   a neutral sentiment score adds the identical constant to every ticker,
   so the shortlist was always going to come out the same with or without
   it. `discover.prefilter_score` now takes momentum alone (`sentiment`
   is optional and treated as neutral when omitted); the full news
   cascade only runs for the ~15 tickers that make the shortlist, in the
   expensive stage, where paying for it is easily worth it.
8. **Every single shortlisted ticker, across three separate real runs, came
   back with zero "bound to pop" picks** -- consistent enough to be worth
   checking the actual math rather than assuming a bug. It wasn't one: for
   ADI (~$400/share), a call with delta in [0.10, 0.30] costs roughly
   $210-$579 *per contract* -- nowhere near a $30 cap. Getting the premium
   down to $30 on a $400 stock means delta around 0.03, well below the
   0.10 floor. Those two settings are simply incompatible for anything
   priced much above $50-75/share, which is exactly why only the cheapest
   names in a shortlist (AES at $15, TECH at $75) ever produced a pick.
   `build_pop_candidate` now checks the delta band *before* the cost cap:
   when a call is in the band but too expensive, it reports the cheapest
   one's real cost and exactly what `pop_max_contract_cost` would need to
   be to see it, instead of repeating an unhelpful "no call found" on
   every single ticker. When nothing is in the band at all regardless of
   price, it says that distinctly too -- a different, rarer situation with
   a different fix (widen the delta range, not raise the cap).
9. **The prefilter's shortlist was blind to price.** #8's fix made a bad
   pick *legible*, but the underlying run was still real: fifteen
   momentum-ranked tickers came back as mostly $200-400+ names (ADI, AMAT,
   AAPL, GOOGL), where the math in #8 makes a cheap pop pick nearly
   impossible, while cheaper stocks that could plausibly have produced one
   (the AES/TECH pattern from #8) never got a look at all, because
   `discover.prefilter_score` ranked purely on momentum -- a stock's price
   never entered the ranking. The user's own framing of the fix: "they
   don't need to be expensive stocks, they can be cheaper stocks, as long
   as it meets all criteria."

   Fixed with `discover.affordability_score`, estimated from the spot price
   the prefilter already has for free (the last close from price history)
   plus an assumed market-average IV (35%, an approximation, documented as
   one) -- no option chain fetched. It reuses the same Black-Scholes math
   the rest of the tool trusts, inverted in closed form:
   `greeks.implied_strike_for_delta` solves for the strike that would
   produce the delta band's midpoint delta on this stock (via the inverse
   normal CDF, not a numerical search), and `black_scholes_greeks` prices
   that strike. The ratio of the configured cost cap to that estimated
   price is the score, capped at 1.0 -- a soft downweight, not a hard
   price cutoff, so an expensive stock with exceptional momentum can still
   outscore a flat, merely-affordable one. Verified against real numbers:
   at the default $30 cap / 0.10-0.30 delta band, a $20 stock scores 1.0
   (estimated contract cost ~$10.58), a $100 stock scores ~0.57 (~$52.89),
   and a $400 stock scores ~0.14 (~$211.56) -- the same order of magnitude
   as real ADI-vs-AES numbers seen in #8's actual runs.
   `discover.prefilter_score` takes it as a third optional component,
   averaged in alongside momentum and sentiment (sentiment already
   defaults to neutral when the prefilter doesn't fetch it; affordability
   is only added to the average when supplied, since there's no equally
   natural "neutral" affordability the way 0 is a neutral sentiment
   score).

## News sources: three free fallbacks, plus one optional paid one

`fetch_news_headlines` tries, in order, stopping at the first one that
returns anything: **yfinance's own feed** → **Yahoo's older RSS feed** →
**Google News RSS**. The first two are both Yahoo, and the second one
turned out not to route around the first one's real problem (see "Real
bugs this surfaced" #6) -- Google News is the one that's *structurally*
different: no Yahoo session or crumb involved at all, and it aggregates
thousands of publishers instead of being tied to one company's feed.

Google News needs a real search query, not just a bare ticker -- `"A"`
(Agilent) or `"V"` (Visa) as a literal search term returns near-random
noise. `discover` passes the actual company name, free: `fetch_sp500_tickers`
now also returns a ticker → name map from Wikipedia's "Security" column
(the same table it already fetches tickers from, so this costs nothing
extra), threaded through to the *expensive* stage's news fetch (news isn't
fetched in the prefilter loop at all -- see "Real bugs this surfaced" #7)
as `fetch_news_headlines(ticker, company_name=...)`. `screen`'s own
watchlist tickers don't have a company name lookup, so that path's Google
fallback searches on the bare ticker + "stock" instead -- noisier, but
still usually well short of the single-letter-ticker problem.

**Finnhub** (`finnhub_client.py`) is a fourth, optional path: a real
structured JSON API from an official financial-data provider, not scraped
HTML, gated on a free key the same "off until configured" way SEC EDGAR
is (`finnhub_api_key` in `config.json`, blank by default; a free key is at
finnhub.io/register). Unlike the three fallbacks above, Finnhub headlines
are always *added* to whatever the fallback chain found rather than only
used when everything else came back empty -- it's the most reliable
single source when configured, so there's no reason to wait for the others
to fail first.

**Verified against live data, and a real cap bug found doing it.** A real
Colab run with a Finnhub key configured came back with 257 headlines for
AAPL — one of the most heavily covered stocks that exists, and Finnhub's
company-news endpoint had no cap applied, unlike every other source here.
Two fixes: `fetch_finnhub_headlines` now sorts by `datetime` and caps to
`count` (10, matching the others) before returning, and `analyze`'s
console output (`_print_capped`) now shows the first 5 positive/negative
headlines and says how many more there are, rather than dumping the full
count to the terminal regardless of source.

The sentiment score itself was already working correctly through this —
+0.06 (near-neutral) over a genuinely mixed real sample (Nvidia buyback
enthusiasm and Apple stock gains against a CEO-layoffs rumor and a lawsuit)
is exactly what the lexicon should produce, not a bug.

**One more, from the capped re-run**: the exact same headline ("New Apple
CEO John Ternus is reportedly planning layoffs...") appeared twice in the
negative list, verbatim. Combining four independent sources means the same
wire story can get picked up by more than one of them -- a story getting
covered twice isn't twice the signal, it's the same signal, and counting it
twice quietly biases the average toward whichever story happened to get
syndicated the most rather than toward genuinely more numerous distinct
stories. `sentiment.score_headlines` now deduplicates
(case/whitespace-insensitive, order-preserving) before scoring, so
`headline_count` reflects distinct stories. This only catches exact
matches -- two outlets paraphrasing the same story slightly differently
("...as memory chip costs rise" vs. "...as costs rise", both real examples
from the same run) still count as separate headlines, which is a smaller,
known remaining gap rather than one this fix claims to solve.

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
- `fetch_news_headlines` — recent headline titles, cascading through three
  free sources (own feed → Yahoo RSS → Google News RSS) -- see "News
  sources" below for the full explanation and why they're structurally
  different rather than three tries at the same thing.
- `fetch_sp500_tickers` — the S&P 500 constituent list *and* a ticker →
  company name map, both from the same Wikipedia table rather than a
  bundled file; used by `discover` (above) and by the Google News
  fallback's search query.

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
| `cheap_max_contract_cost` | 200.00 | **total dollars to buy one contract** for the cheap-contract screen (want $30 total? set this to `30.00`, not `0.30`) |
| `pop_delta_min` / `pop_delta_max` | 0.10 / 0.30 | the delta band a "bound to pop" pick must fall in |
| `pop_max_contract_cost` | 100.00 | total dollars to buy one "bound to pop" contract, same units as above |
| `pop_min_score` | 0.6 | minimum composite score to rank in `screen` |
| `risk_free_rate` | 0.045 | constant rate fed into Black-Scholes |
| `min_days_to_expiry` | 7 | excludes contracts closer to expiry than this from both screens |
| `include_filings` | false | turns on SEC EDGAR fetching (8-K sentiment + 10-Q/10-K growth) |
| `edgar_contact_email` | `""` | your real contact email, required by SEC's fair-access policy when `include_filings` is on |
| `finnhub_api_key` | `""` | optional free key from finnhub.io -- adds a fourth, structured news source on top of the three free fallbacks |

### A real bug: dollars per share vs. dollars per contract

A real run set the premium cap to `30.00` expecting "$30 or less to buy,"
and got contracts back costing $165 -- because `cheap_max_premium` (as it
was named then) was a **per-share** price, and options always trade 100
shares at a time. `$1.65` on the screen was quietly `$165` in real money,
and nothing in the output ever showed that multiplication happening.

Two changes, not just an explanation in chat:

1. **The config keys are renamed and re-scaled**: `cheap_max_premium` /
   `pop_max_premium` are now `cheap_max_contract_cost` /
   `pop_max_contract_cost`, and they mean **total dollars for one
   contract** — the number a person actually has in mind. `config.py`
   converts to the per-share price the pure screening functions compare
   against (`Config.cheap_max_premium` / `Config.pop_max_premium` are now
   computed *properties*, not stored fields) — nothing below `config.py`
   had to change, or ever needs to know contract sizes exist.
2. **Every printed price shows both numbers**: `OptionContract.total_cost`
   (`mid_price * 100`) is now printed alongside every per-share price,
   everywhere a contract shows up in `screen`, `discover`, or `analyze`
   output — `$0.30/share ($30/contract)`, never a bare `$0.30` that could
   be misread as the total.

## Running the tests

```bash
pytest
```

All 113 tests are pure-logic, run in well under a second, and need no
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

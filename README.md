# Learning

My repo for learning to code with AI as a pair programmer — building real,
working projects instead of tutorials, with the goal of picking up solid
software habits and eventually getting comfortable with AI/ML tooling.

Each numbered folder is a self-contained project. They get a little harder
and introduce a few new concepts each time. All of them are things I'm
actually interested in, not made-up exercises.

## Projects

| # | Project | Interest | Concepts |
|---|---------|----------|----------|
| 01 | [Fantasy Lineup Advisor](01-fantasy-lineup/) | Fantasy Football | `pandas`, reconciling messy real-world data, separating I/O from logic, keeping secrets out of git |
| 02 | [College Football Matchup Analyzer](02-cfb-matchup/) | College Football | Monte Carlo simulation, an explainable weighted model, two-layer data fetching for strength-of-schedule |
| 03 | [Options Screener](03-options-screener/) | Finance | Black-Scholes from scratch, an explainable multi-signal score, lexicon-based sentiment |
| 04 | Book Narrator (TBD) | Reading / Audio | not decided yet — see below |

01, 02 and 03 exist so far — the rest are the roadmap and will fill in one
at a time. Project 01 is working and complete, just on pause while 02 gets
built. Project 02's and 03's analytical engines are fully built and
tested, but neither has run against real data yet — each README explains
why and what that takes. Project 04 is placeholder — a tool that turns any
book into narrated audio, not scoped out yet.

## How this repo is organized

- Every project is fully self-contained in its own folder: its own
  `README.md`, its own code, its own tests. Nothing is shared between them
  on purpose — each one should be readable on its own.
- Every project has tests. Not because the code is complicated, but because
  writing tests early is the habit worth building, and it's much easier to
  learn on something small than to retrofit it onto something big later.
- Python only for now (stdlib first, a well-known library like `pytest` or
  `scikit-learn` only when it's actually teaching something new).

## Running things

Each project's own `README.md` has exact commands. In general:

```bash
cd 01-fantasy-lineup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m fantasy_lineup --help
pytest
```

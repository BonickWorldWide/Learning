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
| 01 | [Golf Tracker](01-golf-tracker/) | Golf | functions, dataclasses, JSON file storage, CLI args, unit tests |
| 02 | Budget Tracker | Finance | classes, CSV, aggregating/summarizing data |
| 03 | Card Game (Blackjack) | Games | control flow, randomness, object-oriented design |
| 04 | File Organizer | Automation | working with the filesystem, scheduling, small scripts that save time |
| 05 | Reading List Recommender | AI / Reading | intro to `scikit-learn`, working with a real (tiny) dataset |

Only 01 exists so far — the rest are the roadmap and will fill in one at a
time.

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
cd 01-golf-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m golf_tracker --help
pytest
```

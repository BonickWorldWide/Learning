# 01 · Golf Tracker

A command-line tool to log golf rounds and see your stats over time. No
database, no server — just a JSON file on disk and a well-organized Python
package around it.

## What this teaches

- **Dataclasses** (`models.py`) — a clean way to represent a record (a
  `Round`) without hand-writing `__init__`/`__eq__`.
- **File I/O with JSON** (`storage.py`) — reading and writing structured
  data to disk, and converting between Python objects and JSON-friendly
  dicts.
- **A real CLI with `argparse`** (`cli.py`) — subcommands (`add`, `list`,
  `stats`), required/optional flags, and defaults.
- **Unit tests with `pytest`** (`tests/`) — using `tmp_path` so tests never
  touch your real data file, and testing pure logic (`stats.py`) completely
  separately from I/O.

## Setup

```bash
cd 01-golf-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python -m golf_tracker add --course "Pebble Beach" --par 72 --strokes 88
python -m golf_tracker add --course "St Andrews" --par 72 --strokes 84 --date 2026-06-10
python -m golf_tracker list
python -m golf_tracker stats
```

Rounds are stored in `data/rounds.json` (git-ignored — it's your personal
data, not part of the codebase).

## Running the tests

```bash
pytest
```

## Where to take this next

Some natural next steps, if you want to keep extending this one before
moving to project 02:

- A `--handicap` command that estimates a handicap index from your last N
  rounds (this is genuinely a bit of real math — worth looking up the USGA
  formula).
- Per-hole scores instead of just a total, which would mean a new
  `Hole` model nested inside `Round`.
- Export to CSV for opening in a spreadsheet.

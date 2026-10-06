#!/usr/bin/env bash
# Re-run the whole project end to end (needs data/raw/ from Kaggle, see README).
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python3}
$PY src/prepare_data.py     # Part 1: clean + aggregate -> data/processed
$PY src/forecast.py         # Part 2: backtest + 12-week forecast
$PY src/optimize.py         # Part 3: LP scenarios -> data/outputs
$PY src/make_outputs.py     # Part 4: Tableau CSVs + charts

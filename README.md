# 🏎️ F1 2026 Season Tracker

A Python data project tracking the 2026 Formula 1 season with standings, visualizations, and a historical comparison against the 2022 ground effect regulation era.

## Project Goals
- Practice pandas data wrangling with real sports data
- Build a repeatable weekly data pipeline
- Create interactive Plotly visualizations
- Export data for Tableau BI reporting
- Integrate LLM APIs and F1 data APIs in later phases

## Structure
```
f1-2026-season/
├── data/
│   ├── raw/          # Per-race CSVs (race results + qualifying)
│   ├── processed/    # Merged season master files
│   └── baseline/     # 2022 historical comparison data
├── exports/          # Tableau extract CSVs
├── notebooks/        # Main Colab analysis notebook
└── README.md
```

## Weekly Workflow
1. Add new race CSV to `data/raw/`
2. Run all cells in the notebook
3. Upload updated exports to Tableau
4. Commit and push to GitHub

## Phase Roadmap
- **Phase 1** (Current) — Manual CSV pipeline + pandas + Plotly + Tableau export
- **Phase 2** — Replace CSVs with Ergast / OpenF1 API calls
- **Phase 3** — LLM API integration for post-race narrative generation
- **Phase 4** — Natural language query interface for the season data

## Data Schema
See notebook Section 2 comments for full column definitions.

Key join key: `track_id` — used to match 2026 races to their 2022 equivalents.

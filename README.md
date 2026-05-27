# 🧭 PolarisBI

AI Cockpit untuk IT Business Analyst Asuransi.
Translate pertanyaan Bahasa Indonesia → SQL → insight, dengan opsi on-prem deployment.

## Stack
- Streamlit (UI)
- DuckDB (in-process OLAP)
- Claude API (text-to-SQL via claude-sonnet-4-6)
- python-pptx + matplotlib (deck export — Day 3)

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Setup
cp .env.example .env
# Edit .env: isi ANTHROPIC_API_KEY

# Seed data + initialize DB
python database/seed_data.py
python database/setup.py

# Run app
streamlit run app.py
```

## Status
- [x] Day 1: SQL agent, DuckDB seed, Streamlit UI
- [ ] Day 2: Auto chart Plotly, KPI glossary, refinements
- [ ] Day 3: PPTX export (deck design system ready)
- [ ] Day 4: Polish, deploy ke Streamlit Cloud, demo prep

## Architecture

```
User (Bahasa Indonesia) → Streamlit → Claude → SQL → DuckDB → Display
```

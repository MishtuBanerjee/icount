# CLAUDE.md — icount

## Project Overview

**icount** is a personalized health logging system designed to track, monitor, and analyze health information for chronic conditions (originally epilepsy). The project provides:

1. **A coding protocol** — for structuring qualitative and quantitative health observations
2. **A CSV data format** — 11-column schema compatible with spreadsheets and analysis tools
3. **Basic calculations** — count-based ratios for identifying correlations and trends

The project is designed to be cloned and customized by individuals managing chronic health conditions.

---

## Repository State

This repository is currently in the **documentation/specification phase**. As of the latest commit:

- No implementation code exists yet
- The `README.md` contains the full design specification
- The `.gitignore` is configured for a Python project

All future implementation should follow the design outlined in `README.md`.

---

## Data Format

The core data structure is a flat CSV file with 11 columns:

| Column | Description |
|---|---|
| `Date` | Date of observation |
| `Time` | Time of observation |
| `Event` | The event being observed (e.g., seizure, medication dose) |
| `ObservationID` | Unique identifier for the observation |
| `ObservationType` | Category of observation (qualitative vs. quantitative) |
| `ObservedVariable` | The variable being measured or coded |
| `ObservationValue` | The value of the observed variable |
| `ObservationConfidence` | Confidence level in the observation |
| `Observer` | Who made the observation |
| `Subject` | Who was observed |
| `Comments` | Free-text notes |

This schema follows tidy data principles (Wickham 2014): each row is one observation, each column is one variable.

---

## Data Model

The relational entities underlying the CSV schema:

- **People** — observers and subjects (with roles)
- **Observations** — timestamped events with an observation type
- **Variables** — what is being measured or coded per observation
- **Values & Confidence** — the measured/coded value and certainty
- **Comments** — a special variable type for free-text annotation

---

## Development Conventions

### Language

This is a **Python** project (inferred from `.gitignore`). When implementing code:

- Use Python 3.x
- Follow PEP 8 style conventions
- Prefer simple, readable code over clever abstractions — the target users are non-programmers managing health data

### Project Philosophy

- **No assumed data science knowledge** — all calculations should be explainable as simple count ratios doable by hand or in a spreadsheet
- **Flexibility over rigidity** — the coding protocol allows qualitative and quantitative observations; implementation should preserve this flexibility
- **CSV-first** — the data format must remain compatible with standard spreadsheets (Excel, LibreOffice Calc, Google Sheets)
- **Customizability** — the system is a template; avoid hardcoding domain-specific assumptions that would prevent users from adapting it

### File Structure (when implementing)

Follow a conventional Python project layout:

```
icount/
├── icount/           # main package
│   ├── __init__.py
│   ├── data.py       # CSV I/O and data model
│   ├── coding.py     # coding protocol logic
│   └── calc.py       # basic calculations
├── tests/            # unit tests
├── docs/             # documentation
├── requirements.txt
├── setup.py or pyproject.toml
├── README.md
├── LICENSE
└── CLAUDE.md
```

### Dependencies

No dependencies are currently declared. When adding dependencies:

- Prefer the Python standard library where possible
- Likely candidates: `csv` (stdlib), `pandas` (data manipulation), `pytest` (testing)
- Document all dependencies in `requirements.txt` or `pyproject.toml`

### Testing

- Write tests in `tests/` using `pytest`
- Test data I/O, coding protocol validation, and calculation correctness
- The CSV format is the contract — test round-trip fidelity

---

## Git Conventions

### Commit Message Style

Based on existing commit history, messages follow this pattern:

```
<File/Component> <action> <description> <YYYYMMDD> <initials>
```

Examples from history:
- `Readme 20151007 mb`
- `Readme update protocol_initial 20151001 mb`
- `Readme.md update add_Good 20150908 mb`

For new development, use clear imperative messages, e.g.:
- `Add CSV reader for observation data`
- `Fix confidence value validation`

### Branches

- `master` — stable/main branch
- Feature branches follow `claude/<description>` or similar naming

---

## Key References

The analytical approach is grounded in these sources (see README for full citations):

- **Tidy Data** (Wickham 2014) — informs the CSV schema design
- **Think Bayes** (Downey 2012) — Bayesian reasoning for observation analysis
- **Modelling Count Data** (Hilbe 2014) — statistical basis for the basic calculations
- **Bijou et al. 1968** — behavioral observation methodology (ABC tracking)
- **Meadows 2008** — systems thinking applied to chronic condition management
- **Pearl 2000** — causal reasoning framework for interpreting correlations

---

## Working with This Repository

### Adding New Features

1. Read `README.md` in full before making changes — it is the specification
2. Keep the CSV format as the primary interface; all tools should read/write valid icount CSV files
3. Any new calculated metrics should be explainable in plain language in the docs

### Common Tasks

- **Adding a calculation**: implement in `calc.py`, add plain-language explanation to docs
- **Extending the coding protocol**: update both code and the protocol documentation
- **Changing the data schema**: treat this as a breaking change — update README, all I/O code, and tests together

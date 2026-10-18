# Partidos Soccer Manager

A football management simulation for the web, in the style of Football Manager: run a club through seasons, with squad management, tactics, transfers, contracts, training, youth academy and a minute-by-minute match engine.

## Features

- **Match engine:** minute-by-minute simulation with tactical modifiers (formation, mentality) and AI teams that adjust their approach to the scoreline
- **Transfer market:** offers, negotiations, loans and transfer windows; AI clubs sign players for their weakest positions and bid for yours
- **Contracts and economy:** wages, contract negotiation, club finances and board expectations
- **Squad development:** weekly training, individual development, injuries, ageing and retirements
- **Competitions:** leagues, cups, tournaments and national teams
- **Multi-club careers:** start a career, manage several clubs, talk to players and staff
- **3D pitch view** built with Three.js
- **Data packs:** load league and player data from external packs, with validated formats and ratings

All generated data is fictional: player names, clubs and attributes are created by the game's own generator, never copied from licensed databases.

## Tech

| Layer | Stack |
|---|---|
| Frontend | React 19, Vite, React Router, Tailwind CSS 4, Three.js |
| Backend | Python, FastAPI, SQLAlchemy (async), Pydantic |
| Database | PostgreSQL (Neon) or SQLite for local development |
| Tests | pytest |

## Architecture

```
api/routers/      20 FastAPI routers, one per domain (transfers, tactics, simulation, contracts, academy...)
engine/           13 simulation engines (match, tactics, transfers, contracts, training, injuries, season, AI...)
models.py         SQLAlchemy ORM models
schemas.py        Pydantic request/response schemas
pack_*.py         data pack loading, formats, ratings, contracts and market values
seed.py           generates a fictional league to start playing
tests/            pytest suite for the API and data packs
soccer-frontend/  React app: 22 pages and 20+ reusable components
```

The game logic lives in the `engine/` modules and is independent of the API layer, so each system (match, transfers, training...) can be tested and changed on its own.

## Run locally

**Backend**

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux
pip install -r requirements.txt

cp .env.example .env            # set DATABASE_URL (or use SQLite: sqlite+aiosqlite:///./soccer.db)
python seed.py                  # create a fictional league
uvicorn main:app --reload       # API docs at http://127.0.0.1:8000/docs
```

**Frontend**

```bash
cd soccer-frontend
npm install
npm run dev
```

**Tests**

```bash
pytest
```

## Development notes

Detailed development notes (in Spanish) are in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

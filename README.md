# Warframe Market Set Profit Analyzer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/react-19-61dafb.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9+-3178c6.svg)](https://www.typescriptlang.org/)

A full-stack app for analyzing Warframe Prime set profitability using live data from [warframe.market](https://warframe.market).

The backend continuously gathers market data, scores opportunities with strategy-aware risk/liquidity logic, and stores historical runs in SQLite. The frontend provides a live dashboard, deep analysis views, historical run explorer, and JSON export.

## Highlights

- Continuous background analysis polling on backend startup
- Live progress streaming over SSE (`/api/analysis/progress`)
- Dual execution assumptions:
  - `instant`: sell to buy orders / buy from sell orders
  - `patient`: list at lowest sell / buy at highest bid
- Strategy profiles:
  - `safe_steady`
  - `balanced`
  - `aggressive`
- Composite scoring with trend, volatility, ROI, volume, and liquidity factors
- Historical run storage and replay (`/api/history/{run_id}/analysis`)
- OpenAPI-driven frontend API types (`frontend/src/api/types.ts`)

## Tech Stack

- Backend: FastAPI, Pydantic, httpx, aiosqlite
- Frontend: React 19, TypeScript, Vite, TanStack Query, Zustand, Recharts, Framer Motion
- Tooling: Ruff, Pytest, Playwright, openapi-typescript

## Prerequisites

- Python 3.12+
- Node.js 22+
- npm

## Quick Start

1. Clone the repo

```bash
git clone https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer.git
cd Warframe-Market-Set-Profit-Analyzer
```

2. Install backend dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt -r requirements-test.txt
cd ..
```

3. Install frontend + root Node dependencies

```bash
npm install
npm --prefix frontend install
```

4. Start both backend and frontend

```bash
npm run dev
```

Default local URLs:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Commands

### Root (`package.json`)

- `npm run dev` - run backend + frontend together
- `npm run dev:backend` - run backend only
- `npm run dev:frontend` - run frontend only
- `npm run generate:api-types` - regenerate frontend API types from backend OpenAPI
- `npm run generate:api-types:check` - check if generated API types are up to date
- `npm run lint:backend` - run Ruff checks
- `npm run format:backend` - format + autofix backend code with Ruff

### Backend

Run from `backend/`:

- `pytest` - run backend tests

### Frontend

Run from `frontend/`:

- `npm run dev` - start Vite dev server
- `npm run build` - type-check + production build
- `npm run preview` - preview production build
- `npm run lint` - run ESLint
- `npm run test:e2e` - run Playwright tests
- `npm run test:e2e:headed` - headed Playwright run
- `npm run test:e2e:ui` - Playwright UI mode
- `npm run test:e2e:debug` - Playwright debug mode

## Configuration

Common backend variables (see `.env.example`):

| Variable | Default | Description |
| --- | --- | --- |
| `DEBUG` | `false` | Enable debug logging |
| `DATABASE_PATH` | `cache/market_runs.sqlite` | SQLite file path |
| `CACHE_DIR` | `cache` | Cache directory |
| `RATE_LIMIT_REQUESTS` | `3` | API requests allowed per window |
| `RATE_LIMIT_WINDOW` | `1.0` | Rate limit window in seconds |
| `REQUEST_TIMEOUT` | `10` | Upstream API request timeout (seconds) |
| `ANALYSIS_TIMEOUT` | `600` | Analysis timeout budget (seconds) |
| `CORS_ORIGINS` | localhost list | Comma-separated allowed origins |

Additional backend variables supported by `backend/app/config.py`:

- `APP_NAME`, `APP_VERSION`, `ENVIRONMENT`, `API_PREFIX`
- `DATABASE_URL` (optional SQLite URL form)
- `CACHE_BACKEND`, `CACHE_FILE`, `CACHE_LRU_MAX_ENTRIES`
- `WARFRAME_MARKET_BASE_URL`, `WARFRAME_MARKET_V1_URL`, `WARFRAME_MARKET_V2_URL`
- `DEFAULT_PROFIT_WEIGHT`, `DEFAULT_VOLUME_WEIGHT`
- `ANALYSIS_POLL_INTERVAL_SECONDS` (optional startup polling interval override)

Frontend variables:

- `VITE_API_URL` (default: `/api`)
- `VITE_DEBUG` (`true` to force verbose API logs)

## API Overview

Base prefix is `/api` by default.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/analysis` | Get latest analysis or run one |
| `POST` | `/api/analysis` | Trigger background analysis |
| `GET` | `/api/analysis/status` | Current analysis status |
| `GET` | `/api/analysis/progress` | Live SSE progress stream |
| `POST` | `/api/analysis/rescore` | Re-score using another strategy/mode |
| `GET` | `/api/analysis/strategies` | Available strategy profiles |
| `GET` | `/api/history` | Paginated historical runs |
| `GET` | `/api/history/{run_id}` | Run detail summary |
| `GET` | `/api/history/{run_id}/analysis` | Full historical analysis payload |
| `GET` | `/api/sets` | Known set list |
| `GET` | `/api/sets/{slug}` | Set detail |
| `GET` | `/api/sets/{slug}/history` | Set trend history |
| `GET` | `/api/stats` | Database + cache stats |
| `GET` | `/api/stats/health` | Health check |
| `GET` | `/api/export` | Export all data as JSON payload |
| `GET` | `/api/export/file` | Download JSON export file |
| `GET` | `/api/export/summary` | Export metadata summary |

## Scoring Model

Core formula (strategy-adjusted):

```text
Score = (Profit * log10(Volume)) * ROI_factor * TrendMultiplier / VolatilityPenalty
```

Then a liquidity multiplier is applied. Strategy profiles adjust how strongly ROI, trend, and volatility affect the final score and enforce different minimum volume thresholds.

## Project Layout

```text
.
├── backend/
│   ├── app/
│   │   ├── api/routes/        # FastAPI route handlers
│   │   ├── core/              # Scoring, stats, cache, utilities
│   │   ├── db/                # Async SQLite layer
│   │   ├── models/            # Pydantic schemas
│   │   ├── services/          # Analysis + warframe.market clients
│   │   ├── config.py
│   │   └── main.py
│   ├── tests/
│   ├── requirements.txt
│   └── requirements-test.txt
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   └── store/
│   ├── tests/e2e/
│   └── package.json
├── scripts/
│   ├── export_openapi_schema.py
│   └── generate-api-types.mjs
├── cache/                     # Runtime SQLite/cache artifacts (gitignored)
├── package.json               # Root orchestration scripts
├── pyproject.toml             # Ruff config
└── .env.example
```

## Data Storage

- Runtime DB defaults to `cache/market_runs.sqlite`
- Cache and DB artifacts under `cache/` and `backend/cache/` are gitignored
- Export file endpoint writes `cache/market_data_export.json` before streaming

## Notes

- Docker/Compose files were intentionally removed after migration to non-container local/runtime workflows.
- If backend and frontend are served from different origins in development, set `VITE_API_URL` explicitly.

## License

MIT. See [LICENSE](LICENSE).

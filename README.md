# Warframe Market Set Profit Analyzer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/react-19-61dafb.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9+-3178c6.svg)](https://www.typescriptlang.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)](https://www.docker.com/)

A modern full-stack web application for analyzing Prime set profitability in Warframe using real-time market data from [Warframe Market](https://warframe.market). Features an interactive dark-themed dashboard with charts, real-time analysis progress, and historical trend tracking.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Docker Deployment](#docker-deployment)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Tech Stack](#tech-stack)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## Features

### Real-Time Market Analysis
- **Live Pricing Data**: Fetches current lowest prices for Prime sets and individual parts
- **48-Hour Volume Analysis**: Trading volume data to identify active vs. stagnant markets
- **Comprehensive Market Coverage**: Analyzes all available Prime sets automatically
- **Historical Data Tracking**: SQLite database tracks profit and price trends over time
- **Progress Streaming**: Real-time SSE updates during analysis

### Interactive Dashboard
- **Dark Theme UI**: Custom color scheme optimized for extended use
- **Profit Charts**: Visual bar charts of top profitable sets
- **Volume Charts**: Trading activity visualization
- **Sortable Tables**: Sort by score, profit, volume, or ROI
- **Expandable Rows**: Detailed part breakdown for each set

### Advanced Scoring System
- **Geometric Scoring Model**: `Score = (Profit * log10(Volume)) * ROI * TrendMultiplier / VolatilityPenalty`
- **Strategy Profiles**: Safe & Steady, Balanced, Aggressive - each adjusts how factors contribute to score
- **Trend & Volatility Analysis**: Evaluates price stability and market direction
- **Real-Time Rescoring**: Switch strategies without re-fetching data

### Full REST API
- **FastAPI Backend**: Modern async Python API
- **OpenAPI Documentation**: Auto-generated at `/docs`
- **Background Tasks**: Long-running analysis runs asynchronously
- **Export Capabilities**: JSON export of all analysis data

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 22+
- npm or yarn

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer.git
   cd Warframe-Market-Set-Profit-Analyzer
   ```

2. **Start the Backend**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
   Backend runs at http://localhost:8000

3. **Start the Frontend** (in a new terminal)
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Frontend runs at http://localhost:5173

4. **Open the application**

   Navigate to http://localhost:5173 in your browser.

## Docker Deployment

Deploy the entire stack with Docker Compose:

```bash
# Build and start containers
docker-compose up -d

# View logs
docker-compose logs -f

# Stop containers
docker-compose down
```

Services:
- **Frontend**: http://localhost:80
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### Environment Variables

Copy `.env.example` to `.env` and configure as needed:

```bash
cp .env.example .env
```

## Project Structure

```
Warframe-Market-Set-Profit-Analyzer/
├── backend/
│   ├── app/
│   │   ├── api/routes/        # FastAPI endpoints
│   │   │   ├── analysis.py    # /api/analysis - run analysis, get results
│   │   │   ├── history.py     # /api/history - historical runs
│   │   │   ├── sets.py        # /api/sets - set information
│   │   │   ├── stats.py       # /api/stats - database statistics
│   │   │   └── export.py      # /api/export - data export
│   │   ├── core/              # Business logic
│   │   │   ├── scoring.py     # Geometric scoring engine
│   │   │   ├── strategy_profiles.py  # Trading strategies
│   │   │   ├── profit_calculator.py  # Margin calculations
│   │   │   ├── rate_limiter.py       # API throttling
│   │   │   └── cache_manager.py      # Data caching
│   │   ├── services/          # External integrations
│   │   │   ├── warframe_market.py    # Market API client
│   │   │   └── analysis_service.py   # Analysis orchestration
│   │   ├── models/schemas.py  # Pydantic models
│   │   ├── db/database.py     # Async SQLite operations
│   │   ├── config.py          # Settings management
│   │   └── main.py            # FastAPI application
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/               # API client & types
│   │   ├── components/        # React components
│   │   │   ├── layout/        # Header, Layout
│   │   │   ├── analysis/      # ProfitTable, ScoreBreakdown
│   │   │   ├── charts/        # ProfitChart
│   │   │   └── common/        # Button, Card, Loading
│   │   ├── pages/             # Dashboard, Analysis, History, Export
│   │   ├── hooks/             # useAnalysisProgress
│   │   ├── store/             # Zustand state management
│   │   └── App.tsx            # Root component
│   ├── package.json
│   ├── nginx.conf             # Production server config
│   └── Dockerfile
├── cache/                     # Runtime data (gitignored)
├── docker-compose.yml
├── .env.example
└── LICENSE
```

## API Reference

### Analysis Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/analysis` | Get latest analysis or run new if none exists |
| `POST` | `/api/analysis` | Trigger background analysis |
| `GET` | `/api/analysis/status` | Get current analysis status (JSON) |
| `GET` | `/api/analysis/progress` | Stream analysis progress (SSE) |
| `POST` | `/api/analysis/rescore` | Rescore results with new strategy |
| `GET` | `/api/analysis/strategies` | List available strategy profiles |

### Data Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/history` | List all historical analysis runs |
| `GET` | `/api/history/{run_id}` | Get specific run details |
| `GET` | `/api/sets` | List all known Prime sets |
| `GET` | `/api/sets/{slug}` | Get specific set details |
| `GET` | `/api/stats` | Database statistics |
| `GET` | `/api/export` | Export all data as JSON |

### API Documentation

Interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug logging |
| `DATABASE_PATH` | `cache/market_runs.sqlite` | SQLite database location |
| `CACHE_DIR` | `cache` | Cache directory path |
| `RATE_LIMIT_REQUESTS` | `3` | Max requests per window |
| `RATE_LIMIT_WINDOW` | `1.0` | Rate limit window (seconds) |
| `REQUEST_TIMEOUT` | `10` | HTTP request timeout (seconds) |
| `ANALYSIS_TIMEOUT` | `600` | Max analysis duration (seconds) |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Allowed CORS origins |

### Strategy Profiles

The scoring engine uses strategy profiles that adjust how each factor contributes to the final score:

| Strategy | Description | Best For |
|----------|-------------|----------|
| **Safe & Steady** | Strong volatility penalty, lower trend emphasis. Requires higher liquidity (50+ volume) | Risk-averse traders seeking stable profits |
| **Balanced** | Equal consideration of all factors. Moderate volume threshold (10+) | General trading, most users |
| **Aggressive** | Tolerates volatility, emphasizes ROI and positive trends. Lower volume acceptable (5+) | Experienced traders seeking high gains |

## Tech Stack

### Backend
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern async Python web framework
- **[Pydantic](https://docs.pydantic.dev/)** - Data validation and settings
- **[httpx](https://www.python-httpx.org/)** - Async HTTP client
- **[aiosqlite](https://aiosqlite.omnilib.dev/)** - Async SQLite database
- **[uvicorn](https://www.uvicorn.org/)** - ASGI server

### Frontend
- **[React 19](https://react.dev/)** - UI framework
- **[TypeScript](https://www.typescriptlang.org/)** - Type-safe JavaScript
- **[Vite](https://vitejs.dev/)** - Build tool and dev server
- **[Tailwind CSS](https://tailwindcss.com/)** - Utility-first styling
- **[Zustand](https://zustand-demo.pmnd.rs/)** - Lightweight state management
- **[TanStack Query](https://tanstack.com/query/)** - Server state management
- **[Recharts](https://recharts.org/)** - Chart library
- **[React Router](https://reactrouter.com/)** - Client-side routing

### Infrastructure
- **[Docker](https://www.docker.com/)** - Containerization
- **[Nginx](https://nginx.org/)** - Reverse proxy and static serving

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details on:

- Setting up the development environment
- Code style and conventions
- Pull request process
- Areas where help is needed

### Quick Contribution Ideas
- Add test coverage (pytest for backend, Vitest for frontend)
- Performance optimizations
- New analysis metrics or visualizations
- Documentation improvements

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Warframe Market](https://warframe.market) for providing the excellent public API
- [Digital Extremes](https://www.digitalextremes.com/) for creating Warframe
- The Warframe trading community for inspiration

---

**Happy Trading, Tenno!**

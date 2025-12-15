# Warframe Market Set Profit Analyzer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/react-19-61dafb.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)

A modern full-stack web application for analyzing Prime set profitability in Warframe using real-time market data from [Warframe Market](https://warframe.market). Features a beautiful dark-themed dashboard with interactive charts, real-time analysis, and historical trend tracking.

## Features

### Real-Time Market Analysis
- **Live Pricing Data**: Fetches current lowest prices for Prime sets and individual parts
- **48-Hour Volume Analysis**: Trading volume data to identify active vs. stagnant markets
- **Comprehensive Market Coverage**: Analyzes all available Prime sets automatically
- **Historical Data Tracking**: SQLite database tracks profit and price trends over time

### Interactive Dashboard
- **Beautiful Dark Theme**: Custom color scheme (#080206, #9FBCAD, #7A9DB1, #9681AC)
- **Profit Charts**: Visual bar charts of top profitable sets
- **Volume Charts**: Trading activity visualization
- **Sortable Tables**: Click to sort by score, profit, volume, or ROI
- **Expandable Rows**: Detailed part breakdown for each set

### Advanced Scoring System
- **Weighted Scoring Algorithm**: Combines profit and volume with customizable weights
- **Real-Time Rescoring**: Apply new weights without re-fetching data
- **Preset Strategies**: Balanced, Profit Focus, Volume Focus
- **Interactive Sliders**: Easy weight adjustment

### Full REST API
- **FastAPI Backend**: Modern async Python API
- **OpenAPI Documentation**: Auto-generated at `/docs`
- **Background Tasks**: Long-running analysis runs asynchronously

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

3. **Start the Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Frontend runs at http://localhost:5173

### Docker Deployment

```bash
docker-compose up -d
```

This starts:
- Backend API at http://localhost:8000
- Frontend at http://localhost:80

## Project Structure

```
Warframe-Market-Set-Profit-Analyzer/
├── backend/
│   ├── app/
│   │   ├── api/routes/        # FastAPI endpoints
│   │   │   ├── analysis.py    # /api/analysis
│   │   │   ├── history.py     # /api/history
│   │   │   ├── sets.py        # /api/sets
│   │   │   ├── stats.py       # /api/stats
│   │   │   └── export.py      # /api/export
│   │   ├── core/              # Business logic
│   │   │   ├── rate_limiter.py
│   │   │   ├── profit_calculator.py
│   │   │   ├── scoring.py
│   │   │   └── normalization.py
│   │   ├── services/          # API clients
│   │   │   ├── warframe_market.py
│   │   │   └── analysis_service.py
│   │   ├── models/schemas.py  # Pydantic models
│   │   ├── db/database.py     # Async SQLite
│   │   ├── config.py          # Settings
│   │   └── main.py            # FastAPI app
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/               # API client & types
│   │   ├── components/        # React components
│   │   │   ├── layout/
│   │   │   ├── analysis/
│   │   │   ├── charts/
│   │   │   └── common/
│   │   ├── pages/             # Page components
│   │   ├── store/             # Zustand state
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── cache/                     # Data persistence
├── docker-compose.yml
└── .env.example
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analysis` | Run or get latest analysis |
| POST | `/api/analysis` | Trigger background analysis |
| GET | `/api/analysis/status` | Get analysis progress |
| POST | `/api/analysis/rescore` | Rescore with new weights |
| GET | `/api/history` | List historical runs |
| GET | `/api/history/{run_id}` | Get run details |
| GET | `/api/sets` | List all sets |
| GET | `/api/sets/{slug}` | Get set details |
| GET | `/api/stats` | Database statistics |
| GET | `/api/export` | Export all data |

## Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```env
DEBUG=false
DATABASE_PATH=cache/market_runs.sqlite
RATE_LIMIT_REQUESTS=3
RATE_LIMIT_WINDOW=1.0
DEFAULT_PROFIT_WEIGHT=1.0
DEFAULT_VOLUME_WEIGHT=1.2
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Scoring Weights

| Strategy | Profit Weight | Volume Weight | Use Case |
|----------|---------------|---------------|----------|
| Balanced | 1.0 | 1.2 | Default, good for most users |
| Profit Focus | 1.5 | 0.8 | Maximize profit margins |
| Volume Focus | 0.8 | 1.5 | Prioritize liquid markets |

## Tech Stack

### Backend
- **FastAPI** - Modern async Python framework
- **Pydantic** - Data validation
- **httpx** - Async HTTP client
- **aiosqlite** - Async SQLite
- **uvicorn** - ASGI server

### Frontend
- **React 19** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **Zustand** - State management
- **TanStack Query** - Data fetching
- **Recharts** - Charts
- **React Router** - Routing

## Contributing

We welcome contributions! Key areas:
- Additional analysis metrics
- More chart types
- Performance optimizations
- Test coverage
- Documentation

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Warframe Market](https://warframe.market) for the excellent API
- [Digital Extremes](https://www.digitalextremes.com/) for creating Warframe
- The Warframe trading community

---

**Happy Trading, Tenno!**

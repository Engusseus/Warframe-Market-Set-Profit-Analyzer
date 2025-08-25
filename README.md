# Warframe Market Set Profit Analyzer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)

A comprehensive tool for analyzing Prime set profitability in Warframe using real-time market data from [Warframe Market](https://warframe.market). Identify the most profitable trading opportunities by comparing complete set prices to individual part costs, with advanced scoring algorithms that factor in both profit margins and trading volume.

## ✨ Features

### 📊 **Real-Time Market Analysis**
- **Live Pricing Data**: Fetches current lowest prices for Prime sets and individual parts
- **48-Hour Volume Analysis**: Trading volume data to identify active vs. stagnant markets
- **Comprehensive Market Coverage**: Analyzes all available Prime sets automatically
- **Historical Data Tracking**: SQL database tracks profit and price trends over time

### 💰 **Advanced Profitability Calculations** 
- **Profit Margin Analysis**: Set price vs. sum of individual part costs
- **ROI Calculations**: Return on investment percentages for each set
- **Quantity-Aware Pricing**: Factors in parts that appear multiple times per set
- **Detailed Cost Breakdowns**: Part-by-part expense analysis

### ⚖️ **Intelligent Scoring System**
- **Weighted Scoring Algorithm**: Combines profit and volume with customizable weights
- **Data Normalization**: Fair comparison across different price and volume scales
- **Interactive Configuration**: User-defined weights (default: Profit=1.0×, Volume=1.2×)
- **Top 10 Rankings**: Quickly identify the most profitable opportunities

### 🗄️ **Data Persistence & Export**
- **SQLite Database**: Transaction-safe storage of all analysis runs
- **JSON Export**: Export historical data in LLM-friendly format for analysis
- **Trend Analysis**: Track profit margins and prices over time
- **Data Integrity**: Only complete runs saved - no partial/corrupted data

### 🚀 **Performance & Reliability**
- **Smart Caching System**: SHA-256 hash-based cache invalidation reduces API calls by 95%+
- **Rate Limiting**: Respects API limits with automatic throttling (3 requests/second)
- **Retry Logic**: Exponential backoff for network reliability
- **Graceful Error Handling**: Continues operation even with partial data failures
- **Thread-Safe Operations**: Safe concurrent database access

### 🛠️ **Zero-Configuration Setup**
- **Automatic Environment Management**: Creates and manages Python virtual environment
- **Dependency Auto-Installation**: Installs required packages automatically
- **Cross-Platform Support**: Works on Windows, macOS, and Linux
- **Single Command Execution**: Just run `python main.py`

## 🚀 Quick Start

### Prerequisites
- Python 3.7 or higher
- Internet connection for API access

### Installation & Usage

1. **Clone the repository**
   ```bash
   git clone https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer.git
   cd Warframe-Market-Set-Profit-Analyzer
   ```

2. **Run the analyzer**
   ```bash
   python main.py
   ```

The application will show you a menu:
```
1. Start Market Analysis  - Run analysis and save results to database
2. Export Database to JSON - Export historical data for trend analysis  
3. Exit Application
```

The application will automatically:
- Create a virtual environment if needed
- Install dependencies (`requests==2.31.0`, `rich`)
- Fetch and analyze all Prime set data
- Save results to SQLite database (`cache/market_runs.sqlite`)
- Display comprehensive profitability analysis

### First Run vs. Subsequent Runs

**First Run** (~2-5 minutes):
- Fetches complete Prime set data from Warframe Market API
- Builds comprehensive cache with part quantities and relationships
- Performs full market analysis
- Creates SQLite database and saves results

**Subsequent Runs** (~30-60 seconds):
- Uses cached set data (only refetches if data has changed)
- Fetches only real-time pricing and volume data
- Saves new analysis to database for trend tracking
- Provides same comprehensive analysis with much faster execution

### Data Export & Analysis
Use the **Export Database to JSON** option to:
- Export all historical market runs to `cache/market_data_export.json`
- Analyze profit and price trends over time
- Perform advanced analysis with external tools (Excel, Python, etc.)
- Share data in a structured, LLM-friendly format

## 📋 Sample Output

```
PROFITABILITY ANALYSIS
============================================================

TOP 10 MOST PROFITABLE PRIME SETS
====================================================================================================
Rank Set Name                          Profit   Volume   Score    ROI%     Details
----------------------------------------------------------------------------------------------------
1    Ash Prime Set                      +156     2,340    2.85     +47.3%   View below
2    Banshee Prime Set                  +89      1,890    2.41     +31.2%   View below
3    Ember Prime Set                    +234     1,200    2.38     +78.9%   View below

DETAILED BREAKDOWN (TOP 5)
====================================================================================================

1. Ash Prime Set
------------------------------------------------------------
Set Price: 350 platinum
Part Cost: 194 platinum  
Profit Margin: +156 platinum (+47.3% ROI)
Trading Volume: 2,340 units (48h)
Total Score: 2.85 (Profit: 1.42, Volume: 1.43)

Part Breakdown:
  • Ash Prime Blueprint: 45 × 1 = 45 plat
  • Ash Prime Chassis: 78 × 1 = 78 plat
  • Ash Prime Neuroptics: 71 × 1 = 71 plat
```

## 🎛️ Configuration Options

### Weight Customization
When running the analyzer, you'll be prompted to configure scoring weights:

```
SCORING WEIGHT CONFIGURATION
============================================================
Configure how much weight to give each factor in the final score:
• Profit Weight: How much to emphasize profit margins
• Volume Weight: How much to emphasize trading volume

Weight Selection:
1. Use default weights (Profit=1.0, Volume=1.2)
2. Custom weights

Enter choice (1-2): 
```

**Recommended Weight Strategies:**
- **Conservative Trading** (High Volume Focus): Profit=0.8, Volume=1.5
- **High Risk/Reward** (High Profit Focus): Profit=1.5, Volume=0.8  
- **Balanced Approach** (Default): Profit=1.0, Volume=1.2

## 📁 Project Structure

```
Warframe-Market-Set-Profit-Analyzer/
├── main.py              # Main application with CLI and analysis logic
├── database.py          # SQLite database module (transaction-safe)
├── requirements.txt     # Python dependencies (requests==2.31.0, rich)
├── cache/              # Data storage directory
│   ├── .gitkeep        # Preserves directory structure
│   ├── prime_sets_cache.json     # API response cache (auto-generated)
│   ├── market_runs.sqlite        # SQLite database (auto-generated)
│   └── market_data_export.json   # JSON export file (user-generated)
├── venv/               # Auto-generated virtual environment
├── LICENSE             # MIT License
├── README.md           # This file
├── CONTRIBUTING.md     # Contribution guidelines with database examples
└── CLAUDE.md           # Claude Code development guidance
```

### Database Schema
The SQLite database (`cache/market_runs.sqlite`) stores:
- **market_runs**: Metadata for each analysis run (timestamp, date)
- **set_profits**: Profit margins and lowest prices for each Prime set
- **Indexes**: Optimized for fast queries on timestamps and set names

**Note**: Database files are git-ignored to keep personal analysis data private.

## 🔧 Technical Details

### API Endpoints Used
- **Prime Sets**: `https://api.warframe.market/v2/items`
- **Set Details**: `https://api.warframe.market/v2/item/{slug}`
- **Pricing Data**: `https://api.warframe.market/v2/orders/item/{slug}/top`
- **Volume Data**: `https://api.warframe.market/v1/items/{slug}/statistics`

### Caching Strategy
The application uses SHA-256 hash-based cache invalidation:
- Calculates hash of Prime sets array from API
- Only refetches detailed data when upstream changes detected
- Dramatically improves performance on subsequent runs
- Cache files are automatically managed and git-ignored

### Rate Limiting
- Respects Warframe Market API limits with 3 requests per second
- Automatic waiting with user feedback during rate limiting
- Exponential backoff retry logic for failed requests

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

Key areas for contribution:
- **Database Extensions**: Advanced analytics, custom export formats
- **New Analysis Features**: Additional metrics, scoring algorithms
- **Performance Optimizations**: Async processing, improved caching
- **UI Improvements**: Better console output, progress indicators
- **API Enhancements**: Additional endpoints, data sources
- **Testing**: Unit tests, integration tests, error case coverage

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This tool is for educational and informational purposes. Trading decisions should always consider multiple factors including market volatility, personal risk tolerance, and current game meta. The authors are not responsible for any trading losses.

## 🙏 Acknowledgments

- [Warframe Market](https://warframe.market) for providing the excellent API
- [Digital Extremes](https://www.digitalextremes.com/) for creating Warframe
- The Warframe trading community for market data and feedback

## 📞 Support

- **Issues**: Please use [GitHub Issues](https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/issues)
- **Feature Requests**: Submit via GitHub Issues with the `enhancement` label
- **Questions**: Check existing issues or create a new `question` labeled issue

---

**Happy Trading, Tenno!** 🎮
# Warframe Market Set Profit Analyzer (Development Branch)

**⚠️ This is the development branch. Features may break, change, or be unstable. Use at your own risk!**

A Python tool and interactive web app that analyzes the Warframe Market API to find profitable item sets to trade, balancing both profit margins and trading volume.

---

## 🚀 What's New in This Branch?

- **Interactive Streamlit UI**: Run a beautiful, animated web dashboard to analyze and visualize profits and volumes.
- **One-click Launch**: Just double-click `run-analyzer.bat` on Windows to launch the UI in your browser.
- **Configurable Weights & Options**: Adjust profit, volume, and margin weights and the minimum online sample size from the sidebar.
- **Live Progress, Animations, and Effects**: Enjoy spinners, Lottie animations, and confetti.
- **Results Table & Plot**: View sortable tables and interactive scatter plots of profit vs. volume.
- **Linear Regression (Profit vs. Volume)**: Run statistical analysis with a regression line and R² displayed.
- **Persistent Analytics (SQLite)**: Each run appends results to a single local SQLite DB for cumulative analysis.
- **24/7 Mode**: Optional continuous mode to fetch and append data every N minutes (default 60).
- **Faster Analysis**: Concurrency improvements, fewer requests per set using include=item, and statistics-based pricing (now the default).
- **Live Progress + Controls**: Visible progress bar with ETA and counters, Stop (no save), and Quit (immediate exit) buttons.
- **API Spec Included**: The Warframe.market OpenAPI spec used by the app is included in this repo as `api-doc.da4693bf305141492c84.yml`.
- **All CLI features still available**: You can still run the classic script for CSV/XLSX output.
- **Improved error handling, caching, and async performance**.

---

## ⚠️ Development Status

- This is the **dev branch**. Features may be experimental, incomplete, or break unexpectedly.
- Please report issues or unexpected behavior!

---

## Features

- Fetches all tradable item sets from the Warframe Market API
- Calculates potential profit for each set by comparing set prices to individual part prices
- Tracks 48-hour trading volume for each set
- Scores items based on a weighted combination of profit, profit margin, and volume
- Generates a CSV or XLSX report ordered by score for easy decision-making
- Saves a scatter plot of profit vs. volume for quick visualization
- **Interactive UI**: Run, configure, and visualize everything in your browser
- **Sidebar config**: Adjust weights and the minimum online sample size
- **Live progress, ETA, spinners, and Lottie animations**
- **Expandable details for top sets**
- **Linear regression analysis** (cumulative, over historical runs)

---

## Requirements

- Python 3.8+
- Dependencies listed in `requirements.txt` **plus**:
  - `streamlit`, `plotly`, `scikit-learn`, `streamlit-lottie`

---

## Installation & Usage

### Option 1: One-click Launch (Windows)

1. [Download or clone this repository]([https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer](https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/tree/dev))
2. Double-click `run-analyzer.bat` in the project root
3. The script will automatically:
   - Check if Python is installed
   - Set up a virtual environment
   - Install all required packages (including Streamlit and UI dependencies)
   - Launch the Streamlit UI in your browser
4. Use the sidebar to configure options, then click **Run Analysis**
5. View results, plots, and details interactively

### Option 2: Manual Setup (All Platforms)

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/Warframe-Market-Set-Profit-Analyzer.git
   cd Warframe-Market-Set-Profit-Analyzer
   ```
2. Create a virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   pip install streamlit plotly scikit-learn streamlit-lottie
   ```
4. Run the UI:
   ```
   streamlit run app.py
   ```

### 24/7 Mode (Continuous)

- Toggle "24/7 Mode" in the UI and set the interval (default 60 minutes).
- The app will keep appending results to the local DB (`data/market_history.sqlite`).
- Use the regression button under "Statistical Analysis (Cumulative)" to train on all historical runs.

### Classic CLI Usage

You can still run the classic script for CSV/XLSX output (deprecated in UI mode):
```bash
python wf_market_analyzer.py
```
Or with custom options:
```bash
python wf_market_analyzer.py --platform xbox --output-file xbox_results.csv \
    --profit-weight 1.0 --volume-weight 1.5
```

---

## UI Features & Options

- **Profit/Volume/Margin Weights**: Adjust how each factor affects the score
- **Minimum Online Sell Orders (Sample Size)**: A set is included only if it has at least this many online sell orders; parts must have at least this many 48h statistic price points
- **Debug Mode**: Enable detailed logging
- **Live Progress**: See counters, ETA, progress bar, and animations during analysis
- **Results Table**: Sortable, filterable table of all sets
- **Scatter Plot**: Interactive profit vs. volume plot
- **Expandable Details**: Click to see breakdown for top set
- **Statistical Analysis**: Button for linear regression with regression line and R² using all historical runs
- **24/7 Mode**: Automatically append data every N minutes
 - **Stop**: Immediately stop the current run without saving partial data
 - **Quit**: Exit the application entirely

---

## Known Issues / Limitations

- This is a development branch: features may break, change, or be removed at any time
- API changes or downtime may cause errors
- Some features (e.g., confetti, Lottie) require a modern browser
- Continuous mode depends on the app staying open; server sleep may pause scheduling
- CSV/JSON exports are deprecated in favor of the UI and SQLite persistence (still available via CLI if needed)
- API spec file `api-doc.da4693bf305141492c84.yml` is included for reference (the service may change endpoints/fields over time)

---

## Configuration

Adjust the values in `config.py` for CLI defaults, or use the sidebar in the UI for interactive config.

- `API_BASE_URL`: Base URL for the Warframe Market API
- `REQUESTS_PER_SECOND`: Control the request rate
- `PROFIT_WEIGHT`, `VOLUME_WEIGHT`, and `PROFIT_MARGIN_WEIGHT`: Balance profit, profit margin, and trading volume in the score
- `PRICE_SAMPLE_SIZE`: Minimum online sell orders for a set, and minimum 48h statistic price points for parts
- `USE_STATISTICS_FOR_PRICING`: Always true in the UI; pricing based on `/statistics` for speed and stability
- `DB_PATH`: Path to the SQLite DB for cumulative analytics (all data is stored here)
- Other legacy options (e.g., median pricing, CSV/XLSX) are deprecated in the UI path

---

## How Scoring Works

The tool calculates scores using the following methodology:

1. Normalizes profit, profit margin, and volume data (scaling to 0-1 range)
2. Applies weights to each factor (default: 1.0× for profit, 1.2× for volume, 0× for profit margin)
3. Combines these values into a single score
4. Ranks results in descending order by score

This approach balances the importance of profit margin with how frequently the item trades.

---

## License

MIT License. See [LICENSE](LICENSE) file for details.

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request or open an issue. This branch is under active development.

# Warframe Market Set Profit Analyzer (Development Branch)

**⚠️ This is the development branch. Features may break, change, or be unstable. Use at your own risk!**

A Python tool and interactive web app that analyzes the Warframe Market API to find profitable item sets to trade, balancing both profit margins and trading volume.

---

## 🚀 What's New in This Branch?

- **Interactive Streamlit UI**: Run a beautiful, animated web dashboard to analyze and visualize profits and volumes.
- **One-click Launch**: Just double-click `run-analyzer.bat` on Windows to launch the UI in your browser.
- **Configurable Weights & Options**: Adjust profit, volume, and margin weights, pricing method, and more from the sidebar.
- **Live Progress, Animations, and Effects**: Enjoy spinners, Lottie animations, and confetti.
- **Results Table & Plot**: View sortable tables and interactive scatter plots of profit vs. volume.
- **Linear Regression (Profit vs. Volume)**: Run statistical analysis with a regression line and R² displayed.
- **Persistent Analytics (SQLite)**: Each run appends results to a single local SQLite DB for cumulative analysis.
- **24/7 Mode**: Optional continuous mode to fetch and append data every N minutes (default 60).
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
- **Sidebar config**: Adjust platform, weights, pricing method, and more
- **Progress bars, spinners, and Lottie animations**
- **Expandable details for top sets**
- **(Planned) Linear regression analysis**

---

## Requirements

- Python 3.7+
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

You can still run the classic script for CSV/XLSX output:
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

- **Platform**: Choose PC, PS4, Xbox, or Switch
- **Profit/Volume/Margin Weights**: Adjust how each factor affects the score
- **Price Sample Size**: Number of orders to average/median
- **Median Pricing**: Toggle between average and median price calculations
- **Volume Trends**: Optionally analyze volume trends over N days
- **Debug Mode**: Enable detailed logging
- **Live Progress**: See spinners, progress bars, and Lottie animations during analysis
- **Results Table**: Sortable, filterable table of all sets
- **Scatter Plot**: Interactive profit vs. volume plot
- **Expandable Details**: Click to see breakdown for top set
- **Statistical Analysis**: Button for linear regression with regression line and R² using all historical runs
- **24/7 Mode**: Automatically append data every N minutes

---

## Known Issues / Limitations

- This is a development branch: features may break, change, or be removed at any time
- API changes or downtime may cause errors
- Some features (e.g., confetti, Lottie) require a modern browser
- Continuous mode depends on the app staying open; server sleep may pause scheduling

---

## Configuration

Adjust the values in `config.py` for CLI defaults, or use the sidebar in the UI for interactive config.

- `API_BASE_URL`: Base URL for the Warframe Market API
- `REQUESTS_PER_SECOND`: Control the request rate
- `PROFIT_WEIGHT`, `VOLUME_WEIGHT`, and `PROFIT_MARGIN_WEIGHT`: Balance profit, profit margin, and trading volume in the score
- `OUTPUT_FILE`: File path for the generated CSV/XLSX
- `DEBUG_MODE`: Enable or disable detailed logging
- `PRICE_SAMPLE_SIZE`: Number of orders to sample when calculating prices
- `USE_MEDIAN_PRICING`: Use the median price of the sampled orders instead of the average
- `CACHE_DIR`: Directory where cached API responses are stored
- `CACHE_TTL_DAYS`: Number of days to keep cache files before they expire
- `DB_PATH`: Path to the SQLite DB for cumulative analytics

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

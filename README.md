# Warframe Market Set Profit Analyzer

A Python tool that analyzes the Warframe Market API to find profitable item sets to trade, balancing both profit margins and trading volume.

## Features

- Fetches all tradable item sets from the Warframe Market API
- Calculates potential profit for each set by comparing set prices to individual part prices
- Tracks 48-hour trading volume for each set
- Scores items based on a weighted combination of profit and volume
- Generates a CSV report ordered by score for easy decision-making

## Requirements

- Python 3.7+
- Dependencies listed in `requirements.txt`

## Installation

### Option 1: Simple Download (Windows)

1. [Download the latest release](https://github.com/yourusername/warframe-market-analyzer/releases/latest)
2. Extract the ZIP file to any folder
3. Double-click `run-analyzer.bat`
4. The script will automatically:
   - Check if Python is installed (and prompt you to install it if needed)
   - Set up a virtual environment
   - Install all required packages
   - Run the analyzer
   - Save results to `set_profit_analysis.csv` in the same folder

### Option 2: Manual Setup (All Platforms)

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/warframe-market-analyzer.git
   cd warframe-market-analyzer
   ```

2. Create a virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Run the analyzer:
   ```
   python wf_market_analyzer.py
   ```

## Usage

Run the analyzer:

```
python wf_market_analyzer.py
```

The script will:
1. Fetch all tradable item sets
2. Calculate profit margins for each set
3. Track 48-hour trading volume
4. Generate a score based on profit and volume
5. Save results to `set_profit_analysis.csv`

## Configuration

Edit the constants at the top of `wf_market_analyzer.py` to customize:

- `PROFIT_WEIGHT` and `VOLUME_WEIGHT`: Adjust the balance between profit and volume in scoring
- `REQUESTS_PER_SECOND`: Control API request rate (default: 2)
- `OUTPUT_FILE`: Change the output file name
- `DEBUG_MODE`: Enable/disable detailed logging

## How Scoring Works

The tool calculates scores using the following methodology:

1. Normalizes both profit and volume data (scaling to 0-1 range)
2. Applies weights to each factor (default: 1.0× for profit, 1.2× for volume)
3. Combines these values into a single score
4. Ranks results in descending order by score

This approach balances the importance of profit margin with how frequently the item trades.

## License

MIT License. See [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
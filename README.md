# Warframe Market Set Profit Analyzer

`warframe-market-set-profit-analyzer` is a packaged Python CLI for ranking
Warframe Prime sets by profit and recent trading volume. It uses Warframe
Market v2 for item metadata and orderbooks, and keeps the v1 statistics
endpoint for 48-hour volume because that metric is not currently exposed by v2.

## What It Does

- fetches all Prime set slugs from `/v2/items`
- fetches each set's members and quantities from `/v2/item/{slug}/set`
- fetches top sell orders from `/v2/orders/item/{slug}/top`
- fetches 48-hour volume from `/v1/items/{slug}/statistics`
- calculates set profit as average set price minus summed part costs
- scores each set with weighted min-max normalization for profit and volume
- writes a CSV artifact for each successful run

## Requirements

- Python 3.10+
- On Debian/Ubuntu, install `python3-venv` or `python3-virtualenv` if local
  virtual environment creation is unavailable

## Quick Start

The repo ships with launchers that keep everything inside a repo-local
`.venv/`, so packages do not land in your system Python.

If `./run.sh` cannot create `.venv`, install Linux virtual environment support
first. On Debian/Ubuntu that is:

```bash
sudo apt install python3-venv python3-virtualenv
```

### Fresh clone

Clone the repo, enter it, then run the platform launcher:

```bash
git clone https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer.git
cd Warframe-Market-Set-Profit-Analyzer
./run.sh --help
```

On Windows:

```powershell
git clone https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer.git
cd Warframe-Market-Set-Profit-Analyzer
run.bat --help
```

### Update an existing checkout

If you are following the `dev` branch, pull the latest changes and rerun the
launcher:

```bash
git checkout dev
git pull
./run.sh
```

On Windows:

```powershell
git checkout dev
git pull
run.bat
```

Each launcher will:

- create `.venv/` in the repo if it does not exist
- upgrade `pip` inside that virtual environment
- install or update the packaged CLI from the current checkout
- run `wf-market-analyzer` with any extra arguments you pass through

## Usage

The launchers are the easiest way to run the tool:

```bash
./run.sh
```

On Windows:

```powershell
run.bat
```

Inspect the full flag surface:

```bash
./run.sh --help
```

On Windows:

```powershell
run.bat --help
```

Example:

```bash
./run.sh \
  --profit-weight 1.0 \
  --volume-weight 1.2 \
  --price-sample-size 2 \
  --requests-per-second 3 \
  --timeout 20 \
  --output-dir runs
```

On Windows, replace `./run.sh` with `run.bat`.

By default, each run produces a timestamped CSV artifact with a unique run ID,
for example:

```text
runs/set_profit_analysis_20260305_141516_a1b2c3d4.csv
```

If you need a fixed location for downstream automation, pass `--output-file`.

## Manual Environment Setup

If you prefer to manage the environment yourself, keep the install inside a
virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
wf-market-analyzer --help
```

On Windows:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install .
wf-market-analyzer --help
```

## Scoring Model

```text
Score = normalized_profit * profit_weight + normalized_volume * volume_weight
```

Default weights:

- `profit_weight = 1.0`
- `volume_weight = 1.2`
- `price_sample_size = 2`

## Output Columns

- `Run Timestamp`
- `Set Name`
- `Set Slug`
- `Profit`
- `Set Selling Price`
- `Part Costs Total`
- `Volume (48h)`
- `Score`
- `Part Prices`

## Configuration

The CLI resolves settings in this order:

1. command-line flags
2. environment variables prefixed with `WF_MARKET_ANALYZER_`
3. built-in defaults from [`config.py`](config.py)

Common examples:

- `WF_MARKET_ANALYZER_OUTPUT_DIR=/srv/wfm/runs`
- `WF_MARKET_ANALYZER_OUTPUT_FILE=/srv/wfm/latest.csv`
- `WF_MARKET_ANALYZER_PLATFORM=pc`
- `WF_MARKET_ANALYZER_LANGUAGE=en`
- `WF_MARKET_ANALYZER_CROSSPLAY=true`
- `WF_MARKET_ANALYZER_REQUESTS_PER_SECOND=3`
- `WF_MARKET_ANALYZER_TIMEOUT=20`
- `WF_MARKET_ANALYZER_MAX_RETRIES=3`
- `WF_MARKET_ANALYZER_LOG_LEVEL=INFO`
- `WF_MARKET_ANALYZER_LOG_FILE=/srv/wfm/logs/analyzer.log`
- `WF_MARKET_ANALYZER_JSON_SUMMARY=true`
- `WF_MARKET_ANALYZER_ALLOW_THIN_ORDERBOOKS=false`

## Production Notes

### Operational defaults

- logs go to `stderr` by default
- file logging is optional and rotated when `--log-file` is set
- outputs are written atomically
- thin orderbooks are rejected by default unless `--allow-thin-orderbooks` is enabled
- malformed quantities or volume payloads are treated as invalid data and skipped instead of being silently coerced

### Useful flags

- `--output-file`: write to a stable target path instead of a timestamped file
- `--json-summary`: emit a machine-readable run summary to `stdout`
- `--log-file`: additionally write rotated logs to disk
- `--log-level`: set `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`
- `--crossplay` / `--no-crossplay`: override the request header explicitly
- `--allow-thin-orderbooks` / `--no-allow-thin-orderbooks`: opt in or out of sparse-price analysis

### Exit codes

- `0`: analysis completed successfully
- `1`: unrecoverable runtime or API failure
- `2`: invalid local configuration
- `130`: interrupted by `Ctrl+C` / `KeyboardInterrupt`

### Cron example

```cron
0 */6 * * * /srv/wf-market-analyzer/bin/wf-market-analyzer --output-file /srv/wf-market-analyzer/runs/latest.csv --log-file /srv/wf-market-analyzer/logs/analyzer.log --json-summary >> /srv/wf-market-analyzer/logs/job.json 2>> /srv/wf-market-analyzer/logs/job.stderr
```

## License

MIT. See [LICENSE](LICENSE).

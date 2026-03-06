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

## Installation

Install the packaged CLI:

```bash
python3 -m pip install --break-system-packages .
```

For local development, install with the full QA toolchain:

```bash
python3 -m pip install --break-system-packages -e ".[dev]"
```

`requirements.txt` is kept as a runtime-only dependency file for lightweight
deployments:

```bash
python3 -m pip install --break-system-packages -r requirements.txt
```

## Usage

Run the installed console script:

```bash
wf-market-analyzer
```

Direct module execution still works:

```bash
python3 wf_market_analyzer.py
```

Inspect the full flag surface for your installed version:

```bash
wf-market-analyzer --help
```

Example:

```bash
wf-market-analyzer \
  --profit-weight 1.0 \
  --volume-weight 1.2 \
  --price-sample-size 2 \
  --requests-per-second 3 \
  --timeout 20 \
  --output-dir runs
```

By default, each run produces a timestamped CSV artifact with a unique run ID,
for example:

```text
runs/set_profit_analysis_20260305_141516_a1b2c3d4.csv
```

If you need a fixed location for downstream automation, pass `--output-file`.

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

### Container or CI usage

- write artifacts to a mounted volume instead of the repo checkout
- prefer `--output-file` or `--json-summary` for downstream automation
- send `stderr` to the platform log collector, optionally with `--log-file` for local retention
- keep API request pacing conservative to avoid 429/509 responses
- treat non-zero exit codes as job failures

## Development Workflow

Install the dev extras once, then run:

```bash
ruff check .
mypy wf_market_analyzer.py config.py
pytest
```

GitHub Actions runs the same gates on Python 3.10, 3.11, 3.12, and 3.13.

## Reference Material

- Local Warframe Market v2 API reference:
  [docs/local/warframe-market-api-v2-reference.md](docs/local/warframe-market-api-v2-reference.md)

## License

MIT. See [LICENSE](LICENSE).

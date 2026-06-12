# Warframe Market Set Profit Analyzer

[![CI](https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%E2%80%933.14-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Release](https://img.shields.io/github/v/release/Engusseus/Warframe-Market-Set-Profit-Analyzer)](https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/releases)

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

The analyzer is a polite API citizen: it paces requests (3 per second by
default), identifies itself with a project `User-Agent`, and honors
`Retry-After` when the API asks it to slow down.

## Requirements

- Python 3.10 to 3.14
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

Clone the repo, enter it, then run the platform launcher to start the analyzer
right away:

```bash
git clone https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer.git
cd Warframe-Market-Set-Profit-Analyzer
./run.sh
```

On Windows:

```powershell
git clone https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer.git
cd Warframe-Market-Set-Profit-Analyzer
.\run.bat
```

PowerShell requires `.\` to run a script from the current folder.

Each launcher will:

- create `.venv/` in the repo if it does not exist
- upgrade `pip` inside that virtual environment
- install or update the packaged CLI from the current checkout
- run `wf-market-analyzer` with any extra arguments you pass through

## Usage

The launchers are the easiest way to run the tool. Running them without extra
flags starts the analyzer immediately:

```bash
./run.sh
```

On Windows:

```powershell
.\run.bat
```

Inspect the full flag surface:

```bash
./run.sh --help
```

On Windows:

```powershell
.\run.bat --help
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

On Windows, replace `./run.sh` with `.\run.bat`.

By default, each run produces a timestamped CSV artifact with a unique run ID,
for example:

```text
runs/set_profit_analysis_20260305_141516_a1b2c3d4.csv
```

If you need a fixed location for downstream automation, pass `--output-file`.

## Configuration

Every CLI flag can also be supplied through an environment variable named
`WF_MARKET_ANALYZER_<OPTION>`. CLI flags take precedence over environment
variables, which take precedence over built-in defaults. For example:

```bash
export WF_MARKET_ANALYZER_PROFIT_WEIGHT=2.0
export WF_MARKET_ANALYZER_OUTPUT_DIR=/var/data/wfma
export WF_MARKET_ANALYZER_JSON_SUMMARY=true
wf-market-analyzer
```

Commonly tuned options:

| Option | Env var | Default | Meaning |
| --- | --- | --- | --- |
| `--profit-weight` | `WF_MARKET_ANALYZER_PROFIT_WEIGHT` | `1.0` | Weight of normalized profit in the score |
| `--volume-weight` | `WF_MARKET_ANALYZER_VOLUME_WEIGHT` | `1.2` | Weight of normalized 48h volume in the score |
| `--price-sample-size` | `WF_MARKET_ANALYZER_PRICE_SAMPLE_SIZE` | `2` | Lowest sell orders averaged per item (1-5) |
| `--requests-per-second` | `WF_MARKET_ANALYZER_REQUESTS_PER_SECOND` | `3.0` | Global API request pace |
| `--platform` | `WF_MARKET_ANALYZER_PLATFORM` | `pc` | Platform header sent to the API |
| `--json-summary` | `WF_MARKET_ANALYZER_JSON_SUMMARY` | `false` | Print the run summary as JSON for automation |

Run `wf-market-analyzer --help` for the complete list with descriptions.

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

## Development

Install the package with dev extras, then run the same checks CI runs:

```bash
python -m pip install -e ".[dev]"
python -m pytest        # tests with coverage (90% minimum enforced)
python -m ruff check .  # lint
python -m mypy          # type check
```

CI runs the test suite on Python 3.10 through 3.14 and audits runtime
dependencies with pip-audit on every push and pull request.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

## License

MIT. See [LICENSE](LICENSE).

# Warframe Market Set Profit Analyzer

A simple Python CLI that ranks Warframe Prime sets using the original weighted scoring model from `v0.1.0`.

The tool now uses Warframe Market v2 for item metadata and orderbooks, while keeping the v1 statistics endpoint for 48-hour volume because that data is not yet available in v2.

## What It Does

- fetches all Prime set slugs from `/v2/items`
- fetches each set's parts and quantities from `/v2/item/{slug}/set`
- fetches top sell orders from `/v2/orders/item/{slug}/top`
- fetches 48-hour volume from `/v1/items/{slug}/statistics`
- calculates set profit as:
  - average of the lowest set sell listings
  - minus the summed average of the lowest part sell listings times quantity
- scores each set with weighted min-max normalized profit and volume
- writes one timestamped CSV per run in `runs/`

## Requirements

- Python 3.10+

## Installation

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

Run with defaults:

```bash
python3 wf_market_analyzer.py
```

Optional flags:

```bash
python3 wf_market_analyzer.py \
  --profit-weight 1.0 \
  --volume-weight 1.2 \
  --price-sample-size 2 \
  --output-dir runs \
  --debug
```

Each run creates a new CSV like:

```text
runs/set_profit_analysis_20260305_141516.csv
```

## Scoring Model

The ranking model intentionally stays simple:

```text
Score = normalized_profit * profit_weight + normalized_volume * volume_weight
```

Defaults:

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

## Notes

- Results are sorted by score in descending order.
- Sets with missing pricing or statistics data are skipped.
- The tool keeps all successfully analyzed sets, even if profit is negative.
- `--price-sample-size` accepts values from `1` to `5`, matching the `/v2/orders/item/{slug}/top` sell-order limit.
- The local v2 API reference used for this migration is in [docs/local/warframe-market-api-v2-reference.md](docs/local/warframe-market-api-v2-reference.md).

## Tests

```bash
pytest
```

## License

MIT. See [LICENSE](LICENSE).

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.2] - 2026-09-25

### Security

- Escape spreadsheet formula prefixes in API-derived set names, set slugs,
  and part-price text at the CSV output boundary.
- Protect against line-feed-prefixed formulas and formulas exposed by alternate
  spreadsheet delimiters, including intervening spaces and quotes.

### Added

- Regression coverage for formula prefixes across all API-derived CSV text
  columns and comma, semicolon, and tab imports, while preserving ordinary
  text, numeric values, and atomic CSV output.

### Changed

- Updated GitHub Actions checkout and Python setup actions to v7 and expanded
  the supported mypy development dependency range to include 2.x.

## [0.5.1] - 2026-07-08

### Added

- Added Dependabot version updates for Python dependencies and GitHub Actions.

### Security

- Removed automatic environment creation and package installation from the
  platform launchers. `run.sh` and `run.bat` now only run an analyzer that was
  explicitly installed into `.venv/`, avoiding startup-time dependency
  resolution and package code execution.

## [0.5.0] - 2026-06-12

### Added

- Identifying `User-Agent` header (`wf-market-analyzer/<version> (+repo URL)`)
  on every API request, per Warframe Market API guidelines.
- `Retry-After` header support: when the API rate-limits a request (HTTP 429),
  the analyzer now waits the server-requested delay (capped at 60 seconds)
  instead of relying only on blind exponential backoff.
- Help text for every CLI flag, including defaults and a note about the
  `WF_MARKET_ANALYZER_*` environment variable equivalents.
- GitHub Actions CI: tests on Python 3.10-3.14, ruff, mypy, and a pip-audit
  dependency scan on every push and pull request.
- This changelog.

### Changed

- Error response bodies are now whitespace-collapsed and truncated to 500
  characters before logging, so a malfunctioning or hostile server cannot
  flood logs or inject fake log lines.
- `pyproject.toml` modernized: SPDX license expression, Python 3.14
  classifier, and project URLs for PyPI-style metadata.

### Security

- Bumped the dev test stack to `pytest>=9.0.3` to resolve CVE-2025-71176
  (runtime dependencies were already clean per pip-audit).

## [0.4.0] - 2026-03-08

### Changed

- Relaunched as a hardened, packaged CLI: strict input validation, atomic CSV
  writes, rotating log files, run IDs, JSON run summaries, and a 90%+
  coverage test suite.

## [0.3.0] - 2025-12-17

### Changed

- Transformed the analyzer into a full-stack web application (later reverted
  in favor of the CLI in 0.4.0).

## [0.2.0] - 2025-08-25

### Changed

- Matured the CLI with richer analytics and persistent run artifacts.

## [0.1.0] - 2025-03-22

### Added

- Initial CLI analyzer for ranking Warframe Prime sets by profit and volume.

[0.5.2]: https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/releases/tag/v0.1.0

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.5.0]: https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/releases/tag/v0.1.0

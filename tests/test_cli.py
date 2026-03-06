import json
from datetime import datetime

import pytest

import wf_market_analyzer
from wf_market_analyzer import (
    AnalysisReport,
    PriceData,
    ResultRow,
    RuntimeConfig,
    SetData,
    VolumeData,
    build_summary,
    configure_logging,
    main,
    parse_args,
    read_env,
    render_human_summary,
    resolve_option,
    run_analysis,
    runtime_config_from_args,
    runtime_config_to_log_dict,
)


def sample_report() -> AnalysisReport:
    return AnalysisReport(
        results=[
            ResultRow(
                set_data=SetData(
                    slug="alpha_prime_set",
                    name="Alpha Prime Set",
                    parts={"alpha_prime_blueprint": 1},
                    part_names={"alpha_prime_blueprint": "Alpha Prime Blueprint"},
                ),
                price_data=PriceData(
                    set_price=100.0,
                    part_prices={"alpha_prime_blueprint": 15.0},
                    total_part_cost=15.0,
                    profit=85.0,
                ),
                volume_data=VolumeData(volume_48h=12),
                score=1.0,
                run_timestamp="2026-03-05T14:15:16-05:00",
            )
        ],
        completed_at=datetime.fromisoformat("2026-03-05T14:15:16-05:00"),
        catalog_set_count=3,
        metadata_set_count=2,
        skipped_invalid_set_count=1,
        skipped_missing_price_count=0,
        skipped_missing_volume_count=1,
    )


def test_runtime_config_post_init_normalizes_values(tmp_path):
    settings = RuntimeConfig(
        platform=" PC ",
        language=" EN ",
        output_dir=tmp_path / "runs",
        output_file=tmp_path / "result.csv",
        log_file=tmp_path / "logs" / "tool.log",
        debug=True,
    )

    assert settings.platform == "pc"
    assert settings.language == "en"
    assert settings.output_file == tmp_path / "result.csv"
    assert settings.log_file == tmp_path / "logs" / "tool.log"
    assert settings.log_level == "DEBUG"
    assert settings.headers["Crossplay"] == "true"


def test_configure_logging_adds_stderr_and_rotating_file_handlers(tmp_path):
    settings = RuntimeConfig(
        log_file=tmp_path / "logs" / "tool.log",
        run_id="run12345",
        debug=False,
    )

    configure_logging(settings)
    wf_market_analyzer.logger.info("hello")

    log_contents = settings.log_file.read_text(encoding="utf-8")
    handler_types = {type(handler).__name__ for handler in wf_market_analyzer.logger.handlers}

    assert "StreamHandler" in handler_types
    assert "RotatingFileHandler" in handler_types
    assert "run_id=run12345" in log_contents


def test_read_env_treats_blank_values_as_unset(monkeypatch):
    monkeypatch.setenv("WF_MARKET_ANALYZER_OUTPUT_DIR", "   ")
    monkeypatch.setenv("WF_MARKET_ANALYZER_PLATFORM", "pc")

    assert read_env("OUTPUT_DIR") is None
    assert read_env("PLATFORM") == "pc"


def test_resolve_option_prefers_cli_then_env_then_default(monkeypatch):
    monkeypatch.setenv("WF_MARKET_ANALYZER_MAX_RETRIES", "7")

    assert resolve_option(3, "MAX_RETRIES", 5, wf_market_analyzer.positive_int) == 3
    assert resolve_option(None, "MAX_RETRIES", 5, wf_market_analyzer.positive_int) == 7
    assert resolve_option(None, "MISSING", 5, wf_market_analyzer.positive_int) == 5


def test_resolve_option_raises_for_invalid_env(monkeypatch):
    monkeypatch.setenv("WF_MARKET_ANALYZER_MAX_RETRIES", "nope")

    with pytest.raises(ValueError, match="WF_MARKET_ANALYZER_MAX_RETRIES"):
        resolve_option(None, "MAX_RETRIES", 5, wf_market_analyzer.positive_int)


def test_parse_args_and_runtime_config_from_args_use_cli_and_env(monkeypatch, tmp_path):
    monkeypatch.setenv("WF_MARKET_ANALYZER_PLATFORM", "xbox")
    monkeypatch.setenv("WF_MARKET_ANALYZER_JSON_SUMMARY", "true")
    monkeypatch.setenv("WF_MARKET_ANALYZER_TIMEOUT", "30")

    args = parse_args(
        [
            "--output-dir",
            str(tmp_path),
            "--profit-weight",
            "2",
            "--crossplay",
            "--log-level",
            "warning",
        ]
    )
    settings = runtime_config_from_args(args)

    assert settings.output_dir == tmp_path
    assert settings.platform == "xbox"
    assert settings.request_timeout_seconds == 30.0
    assert settings.json_summary is True
    assert settings.crossplay is True
    assert settings.profit_weight == 2.0
    assert settings.log_level == "WARNING"


def test_runtime_config_from_args_rejects_zero_weights():
    args = parse_args(["--profit-weight", "0", "--volume-weight", "0"])

    with pytest.raises(ValueError, match="At least one"):
        runtime_config_from_args(args)


def test_parse_args_rejects_invalid_sample_size():
    with pytest.raises(SystemExit):
        parse_args(["--price-sample-size", "6"])


def test_runtime_config_to_log_dict_serializes_paths(tmp_path):
    settings = RuntimeConfig(
        output_dir=tmp_path / "runs",
        output_file=tmp_path / "out.csv",
        log_file=tmp_path / "tool.log",
    )

    payload = runtime_config_to_log_dict(settings)

    assert payload["output_dir"] == str(tmp_path / "runs")
    assert payload["output_file"] == str(tmp_path / "out.csv")
    assert payload["log_file"] == str(tmp_path / "tool.log")


def test_build_summary_and_render_human_summary(tmp_path):
    settings = RuntimeConfig(run_id="run12345", allow_thin_orderbooks=True, price_sample_size=3)
    summary = build_summary(tmp_path / "result.csv", sample_report(), settings, 1.23456)
    rendered = render_human_summary(summary)

    assert summary["status"] == "ok"
    assert summary["duration_seconds"] == 1.235
    assert "Run run12345 completed in 1.235s" in rendered
    assert "CSV written to:" in rendered


def test_run_analysis_writes_output_file(tmp_path):
    report = sample_report()

    class FakeAnalyzer:
        def __init__(self, settings, transport=None):
            del transport
            self.settings = settings

        async def analyze(self):
            return report

    settings = RuntimeConfig(output_file=tmp_path / "explicit.csv")
    original_analyzer = wf_market_analyzer.SetProfitAnalyzer
    wf_market_analyzer.SetProfitAnalyzer = FakeAnalyzer
    try:
        output_path, returned_report = wf_market_analyzer.asyncio.run(run_analysis(settings))
    finally:
        wf_market_analyzer.SetProfitAnalyzer = original_analyzer

    assert output_path == tmp_path / "explicit.csv"
    assert returned_report is report
    assert output_path.exists()


def test_main_success_human_summary(monkeypatch, tmp_path, capsys):
    report = sample_report()

    async def fake_run_analysis(settings):
        assert settings.output_dir == tmp_path
        return tmp_path / "result.csv", report

    monkeypatch.setattr(wf_market_analyzer, "run_analysis", fake_run_analysis)

    exit_code = main(["--output-dir", str(tmp_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Ranked 1 sets" in captured.out
    assert "starting" in captured.err


def test_main_success_json_summary(monkeypatch, tmp_path, capsys):
    report = sample_report()

    async def fake_run_analysis(settings):
        return tmp_path / "result.csv", report

    monkeypatch.setattr(wf_market_analyzer, "run_analysis", fake_run_analysis)

    exit_code = main(["--json-summary", "--output-dir", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["output_path"] == str(tmp_path / "result.csv")


def test_main_failure_human_summary(monkeypatch, capsys):
    async def fake_run_analysis(settings):
        del settings
        raise RuntimeError("network down")

    monkeypatch.setattr(wf_market_analyzer, "run_analysis", fake_run_analysis)

    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Analysis failed: network down" in captured.err


def test_main_failure_json_summary(monkeypatch, capsys):
    async def fake_run_analysis(settings):
        del settings
        raise RuntimeError("network down")

    monkeypatch.setattr(wf_market_analyzer, "run_analysis", fake_run_analysis)

    exit_code = main(["--json-summary"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["error"] == "network down"


def test_main_keyboard_interrupt(monkeypatch, capsys):
    def raise_interrupt(coro):
        coro.close()
        raise KeyboardInterrupt

    monkeypatch.setattr(wf_market_analyzer.asyncio, "run", raise_interrupt)

    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 130
    assert captured.out == ""


def test_main_configuration_error(capsys):
    exit_code = main(["--profit-weight", "0", "--volume-weight", "0"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Configuration error" in captured.err

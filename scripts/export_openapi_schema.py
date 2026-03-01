#!/usr/bin/env python3
"""Export the backend OpenAPI schema to a JSON file."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_openapi_schema() -> dict:
    backend_dir = _repo_root() / "backend"
    sys.path.insert(0, str(backend_dir))
    from app.api.router import api_router

    app = FastAPI(
        title="Warframe Market Analyzer",
        version="2.0.0",
        description="API for analyzing Warframe Market Prime set profitability",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(api_router, prefix="/api")

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "name": "Warframe Market Analyzer",
            "version": "2.0.0",
            "docs": "/docs",
            "api": "/api",
        }

    return app.openapi()


def main() -> int:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    schema = _load_openapi_schema()
    payload = json.dumps(schema, indent=2)

    if output_path is None:
        print(payload)
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"{payload}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

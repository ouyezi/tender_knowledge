#!/usr/bin/env python3
"""End-to-end pipeline test: import -> knowledge publish -> retrieval."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from e2e.integration_harness import run_integration_pipeline
from e2e.logger import JsonlRunLogger
from e2e.runner import E2EPipelineRunner, default_log_file
from e2e.client import LiveClient
from e2e.types import PipelineConfig

DEFAULT_FIXTURES = {
    "actual_bid": ROOT / "backend/tests/fixtures/sample-actual-bid.docx",
    "template_file": ROOT / "backend/tests/fixtures/sample-template.docx",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="E2E import-to-retrieval pipeline test")
    parser.add_argument("--purpose", choices=["actual_bid", "template_file"], required=True)
    parser.add_argument("--kb-id", default=os.getenv("KB_ID"))
    parser.add_argument("--file", type=Path, default=None)
    parser.add_argument("--mode", choices=["live", "integration"], default="live")
    parser.add_argument("--auto-publish-count", type=int, default=1, help="Auto-publish N candidates (0 = skip publish/retrieval)")
    parser.add_argument(
        "--stop-after",
        choices=["candidates", "publish", "retrieval"],
        default="retrieval",
        help="Stop pipeline after a phase (default: full run through retrieval)",
    )
    parser.add_argument("--poll-max", type=int, default=600)
    parser.add_argument("--keep-services", action="store_true")
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument("--base-url", default=os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument(
        "--import-id",
        default=None,
        help="Skip upload; resume from existing import (need_confirm / confirmed / later)",
    )
    parser.add_argument(
        "--duplicate-action",
        choices=["normal", "new_version"],
        default="normal",
        help="Upload duplicate handling (new_version requires --parent-import-id)",
    )
    parser.add_argument(
        "--parent-import-id",
        default=None,
        help="Parent import when uploading a new version of a duplicate file",
    )
    parser.add_argument(
        "--from-step",
        choices=["auto", "upload", "confirm", "parse", "candidates", "publish", "retrieval"],
        default="auto",
        help="Start pipeline at a phase (later steps require --import-id)",
    )
    return parser


def build_config(args: argparse.Namespace) -> PipelineConfig:
    file_path = args.file or DEFAULT_FIXTURES[args.purpose]
    if not file_path.exists():
        raise SystemExit(f"file not found: {file_path}")
    kb_id = args.kb_id or ""
    if args.mode == "live" and not kb_id:
        raise SystemExit("--kb-id is required for live mode")
    return PipelineConfig(
        purpose=args.purpose,
        kb_id=kb_id,
        file_path=file_path,
        mode=args.mode,
        auto_publish_count=args.auto_publish_count,
        poll_max_seconds=args.poll_max,
        keep_services=args.keep_services,
        log_file=args.log_file,
        base_url=args.base_url,
        resume_import_id=args.import_id,
        duplicate_action=args.duplicate_action,
        parent_import_id=args.parent_import_id,
        from_step=args.from_step,
        stop_after=args.stop_after,
    )


def _patch_chapter_rules(module) -> None:
    module._CACHE = {
        "default": {"candidate_type": "ku", "suggested_knowledge_type": "solution"},
        "rules": {},
    }


def main() -> int:
    args = build_parser().parse_args()
    cfg = build_config(args)

    if cfg.mode == "integration":
        return run_integration_pipeline(cfg, monkeypatch_chapter_rules=_patch_chapter_rules)

    log_file = cfg.log_file or default_log_file(cfg)
    logger = JsonlRunLogger(
        log_file=log_file,
        run_id=str(uuid4()),
        purpose=cfg.purpose,
        mode=cfg.mode,
    )
    api = LiveClient(base_url=cfg.base_url, operator_id=cfg.operator_id)
    runner = E2EPipelineRunner(cfg, api, logger)
    try:
        return runner.run()
    finally:
        if not cfg.keep_services:
            subprocess.run(["bash", str(ROOT / "scripts/stop.sh")], cwd=str(ROOT), check=False)


if __name__ == "__main__":
    raise SystemExit(main())

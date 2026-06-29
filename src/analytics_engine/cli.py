"""CLI entry point — run pipeline, start API server, or start scheduler."""

from __future__ import annotations

import argparse
import logging
import sys


def main():
    parser = argparse.ArgumentParser(description="Project K Analytics Engine")
    sub = parser.add_subparsers(dest="command")

    # Pipeline command
    pipe = sub.add_parser("pipeline", help="Run pipeline for a client")
    pipe.add_argument("--client-id", required=True, help="Client ID to process")

    # API command
    sub.add_parser("api", help="Start the FastAPI server")

    # Scheduler command
    sub.add_parser("scheduler", help="Start the batch scheduler")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.command == "pipeline":
        _run_pipeline(args.client_id)
    elif args.command == "api":
        _run_api()
    elif args.command == "scheduler":
        _run_scheduler()
    else:
        parser.print_help()
        sys.exit(1)


def _run_pipeline(client_id: str):
    from analytics_engine.core.config import ConfigLoader
    from analytics_engine.db.engine import get_duck
    from analytics_engine.db.session import create_session
    from analytics_engine.pipeline.orchestrator import PipelineOrchestrator

    config = ConfigLoader()
    orchestrator = PipelineOrchestrator(
        session_factory=create_session,
        duck_factory=get_duck,
        config_loader=config,
    )
    ctx = orchestrator.run_for_client(client_id)
    print(f"Pipeline complete: {ctx.metrics_computed} metrics, {ctx.alerts_raised} alerts")


def _run_api():
    import os

    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8100"))
    uvicorn.run("analytics_engine.api.app:app", host=host, port=port, reload=True)


def _run_scheduler():
    import signal

    from analytics_engine.core.config import ConfigLoader
    from analytics_engine.pipeline.scheduler import PipelineScheduler

    config = ConfigLoader()
    scheduler = PipelineScheduler(config)
    scheduler.start()

    print("Scheduler running. Press Ctrl+C to stop.")

    def _shutdown(signum, frame):
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    import time
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()

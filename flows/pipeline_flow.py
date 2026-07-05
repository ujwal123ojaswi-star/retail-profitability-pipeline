"""Prefect flow: ingest -> load -> dbt build.

Run once:        python flows/pipeline_flow.py
Serve daily:     python flows/pipeline_flow.py --serve

Each step is a Prefect task so the run shows up as a DAG with per-step status.
dbt is invoked as a subprocess from the dbt/ directory (where profiles.yml lives).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from prefect import flow, task

from ingest.fred import ingest_fred
from ingest.load_raw import load_raw
from ingest.sec import ingest_sec

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DBT_DIR = PROJECT_ROOT / "dbt"


@task(retries=2, retry_delay_seconds=10)
def ingest_sec_task() -> str:
    return ingest_sec()


@task(retries=2, retry_delay_seconds=10)
def ingest_fred_task() -> str:
    return ingest_fred()


@task
def load_raw_task() -> None:
    load_raw()


@task
def dbt_task(command: list[str]) -> None:
    """Run a dbt command from the dbt project directory."""
    full = ["dbt", *command, "--profiles-dir", "."]
    print(f"[dbt] {' '.join(full)}")
    result = subprocess.run(full, cwd=DBT_DIR, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(f"dbt {command} failed with code {result.returncode}")


@flow(name="retail-profitability-pipeline")
def pipeline() -> None:
    sec_path = ingest_sec_task()
    fred_path = ingest_fred_task()
    load = load_raw_task(wait_for=[sec_path, fred_path])
    deps = dbt_task(["deps"], wait_for=[load])
    build = dbt_task(["build"], wait_for=[deps])  # build = run + test
    _ = build


if __name__ == "__main__":
    if "--serve" in sys.argv:
        pipeline.serve(name="daily-refresh", cron="0 6 * * *")
    else:
        pipeline()

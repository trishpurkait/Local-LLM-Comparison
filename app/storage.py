import json
from pathlib import Path
from typing import Any, Dict, List

from app.config import RESULTS_DIR
from app.schemas import EvaluationReport


def ensure_results_dir() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def save_report(report: EvaluationReport) -> Path:
    ensure_results_dir()

    file_path = RESULTS_DIR / f"{report.run_id}.json"

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(
            report.model_dump(),
            file,
            indent=2,
            ensure_ascii=False
        )

    return file_path


def load_report(run_id: str) -> Dict[str, Any]:
    file_path = RESULTS_DIR / f"{run_id}.json"

    if not file_path.exists():
        raise FileNotFoundError(f"No report found for run_id: {run_id}")

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def list_reports() -> List[Dict[str, Any]]:
    ensure_results_dir()

    reports = []

    json_files = sorted(
        RESULTS_DIR.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True
    )

    for file_path in json_files:
        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        reports.append({
            "run_id": data.get("run_id"),
            "models": data.get("models", []),
            "total_prompts": data.get("total_prompts", 0),
            "ranking": data.get("ranking", {})
        })

    return reports
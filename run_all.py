"""Rebuild the MetaShift-Bench public-data core from the frozen configuration."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "configs/benchmark_release_v1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild MetaShift-Bench outputs.")
    parser.add_argument(
        "--with-aqs-api",
        action="store_true",
        help="Download the optional QA-collocation responses using local credentials.",
    )
    return parser.parse_args()


def load_windows_user_environment() -> None:
    """Load local user credentials for a new Windows process without printing them."""

    if os.name != "nt":
        return
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            for variable in ("AQS_API_EMAIL", "AQS_API_KEY"):
                if not os.environ.get(variable):
                    try:
                        value, _ = winreg.QueryValueEx(key, variable)
                    except FileNotFoundError:
                        continue
                    os.environ[variable] = value
    except OSError:
        return


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def require_clean_worktree() -> None:
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True, encoding="utf-8"
    )
    if status.strip():
        raise RuntimeError(
            "run_all.py requires a clean source worktree so outputs can be tied "
            "to a fixed commit. Commit or discard source changes first."
        )


def write_run_manifest(config: dict[str, object]) -> None:
    from importlib.metadata import version

    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()
    manifest = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "git_commit": commit,
        "python": sys.version,
        "platform": platform.platform(),
        "packages": {
            package: version(package)
            for package in ("numpy", "pandas", "scipy", "ruptures", "matplotlib")
        },
        "config": config,
    }
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    require_clean_worktree()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    python = sys.executable
    multipliers = [
        str(value) for value in config["synthetic_perturbations"]["magnitude_multipliers"]
    ]

    run([python, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run([python, "scripts/scan_data_gate.py", "--download"])
    run(
        [
            python,
            "scripts/build_stable_synthetic_cases.py",
            "--case-count",
            str(config["stable_synthetic_cases"]["case_count"]),
            "--calibration-case-count",
            str(config["stable_synthetic_cases"]["calibration_cases"]),
        ]
    )
    run(
        [
            python,
            "scripts/run_stable_synthetic_benchmark.py",
            "--label",
            "stable_full_v1",
            "--magnitude-multipliers",
            *multipliers,
        ]
    )
    run(
        [
            python,
            "scripts/run_reliability_ablations.py",
            "--label",
            "stable_full_v1",
            "--magnitude-multipliers",
            *multipliers,
        ]
    )
    run([python, "scripts/verify_benchmark_ablation_alignment.py"])
    run(
        [
            python,
            "scripts/run_real_transition_audit.py",
            "--parameter-code",
            "88101",
            "--label",
            "88101",
        ]
    )
    run([python, "scripts/run_event_intervals.py"])
    run([python, "scripts/run_leave_one_donor_out.py"])
    run([python, "scripts/run_colocated_validation.py"])
    if args.with_aqs_api:
        load_windows_user_environment()
        if not (
            os.environ.get("AQS_API_EMAIL") and os.environ.get("AQS_API_KEY")
        ):
            raise RuntimeError(
                "--with-aqs-api requires locally configured AQS_API_EMAIL and AQS_API_KEY."
            )
        run([python, "scripts/download_qa_collocation.py"])
        run([python, "scripts/analyze_external_validation.py"])
    else:
        print(
            "Skipping API-backed QA refresh; existing local QA responses may still "
            "be analyzed only when credentials are supplied."
        )
    run([python, "scripts/run_time_placebos.py"])
    run([python, "scripts/run_additional_placebos.py"])
    run([python, "scripts/synthesize_real_event_evidence.py"])
    run(
        [
            python,
            "scripts/scan_data_gate.py",
            "--parameter-code",
            "88502",
            "--output-dir",
            "artifacts/data_gate_88502",
            "--download",
        ]
    )
    run(
        [
            python,
            "scripts/run_real_transition_audit.py",
            "--parameter-code",
            "88502",
            "--label",
            "88502",
        ]
    )
    run([python, "-m", "unittest", "discover", "-s", "tests", "-v"])
    write_run_manifest(config)
    run([python, "scripts/make_figures.py"])
    run([python, "scripts/evaluate_release_gate.py"])
    run([python, "scripts/export_evidence_bundle.py"])


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Measure failure signatures and faulty-program execution similarity on LFTBench."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_metadata(path: Path, root: Path) -> dict[str, Any]:
    data = path.read_bytes()
    try:
        relative = str(path.relative_to(root))
    except ValueError:
        relative = str(path)
    return {"path": relative, "bytes": len(data), "sha256": sha256_bytes(data)}


def run_binary(binary: Path, input_data: bytes, timeout_seconds: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [str(binary)],
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        duration = time.perf_counter() - started
        if completed.returncode == 0:
            outcome = "normal"
        elif completed.returncode < 0:
            outcome = f"signal_{-completed.returncode}"
        else:
            outcome = f"exit_{completed.returncode}"
        return {
            "outcome": outcome,
            "returncode": completed.returncode,
            "duration_seconds": duration,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired as timeout:
        return {
            "outcome": "timeout",
            "returncode": None,
            "duration_seconds": time.perf_counter() - started,
            "stdout": timeout.stdout or b"",
            "stderr": timeout.stderr or b"",
        }


def public_run_record(run: dict[str, Any]) -> dict[str, Any]:
    stdout = run["stdout"]
    stderr = run["stderr"]
    return {
        "outcome": run["outcome"],
        "returncode": run["returncode"],
        "duration_seconds": run["duration_seconds"],
        "stdout_bytes": len(stdout),
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_bytes": len(stderr),
        "stderr_sha256": sha256_bytes(stderr),
    }


def parse_number(token: bytes) -> float | None:
    try:
        return float(token.decode("ascii"))
    except (UnicodeDecodeError, ValueError, OverflowError):
        return None


def build_failure_signature(accepted: dict[str, Any], faulty: dict[str, Any]) -> dict[str, Any]:
    accepted_stdout = accepted["stdout"].strip()
    faulty_stdout = faulty["stdout"].strip()
    accepted_tokens = accepted_stdout.split()
    faulty_tokens = faulty_stdout.split()

    if accepted["outcome"] != "normal":
        category = "oracle_program_not_normal"
    elif faulty["outcome"] == "timeout":
        category = "faulty_program_timeout"
    elif faulty["outcome"].startswith("signal_"):
        category = "faulty_program_signal"
    elif faulty["outcome"].startswith("exit_"):
        category = "faulty_program_nonzero_exit"
    elif accepted_stdout == faulty_stdout:
        category = "output_match"
    else:
        category = "output_mismatch"

    first_difference = None
    mismatch_kind = None
    numeric_direction = None
    mismatched_positions = 0
    for index, (expected, observed) in enumerate(
        itertools.zip_longest(accepted_tokens, faulty_tokens)
    ):
        if expected == observed:
            continue
        mismatched_positions += 1
        if first_difference is None:
            first_difference = index
            if expected is None:
                mismatch_kind = "extra_observed_token"
            elif observed is None:
                mismatch_kind = "missing_observed_token"
            else:
                mismatch_kind = "token_substitution"
                expected_number = parse_number(expected)
                observed_number = parse_number(observed)
                if expected_number is not None and observed_number is not None:
                    if observed_number < expected_number:
                        numeric_direction = "observed_less"
                    elif observed_number > expected_number:
                        numeric_direction = "observed_greater"
                    else:
                        numeric_direction = "numerically_equal"

    denominator = max(len(accepted_tokens), len(faulty_tokens), 1)
    signature_key = {
        "category": category,
        "accepted_outcome": accepted["outcome"],
        "faulty_outcome": faulty["outcome"],
        "mismatch_kind": mismatch_kind,
        "numeric_direction": numeric_direction,
    }
    return {
        **signature_key,
        "signature_key": signature_key,
        "failure_observed": category not in {"output_match", "oracle_program_not_normal"},
        "accepted_tokens": len(accepted_tokens),
        "observed_tokens": len(faulty_tokens),
        "first_difference_token": first_difference,
        "first_difference_fraction": (
            first_difference / denominator if first_difference is not None else None
        ),
        "mismatched_token_positions": mismatched_positions,
        "mismatched_token_fraction": mismatched_positions / denominator,
    }


def clear_coverage_files(work_dir: Path) -> None:
    for pattern in ("*.gcda", "*.gcov.json.gz"):
        for path in work_dir.glob(pattern):
            path.unlink()


def parse_gcov(work_dir: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["gcov", "-b", "-c", "-j", "faulty.cpp"],
        cwd=work_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    archives = sorted(work_dir.glob("*.gcov.json.gz"))
    if completed.returncode != 0 or not archives:
        return {
            "status": "gcov_failed",
            "returncode": completed.returncode,
            "stderr": completed.stderr.decode("utf-8", errors="replace")[-2000:],
            "covered_lines": {},
            "covered_branches": {},
        }

    covered_lines: dict[str, int] = {}
    covered_branches: dict[str, int] = {}
    for archive in archives:
        with gzip.open(archive, "rt", encoding="utf-8") as handle:
            data = json.load(handle)
        for source_file in data.get("files", []):
            if Path(source_file.get("file", "")).name != "faulty.cpp":
                continue
            for line in source_file.get("lines", []):
                line_number = int(line["line_number"])
                count = int(line.get("count", 0))
                if count > 0:
                    covered_lines[str(line_number)] = count
                for branch_index, branch in enumerate(line.get("branches", [])):
                    branch_count = int(branch.get("count", 0))
                    if branch_count > 0:
                        covered_branches[f"{line_number}:{branch_index}"] = branch_count
    return {
        "status": "ok",
        "covered_lines": covered_lines,
        "covered_branches": covered_branches,
    }


def run_with_coverage(
    binary: Path, input_data: bytes, timeout_seconds: float, work_dir: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    clear_coverage_files(work_dir)
    run = run_binary(binary, input_data, timeout_seconds)
    coverage = parse_gcov(work_dir)
    return run, coverage


def set_metrics(original: dict[str, int], reduced: dict[str, int]) -> dict[str, float | int | None]:
    original_keys = set(original)
    reduced_keys = set(reduced)
    intersection = original_keys & reduced_keys
    union = original_keys | reduced_keys
    dot = sum(original[key] * reduced[key] for key in intersection)
    original_norm = math.sqrt(sum(value * value for value in original.values()))
    reduced_norm = math.sqrt(sum(value * value for value in reduced.values()))
    return {
        "original_covered": len(original_keys),
        "reduced_covered": len(reduced_keys),
        "intersection": len(intersection),
        "recall_of_original": len(intersection) / len(original_keys) if original_keys else None,
        "precision_to_original": len(intersection) / len(reduced_keys) if reduced_keys else None,
        "jaccard": len(intersection) / len(union) if union else None,
        "count_cosine": (
            dot / (original_norm * reduced_norm)
            if original_norm > 0 and reduced_norm > 0
            else None
        ),
    }


def compile_program(source: Path, output: Path, coverage: bool) -> dict[str, Any]:
    command = ["g++", "-std=c++20", "-o", str(output), source.name]
    if coverage:
        command.extend(["-O0", "-g", "-fprofile-arcs", "-ftest-coverage", "-fno-inline"])
    else:
        command.append("-O2")
    completed = subprocess.run(
        command,
        cwd=source.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "status": "ok" if completed.returncode == 0 else "compile_failed",
        "returncode": completed.returncode,
        "stderr": completed.stderr.decode("utf-8", errors="replace")[-4000:],
    }


def analyze_case(job: dict[str, Any]) -> dict[str, Any]:
    root = Path(job["root"])
    work_root = Path(job["work_root"])
    task = job["task"]
    submission = job["submission"]
    case_id = f"{task}/{submission}"
    case_work = work_root / task / submission
    if case_work.exists():
        shutil.rmtree(case_work)
    case_work.mkdir(parents=True)

    faulty_source = root / f"lftbench/data/submissions/cpp/{task}_{submission}.cpp"
    accepted_source = root / f"lftbench/data/ground_truth/cpp/{task}.cpp"
    original_input = root / f"lftbench/data/test_inputs/original/{task}_{submission}.txt"
    reduced_input = root / f"results/{task}/{submission}/reduced_input.txt"
    required = [faulty_source, accepted_source, original_input, reduced_input]
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    if missing:
        return {"schema_version": 1, "case_id": case_id, "status": "missing_files", "missing": missing}

    local_faulty = case_work / "faulty.cpp"
    local_accepted = case_work / "accepted.cpp"
    shutil.copy2(faulty_source, local_faulty)
    shutil.copy2(accepted_source, local_accepted)
    faulty_binary = case_work / "faulty"
    accepted_binary = case_work / "accepted"
    faulty_compile = compile_program(local_faulty, faulty_binary, coverage=True)
    accepted_compile = compile_program(local_accepted, accepted_binary, coverage=False)
    if faulty_compile["status"] != "ok" or accepted_compile["status"] != "ok":
        return {
            "schema_version": 1,
            "case_id": case_id,
            "task": task,
            "submission": submission,
            "status": "compile_failed",
            "faulty_compile": faulty_compile,
            "accepted_compile": accepted_compile,
        }

    executions: dict[str, Any] = {}
    coverages: dict[str, Any] = {}
    for condition, input_path in (("original", original_input), ("reduced", reduced_input)):
        input_data = input_path.read_bytes()
        accepted_run = run_binary(accepted_binary, input_data, job["timeout_seconds"])
        faulty_run, coverage_data = run_with_coverage(
            faulty_binary, input_data, job["timeout_seconds"], case_work
        )
        executions[condition] = {
            "input": file_metadata(input_path, root),
            "accepted": public_run_record(accepted_run),
            "faulty": public_run_record(faulty_run),
            "failure_signature": build_failure_signature(accepted_run, faulty_run),
        }
        coverages[condition] = coverage_data

    original_signature = executions["original"]["failure_signature"]
    reduced_signature = executions["reduced"]["failure_signature"]
    signature_match = original_signature["signature_key"] == reduced_signature["signature_key"]
    coverage_ok = all(coverages[name]["status"] == "ok" for name in ("original", "reduced"))
    similarity = None
    if coverage_ok:
        similarity = {
            "lines": set_metrics(
                coverages["original"]["covered_lines"], coverages["reduced"]["covered_lines"]
            ),
            "branches": set_metrics(
                coverages["original"]["covered_branches"],
                coverages["reduced"]["covered_branches"],
            ),
        }

    return {
        "schema_version": 1,
        "case_id": case_id,
        "task": task,
        "submission": submission,
        "status": "ok" if coverage_ok else "coverage_failed",
        "recorded_reducefix_status": job["recorded_status"],
        "sources": {
            "faulty": file_metadata(faulty_source, root),
            "accepted": file_metadata(accepted_source, root),
        },
        "executions": executions,
        "coverage": coverages,
        "failure_signature_match": signature_match,
        "execution_similarity": similarity,
    }


def load_jobs(root: Path, work_root: Path, timeout_seconds: float) -> list[dict[str, Any]]:
    reducer_results = json.loads((root / "result_reducer_reducefix.json").read_text(encoding="utf-8"))
    jobs = []
    for task, task_data in sorted(reducer_results.items()):
        for result in sorted(task_data["results"], key=lambda row: str(row["submission_id"])):
            if int(result["status_code"]) != 200:
                continue
            jobs.append(
                {
                    "root": str(root),
                    "work_root": str(work_root),
                    "task": task,
                    "submission": str(result["submission_id"]),
                    "recorded_status": int(result["status_code"]),
                    "timeout_seconds": timeout_seconds,
                }
            )
    return jobs


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    root = script_dir.parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument("--output", type=Path, default=script_dir / "lft_failure_fidelity.jsonl")
    parser.add_argument(
        "--work-root",
        type=Path,
        default=Path(tempfile.gettempdir()) / "reducefix-lft-failure-fidelity",
    )
    parser.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--case-limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.repo_root.resolve()
    work_root = args.work_root.resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    jobs = load_jobs(root, work_root, args.timeout_seconds)
    if args.case_limit is not None:
        jobs = jobs[: args.case_limit]
    if args.output.exists() and args.overwrite:
        args.output.unlink()
    completed: set[str] = set()
    if args.output.exists():
        for line in args.output.read_text(encoding="utf-8").splitlines():
            if line:
                completed.add(json.loads(line)["case_id"])
    jobs = [job for job in jobs if f"{job['task']}/{job['submission']}" not in completed]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with args.output.open("a", encoding="utf-8") as handle:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            future_to_job = {executor.submit(analyze_case, job): job for job in jobs}
            for index, future in enumerate(as_completed(future_to_job), start=1):
                job = future_to_job[future]
                try:
                    result = future.result()
                except Exception as exception:
                    result = {
                        "schema_version": 1,
                        "case_id": f"{job['task']}/{job['submission']}",
                        "task": job["task"],
                        "submission": job["submission"],
                        "status": "analysis_exception",
                        "detail": f"{type(exception).__name__}: {exception}",
                    }
                handle.write(json.dumps(result, sort_keys=True) + "\n")
                handle.flush()
                if index % 10 == 0 or index == len(jobs):
                    print(
                        f"progress={index}/{len(jobs)} elapsed_seconds={time.time() - started:.1f}",
                        flush=True,
                    )


if __name__ == "__main__":
    main()

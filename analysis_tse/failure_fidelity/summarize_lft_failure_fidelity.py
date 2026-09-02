#!/usr/bin/env python3
"""Summarize LFTBench failure fidelity and its relation to archived repair outcomes."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def load_manifest(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def cluster_bootstrap(
    rows: list[dict[str, Any]], value_key: str, seed: int = 20260806, repetitions: int = 10000
) -> dict[str, Any]:
    values = [float(row[value_key]) for row in rows if row.get(value_key) is not None]
    if not values:
        return {"n": 0, "mean": None, "ci95": [None, None]}
    by_task: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.get(value_key) is not None:
            by_task[row["task"]].append(float(row[value_key]))
    tasks = sorted(by_task)
    rng = np.random.default_rng(seed)
    samples = np.empty(repetitions)
    for index in range(repetitions):
        selected = rng.choice(tasks, size=len(tasks), replace=True)
        sample = [value for task in selected for value in by_task[task]]
        samples[index] = float(np.mean(sample))
    return {
        "n": len(values),
        "tasks": len(tasks),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "ci95": [float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))],
        "wins_ties_losses": {
            "wins": sum(value > 0 for value in values),
            "ties": sum(value == 0 for value in values),
            "losses": sum(value < 0 for value in values),
        },
    }


def describe(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "p25": None, "p75": None}
    array = np.asarray(values, dtype=float)
    return {
        "n": len(values),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p25": float(np.quantile(array, 0.25)),
        "p75": float(np.quantile(array, 0.75)),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
    }


def build_repair_case_rows(manifest: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in manifest:
        grouped[(row["task"], str(row["submission"]), row["model"], row["condition"])].append(row)

    case_model: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)
    for (task, submission, model, condition), rows in grouped.items():
        if len(rows) > 10:
            raise ValueError(f"more than ten candidates: {task}/{submission} {model} {condition}")
        case_id = f"{task}/{submission}"
        case_model[(case_id, model)][condition] = {
            "rate": sum(bool(row["passed"]) for row in rows) / 10,
            "shown_form": rows[0]["shown_form"],
            "shown_fraction": rows[0].get("shown_fraction"),
        }

    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (case_id, model), conditions in case_model.items():
        if not all(condition in conditions for condition in ("orig_tc", "reduced_tc", "no_tc")):
            continue
        if conditions["reduced_tc"]["shown_form"] == "source_mismatch":
            continue
        task, submission = case_id.split("/", 1)
        by_case[case_id].append(
            {
                "task": task,
                "submission": submission,
                "model": model,
                "origin_rate": conditions["orig_tc"]["rate"],
                "reduced_rate": conditions["reduced_tc"]["rate"],
                "baseline_rate": conditions["no_tc"]["rate"],
                "gain_reduced_origin": conditions["reduced_tc"]["rate"]
                - conditions["orig_tc"]["rate"],
                "gain_reduced_baseline": conditions["reduced_tc"]["rate"]
                - conditions["no_tc"]["rate"],
                "origin_shown_form": conditions["orig_tc"]["shown_form"],
                "origin_shown_fraction": conditions["orig_tc"]["shown_fraction"],
            }
        )

    result = {}
    for case_id, rows in by_case.items():
        result[case_id] = {
            "models": len(rows),
            "repair_origin_rate": float(np.mean([row["origin_rate"] for row in rows])),
            "repair_reduced_rate": float(np.mean([row["reduced_rate"] for row in rows])),
            "repair_baseline_rate": float(np.mean([row["baseline_rate"] for row in rows])),
            "repair_gain_reduced_origin": float(
                np.mean([row["gain_reduced_origin"] for row in rows])
            ),
            "repair_gain_reduced_baseline": float(
                np.mean([row["gain_reduced_baseline"] for row in rows])
            ),
            "origin_prefix_model_rows": sum(
                row["origin_shown_form"] == "prefix" for row in rows
            ),
        }
    return result


def correlation(rows: list[dict[str, Any]], x_key: str, y_key: str) -> dict[str, Any]:
    pairs = [
        (float(row[x_key]), float(row[y_key]))
        for row in rows
        if row.get(x_key) is not None and row.get(y_key) is not None
    ]
    if len(pairs) < 3:
        return {"n": len(pairs), "spearman_rho": None, "p_value": None}
    x, y = zip(*pairs)
    result = spearmanr(x, y)
    return {"n": len(pairs), "spearman_rho": float(result.statistic), "p_value": float(result.pvalue)}


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    root = script_dir.parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument("--fidelity", type=Path, default=script_dir / "lft_failure_fidelity.jsonl")
    parser.add_argument(
        "--manifest", type=Path, default=root / "analysis_tse/output/analysis_manifest.jsonl.gz"
    )
    parser.add_argument("--output", type=Path, default=script_dir / "lft_failure_fidelity_summary.json")
    parser.add_argument("--case-csv", type=Path, default=script_dir / "lft_failure_fidelity_cases.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.repo_root.resolve()
    fidelity = load_jsonl(args.fidelity.resolve())
    if len(fidelity) != len({row["case_id"] for row in fidelity}):
        raise ValueError("duplicate case IDs in fidelity rows")
    manifest = load_manifest(args.manifest.resolve())
    repair = build_repair_case_rows(manifest)
    reducer_results = json.loads((root / "result_reducer_reducefix.json").read_text(encoding="utf-8"))
    recorded = {
        f"{task}/{row['submission_id']}": row
        for task, data in reducer_results.items()
        for row in data["results"]
    }

    case_rows = []
    for row in fidelity:
        original = row["executions"]["original"]
        reduced = row["executions"]["reduced"]
        signature = reduced["failure_signature"]
        original_bytes = original["input"]["bytes"]
        reduced_bytes = reduced["input"]["bytes"]
        strict_output_divergence = signature["category"] == "output_mismatch"
        if strict_output_divergence:
            fidelity_class = (
                "signature_match" if row["failure_signature_match"] else "signature_changed"
            )
        else:
            fidelity_class = "output_divergence_not_preserved"
        record = recorded[row["case_id"]]
        case_record = {
            "case_id": row["case_id"],
            "task": row["task"],
            "submission": row["submission"],
            "fidelity_class": fidelity_class,
            "strict_output_divergence_preserved": strict_output_divergence,
            "reduced_failure_category": signature["category"],
            "failure_signature_match": row["failure_signature_match"],
            "original_bytes": original_bytes,
            "reduced_bytes": reduced_bytes,
            "compression_ratio": 1 - reduced_bytes / original_bytes,
            "strictly_smaller": reduced_bytes < original_bytes,
            "recorded_size_matches_artifact": (
                int(record["original_size_bytes"]) == original_bytes
                and int(record["reduced_size_bytes"]) == reduced_bytes
            ),
            "line_recall": row["execution_similarity"]["lines"]["recall_of_original"],
            "line_jaccard": row["execution_similarity"]["lines"]["jaccard"],
            "line_count_cosine": row["execution_similarity"]["lines"]["count_cosine"],
            "branch_recall": row["execution_similarity"]["branches"]["recall_of_original"],
            "branch_jaccard": row["execution_similarity"]["branches"]["jaccard"],
            "branch_count_cosine": row["execution_similarity"]["branches"]["count_cosine"],
        }
        case_record.update(repair.get(row["case_id"], {}))
        case_rows.append(case_record)

    repair_rows = [row for row in case_rows if row.get("repair_gain_reduced_origin") is not None]
    fidelity_groups = {}
    for group in (
        "signature_match",
        "signature_changed",
        "output_divergence_not_preserved",
    ):
        rows = [row for row in repair_rows if row["fidelity_class"] == group]
        fidelity_groups[group] = {
            "cases": len(rows),
            "repair_gain_reduced_origin": cluster_bootstrap(rows, "repair_gain_reduced_origin"),
            "repair_gain_reduced_baseline": cluster_bootstrap(rows, "repair_gain_reduced_baseline"),
            "compression_ratio": describe([row["compression_ratio"] for row in rows]),
            "branch_recall": describe(
                [row["branch_recall"] for row in rows if row["branch_recall"] is not None]
            ),
        }

    execution_bins = {}
    bins = (
        ("branch_recall_lt_0_75", lambda value: value < 0.75),
        ("branch_recall_0_75_to_lt_0_95", lambda value: 0.75 <= value < 0.95),
        ("branch_recall_0_95_to_lt_1", lambda value: 0.95 <= value < 1.0),
        ("branch_recall_1", lambda value: value == 1.0),
    )
    strict_rows = [
        row
        for row in repair_rows
        if row["strict_output_divergence_preserved"] and row["branch_recall"] is not None
    ]
    for label, predicate in bins:
        rows = [row for row in strict_rows if predicate(row["branch_recall"])]
        execution_bins[label] = {
            "cases": len(rows),
            "repair_gain_reduced_origin": cluster_bootstrap(rows, "repair_gain_reduced_origin"),
        }

    strict_all = [row for row in case_rows if row["strict_output_divergence_preserved"]]
    summary = {
        "schema_version": 1,
        "recorded_success_cases": len(case_rows),
        "unique_cases": len({row["case_id"] for row in case_rows}),
        "artifact_size_matches_recorded": sum(
            row["recorded_size_matches_artifact"] for row in case_rows
        ),
        "strictly_smaller": sum(row["strictly_smaller"] for row in case_rows),
        "reduced_failure_categories": dict(
            Counter(row["reduced_failure_category"] for row in case_rows)
        ),
        "strict_output_divergence_preserved": len(strict_all),
        "strict_output_divergence_rate_over_200": len(strict_all) / 200,
        "strict_output_divergence_rate_over_recorded_success": len(strict_all) / len(case_rows),
        "signature_match_within_strict": sum(row["failure_signature_match"] for row in strict_all),
        "signature_match_rate_within_strict": (
            sum(row["failure_signature_match"] for row in strict_all) / len(strict_all)
        ),
        "execution_similarity_within_strict": {
            key: describe([row[key] for row in strict_all if row[key] is not None])
            for key in (
                "line_recall",
                "line_jaccard",
                "line_count_cosine",
                "branch_recall",
                "branch_jaccard",
                "branch_count_cosine",
            )
        },
        "repair_case_rows_after_source_mismatch_quarantine": len(repair_rows),
        "fidelity_groups": fidelity_groups,
        "execution_bins": execution_bins,
        "correlations_within_strict": {
            "branch_recall_vs_repair_gain": correlation(
                strict_rows, "branch_recall", "repair_gain_reduced_origin"
            ),
            "branch_jaccard_vs_repair_gain": correlation(
                strict_rows, "branch_jaccard", "repair_gain_reduced_origin"
            ),
            "branch_count_cosine_vs_repair_gain": correlation(
                strict_rows, "branch_count_cosine", "repair_gain_reduced_origin"
            ),
            "compression_ratio_vs_repair_gain": correlation(
                strict_rows, "compression_ratio", "repair_gain_reduced_origin"
            ),
        },
        "analysis_policy": {
            "strict_output_divergence": "accepted and faulty programs both exit normally and stripped stdout differs",
            "signature_match": "same outcome category, mismatch kind, and first numeric-difference direction",
            "repair_unit": "mean candidate-success rate across available models for each case",
            "repair_quarantine": "exclude case-model rows whose archived Reduced Test is a source mismatch",
            "inference": "task-cluster bootstrap with 10,000 resamples",
        },
    }
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fieldnames = sorted({key for row in case_rows for key in row})
    with args.case_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(case_rows, key=lambda row: row["case_id"]))
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

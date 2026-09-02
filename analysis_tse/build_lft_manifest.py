#!/usr/bin/env python3
"""Freeze LFTBench prompt provenance and recompute paired repair statistics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


MODEL_SPECS = {
    "Qwen2.5-Coder-7B-Instruct": {
        "result": "result_repair_qwen25-coder7b.json",
        "artifact_suffix": "coder7b_qwen2.5-coder-7b-instruct",
    },
    "GLM-4-9B-Chat": {
        "result": "result_repair_glm4-9b.json",
        "artifact_suffix": "qwenplus-glm4-9b",
    },
    "DeepSeek-V3": {
        "result": "result_repair_deepseekv3.json",
        "artifact_suffix": "qwenplus-deepseekv3",
    },
    "Qwen2.5-Plus": {
        "result": "result_repair_qwenplus.json",
        "artifact_suffix": "qwenplus-qwenplus",
    },
}

CONDITIONS = ("no_tc", "orig_tc", "reduced_tc")


def sha256(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_bytes(path: Path | None) -> bytes | None:
    if path is None or not path.is_file():
        return None
    return path.read_bytes()


def relative(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


def classify_visible(source: bytes | None, visible: bytes | None) -> str:
    if visible is None:
        return "missing"
    if source is None:
        return "source_missing"
    if visible == source:
        return "full"
    if source.startswith(visible):
        if len(visible) in (20_480, 40_960):
            return f"prefix_{len(visible)}"
        return "prefix_other"
    return "not_source_prefix"


def flatten_results(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for task, task_data in payload.items():
        for row in task_data.get("results", []):
            rows[(task, str(row["submission_id"]))] = row
    return rows


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def artifact_path(
    case_dir: Path,
    submission: str,
    component: str,
    condition: str,
    version: int,
    suffix: str,
    extension: str = "txt",
) -> Path:
    return case_dir / (
        f"{submission}.{component}_{condition}_v{version}_{suffix}.{extension}"
    )


def pass_at_k(correct: int, total: int, k: int) -> float:
    if total <= 0:
        return math.nan
    k = min(k, total)
    if total - correct < k:
        return 1.0
    return 1.0 - math.comb(total - correct, k) / math.comb(total, k)


def percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    if not values:
        return math.nan
    index = (len(values) - 1) * q
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return values[low]
    return values[low] * (high - index) + values[high] * (index - low)


def cluster_bootstrap(
    rows: list[dict[str, Any]],
    value_key: str,
    seed: int = 20260806,
    samples: int = 10_000,
) -> dict[str, float]:
    by_task: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_task[row["task"]].append(float(row[value_key]))
    tasks = sorted(by_task)
    observed_values = [value for task in tasks for value in by_task[task]]
    observed = statistics.fmean(observed_values) if observed_values else math.nan
    if not tasks:
        return {"estimate": observed, "ci_low": math.nan, "ci_high": math.nan}
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(samples):
        sampled = [rng.choice(tasks) for _ in tasks]
        values = [value for task in sampled for value in by_task[task]]
        estimates.append(statistics.fmean(values))
    return {
        "estimate": observed,
        "ci_low": percentile(estimates, 0.025),
        "ci_high": percentile(estimates, 0.975),
        "bootstrap_samples": samples,
        "cluster": "task",
    }


def reducer_audit(root: Path) -> dict[str, Any]:
    reducefix_path = root / "result_reducer_reducefix.json"
    ddmin_path = root / "result_reducer_ddmin.json"
    ddmin_repair_path = root / "result_ddmin_repair_qwen2.5-coder-7b.json"
    reducefix = flatten_results(load_json(reducefix_path))
    ddmin = flatten_results(load_json(ddmin_path))
    ddmin_repair = flatten_results(load_json(ddmin_repair_path))

    reducefix_success = {
        key for key, row in reducefix.items() if row.get("status_code") == 200
    }
    ddmin_success = {key for key, row in ddmin.items() if row.get("status_code") == 200}
    repair_success = {
        key for key, row in ddmin_repair.items() if row.get("status_code") == 200
    }

    comparable = sorted(set(ddmin_repair) & set(reducefix) & set(ddmin))
    matches_reducefix = 0
    matches_ddmin = 0
    matches_neither = 0
    details = []
    for key in comparable:
        repair_size = ddmin_repair[key].get("reduced_size_bytes")
        reducefix_size = reducefix[key].get("reduced_size_bytes")
        ddmin_size = ddmin[key].get("reduced_size_bytes")
        match_reducefix = repair_size == reducefix_size and repair_size is not None
        match_ddmin = repair_size == ddmin_size and repair_size is not None
        matches_reducefix += int(match_reducefix)
        matches_ddmin += int(match_ddmin)
        matches_neither += int(not match_reducefix and not match_ddmin)
        if match_reducefix != match_ddmin or (not match_reducefix and not match_ddmin):
            details.append(
                {
                    "task": key[0],
                    "submission": key[1],
                    "ddmin_repair_size": repair_size,
                    "reducefix_size": reducefix_size,
                    "ddmin_size": ddmin_size,
                    "matches_reducefix": match_reducefix,
                    "matches_ddmin": match_ddmin,
                }
            )

    return {
        "source_files": {
            relative(path, root): sha256(path)
            for path in (reducefix_path, ddmin_path, ddmin_repair_path)
        },
        "reducefix_success": len(reducefix_success),
        "ddmin_success": len(ddmin_success),
        "strict_joint_success": len(reducefix_success & ddmin_success),
        "ddmin_repair_status_200": len(repair_success),
        "comparable_size_rows": len(comparable),
        "ddmin_repair_size_matches_reducefix": matches_reducefix,
        "ddmin_repair_size_matches_ddmin": matches_ddmin,
        "ddmin_repair_size_matches_neither": matches_neither,
        "claim_eligible": matches_ddmin > matches_reducefix,
        "conclusion": (
            "The current ddmin repair file is not claim-eligible: its recorded reduced "
            "sizes align predominantly with ReduceFix artifacts rather than ddmin artifacts."
            if matches_reducefix >= matches_ddmin
            else "The size audit does not detect predominant alignment with ReduceFix."
        ),
        "mismatch_rows": details,
    }


def build_manifest(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reducer_files = {
        "reducefix": root / "result_reducer_reducefix.json",
        "ddmin": root / "result_reducer_ddmin.json",
    }
    reducers = {
        name: flatten_results(load_json(path)) for name, path in reducer_files.items()
    }
    manifest: list[dict[str, Any]] = []
    case_model_rows: list[dict[str, Any]] = []

    for model, spec in MODEL_SPECS.items():
        result_path = root / spec["result"]
        result_hash = sha256(result_path)
        payload = load_json(result_path)
        for task, task_data in payload.items():
            for result in task_data.get("results", []):
                submission = str(result["submission_id"])
                case_dir = root / "results" / task / submission
                original_path = first_existing(
                    (
                        root / "results" / task / f"original_input_{submission}.txt",
                        case_dir / "original_input.txt",
                        root / "lftbench" / "data" / "test_inputs" / "original" / f"{task}_{submission}.txt",
                    )
                )
                reduced_path = first_existing(
                    (
                        case_dir / "reduced_input.txt",
                        root / "results" / task / f"reduced_input_{submission}.txt",
                    )
                )
                sources = {"orig_tc": original_path, "reduced_tc": reduced_path}
                source_bytes = {name: read_bytes(path) for name, path in sources.items()}
                evaluation = result.get("evaluation", {})
                summary_row: dict[str, Any] = {
                    "task": task,
                    "submission": submission,
                    "model": model,
                    "origin_source_bytes": len(source_bytes["orig_tc"] or b""),
                    "reduced_source_bytes": len(source_bytes["reduced_tc"] or b""),
                }
                for condition in CONDITIONS:
                    version_rows = evaluation.get(condition, {}).get("versions", [])
                    successful = sum(bool(row.get("passed")) for row in version_rows)
                    total = len(version_rows)
                    summary_row[f"{condition}_correct"] = successful
                    summary_row[f"{condition}_total"] = total
                    visible_classes: list[str] = []
                    visible_lengths: list[int] = []
                    visible_fractions: list[float] = []
                    prompt_contains_input: list[bool] = []
                    prompt_contains_expected: list[bool] = []
                    prompt_contains_actual: list[bool] = []

                    for version_result in version_rows:
                        version = int(version_result["version"])
                        suffix = spec["artifact_suffix"]
                        prompt_path = artifact_path(
                            case_dir, submission, "prompt", condition, version, suffix
                        )
                        response_path = artifact_path(
                            case_dir, submission, "llm_response", condition, version, suffix
                        )
                        fixed_path = artifact_path(
                            case_dir,
                            submission,
                            "fixed_code",
                            condition,
                            version,
                            suffix,
                            extension="cpp",
                        )
                        input_path = (
                            artifact_path(
                                case_dir,
                                submission,
                                "llm_input",
                                condition,
                                version,
                                suffix,
                            )
                            if condition != "no_tc"
                            else None
                        )
                        expected_path = (
                            artifact_path(
                                case_dir,
                                submission,
                                "expected_output",
                                condition,
                                version,
                                suffix,
                            )
                            if condition != "no_tc"
                            else None
                        )
                        actual_path = (
                            artifact_path(
                                case_dir,
                                submission,
                                "actual_output",
                                condition,
                                version,
                                suffix,
                            )
                            if condition != "no_tc"
                            else None
                        )
                        visible = read_bytes(input_path)
                        source = source_bytes.get(condition)
                        prompt = read_bytes(prompt_path)
                        expected = read_bytes(expected_path)
                        actual = read_bytes(actual_path)
                        visible_class = (
                            classify_visible(source, visible)
                            if condition != "no_tc"
                            else "not_applicable"
                        )
                        visible_fraction = (
                            len(visible) / len(source)
                            if visible is not None and source
                            else None
                        )
                        if condition != "no_tc":
                            visible_classes.append(visible_class)
                            if visible is not None:
                                visible_lengths.append(len(visible))
                            if visible_fraction is not None:
                                visible_fractions.append(visible_fraction)
                            prompt_contains_input.append(
                                bool(prompt is not None and visible is not None and visible in prompt)
                            )
                            prompt_contains_expected.append(
                                bool(
                                    prompt is not None
                                    and expected is not None
                                    and expected.strip() in prompt
                                )
                            )
                            prompt_contains_actual.append(
                                bool(
                                    prompt is not None
                                    and actual is not None
                                    and actual.strip() in prompt
                                )
                            )

                        manifest.append(
                            {
                                "task": task,
                                "submission": submission,
                                "model": model,
                                "condition": condition,
                                "version": version,
                                "passed": bool(version_result.get("passed")),
                                "status": version_result.get("status"),
                                "result_source": relative(result_path, root),
                                "result_source_sha256": result_hash,
                                "original_input_path": relative(original_path, root),
                                "original_input_sha256": sha256(original_path),
                                "reduced_input_path": relative(reduced_path, root),
                                "reduced_input_sha256": sha256(reduced_path),
                                "shown_input_path": relative(input_path, root),
                                "shown_input_sha256": sha256(input_path),
                                "shown_input_bytes": len(visible) if visible is not None else None,
                                "shown_fraction": visible_fraction,
                                "shown_form": visible_class,
                                "prompt_path": relative(prompt_path, root),
                                "prompt_sha256": sha256(prompt_path),
                                "response_path": relative(response_path, root),
                                "response_sha256": sha256(response_path),
                                "fixed_code_path": relative(fixed_path, root),
                                "fixed_code_sha256": sha256(fixed_path),
                                "expected_output_path": relative(expected_path, root),
                                "expected_output_sha256": sha256(expected_path),
                                "actual_output_path": relative(actual_path, root),
                                "actual_output_sha256": sha256(actual_path),
                                "prompt_contains_shown_input": (
                                    bool(prompt is not None and visible is not None and visible in prompt)
                                    if condition != "no_tc"
                                    else None
                                ),
                                "prompt_contains_expected_output": (
                                    bool(
                                        prompt is not None
                                        and expected is not None
                                        and expected.strip() in prompt
                                    )
                                    if condition != "no_tc"
                                    else None
                                ),
                                "prompt_contains_actual_output": (
                                    bool(
                                        prompt is not None
                                        and actual is not None
                                        and actual.strip() in prompt
                                    )
                                    if condition != "no_tc"
                                    else None
                                ),
                                "reducefix_status": reducers["reducefix"]
                                .get((task, submission), {})
                                .get("status_code"),
                                "reducefix_reduced_bytes": reducers["reducefix"]
                                .get((task, submission), {})
                                .get("reduced_size_bytes"),
                                "ddmin_status": reducers["ddmin"]
                                .get((task, submission), {})
                                .get("status_code"),
                                "ddmin_reduced_bytes": reducers["ddmin"]
                                .get((task, submission), {})
                                .get("reduced_size_bytes"),
                            }
                        )

                    if condition != "no_tc":
                        class_counts = Counter(visible_classes)
                        summary_row[f"{condition}_shown_form"] = (
                            class_counts.most_common(1)[0][0] if class_counts else "missing"
                        )
                        summary_row[f"{condition}_shown_forms"] = dict(class_counts)
                        summary_row[f"{condition}_shown_bytes"] = (
                            int(statistics.median(visible_lengths)) if visible_lengths else None
                        )
                        summary_row[f"{condition}_shown_fraction"] = (
                            statistics.median(visible_fractions)
                            if visible_fractions
                            else None
                        )
                        summary_row[f"{condition}_prompt_contains_input"] = all(
                            prompt_contains_input
                        ) if prompt_contains_input else False
                        summary_row[f"{condition}_prompt_contains_expected"] = all(
                            prompt_contains_expected
                        ) if prompt_contains_expected else False
                        summary_row[f"{condition}_prompt_contains_actual"] = all(
                            prompt_contains_actual
                        ) if prompt_contains_actual else False

                summary_row["delta_reduced_origin"] = (
                    summary_row["reduced_tc_correct"] - summary_row["orig_tc_correct"]
                ) / max(summary_row["orig_tc_total"], 1)
                summary_row["delta_reduced_no_test"] = (
                    summary_row["reduced_tc_correct"] - summary_row["no_tc_correct"]
                ) / max(summary_row["no_tc_total"], 1)
                summary_row["origin_truncated"] = (
                    summary_row["orig_tc_shown_form"] != "full"
                )
                summary_row["reduced_truncated"] = (
                    summary_row["reduced_tc_shown_form"] != "full"
                )
                case_model_rows.append(summary_row)

    return manifest, case_model_rows


def summarize_visible(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"models": {}, "all_case_model_rows": len(rows)}
    for model in MODEL_SPECS:
        model_rows = [row for row in rows if row["model"] == model]
        result["models"][model] = {
            "cases": len(model_rows),
            "origin_truncated": sum(row["origin_truncated"] for row in model_rows),
            "reduced_truncated": sum(row["reduced_truncated"] for row in model_rows),
            "origin_shown_forms": dict(
                Counter(row["orig_tc_shown_form"] for row in model_rows)
            ),
            "reduced_shown_forms": dict(
                Counter(row["reduced_tc_shown_form"] for row in model_rows)
            ),
            "origin_prompt_contains_input": sum(
                row["orig_tc_prompt_contains_input"] for row in model_rows
            ),
            "reduced_prompt_contains_input": sum(
                row["reduced_tc_prompt_contains_input"] for row in model_rows
            ),
        }

    truncated = [row for row in rows if row["origin_truncated"]]
    full = [row for row in rows if not row["origin_truncated"]]
    result["repair_delta_by_origin_visibility"] = {
        "truncated": {
            "rows": len(truncated),
            "reduced_minus_origin": cluster_bootstrap(
                truncated, "delta_reduced_origin", seed=20260806
            ),
        },
        "full": {
            "rows": len(full),
            "reduced_minus_origin": cluster_bootstrap(
                full, "delta_reduced_origin", seed=20260807
            ),
        },
    }
    return result


def summarize_repair(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {"overall": {}, "by_model": {}, "paired": {}}
    for condition in CONDITIONS:
        condition_rows = [row for row in rows if row[f"{condition}_total"]]
        output["overall"][condition] = {
            f"pass@{k}": statistics.fmean(
                pass_at_k(row[f"{condition}_correct"], row[f"{condition}_total"], k)
                for row in condition_rows
            )
            for k in (1, 5, 10)
        }
        output["overall"][condition]["correct_candidates"] = sum(
            row[f"{condition}_correct"] for row in condition_rows
        )

    for model in MODEL_SPECS:
        model_rows = [row for row in rows if row["model"] == model]
        output["by_model"][model] = {}
        for condition in CONDITIONS:
            output["by_model"][model][condition] = {
                f"pass@{k}": statistics.fmean(
                    pass_at_k(
                        row[f"{condition}_correct"], row[f"{condition}_total"], k
                    )
                    for row in model_rows
                )
                for k in (1, 5, 10)
            }

    for name, key in (
        ("reduced_minus_origin", "delta_reduced_origin"),
        ("reduced_minus_no_test", "delta_reduced_no_test"),
    ):
        values = [row[key] for row in rows]
        output["paired"][name] = {
            "mean_candidate_success_delta": cluster_bootstrap(rows, key),
            "wins": sum(value > 0 for value in values),
            "ties": sum(value == 0 for value in values),
            "losses": sum(value < 0 for value in values),
            "unit": "task-submission-model",
        }
    return output


def write_outputs(
    output_dir: Path,
    manifest: list[dict[str, Any]],
    case_model_rows: list[dict[str, Any]],
    root: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "analysis_manifest.jsonl").open("w", encoding="utf-8") as handle:
        for row in manifest:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    csv_fields = [
        "task",
        "submission",
        "model",
        "origin_source_bytes",
        "orig_tc_shown_bytes",
        "orig_tc_shown_fraction",
        "orig_tc_shown_form",
        "origin_truncated",
        "reduced_source_bytes",
        "reduced_tc_shown_bytes",
        "reduced_tc_shown_fraction",
        "reduced_tc_shown_form",
        "reduced_truncated",
        "no_tc_correct",
        "orig_tc_correct",
        "reduced_tc_correct",
        "delta_reduced_origin",
        "delta_reduced_no_test",
        "orig_tc_prompt_contains_input",
        "orig_tc_prompt_contains_expected",
        "orig_tc_prompt_contains_actual",
        "reduced_tc_prompt_contains_input",
        "reduced_tc_prompt_contains_expected",
        "reduced_tc_prompt_contains_actual",
    ]
    with (output_dir / "visible_evidence_rows.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(case_model_rows)

    payloads = {
        "visible_evidence_summary.json": summarize_visible(case_model_rows),
        "paired_repair_stats.json": summarize_repair(case_model_rows),
        "provenance_audit.json": reducer_audit(root),
    }
    for filename, payload in payloads.items():
        with (output_dir / filename).open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="ReduceFix repository root",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "output",
        help="directory for derived artifacts",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    manifest, case_model_rows = build_manifest(root)
    write_outputs(args.output.resolve(), manifest, case_model_rows, root)
    print(
        json.dumps(
            {
                "manifest_rows": len(manifest),
                "case_model_rows": len(case_model_rows),
                "output": str(args.output.resolve()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Print and sanity-check key manuscript numbers from result snapshots."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from hashlib import sha256
from math import comb, inf
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANUSCRIPT_ROOT = ROOT.parent
MANUSCRIPT_SOURCE_FILES = [
    path
    for path in sorted(MANUSCRIPT_ROOT.glob("*.tex"))
    + [
        MANUSCRIPT_ROOT / "submission_letter_tse.md",
        MANUSCRIPT_ROOT / "submission_letter_tse.txt",
        MANUSCRIPT_ROOT / "readme.txt",
        ROOT / "README.md",
    ]
    if path.is_file()
]
MAIN_WORD_COUNT_FILES = [
    "0.abstract.tex",
    "1.introduction.tex",
    "2.motivating_example.tex",
    "3.approach.tex",
    "4.experimental_setup.tex",
    "5.experiments.tex",
    "5.experiments-rq1.tex",
    "5.experiments-rq2.tex",
    "5.experiments-rq3.tex",
    "5.experiments-rq4.tex",
    "5.experiments-rq5.tex",
    "7.threats.tex",
    "8.related_works.tex",
    "9.conclusion.tex",
]


def load(name: str) -> dict:
    with (ROOT / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def pct(value: float) -> float:
    return round(value * 100.0, 1)


def rounded(value: float) -> float:
    return round(float(value), 1)


def check_equal(label: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def two_sided_sign_p(better: int, worse: int) -> float:
    n = better + worse
    if n == 0:
        return 1.0
    tail = sum(comb(n, k) for k in range(0, min(better, worse) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def check_p(label: str, actual: float, expected_rounded: float) -> None:
    check_equal(label, round(actual, 3), expected_rounded)


def check_contains(label: str, file_name: str, expected: str) -> None:
    path = MANUSCRIPT_ROOT / file_name
    if not path.exists():
        print(f"Skipping manuscript source check {label}: {file_name} not found.")
        return
    text = path.read_text(encoding="utf-8")
    if expected not in text:
        raise AssertionError(f"{label}: {expected!r} not found in {file_name}")


def check_not_contains(label: str, file_name: str, unexpected: str) -> None:
    path = MANUSCRIPT_ROOT / file_name
    if not path.exists():
        print(f"Skipping manuscript source check {label}: {file_name} not found.")
        return
    text = path.read_text(encoding="utf-8")
    if unexpected in text:
        raise AssertionError(f"{label}: unexpected {unexpected!r} found in {file_name}")


def check_readme_hashes() -> None:
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    entries = re.findall(r"- `([0-9a-f]{64})  ([^`]+)`", text)
    if not entries:
        raise AssertionError("artifact README: no SHA256 entries found")
    for expected_hash, file_name in entries:
        path = ROOT / file_name
        if not path.exists():
            raise AssertionError(f"artifact README hash target missing: {file_name}")
        actual_hash = sha256(path.read_bytes()).hexdigest()
        check_equal(f"artifact README hash {file_name}", actual_hash, expected_hash)


def check_source_hygiene() -> None:
    forbidden = [
        "TODO",
        "FIXME",
        "XXX",
        "??",
        "selected by outcome",
        "post hoc",
        "cherrypick",
        "cherry-pick",
        "selected by artifact",
        "not on which prompt",
        "published absolute rates",
        "rather than reproducing",
        "183-case",
        "166-case",
        "184-case",
        "/home/barty",
        "/root",
        "192.168",
        "paper.llm4code",
        "git.jisuan",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "validator-correct",
        "semantic proof",
        "without conditioning",
        "show that reducer synthesis transfers",
        "show that the gains come from",
        "gains come from validated selection",
        "isolates the effect",
        "changes repair correctness",
        "whole-test",
        "full-test",
        "unreduced-test",
        "unreduced test",
        "unreduced prompt",
        "unreduced prompts",
        "unreduced input",
        "fixed-source-context",
        "fixed source context",
        "fixed repair context",
        "when the source context is fixed",
        "when a validator is available",
        "only reduction is used",
        "higher measured",
        "when a patch validator is available",
        "fixed-context repair",
        "globally shortest",
        "not evidence that each",
        "not a claim that every",
        "bounded transfer",
        "weakening the contribution",
        "improves repair correctness",
        "raises fixed-source-context repair correctness",
        "yields higher fixed-source-context repository repair correctness",
        "explains why the repository-level repair gain",
        "To reduce training-exposure risk",
        "reduce dataset and pretraining-exposure risk",
        "\\resizebox",
        "\\vspace",
    ]
    for path in MANUSCRIPT_SOURCE_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for phrase in forbidden:
            if phrase in text:
                rel = path.relative_to(MANUSCRIPT_ROOT)
                raise AssertionError(f"source hygiene: unexpected {phrase!r} found in {rel}")


def check_figure_descriptions() -> None:
    for path in sorted(MANUSCRIPT_ROOT.glob("*.tex")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines):
            if "\\includegraphics" not in line:
                continue
            end = next((j for j in range(idx, len(lines)) if "\\end{figure" in lines[j]), min(len(lines), idx + 30))
            block = "\n".join(lines[idx : end + 1])
            if "\\Description" not in block:
                rel = path.relative_to(MANUSCRIPT_ROOT)
                raise AssertionError(f"figure description: missing \\Description near {rel}:{idx + 1}")


def strip_tex_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in text.splitlines())


def existing_tex_path(raw_name: str, suffixes: tuple[str, ...]) -> Path | None:
    name = raw_name.strip()
    path = MANUSCRIPT_ROOT / name
    candidates = [path]
    for suffix in suffixes:
        if not str(path).endswith(suffix):
            candidates.append(Path(str(path) + suffix))
        if not path.suffix:
            candidates.append(path.with_suffix(suffix))
    return next((candidate for candidate in dict.fromkeys(candidates) if candidate.exists()), None)


def check_latex_structure() -> None:
    label_locations: dict[str, list[str]] = defaultdict(list)
    references: list[tuple[str, str]] = []
    missing_inputs: list[str] = []
    missing_graphics: list[str] = []

    for path in sorted(MANUSCRIPT_ROOT.glob("*.tex")):
        rel = path.relative_to(MANUSCRIPT_ROOT)
        text = strip_tex_comments(path.read_text(encoding="utf-8"))
        for match in re.finditer(r"\\label\{([^}]+)\}|\blabel\s*=\s*\{([^}]+)\}", text):
            label = next(group for group in match.groups() if group)
            line = text[: match.start()].count("\n") + 1
            label_locations[label].append(f"{rel}:{line}")
        for match in re.finditer(r"\\(?:ref|eqref|autoref|pageref)\*?\{([^}]+)\}", text):
            line = text[: match.start()].count("\n") + 1
            references.append((match.group(1), f"{rel}:{line}"))
        for match in re.finditer(r"\\(?:input|include)\{([^}]+)\}", text):
            if existing_tex_path(match.group(1), (".tex",)) is None:
                line = text[: match.start()].count("\n") + 1
                missing_inputs.append(f"{rel}:{line} -> {match.group(1)}")
        for match in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text):
            if existing_tex_path(match.group(1), (".pdf", ".png", ".jpg", ".jpeg")) is None:
                line = text[: match.start()].count("\n") + 1
                missing_graphics.append(f"{rel}:{line} -> {match.group(1)}")

    duplicates = {label: locations for label, locations in label_locations.items() if len(locations) > 1}
    if duplicates:
        details = "; ".join(f"{label}: {', '.join(locations)}" for label, locations in sorted(duplicates.items()))
        raise AssertionError(f"latex structure gate: duplicate labels: {details}")
    label_names = set(label_locations)
    missing_refs = [f"{location} -> {label}" for label, location in references if label not in label_names]
    if missing_refs:
        raise AssertionError("latex structure gate: missing references: " + "; ".join(missing_refs))
    if missing_inputs:
        raise AssertionError("latex structure gate: missing input/include files: " + "; ".join(missing_inputs))
    if missing_graphics:
        raise AssertionError("latex structure gate: missing graphics files: " + "; ".join(missing_graphics))


def tex_word_count(text: str) -> int:
    for environment in ("table", "table*", "figure", "figure*", "lstlisting", "algorithm", "equation", "align", "longtable", "tabular"):
        text = re.sub(
            r"\\begin\{" + re.escape(environment) + r"\}.*?\\end\{" + re.escape(environment) + r"\}",
            " ",
            text,
            flags=re.S,
        )
    text = re.sub(r"\\\[.*?\\\]", " ", text, flags=re.S)
    text = re.sub(r"\$.*?\$", " ", text, flags=re.S)
    text = re.sub(r"(?<!\\)%.*", " ", text)
    text = re.sub(r"\\begin\{[^{}]+\}|\\end\{[^{}]+\}", " ", text)
    text = re.sub(r"\\(cite\w*|ref|label|input|includegraphics|Description|caption)\*?(?:\[[^\]]*\])?\{[^{}]*\}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"[{}_^$&~#]", " ", text)
    return len(re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", text))


def check_submission_gates() -> None:
    abstract_text = (MANUSCRIPT_ROOT / "0.abstract.tex").read_text(encoding="utf-8")
    abstract_words = tex_word_count(abstract_text)
    if abstract_words > 220:
        raise AssertionError(f"submission gate: abstract word count {abstract_words} exceeds 220")
    main_text = "\n".join((MANUSCRIPT_ROOT / name).read_text(encoding="utf-8") for name in MAIN_WORD_COUNT_FILES)
    main_words = tex_word_count(main_text)
    if main_words > 11000:
        raise AssertionError(f"submission gate: main manuscript word count {main_words} exceeds 11000")
    print(f"  submission gates: abstract/main rough word counts = {abstract_words}/{main_words}")


def check_submission_format_gates() -> None:
    main = (MANUSCRIPT_ROOT / "main.tex").read_text(encoding="utf-8")
    appendix_path = MANUSCRIPT_ROOT / "appendix_main.tex"
    if not appendix_path.is_file():
        print("  appendix wiring: supplement absent, check skipped")
        return
    appendix = appendix_path.read_text(encoding="utf-8")
    authors = (MANUSCRIPT_ROOT / "authors.tex").read_text(encoding="utf-8")
    cover = (MANUSCRIPT_ROOT / "submission_letter_tse.md").read_text(encoding="utf-8")
    readme = (MANUSCRIPT_ROOT / "readme.txt").read_text(encoding="utf-8")
    required_main = [
        "\\documentclass[10pt,journal,compsoc]{IEEEtran}",
        "\\setcounter{secnumdepth}{3}",
    ]
    required_appendix = [
        "\\documentclass[10pt,journal,compsoc]{IEEEtran}",
        "\\externaldocument{main}",
        "\\bibliography{sample-base}",
    ]
    # IEEE requires the earlier conference version to be disclosed on page one.
    required_authors = [
        "A preliminary version of this work appeared at ICSE 2026",
    ]
    required_cover = [
        "not under review elsewhere",
    ]
    required_readme = [
        "artifact_snapshot/check_snapshot_numbers.py",
    ]
    for label, text, required in [
        ("main template", main, required_main),
        ("appendix template", appendix, required_appendix),
        ("prior-publication disclosure", authors, required_authors),
        ("cover letter", cover, required_cover),
        ("supplementary readme", readme, required_readme),
    ]:
        for phrase in required:
            if phrase not in text:
                raise AssertionError(f"submission format gate: {phrase!r} missing from {label}")
    print("  submission format gates: IEEE/TSE template, appendix wiring, and prior-version disclosure present")


def check_bib_consistency() -> None:
    bib_text = (MANUSCRIPT_ROOT / "sample-base.bib").read_text(encoding="utf-8")
    bib_entries: dict[str, tuple[str, set[str]]] = {}
    for match in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)(?=\n@\w+\s*\{|\Z)", bib_text, flags=re.S):
        entry_type, key, body = match.groups()
        fields = {field.lower() for field in re.findall(r"\n\s*([A-Za-z][A-Za-z0-9_-]*)\s*=", body)}
        bib_entries[key] = (entry_type.lower(), fields)
    bib_keys = set(bib_entries)
    used_keys: set[str] = set()
    for path in sorted(MANUSCRIPT_ROOT.glob("*.tex")):
        text = path.read_text(encoding="utf-8")
        for cite_group in re.findall(r"\\cite\w*\{([^}]+)\}", text):
            used_keys.update(key.strip() for key in cite_group.split(",") if key.strip())
    missing = sorted(used_keys - bib_keys)
    # Entries cited only by the supplement look unused when it is not
    # checked out, which says nothing about the bibliography.
    supplement_present = (MANUSCRIPT_ROOT / "appendix_main.tex").is_file()
    unused = sorted(bib_keys - used_keys) if supplement_present else []
    if missing:
        raise AssertionError(f"citation gate: missing BibTeX keys {missing}")
    if unused:
        raise AssertionError(f"citation gate: unused BibTeX keys {unused}")
    required_fields = {
        "article": {"author", "title", "journal", "year"},
        "inproceedings": {"author", "title", "booktitle", "year"},
        "misc": {"author", "title", "year"},
    }
    metadata_gaps = []
    for key in sorted(used_keys):
        entry_type, fields = bib_entries[key]
        required = required_fields.get(entry_type, {"author", "title", "year"})
        absent = sorted(required - fields)
        if absent:
            metadata_gaps.append(f"{key} ({entry_type}): missing {', '.join(absent)}")
    if metadata_gaps:
        raise AssertionError("citation metadata gate: " + "; ".join(metadata_gaps))
    print(f"  citation gate: {len(used_keys)} cited keys all resolve, no BibTeX entries are unused, and required metadata is present")


def check_repair_row(label: str, actual: list[float], expected: list[float]) -> None:
    check_equal(label, [round(float(value), 1) for value in actual], expected)


def best_locality_records(locality: dict) -> dict:
    best = defaultdict(lambda: {"aed": inf, "ccr": -inf, "changed_lines": inf})
    for record in locality["records"]:
        key = (record["model"], record["case_key"], record["strategy"])
        if record["aed"] < best[key]["aed"]:
            best[key]["aed"] = record["aed"]
        if record["ccr"] > best[key]["ccr"]:
            best[key]["ccr"] = record["ccr"]
        if record["changed_lines"] < best[key]["changed_lines"]:
            best[key]["changed_lines"] = record["changed_lines"]
    return best


def paired_locality_sign_test(best: dict, metric: str, other: str, higher_is_better: bool) -> tuple[int, int, int, float]:
    better = worse = tie = 0
    for model, case_key, strategy in list(best):
        if strategy != "reduced_tc":
            continue
        other_key = (model, case_key, other)
        if other_key not in best:
            continue
        reduced_value = best[(model, case_key, strategy)][metric]
        other_value = best[other_key][metric]
        if reduced_value == other_value:
            tie += 1
        elif (reduced_value > other_value) if higher_is_better else (reduced_value < other_value):
            better += 1
        else:
            worse += 1
    return better, worse, tie, two_sided_sign_p(better, worse)



def load_jsonl(name: str) -> list:
    rows = []
    with (ROOT / name).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def report_search_behaviour() -> None:
    """Recompute the generated reducers' own search figures."""
    from statistics import median

    rf = load_jsonl("reducer_search_log.jsonl")
    reduced = [
        r for r in rf
        if r.get("status") == "ok"
        and r.get("reduced_size") is not None
        and r["reduced_size"] < r["original_size"]
    ]
    calls = [r["predicate_calls"] for r in reduced if r.get("predicate_calls")]
    per_call = [
        (r["original_size"] - r["reduced_size"]) / r["predicate_calls"]
        for r in reduced if r.get("predicate_calls")
    ]
    accepted = [
        100.0 * r["accepted_moves"] / r["predicate_calls"] for r in reduced
        if r.get("accepted_moves") is not None and r.get("predicate_calls")
    ]
    moves = [r["accepted_moves"] for r in reduced
             if r.get("accepted_moves") is not None]

    print("\nGenerated-reducer search behaviour")
    print(f"  programs reduced: {len(reduced)}")
    print(f"  median evaluations={median(calls):.0f}, "
          f"bytes per evaluation={median(per_call):,.0f}, "
          f"advancing={median(accepted):.1f}%, "
          f"accepted moves={median(moves):.0f}")

    check_equal("search: median evaluations", round(median(calls)), 24)
    check_equal("search: median bytes per evaluation",
                round(median(per_call)), 26132)
    check_equal("search: median advancing share",
                round(median(accepted), 1), 58.1)
    check_equal("search: median accepted moves", round(median(moves)), 18)



def check_fault_failure_vocabulary() -> None:
    """Keep the manuscript's prose to the standard fault/error/failure terms."""
    import re

    banned = {
        "bug": r"\\b[Bb]ugs?\\b",
        "error": r"\\b[Ee]rrors?\\b",
        "method": r"\\b[Mm]ethods?\\b",
        "wrong answer": r"\\b[Ww]rong answers?\\b",
    }
    # The prompt template reproduces what was sent to the models, so its
    # wording belongs to the experiment rather than to the prose.
    exempt_files = {"supplementary.tex"}
    exempt_lines = ("\\cite", "\\bibitem", "@", "url{", "lstlisting")

    offences = []
    for path in sorted(MANUSCRIPT_ROOT.glob("*.tex")):
        if path.name in exempt_files:
            continue
        inside_listing = False
        for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip()
            if "\\begin{lstlisting}" in line:
                inside_listing = True
            if "\\end{lstlisting}" in line:
                inside_listing = False
                continue
            if inside_listing or stripped.startswith("%"):
                continue
            if any(token in line for token in exempt_lines):
                continue
            for term, pattern in banned.items():
                if re.search(pattern, line):
                    offences.append(f"{path.name}:{number} uses {term!r}")

    print("\nFault/error/failure vocabulary")
    if offences:
        for offence in offences:
            print(f"  {offence}")
        raise AssertionError(
            "vocabulary: the manuscript prose must distinguish fault, error, "
            "and failure, and must not use 'bug' or 'method': "
            + "; ".join(offences[:4])
        )
    print("  prose keeps fault, error, and failure distinct")


def main() -> None:
    oss = load("oss_fuzz_ge4k_complete10_deep_stats.json")
    dbms = load("sqlancer_sqlite_main_current_cleanup_summary.json")
    locality = load("lftbench_patch_locality_rq2.json")
    core = load("lftbench_core_results.json")
    case_studies = load("oss_fuzz_case_study_snapshot.json")

    motivating_records = [
        record for record in locality["records"]
        if record.get("case_key") == "abc376c/65060141"
        and record.get("strategy") == "reduced_tc"
        and record.get("model") == "qwen25-coder7b"
    ]
    check_equal("ABC376C motivating example correct reduced-test versions", [
        record["version"] for record in motivating_records
    ], [5])

    print("LFTBench core reducer and repair results")
    dataset = core["dataset_stats"]
    check_equal("LFTBench C++ submissions", dataset["cpp_submission_count"], 200)
    check_equal("LFTBench C++ tasks", dataset["cpp_task_count"], 20)
    check_equal("LFTBench C++ submissions per task", dataset["cpp_counts_per_task_unique"], [10])
    check_equal("LFTBench-Py submissions", dataset["python_submission_count"], 20)
    check_equal("LFTBench-Py tasks", dataset["python_task_count"], 20)
    check_equal("LFTBench-Py submissions per task", dataset["python_counts_per_task_unique"], [1])
    check_equal("LFTBench median failing input bytes", dataset["median_failing_input_bytes"], 1300007)
    check_equal("LFTBench largest failing input bytes", dataset["max_failing_input_bytes"], 8211979)
    check_equal("LFTBench task ids", dataset["task_ids"], [
        "abc361c",
        "abc362d",
        "abc363e",
        "abc364d",
        "abc365d",
        "abc366c",
        "abc367d",
        "abc368c",
        "abc369d",
        "abc370d",
        "abc371d",
        "abc372e",
        "abc373e",
        "abc374e",
        "abc375c",
        "abc376c",
        "abc376d",
        "abc376e",
        "abc377c",
        "abc377f",
    ])
    rq1 = core["rq1_reducer_by_input_format"]["overall"]
    check_equal("LFTBench RQ1 overall cases", rq1["n"], 200)
    check_equal("LFTBench RQ1 overall SR", rq1["sr"], {"reducefix": 95.0, "pure_llm": 40.0, "ddmin": 35.5})
    check_equal("LFTBench RQ1 ReduceFix CR", rq1["cr_mean_median"]["reducefix"], [89.1, 100.0])
    expected_rq1_difficulties = {
        "C": (60, {"reducefix": 100.0, "pure_llm": 63.3, "ddmin": 30.0}, {
            "reducefix": [84.5, 100.0],
            "pure_llm": [100.0, 100.0],
            "ddmin": [100.0, 100.0],
        }),
        "D": (80, {"reducefix": 96.2, "pure_llm": 36.2, "ddmin": 17.5}, {
            "reducefix": [97.0, 100.0],
            "pure_llm": [100.0, 100.0],
            "ddmin": [100.0, 100.0],
        }),
        "E&F": (60, {"reducefix": 88.3, "pure_llm": 21.7, "ddmin": 65.0}, {
            "reducefix": [83.0, 99.9],
            "pure_llm": [99.1, 99.2],
            "ddmin": [84.2, 99.9],
        }),
        "overall": (200, {"reducefix": 95.0, "pure_llm": 40.0, "ddmin": 35.5}, {
            "reducefix": [89.1, 100.0],
            "pure_llm": [99.8, 100.0],
            "ddmin": [91.3, 100.0],
        }),
    }
    for difficulty, (expected_n, expected_sr, expected_cr) in expected_rq1_difficulties.items():
        row = core["rq1_reducer_by_difficulty"][difficulty]
        check_equal(f"LFTBench RQ1 {difficulty} n", row["n"], expected_n)
        check_equal(f"LFTBench RQ1 {difficulty} SR", row["sr"], expected_sr)
        check_equal(f"LFTBench RQ1 {difficulty} CR", row["cr_mean_median"], expected_cr)
    expected_rq1_formats = {
        "single_sequence": (80, {"reducefix": 97.5, "pure_llm": 36.2, "ddmin": 52.5}),
        "multi_sequence": (40, {"reducefix": 100.0, "pure_llm": 50.0, "ddmin": 22.5}),
        "dependent_sequence": (40, {"reducefix": 85.0, "pure_llm": 22.5, "ddmin": 35.0}),
        "matrix_2d": (10, {"reducefix": 90.0, "pure_llm": 0.0, "ddmin": 60.0}),
        "graph": (20, {"reducefix": 95.0, "pure_llm": 65.0, "ddmin": 0.0}),
        "string": (10, {"reducefix": 100.0, "pure_llm": 90.0, "ddmin": 0.0}),
        "overall": (200, {"reducefix": 95.0, "pure_llm": 40.0, "ddmin": 35.5}),
    }
    for input_format, (expected_n, expected_sr) in expected_rq1_formats.items():
        row = core["rq1_reducer_by_input_format"][input_format]
        check_equal(f"LFTBench RQ1 {input_format} n", row["n"], expected_n)
        check_equal(f"LFTBench RQ1 {input_format} SR", row["sr"], expected_sr)
    rq2 = core["rq2_repair"]["qwen2.5-coder-7b-instruct"]
    check_repair_row("LFTBench RQ2 Qwen Baseline", rq2["baseline"], [4.6, 13.9, 20.0])
    check_repair_row("LFTBench RQ2 Qwen Origin Test", rq2["origin_test"], [4.1, 13.1, 19.0])
    check_repair_row("LFTBench RQ2 Qwen Reduced Test", rq2["reduced_test"], [6.3, 17.9, 25.5])
    check_repair_row("LFTBench RQ2 ddmin-only", rq2["ddmin_only"], [5.7, 16.1, 22.0])
    check_equal("LFTBench RQ2 pass@10 by model", core["rq2_repair"]["pass_at_10_by_model"], {
        "qwen2.5-coder-7b-instruct": {"baseline": 20.0, "origin_test": 19.0, "reduced_test": 25.5},
        "glm-4-9b-chat": {"baseline": 8.5, "origin_test": 6.5, "reduced_test": 10.0},
        "qwen-plus": {"baseline": 59.0, "origin_test": 59.0, "reduced_test": 61.0},
        "deepseek-v3": {"baseline": 66.5, "origin_test": 63.0, "reduced_test": 67.0},
    })
    expected_rq2_by_model = {
        "qwen2.5-coder-7b-instruct": {
            "C": {"baseline": [5.5, 17.1, 23.3], "origin_test": [3.7, 13.2, 20.0], "reduced_test": [5.5, 16.7, 25.0]},
            "D": {"baseline": [6.4, 17.4, 25.0], "origin_test": [6.1, 17.4, 23.8], "reduced_test": [9.9, 26.0, 36.2]},
            "E&F": {"baseline": [1.3, 5.9, 10.0], "origin_test": [1.8, 7.1, 11.7], "reduced_test": [2.3, 8.5, 11.7]},
            "Overall": {"baseline": [4.6, 13.9, 20.0], "origin_test": [4.1, 13.1, 19.0], "reduced_test": [6.3, 17.9, 25.5]},
        },
        "glm-4-9b-chat": {
            "C": {"baseline": [2.8, 5.8, 8.3], "origin_test": [1.3, 3.8, 5.0], "reduced_test": [2.2, 4.1, 5.0]},
            "D": {"baseline": [3.5, 10.6, 13.8], "origin_test": [2.0, 7.3, 11.2], "reduced_test": [5.8, 14.5, 20.0]},
            "E&F": {"baseline": [0.7, 1.6, 1.7], "origin_test": [0.5, 1.5, 1.7], "reduced_test": [1.2, 1.7, 1.7]},
            "Overall": {"baseline": [2.4, 6.5, 8.5], "origin_test": [1.3, 4.5, 6.5], "reduced_test": [3.3, 7.5, 10.0]},
        },
        "qwen-plus": {
            "C": {"baseline": [37.3, 60.3, 68.3], "origin_test": [31.8, 53.6, 63.3], "reduced_test": [33.7, 53.5, 65.0]},
            "D": {"baseline": [40.1, 55.6, 60.0], "origin_test": [39.9, 58.7, 61.3], "reduced_test": [43.6, 58.7, 62.5]},
            "E&F": {"baseline": [22.5, 39.7, 48.3], "origin_test": [24.0, 45.7, 51.7], "reduced_test": [25.0, 46.5, 55.0]},
            "Overall": {"baseline": [34.0, 52.2, 59.0], "origin_test": [32.7, 53.3, 59.0], "reduced_test": [35.0, 53.5, 61.0]},
        },
        "deepseek-v3": {
            "C": {"baseline": [56.5, 76.3, 80.0], "origin_test": [56.7, 75.5, 78.3], "reduced_test": [56.3, 77.6, 81.7]},
            "D": {"baseline": [44.5, 59.1, 62.5], "origin_test": [48.9, 59.2, 60.0], "reduced_test": [48.1, 61.0, 63.7]},
            "E&F": {"baseline": [35.0, 53.2, 58.3], "origin_test": [32.0, 50.0, 51.7], "reduced_test": [32.5, 51.4, 56.7]},
            "Overall": {"baseline": [45.2, 62.5, 66.5], "origin_test": [46.2, 61.3, 63.0], "reduced_test": [45.9, 63.1, 67.0]},
        },
    }
    for model, expected_by_difficulty in expected_rq2_by_model.items():
        for difficulty, expected_by_strategy in expected_by_difficulty.items():
            for strategy, expected in expected_by_strategy.items():
                check_repair_row(
                    f"LFTBench RQ2 {model} {difficulty} {strategy}",
                    core["rq2_repair"]["by_model_difficulty"][model][difficulty][strategy],
                    expected,
                )
    qwen_sign = rq2["pass_at_10_sign_tests"]["reduced_test_vs_origin_test"]
    check_equal("LFTBench RQ2 Qwen pass@10 sign counts", (
        qwen_sign["better"],
        qwen_sign["worse"],
        qwen_sign["tie"],
    ), (23, 10, 167))
    check_p("LFTBench RQ2 Qwen pass@10 sign p", two_sided_sign_p(qwen_sign["better"], qwen_sign["worse"]), 0.035)
    check_p("LFTBench RQ2 Qwen pass@10 stored p", qwen_sign["two_sided_p"], 0.035)
    lftbench_py = core["rq2_repair"]["lftbench_py"]
    check_repair_row("LFTBench-Py RQ2 Baseline", lftbench_py["baseline"], [42.7, 66.3, 70.0])
    check_repair_row("LFTBench-Py RQ2 Origin Test", lftbench_py["origin_test"], [38.2, 55.6, 60.0])
    check_repair_row("LFTBench-Py RQ2 Reduced Test", lftbench_py["reduced_test"], [46.5, 71.5, 75.0])
    rq3 = core["rq3_prompt_composition"]
    check_equal("LFTBench RQ3 prompt KB", rq3["prompt_kb"], {
        "baseline": 3.2,
        "diff_lines": 3.2,
        "reduced_test": 6.6,
        "origin_test": 30.5,
        "reduced_plus_origin": 36.4,
    })
    check_equal("LFTBench RQ3 pass@k", rq3["pass_at_k"], {
        "reduced_test": [6.3, 17.9, 25.5],
        "diff_lines": [5.1, 14.8, 20.0],
        "reduced_plus_origin": [4.0, 13.3, 19.0],
    })
    rq4 = core["rq4_integrations"]
    check_repair_row("LFTBench RQ4 ChatRepair Origin Test", rq4["chatrepair"]["origin_test"], [9.2, 22.6, 30.5])
    check_repair_row("LFTBench RQ4 ChatRepair Reduced Test", rq4["chatrepair"]["reduced_test"], [12.1, 29.0, 37.0])
    check_repair_row("LFTBench RQ4 CREF Origin Test", rq4["cref"]["origin_test"], [13.9, 31.6, 39.0])
    check_repair_row("LFTBench RQ4 CREF Reduced Test", rq4["cref"]["reduced_test"], [14.7, 32.7, 40.0])
    expected_rq4 = {
        "chatrepair": {
            "C": {"origin_test": [12.2, 30.9, 41.7], "reduced_test": [14.5, 36.6, 45.0]},
            "D": {"origin_test": [12.1, 28.2, 37.5], "reduced_test": [16.2, 35.6, 46.2]},
            "E&F": {"origin_test": [2.3, 6.8, 10.0], "reduced_test": [4.0, 12.8, 16.7]},
            "Overall": {"origin_test": [9.2, 22.6, 30.5], "reduced_test": [12.1, 29.0, 37.0]},
        },
        "cref": {
            "C": {"origin_test": [15.8, 37.3, 45.0], "reduced_test": [17.3, 39.5, 46.7]},
            "D": {"origin_test": [18.8, 39.4, 47.5], "reduced_test": [19.4, 39.7, 47.5]},
            "E&F": {"origin_test": [5.5, 15.6, 21.7], "reduced_test": [5.7, 16.4, 23.3]},
            "Overall": {"origin_test": [13.9, 31.6, 39.0], "reduced_test": [14.7, 32.7, 40.0]},
        },
    }
    for harness, expected_by_difficulty in expected_rq4.items():
        for difficulty, expected_by_strategy in expected_by_difficulty.items():
            for strategy, expected in expected_by_strategy.items():
                check_repair_row(
                    f"LFTBench RQ4 {harness} {difficulty} {strategy}",
                    rq4[harness]["by_difficulty"][difficulty][strategy],
                    expected,
                )
    print("  RQ1 overall SR ReduceFix/Pure LLM/ddmin = 95.0/40.0/35.5")
    print("  RQ2 Qwen pass@10 Baseline/Origin/Reduced = 20.0/19.0/25.5")
    print("  RQ3 Reduced Test vs Diff Lines pass@10 = 25.5/20.0")
    print("  RQ4 ChatRepair Reduced Test pass@1/5/10 = 12.1/29.0/37.0")

    print("OSS-Fuzz reduction (end-to-end CR, failures count as zero)")
    check_equal("OSS-Fuzz n", oss["n"], 167)
    selection = oss["cohort_selection"]
    check_equal("OSS-Fuzz cohort selection rule", (
        selection["failure_inducing_test_min_bytes"],
        selection["developer_patch_max_bytes"],
        selection["cases_with_failure_inducing_test_ge_4kb"],
        selection["cases_after_patch_size_filter"],
        selection["reported_cohort_cases"],
    ), (4096, 524288, 200, 167, 167))
    print("  cohort rule: failure-inducing test >=4KB and developer patch <512KB => 167 cases")
    for key, label in [("ddmin", "ddmin-only"), ("reducefix", "ReduceFix"), ("generated", "Pure LLM")]:
        item = oss["reduction"]["overall"][key]
        row = (
            item["n"],
            pct(item["sr"]),
            pct(item["cr_avg_end_to_end"]),
            pct(item["cr_median_end_to_end"]),
        )
        print(f"  {label}: cases={row[0]}, SR={row[1]}, avg/med CR={row[2]}/{row[3]}")
    check_equal("ReduceFix OSS-Fuzz reduction row", (
        oss["reduction"]["overall"]["reducefix"]["n"],
        pct(oss["reduction"]["overall"]["reducefix"]["sr"]),
        pct(oss["reduction"]["overall"]["reducefix"]["cr_avg_end_to_end"]),
        pct(oss["reduction"]["overall"]["reducefix"]["cr_median_end_to_end"]),
    ), (167, 83.2, 46.5, 51.3))

    print("\nOSS-Fuzz repair and locality")
    for strategy, label in [
        ("without_test", "Baseline"),
        ("origin_test", "Origin Test"),
        ("reduced_test", "Reduced Test"),
    ]:
        repair = oss["repair_pass"][strategy]
        loc = oss["patch_locality"]["correct_patches"][strategy]
        row = (
            pct(repair["pass@1"]),
            pct(repair["pass@5"]),
            pct(repair["pass@10"]),
            oss["strategy_passed_versions"][strategy],
            oss["strategy_any_success_cases"][strategy],
            rounded(loc["aed_avg"]),
            rounded(loc["aed_median"]),
            pct(loc["ccr_avg"]),
            pct(loc["ccr_median"]),
        )
        print(
            f"  {label}: pass@1/5/10={row[0]}/{row[1]}/{row[2]}, "
            f"patches/cases={row[3]}/{row[4]}, AED={row[5]}/{row[6]}, CCR={row[7]}/{row[8]}"
        )
    check_equal("Reduced Test OSS-Fuzz repair row", (
        pct(oss["repair_pass"]["reduced_test"]["pass@1"]),
        pct(oss["repair_pass"]["reduced_test"]["pass@5"]),
        pct(oss["repair_pass"]["reduced_test"]["pass@10"]),
        oss["strategy_passed_versions"]["reduced_test"],
        oss["strategy_any_success_cases"]["reduced_test"],
    ), (5.9, 11.3, 14.4, 98, 24))
    check_equal("OSS-Fuzz repair relative gains", (
        pct(oss["repair_deltas"]["reduced_minus_origin_pass@10"] / oss["repair_pass"]["origin_test"]["pass@10"]),
        pct(oss["repair_deltas"]["reduced_minus_without_pass@10"] / oss["repair_pass"]["without_test"]["pass@10"]),
    ), (26.3, 20.0))
    print("  pass@10 relative gains: Reduced vs Origin=26.3%; Reduced vs Baseline=20.0%")

    print("\nOSS-Fuzz motivating and case-study examples")
    check_equal("OSS-Fuzz case-study cohort", (
        case_studies["cohort"]["name"],
        case_studies["cohort"]["cases"],
    ), ("complete_10_each_strategy", 167))
    libvips = case_studies["cases"]["libvips/arvo-26855"]
    check_equal("libvips/arvo-26855 reduction trace", (
        libvips["in_cohort"],
        libvips["original_size"],
        libvips["ddmin_size"],
        libvips["ddmin_time_seconds"],
        libvips["reducefix_size"],
        libvips["generated_size"],
    ), (True, 9474, 9474, 240.0, 278, 750))
    php = case_studies["cases"]["php-src/arvo-51180"]
    check_equal("php-src/arvo-51180 repair trace", (
        php["in_cohort"],
        pct(php["reducefix_ratio"]),
        php["strategy_passed_versions"]["reduced_test"],
        php["strategy_passed_versions"]["without_test"],
        php["strategy_passed_versions"]["origin_test"],
    ), (True, 96.2, 10, 9, 8))
    hunspell = case_studies["cases"]["hunspell/arvo-51242"]
    check_equal("hunspell/arvo-51242 repair trace", (
        hunspell["in_cohort"],
        hunspell["ddmin_success"],
        pct(hunspell["reducefix_ratio"]),
        hunspell["strategy_passed_versions"]["reduced_test"],
        hunspell["strategy_passed_versions"]["without_test"],
        hunspell["strategy_passed_versions"]["origin_test"],
    ), (True, False, 60.0, 9, 2, 5))
    print("  libvips/arvo-26855 in cohort; sizes origin/ddmin/ReduceFix/Pure LLM = 9474/9474/278/750")
    print("  php-src/arvo-51180 patches Reduced/Baseline/Origin = 10/9/8")
    print("  hunspell/arvo-51242 patches Reduced/Baseline/Origin = 9/2/5")

    print("\nDBMS SQLancer reduction")
    for method in ["line-ddmin", "statement-ddmin", "reducefix-sql", "reducefix-sql-cleanup"]:
        item = dbms["methods"][method]
        row = (
            item["n"],
            round(item["avg_cr"], 2),
            round(item["median_cr"], 2),
            rounded(item["avg_reduced_bytes"]),
            rounded(item["avg_reduced_statements"]),
        )
        print(f"  {method}: cases={row[0]}, avg/med CR={row[1]}/{row[2]}, bytes/stmts={row[3]}/{row[4]}")
    cleanup = dbms["methods"]["reducefix-sql-cleanup"]
    check_equal("DBMS cleanup row", (
        cleanup["n"],
        round(cleanup["avg_cr"], 2),
        round(cleanup["median_cr"], 2),
        rounded(cleanup["avg_reduced_bytes"]),
        rounded(cleanup["avg_reduced_statements"]),
    ), (78, 16.57, 7.74, 155.2, 3.6))
    dbms_sign = dbms["comparisons"]["reducefix_sql_cleanup_vs_statement_ddmin"]["compression_rate"]
    check_equal("DBMS cleanup-vs-statement sign counts", (
        dbms_sign["better"],
        dbms_sign["worse"],
        dbms_sign["tie"],
    ), (12, 2, 64))
    check_p("DBMS cleanup-vs-statement sign p", two_sided_sign_p(dbms_sign["better"], dbms_sign["worse"]), 0.013)

    print("\nLFTBench RQ-2 patch locality")
    for strategy, label in [("no_tc", "Baseline"), ("orig_tc", "Origin Test"), ("reduced_tc", "Reduced Test")]:
        item = locality["summary"]["by_strategy"][strategy]
        row = (rounded(item["aed_median"]), pct(item["ccr_median"]))
        print(f"  {label}: median AED={row[0]}, median CCR={row[1]}")
    reduced = locality["summary"]["by_strategy"]["reduced_tc"]
    check_equal("LFTBench reduced locality", (rounded(reduced["aed_median"]), pct(reduced["ccr_median"])), (412.0, 37.2))
    best = best_locality_records(locality)
    expected_locality_signs = [
        ("AED vs Baseline", "aed", "no_tc", False, (153, 105, 8, 0.003)),
        ("AED vs Origin Test", "aed", "orig_tc", False, (151, 109, 9, 0.011)),
        ("CCR vs Baseline", "ccr", "no_tc", True, (142, 106, 18, 0.026)),
        ("CCR vs Origin Test", "ccr", "orig_tc", True, (148, 96, 25, 0.001)),
    ]
    print("\nReported paired sign tests")
    for label, metric, other, higher_is_better, expected in expected_locality_signs:
        better, worse, tie, p_value = paired_locality_sign_test(best, metric, other, higher_is_better)
        check_equal(f"LFTBench locality {label} sign counts", (better, worse, tie), expected[:3])
        check_p(f"LFTBench locality {label} sign p", p_value, expected[3])
        print(f"  {label}: better/worse/tie={better}/{worse}/{tie}, p={round(p_value, 3)}")
    print(
        "  Qwen pass@10 Reduced vs Origin: "
        f"better/worse/tie={qwen_sign['better']}/{qwen_sign['worse']}/{qwen_sign['tie']}, "
        f"p={round(qwen_sign['two_sided_p'], 3)}"
    )
    print(
        "  DBMS CR ReduceFix-SQL+cleanup vs stmt-ddmin: "
        f"better/worse/tie={dbms_sign['better']}/{dbms_sign['worse']}/{dbms_sign['tie']}, "
        f"p={round(two_sided_sign_p(dbms_sign['better'], dbms_sign['worse']), 3)}"
    )

    report_search_behaviour()

    print("\nManuscript number spot checks")
    # Sentence-level assertions decayed on every rewrite and could not survive an
    # edit pass; these guard the invariant that matters instead, namely that a
    # value reported in one place is reported the same way everywhere it appears.
    check_contains("visible-evidence caps (setup)", "4.experimental_setup.tex",
                   "20{,}480")
    check_contains("visible-evidence caps (setup)", "4.experimental_setup.tex",
                   "40{,}960")
    check_contains("reserved output budget", "4.experimental_setup.tex",
                   "4{,}096")

    number_checks = [
        ("reduction success rate", "5.experiments-rq2.tex", ["95.0", "40.0", "35.5"]),
        ("reduction success rate (abstract)", "0.abstract.tex", ["95.0", "40.0", "35.5"]),
        ("aggregate repair", "0.abstract.tex", ["40.9", "36.9"]),
        ("aggregate repair (RQ-1)", "5.experiments-rq1.tex", ["40.9", "36.9"]),
        ("visible-evidence audit", "5.experiments-rq1.tex", ["78.4", "92.5"]),
        ("gain by stratum", "5.experiments-rq1.tex", ["+10.2", "+2.6", "548", "451", "+0.6", "+6.8"]),
        ("gain by stratum (intro)", "1.introduction.tex", ["+10.2"]),
        ("witness position", "5.experiments-rq1.tex", ["77", "50", "25"]),
        ("prompt cost per passing patch", "5.experiments-rq1.tex", ["33.2", "167.3", "14.8"]),
        ("solved pairs by condition", "5.experiments-rq1.tex", ["327", "295", "308"]),
        ("OSS-Fuzz reduction", "5.experiments-rq5.tex", ["83.2", "43.7"]),
        ("OSS-Fuzz repair", "5.experiments-rq5.tex", ["14.4", "11.4", "12.0"]),
        ("OSS-Fuzz cohort size", "4.experimental_setup.tex", ["167"]),
        ("benchmark scale", "4.experimental_setup.tex", ["200", "1.3"]),
    ]
    for label, file_name, values in number_checks:
        for value in values:
            check_contains(label, file_name, value)
        print(f"  {label}: {', '.join(values)} present in {file_name}")

    check_not_contains("reducer prompt I/O-pair mismatch", "3.approach.tex", "and a few I/O pairs")
    print("  reducer prompt I/O-pair mismatch: absent from 3.approach.tex")
    for unexpected in ("basicstyle=\\scriptsize", "basicstyle=\\ttfamily\\footnotesize", "basicstyle=\\small"):
        check_not_contains("listing default font", "macros.tex", unexpected)
        print(f"  listing default font: {unexpected} absent from macros.tex")

    if (MANUSCRIPT_ROOT / "main.tex").is_file():
        check_fault_failure_vocabulary()
        check_source_hygiene()
        print("  source hygiene: no reviewer-risk residual phrases found")
        check_figure_descriptions()
        print("  figure descriptions: every included figure has a nearby \\Description")
        check_latex_structure()
        print("  latex structure gates: labels, refs, inputs, and graphics resolve")
        check_submission_gates()
        check_submission_format_gates()
        check_bib_consistency()
    else:
        print("  manuscript source not present here; manuscript gates skipped")

    check_readme_hashes()
    print("  artifact README hashes: match current snapshot files")

    print("\nAll snapshot checks passed.")


if __name__ == "__main__":
    main()

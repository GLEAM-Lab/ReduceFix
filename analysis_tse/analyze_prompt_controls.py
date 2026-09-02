#!/usr/bin/env python3
"""Length, position, and selection effects on repair, one factor at a time.

Each contrast is paired on the same faulty program and differs in exactly one
property of the prompt, so a difference is attributable to that property:

  length    validated witness alone  vs  the same witness padded to Origin scale
  position  padded witness at the head  vs  middle  vs  tail (all equal length)
  selection validated witness  vs  an equal-length head excerpt of the original

Confidence intervals resample tasks as clusters, because the programs are drawn
from only 20 problems.
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

BOOTSTRAP = 10000
SEED = 20260808


def load(paths):
    rows = {}
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                rows[(r["condition"], r["problem_id"], r["submission_id"])] = r
    return rows


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def cluster_bootstrap(pairs, rng):
    by = defaultdict(list)
    for task, value in pairs:
        by[task].append(value)
    tasks = list(by)
    if not tasks:
        return None, None
    samples = []
    for _ in range(BOOTSTRAP):
        drawn = []
        for _ in range(len(tasks)):
            drawn.extend(by[tasks[rng.randrange(len(tasks))]])
        samples.append(mean(drawn))
    samples.sort()
    return samples[int(0.025 * BOOTSTRAP)], samples[int(0.975 * BOOTSTRAP) - 1]


def contrast(rows, cond_a, cond_b, rng, k=10):
    keys = [(p, s) for (c, p, s) in rows if c == cond_a]
    paired = []
    for p, s in keys:
        a, b = rows.get((cond_a, p, s)), rows.get((cond_b, p, s))
        if a and b and a.get("status") == "done" and b.get("status") == "done":
            paired.append((p, a, b))
    if not paired:
        return None
    ra = [1.0 if a.get(f"pass@{k}") else 0.0 for _, a, _ in paired]
    rb = [1.0 if b.get(f"pass@{k}") else 0.0 for _, _, b in paired]
    diffs = [(p, x - y) for (p, _, _), x, y in zip(paired, ra, rb)]
    lo, hi = cluster_bootstrap(diffs, rng)
    wins = sum(1 for _, d in diffs if d > 0)
    losses = sum(1 for _, d in diffs if d < 0)
    return {
        "n": len(paired), "a": cond_a, "b": cond_b,
        f"{cond_a}_pass@{k}": round(mean(ra), 4),
        f"{cond_b}_pass@{k}": round(mean(rb), 4),
        "difference": round(mean(ra) - mean(rb), 4),
        "ci95": [None if lo is None else round(lo, 4),
                 None if hi is None else round(hi, 4)],
        "wins_ties_losses": [wins, len(diffs) - wins - losses, losses],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validated", nargs="+", required=True)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    rows = load(args.validated)
    conds = sorted({c for c, _, _ in rows})
    rng = random.Random(SEED)

    report = {"conditions_present": conds, "bootstrap_resamples": BOOTSTRAP,
              "contrasts": {}}
    for k in (5, 10):
        report["contrasts"][f"pass@{k}"] = {
            "length_short_vs_padded":
                contrast(rows, "reducefix", "reduced_padded", rng, k),
            "position_head_vs_middle":
                contrast(rows, "reduced_padded", "reduced_middle", rng, k),
            "position_head_vs_tail":
                contrast(rows, "reduced_padded", "reduced_tail", rng, k),
            "position_middle_vs_tail":
                contrast(rows, "reduced_middle", "reduced_tail", rng, k),
            "selection_witness_vs_excerpt":
                contrast(rows, "reducefix", "origin_excerpt", rng, k),
        }

    # Raw per-condition rates for context.
    rates = {}
    for c in conds:
        sub = [r for (cc, _, _), r in rows.items()
               if cc == c and r.get("status") == "done"]
        if sub:
            rates[c] = {
                "n": len(sub),
                **{f"pass@{k}": round(
                    sum(1 for r in sub if r.get(f"pass@{k}")) / len(sub), 4)
                   for k in (1, 5, 10)},
            }
    report["per_condition_rates"] = rates

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""What in a failure-inducing test helps repair, and what about a long one hurts.

Every contrast is paired on the same faulty program and differs in exactly one
property of the prompt. Confidence intervals resample tasks as clusters, since
the programs come from only 20 problems.

Evidence decomposition (all start from the same validated witness):
  ev_outputs_only   the input removed entirely
  ev_input_only     the outputs removed
  ev_diff_only      the outputs replaced by their differing lines

Length placement (both padded to the same total prompt size):
  reduced_padded    length added to the input
  len_long_output   length added to the outputs
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

BOOTSTRAP = 10000
SEED = 20260808


def load(paths):
    """Merge validation files, preferring a completed run for each key.

    A condition that was regenerated after a prompt-budget fix appears in more
    than one file; without this preference the superseded rows would win purely
    by load order.
    """
    rows = {}
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            key = (r["condition"], r["problem_id"], r["submission_id"])
            prev = rows.get(key)
            if prev is None or (r.get("status") == "done"
                                and prev.get("status") != "done"):
                rows[key] = r
    return rows


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def cluster_bootstrap(diffs, rng):
    by = defaultdict(list)
    for task, value in diffs:
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


def contrast(rows, a, b, rng, k):
    keys = [(p, s) for (c, p, s) in rows if c == a]
    paired = []
    for p, s in keys:
        x, y = rows.get((a, p, s)), rows.get((b, p, s))
        if x and y and x.get("status") == "done" and y.get("status") == "done":
            paired.append((p, x, y))
    if not paired:
        return None
    ra = [1.0 if x.get(f"pass@{k}") else 0.0 for _, x, _ in paired]
    rb = [1.0 if y.get(f"pass@{k}") else 0.0 for _, _, y in paired]
    diffs = [(p, u - v) for (p, _, _), u, v in zip(paired, ra, rb)]
    lo, hi = cluster_bootstrap(diffs, rng)
    wins = sum(1 for _, d in diffs if d > 0)
    losses = sum(1 for _, d in diffs if d < 0)
    return {
        "n": len(paired), "baseline": a, "variant": b,
        "baseline_rate": round(mean(ra), 4), "variant_rate": round(mean(rb), 4),
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
    rng = random.Random(SEED)
    report = {"bootstrap_resamples": BOOTSTRAP, "per_condition": {}, "contrasts": {}}

    for c in sorted({c for c, _, _ in rows}):
        sub = [r for (cc, _, _), r in rows.items()
               if cc == c and r.get("status") == "done"]
        if sub:
            report["per_condition"][c] = {
                "n": len(sub),
                **{f"pass@{k}": round(
                    sum(1 for r in sub if r.get(f"pass@{k}")) / len(sub), 4)
                   for k in (1, 5, 10)},
            }

    for k in (5, 10):
        report["contrasts"][f"pass@{k}"] = {
            "evidence_remove_input":
                contrast(rows, "reducefix", "ev_outputs_only", rng, k),
            "evidence_remove_outputs":
                contrast(rows, "reducefix", "ev_input_only", rng, k),
            "evidence_diff_instead_of_outputs":
                contrast(rows, "reducefix", "ev_diff_only", rng, k),
            "length_on_input":
                contrast(rows, "reducefix", "reduced_padded", rng, k),
            "length_on_output":
                contrast(rows, "reducefix", "len_long_output", rng, k),
            "length_input_vs_output":
                contrast(rows, "reduced_padded", "len_long_output", rng, k),
            "position_head_vs_middle":
                contrast(rows, "reduced_padded", "reduced_middle", rng, k),
            "selection_witness_vs_excerpt":
                contrast(rows, "reducefix", "origin_excerpt", rng, k),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("per-condition pass@10:")
    for c, v in sorted(report["per_condition"].items(),
                       key=lambda kv: -kv[1]["pass@10"]):
        print(f"   {c:18s} n={v['n']:3d}  pass@10={v['pass@10']:6.1%}")
    for k in (10, 5):
        print(f"\npaired contrasts, pass@{k}:")
        for name, c in report["contrasts"][f"pass@{k}"].items():
            if not c:
                print(f"   {name}: (no pairs)")
                continue
            sig = "" if (c["ci95"][0] is None or c["ci95"][0] <= 0 <= c["ci95"][1]) else "  *"
            print(f"   {name:34s} {c['baseline_rate']:6.1%} vs {c['variant_rate']:6.1%}"
                  f"  diff={c['difference']:+7.1%}"
                  f"  CI=[{c['ci95'][0]:+.3f},{c['ci95'][1]:+.3f}]"
                  f"  W/T/L={c['wins_ties_losses']}  n={c['n']}{sig}")


if __name__ == "__main__":
    main()

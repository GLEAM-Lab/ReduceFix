#!/usr/bin/env python3
"""Which program-model combinations each prompt repairs, and how reliable the
prompts are on the combinations they both repair.

Counting repaired combinations per condition and comparing per-candidate
success within each condition's own repaired set mixes two populations: the
sets differ, so the comparison confounds reliability with composition. This
script reports the transfer table instead, and compares candidate success only
on the combinations both prompts repair.
"""
import gzip
import json
import random
import statistics as st
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / 'analysis_tse/output/analysis_manifest.jsonl.gz'
RNG = random.Random(7)
ORIGIN, REDUCED, NOTEST = 'orig_tc', 'reduced_tc', 'no_tc'


def load():
    passed = defaultdict(lambda: defaultdict(list))
    with gzip.open(MANIFEST, 'rt', encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            key = (r['task'], str(r['submission']), r['model'])
            passed[key][r['condition']].append(bool(r['passed']))
    return passed


def task_clustered_ci(values_by_task, n=10000):
    tasks = list(values_by_task)
    means = []
    for _ in range(n):
        vals = []
        for _ in tasks:
            vals.extend(values_by_task[RNG.choice(tasks)])
        means.append(sum(vals) / len(vals))
    means.sort()
    return means[int(0.025 * n)], means[int(0.975 * n)]


def main():
    passed = load()
    repaired = {c: sum(1 for v in passed.values() if any(v.get(c, [])))
                for c in (ORIGIN, REDUCED, NOTEST)}
    print('repaired program-model combinations')
    for c, label in ((ORIGIN, 'Origin Test'), (NOTEST, 'Baseline'), (REDUCED, 'Reduced Test')):
        print(f'  {label:13s} {repaired[c]:4d}')

    cells = defaultdict(list)
    for key, v in passed.items():
        if ORIGIN not in v or REDUCED not in v:
            continue
        o, r = v[ORIGIN], v[REDUCED]
        cells[(any(o), any(r))].append((key,
                                        100.0 * sum(o) / len(o),
                                        100.0 * sum(r) / len(r)))
    print('\ntransfer table (Origin Test x Reduced Test)')
    for key, label in (((True, True), 'both repaired'),
                       ((False, True), 'only Reduced Test'),
                       ((True, False), 'only Origin Test'),
                       ((False, False), 'neither')):
        print(f'  {label:19s} {len(cells[key]):4d}')

    both = cells[(True, True)]
    origin_rate = st.mean(o for _, o, _ in both)
    reduced_rate = st.mean(r for _, _, r in both)
    diffs = defaultdict(list)
    for (task, _, _), o, r in both:
        diffs[task].append(r - o)
    mean_diff = st.mean(d for ds in diffs.values() for d in ds)
    lo, hi = task_clustered_ci(diffs)
    print('\ncandidate success on the combinations both prompts repair'
          f' (n={len(both)}, T={len(diffs)})')
    print(f'  Origin Test  {origin_rate:.1f}%')
    print(f'  Reduced Test {reduced_rate:.1f}%')
    print(f'  paired difference {mean_diff:+.1f} [{lo:+.1f}, {hi:+.1f}]')


if __name__ == '__main__':
    main()

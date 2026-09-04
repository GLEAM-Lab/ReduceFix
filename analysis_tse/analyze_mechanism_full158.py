#!/usr/bin/env python3
"""The evidence-versus-length contrasts on the pre-specified population.

The population is every program whose reduced counterexample preserves the
failure and is not a copy of the original (158 programs), fixed before any
outcome was observed, rather than the 46 programs an earlier round happened to
repair. Rows come from the 40-candidate runs: the 46-program deep run and the
112-program run that completes the population.
"""
import gzip
import hashlib
import json
import random
import statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'output/analysis_manifest.jsonl.gz'
LOCAL_MODEL = 'Qwen2.5-Coder-7B-Instruct'
SOURCES = ['validated_deep40.jsonl', 'validated_placebo.jsonl',
           'validated_full158.jsonl', 'validated_two160.jsonl',
           'validated_acc190.jsonl']
RNG = random.Random(20260904)
ROWS = [
    ('ev_none', 'Nothing'),
    ('ev_input_only', 'The input only'),
    ('ev_outputs_only', 'The outputs only'),
    ('ev_placebo', 'Both, digits randomized'),
    ('ev_full', 'Both (the full counterexample)'),
    ('len_long_output_matched', 'Both, padded to original-test length'),
]


def key(r):
    return (r['problem_id'], str(r['submission_id']))


def candidate_success(r):
    versions = r.get('versions') or []
    if not versions:
        return None
    return 100.0 * sum(1 for v in versions if v.get('passed')) / len(versions)


def counts(r):
    versions = r.get('versions') or []
    if not versions:
        return None
    return len(versions), sum(1 for v in versions if v.get('passed'))


def pass_at_k(n, c, k):
    """Unbiased pass@k over n samples of which c pass."""
    if n - c < k:
        return 100.0
    p = 1.0
    for i in range(k):
        p *= (n - c - i) / (n - i)
    return 100.0 * (1.0 - p)


def load():
    by_condition = defaultdict(dict)
    raw = defaultdict(dict)
    for name in SOURCES:
        path = HERE / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get('status') != 'done':
                continue
            value = candidate_success(r)
            if value is None:
                continue
            # a re-run appends a second row; the last one wins
            by_condition[r['condition']][key(r)] = value
            raw[r['condition']][key(r)] = counts(r)
    return by_condition, raw


def bootstrap(paired, n=10000):
    """Task-clustered bootstrap. The resampling stream is seeded from the
    sorted set of pairs, so every contrast reproduces exactly regardless of
    call order or dict iteration."""
    by_task = defaultdict(list)
    for (task, sub), diff in sorted(paired.items()):
        by_task[task].append(diff)
    tasks = sorted(by_task)
    seed_material = '|'.join(f'{t}/{s}:{paired[(t, s)]:.6f}' for (t, s) in sorted(paired))
    rng = random.Random(int(hashlib.sha256(seed_material.encode()).hexdigest()[:16], 16))
    means = []
    for _ in range(n):
        vals = []
        for _ in tasks:
            vals.extend(by_task[rng.choice(tasks)])
        means.append(sum(vals) / len(vals))
    means.sort()
    flat = [d for ds in by_task.values() for d in ds]
    return st.mean(flat), means[int(0.025 * n)], means[int(0.975 * n)], len(tasks)


def contrast(by_condition, treatment, control):
    a, b = by_condition.get(treatment, {}), by_condition.get(control, {})
    shared = set(a) & set(b)
    if not shared:
        return None
    return bootstrap({k: a[k] - b[k] for k in shared}), len(shared)


def repairable_programs():
    """Programs the local repair model repairs under some RQ-1 prompt.

    The RQ-1 runs are a different sample from the 40-candidate cells analysed
    here, so splitting on them does not condition on the data being compared.
    """
    out = set()
    with gzip.open(MANIFEST, 'rt', encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            if r['model'] == LOCAL_MODEL and r['passed']:
                out.add((r['task'], str(r['submission'])))
    return out


def pass_at_k_contrast(raw, treatment, control, k):
    a, b = raw.get(treatment, {}), raw.get(control, {})
    shared = set(a) & set(b)
    if not shared:
        return None
    paired = {}
    for key_ in shared:
        na, ca = a[key_]
        nb, cb = b[key_]
        paired[key_] = pass_at_k(na, ca, k) - pass_at_k(nb, cb, k)
    return bootstrap(paired), len(shared)


def main():
    by_condition, raw = load()
    print('cells (programs with a validated 40-candidate run)')
    for cond, label in ROWS:
        print(f'  {label:38s} n={len(by_condition.get(cond, {})):4d}')

    print('\npass@1 (mean candidate success) and difference against no evidence')
    for cond, label in ROWS[:-1]:
        cells = by_condition.get(cond, {})
        if not cells:
            print(f'  {label:38s} not yet available')
            continue
        rate = st.mean(cells.values())
        if cond == 'ev_none':
            print(f'  {label:38s} {rate:5.1f}%   n/a')
            continue
        result = contrast(by_condition, cond, 'ev_none')
        (mean, lo, hi, T), n = result
        print(f'  {label:38s} {rate:5.1f}%   {mean:+5.1f} [{lo:+5.1f}, {hi:+5.1f}]  n={n} T={T}')

    cond, label = ROWS[-1]
    cells = by_condition.get(cond, {})
    if cells:
        rate = st.mean(cells.values())
        (mean, lo, hi, T), n = contrast(by_condition, cond, 'ev_full')
        print('\ndifference against the full counterexample')
        print(f'  {label:38s} {rate:5.1f}%   {mean:+5.1f} [{lo:+5.1f}, {hi:+5.1f}]  n={n} T={T}')
        result = contrast(by_condition, 'ev_placebo', cond)
        if result:
            (mean, lo, hi, T), n = result
            print('\ndigit-randomized at counterexample length against the genuine'
                  ' counterexample at original-test length')
            print(f'  candidate success {mean:+.1f} [{lo:+.1f}, {hi:+.1f}]  n={n} T={T}')

    repairable = repairable_programs()
    population = set(by_condition['ev_none'])
    groups = (('all', population),
              ('repairable', population & repairable),
              ('not repairable', population - repairable))
    print('\nsplit by whether the local model repairs the program under some RQ-1 prompt')
    for label, pop in groups[1:]:
        print(f'  {label:16s} {len(pop):3d} programs')
    print('\nmean candidate success by group')
    for cond, plabel in ROWS:
        cells = by_condition.get(cond, {})
        if not cells:
            continue
        line = f'  {plabel:38s}'
        for label, pop in groups:
            vals = [v for k, v in cells.items() if k in pop]
            line += f'  {label} {st.mean(vals):5.2f}% (n={len(vals):3d})' if vals else ''
        print(line)

    # the table: every row on the programs that have all six cells, so the
    # rows share one denominator per column and can be read against each other
    common = set(population)
    for cond, _ in ROWS:
        common &= set(by_condition.get(cond, {}))
    print(f'\nmean candidate success on the programs with all six cells (n={len(common)}: '
          f'repairable {len(common & repairable)}, not {len(common - repairable)})')
    for cond, plabel in ROWS:
        cells = by_condition[cond]
        line = f'  {plabel:38s}'
        for label, pop in groups:
            vals = [cells[k] for k in common & pop]
            line += f'  {label} {st.mean(vals):5.2f}%'
        print(line)
    print('\ncontrasts by group')
    for treatment, control, label in (
            ('ev_input_only', 'ev_none', 'input only vs nothing'),
            ('ev_outputs_only', 'ev_none', 'outputs only vs nothing'),
            ('ev_full', 'ev_none', 'full counterexample vs nothing'),
            ('ev_placebo', 'ev_none', 'digit-randomized vs nothing'),
            ('ev_full', 'ev_placebo', 'full counterexample vs digit-randomized'),
            ('len_long_output_matched', 'ev_none', 'padded vs nothing'),
            ('len_long_output_matched', 'ev_full', 'padded vs full counterexample'),
            ('ev_placebo', 'len_long_output_matched',
             'digit-randomized short vs genuine padded')):
        a, b = by_condition.get(treatment, {}), by_condition.get(control, {})
        for glabel, pop in groups:
            shared = set(a) & set(b) & pop
            if len(shared) < 5:
                continue
            mean, lo, hi, T = bootstrap({k: a[k] - b[k] for k in shared})
            print(f'  {label:42s} {glabel:15s} {mean:+5.1f} '
                  f'[{lo:+5.1f}, {hi:+5.1f}]  n={len(shared):3d} T={T}')

    print('\ninteraction: contrast on repairable minus contrast on not repairable'
          ' (task-clustered bootstrap over both groups)')
    for treatment, control, label in (
            ('len_long_output_matched', 'ev_full', 'padded vs full counterexample'),
            ('ev_placebo', 'len_long_output_matched', 'digit-randomized short vs genuine padded')):
        a, b = by_condition.get(treatment, {}), by_condition.get(control, {})
        ins = {k: a[k] - b[k] for k in set(a) & set(b) & groups[1][1]}
        out = {k: a[k] - b[k] for k in set(a) & set(b) & groups[2][1]}
        by_task = defaultdict(lambda: ([], []))
        for (t, s), d in sorted(ins.items()):
            by_task[t][0].append(d)
        for (t, s), d in sorted(out.items()):
            by_task[t][1].append(d)
        tasks = sorted(by_task)
        seed = int(hashlib.sha256(('interaction:' + label).encode()).hexdigest()[:16], 16)
        rng = random.Random(seed)
        draws = []
        for _ in range(10000):
            i_vals, o_vals = [], []
            for _ in tasks:
                t = rng.choice(tasks)
                i_vals.extend(by_task[t][0])
                o_vals.extend(by_task[t][1])
            if i_vals and o_vals:
                draws.append(sum(i_vals) / len(i_vals) - sum(o_vals) / len(o_vals))
        draws.sort()
        point = st.mean(ins.values()) - st.mean(out.values())
        print(f'  {label:42s} {point:+5.1f} [{draws[int(0.025 * len(draws))]:+5.1f}, '
              f'{draws[int(0.975 * len(draws))]:+5.1f}]  n={len(ins)}+{len(out)} T={len(tasks)}')

    print('\npass@k differences (unbiased over 40 samples)')
    for treatment, control, label in (
            ('ev_full', 'ev_none', 'full counterexample vs no evidence'),
            ('ev_placebo', 'ev_none', 'digit-randomized vs no evidence'),
            ('ev_full', 'ev_placebo', 'full counterexample vs digit-randomized'),
            ('ev_placebo', 'len_long_output_matched',
             'digit-randomized short vs genuine padded')):
        for k in (5, 10):
            result = pass_at_k_contrast(raw, treatment, control, k)
            if not result:
                continue
            (mean, lo, hi, T), n = result
            print(f'  pass@{k:<2d} {label:44s} {mean:+5.1f} [{lo:+5.1f}, {hi:+5.1f}]  n={n}')


if __name__ == '__main__':
    main()

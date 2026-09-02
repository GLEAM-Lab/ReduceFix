#!/usr/bin/env python3
"""Input versus output: which part of a failure witness carries the repair signal.

Two questions, one common population. Every condition below is computed on the
programs that completed in all of them, so the cells are comparable to each
other rather than each to its own subset.

  A. The 2x2. ev_none / ev_input_only / ev_outputs_only / ev_full give the main
     effect of showing the input, the main effect of showing the outputs, and
     their interaction.

  B. Inside the output pair. ev_expected_only and ev_observed_only ask whether
     one side alone suffices; ev_diff_only asks whether the differing lines are
     enough; ev_swapped exchanges the two labels, so if repair is unaffected the
     model is reacting to the presence of a mismatch rather than to its
     direction.

Usage: analyze_factorial.py validated_factorial.jsonl [out.json]
"""
import itertools
import json
import random
import statistics
import sys

random.seed(20260810)

CELLS = ['ev_none', 'ev_input_only', 'ev_outputs_only', 'ev_full']
EXTRA = ['ev_expected_only', 'ev_observed_only', 'ev_diff_only', 'ev_swapped']


def load(p):
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]


def key(r):
    return (r['problem_id'], r['submission_id'])


def boot(vals, n=10000):
    if not vals:
        return (float('nan'),) * 3
    m = []
    for _ in range(n):
        m.append(sum(random.choice(vals) for _ in vals) / len(vals))
    m.sort()
    return statistics.mean(vals), m[int(.025 * n)], m[int(.975 * n)]


def boot_tasks(pairs, n=10000):
    """Cluster the resample on tasks, matching the rest of the paper."""
    by_task = {}
    for task, v in pairs:
        by_task.setdefault(task, []).append(v)
    tasks = list(by_task)
    if not tasks:
        return (float('nan'),) * 3
    m = []
    for _ in range(n):
        vals = []
        for _ in tasks:
            vals.extend(by_task[random.choice(tasks)])
        m.append(sum(vals) / len(vals))
    m.sort()
    flat = [v for vs in by_task.values() for v in vs]
    return statistics.mean(flat), m[int(.025 * n)], m[int(.975 * n)]


def main():
    rows = load(sys.argv[1])
    by_cond = {}
    for r in rows:
        if r.get('status') == 'done' and r.get('pass@10') is not None:
            by_cond.setdefault(r['condition'], {})[key(r)] = r

    print('conditions present: %s'
          % ', '.join('%s(%d)' % (c, len(v)) for c, v in sorted(by_cond.items())))

    present = [c for c in CELLS + EXTRA if c in by_cond]
    common = set.intersection(*[set(by_cond[c]) for c in present])
    print('\ncommon population across %d conditions: %d programs'
          % (len(present), len(common)))
    if not common:
        print('no common population; cannot compare')
        return

    def rate(cond, metric='pass@10'):
        return 100.0 * sum(by_cond[cond][k][metric] for k in common) / len(common)

    print('\n--- cell means on the common population (pass@10) ---')
    for c in present:
        print('  %-18s %5.1f%%' % (c, rate(c)))

    if all(c in by_cond for c in CELLS):
        print('\n--- 2x2: main effects and interaction (percentage points) ---')
        def delta(a, b):
            pairs = [(k[0], 100.0 * (by_cond[a][k]['pass@10'] - by_cond[b][k]['pass@10']))
                     for k in common]
            return boot_tasks(pairs)

        contrasts = [
            ('outputs added, no input   (outputs_only - none)', 'ev_outputs_only', 'ev_none'),
            ('outputs added, with input (full - input_only)', 'ev_full', 'ev_input_only'),
            ('input added, no outputs   (input_only - none)', 'ev_input_only', 'ev_none'),
            ('input added, with outputs (full - outputs_only)', 'ev_full', 'ev_outputs_only'),
        ]
        for label, a, b in contrasts:
            m, lo, hi = delta(a, b)
            print('  %-48s %+6.2f  [%+6.2f, %+6.2f]%s'
                  % (label, m, lo, hi, '  significant' if (lo > 0 or hi < 0) else ''))

        inter = [(k[0], 100.0 * ((by_cond['ev_full'][k]['pass@10']
                                  - by_cond['ev_outputs_only'][k]['pass@10'])
                                 - (by_cond['ev_input_only'][k]['pass@10']
                                    - by_cond['ev_none'][k]['pass@10'])))
                 for k in common]
        m, lo, hi = boot_tasks(inter)
        print('  %-48s %+6.2f  [%+6.2f, %+6.2f]%s'
              % ('interaction (input effect | outputs present)', m, lo, hi,
                 '  significant' if (lo > 0 or hi < 0) else ''))

    print('\n--- inside the output pair (vs ev_full) ---')
    for c in EXTRA:
        if c not in by_cond:
            continue
        pairs = [(k[0], 100.0 * (by_cond[c][k]['pass@10'] - by_cond['ev_full'][k]['pass@10']))
                 for k in common]
        m, lo, hi = boot_tasks(pairs)
        print('  %-24s %+6.2f  [%+6.2f, %+6.2f]%s'
              % (c + ' - ev_full', m, lo, hi,
                 '  significant' if (lo > 0 or hi < 0) else ''))

    if len(sys.argv) > 2:
        out = {'n_common': len(common),
               'cells': {c: rate(c) for c in present}}
        json.dump(out, open(sys.argv[2], 'w', encoding='utf-8'), indent=1)
        print('\nwrote %s' % sys.argv[2])


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""What does the input contribute, and what do the outputs contribute?

The first attempt at this crossed the two components over 147 programs at ten
candidates each. Two draws of an identical prompt differ by 6.8 points of pass@10
on that cohort, and every cell difference sat inside that, so nothing could be
read off it. This version changes what the earlier one got wrong: the population
is the 46 programs the base model repairs at all, because the remaining 101 are
zero under every condition and only add noise, and each cell has 40 candidates
rather than 10, which quarters the sampling variance of its mean.

The four cells give the two main effects and their interaction:

                       outputs absent      outputs present
  input absent         ev_none             ev_outputs_only
  input present        ev_input_only       ev_full

Reported on candidate success, which uses all forty draws per program instead of
collapsing them to a single bit, and paired per program with task-clustered
intervals.

Usage: analyze_io_contribution.py validated_deep40.jsonl
"""
import collections
import json
import random
import statistics
import sys

random.seed(20260810)

CELLS = ['ev_none', 'ev_input_only', 'ev_outputs_only', 'ev_full']


def load(p):
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]


def key(r):
    return (r['problem_id'], str(r['submission_id']))


def cand(r):
    v = r.get('versions') or []
    return 100.0 * sum(1 for x in v if x.get('passed')) / len(v) if v else 0.0


def boot(pairs, n=10000):
    d = collections.defaultdict(list)
    for t, v in pairs:
        d[t].append(v)
    ts = list(d)
    m = []
    for _ in range(n):
        vals = []
        for _ in ts:
            vals.extend(d[random.choice(ts)])
        m.append(sum(vals) / len(vals))
    m.sort()
    flat = [v for vs in d.values() for v in vs]
    return statistics.mean(flat), m[int(.025 * n)], m[int(.975 * n)]


def main():
    by = {}
    for r in load(sys.argv[1]):
        if r.get('status') == 'done':
            by.setdefault(r['condition'], {})[key(r)] = r
    print('conditions: %s' % {c: len(v) for c, v in sorted(by.items())})

    have = [c for c in CELLS if c in by]
    if len(have) < 4:
        print('\nthe factorial needs all four cells; missing %s'
              % [c for c in CELLS if c not in by])
        return
    common = sorted(set.intersection(*[set(by[c]) for c in have]))
    print('programs present in all four cells: %d' % len(common))
    n_cand = statistics.median([len(by['ev_full'][k].get('versions') or [])
                                for k in common])
    print('candidates per cell: %d\n' % n_cand)

    print('%-18s %10s' % ('cell', 'candidate success'))
    for c in CELLS:
        print('%-18s %9.2f%%' % (c, statistics.mean([cand(by[c][k]) for k in common])))

    print('\ncontribution of each component, paired per program')
    contrasts = [
        ('outputs, with no input   (outputs_only - none)', 'ev_outputs_only', 'ev_none'),
        ('outputs, alongside input (full - input_only)', 'ev_full', 'ev_input_only'),
        ('input, with no outputs   (input_only - none)', 'ev_input_only', 'ev_none'),
        ('input, alongside outputs (full - outputs_only)', 'ev_full', 'ev_outputs_only'),
    ]
    for label, a, b in contrasts:
        pairs = [(k[0], cand(by[a][k]) - cand(by[b][k])) for k in common]
        m, lo, hi = boot(pairs)
        print('  %-48s %+6.2f  [%+6.2f, %+6.2f]%s'
              % (label, m, lo, hi, '  significant' if (lo > 0 or hi < 0) else ''))

    inter = [(k[0], (cand(by['ev_full'][k]) - cand(by['ev_outputs_only'][k]))
              - (cand(by['ev_input_only'][k]) - cand(by['ev_none'][k])))
             for k in common]
    m, lo, hi = boot(inter)
    print('  %-48s %+6.2f  [%+6.2f, %+6.2f]%s'
          % ('interaction (does the input depend on the outputs)', m, lo, hi,
             '  significant' if (lo > 0 or hi < 0) else ''))

    print('\ndetectable difference at this design')
    print('  a contrast is only interpretable if it exceeds what two draws of the')
    print('  same prompt produce; that reference is measured separately and was')
    print('  6.8 points of pass@10 at ten candidates over 147 programs.')


if __name__ == '__main__':
    main()

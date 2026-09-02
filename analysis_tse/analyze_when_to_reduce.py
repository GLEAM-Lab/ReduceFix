#!/usr/bin/env python3
"""A decision table for when reduction is worth running.

Three properties have each been shown to matter on their own: whether the
original test would be truncated in the prompt, whether the reduced test keeps
the original failure signature, and whether the Origin Test had already produced
a patch. They are not independent questions for a practitioner, who has to
decide once, per case, before spending a reduction budget.

This crosses them, so the decision can be read off rather than inferred, and
checks whether execution coverage of the reduced test adds anything the
signature does not already capture.
"""
import collections
import csv
import json
import os
import random
import statistics

os.chdir('C:/Users/Administrator/ReduceFix/ReduceFix/analysis_tse')
random.seed(20260810)


def load(p):
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]


fid = {}
for r in load('failure_fidelity/lft_failure_fidelity.jsonl'):
    fid[(r['task'], str(r['submission']))] = r

rows = []
with open('output/visible_evidence_rows.csv', encoding='utf-8') as fh:
    for r in csv.DictReader(fh):
        f = fid.get((r['task'], str(r['submission'])))
        if not f:
            continue
        try:
            r['delta'] = float(r['delta_reduced_origin'])
            r['ot'] = float(r['orig_tc_correct'])
        except (ValueError, KeyError):
            continue
        r['trunc'] = r['origin_truncated'].strip().lower() == 'true'
        r['sig'] = bool(f.get('failure_signature_match'))
        br = (f.get('execution_similarity') or {}).get('branches') or {}
        r['recall'] = br.get('recall_of_original')
        r['prec'] = br.get('precision_to_original')
        r['jac'] = br.get('jaccard')
        rows.append(r)

print('pairs: %d\n' % len(rows))


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


print('=' * 78)
print('DECISION TABLE: gain from reducing, by what is known before reducing')
print('%-12s %-12s %6s %8s %8s %-22s' % ('origin fits', 'signature', 'n',
                                         'helped', 'hurt', 'mean gain [95% CI]'))
for trunc in (True, False):
    for sig in (True, False):
        grp = [r for r in rows if r['trunc'] is trunc and r['sig'] is sig]
        if not grp:
            continue
        h = sum(1 for r in grp if r['delta'] > 0)
        l = sum(1 for r in grp if r['delta'] < 0)
        m, lo, hi = boot([(r['task'], 100 * r['delta']) for r in grp])
        print('%-12s %-12s %6d %8d %8d %+6.2f [%+6.2f, %+6.2f]%s'
              % ('truncated' if trunc else 'fits', 'kept' if sig else 'drifted',
                 len(grp), h, l, m, lo, hi,
                 '  *' if (lo > 0 or hi < 0) else ''))

print('\nthe same table restricted to cases the Origin Test had NOT already repaired')
print('(where reduction cannot lose anything)')
for trunc in (True, False):
    for sig in (True, False):
        grp = [r for r in rows if r['trunc'] is trunc and r['sig'] is sig and r['ot'] == 0]
        if not grp:
            continue
        h = sum(1 for r in grp if r['delta'] > 0)
        l = sum(1 for r in grp if r['delta'] < 0)
        m, lo, hi = boot([(r['task'], 100 * r['delta']) for r in grp])
        print('%-12s %-12s %6d %8d %8d %+6.2f [%+6.2f, %+6.2f]%s'
              % ('truncated' if trunc else 'fits', 'kept' if sig else 'drifted',
                 len(grp), h, l, m, lo, hi,
                 '  *' if (lo > 0 or hi < 0) else ''))

print('\n' + '=' * 78)
print('DOES EXECUTION COVERAGE BEAT THE SIGNATURE AS A CRITERION')
have = [r for r in rows if isinstance(r.get('recall'), (int, float))]
print('pairs with branch coverage recorded: %d' % len(have))
if have:
    for name, field in (('branch recall of the original', 'recall'),
                        ('branch jaccard', 'jac')):
        vals = sorted(have, key=lambda r: r[field])
        q = max(1, len(vals) // 3)
        print('  %s' % name)
        for i, lab in enumerate(('lowest third', 'middle third', 'top third')):
            part = vals[i * q:(i + 1) * q] if i < 2 else vals[2 * q:]
            m, lo, hi = boot([(r['task'], 100 * r['delta']) for r in part])
            print('    %-14s %.2f-%.2f  n=%-4d %+6.2f [%+6.2f, %+6.2f]%s'
                  % (lab, part[0][field], part[-1][field], len(part), m, lo, hi,
                     '  *' if (lo > 0 or hi < 0) else ''))

    full = [r for r in have if r['recall'] is not None and r['recall'] >= 0.999]
    part = [r for r in have if r['recall'] is not None and r['recall'] < 0.999]
    for lab, grp in (('reduced test covers every original branch', full),
                     ('some original branches no longer covered', part)):
        if grp:
            m, lo, hi = boot([(r['task'], 100 * r['delta']) for r in grp])
            print('  %-42s n=%-4d %+6.2f [%+6.2f, %+6.2f]%s'
                  % (lab, len(grp), m, lo, hi, '  *' if (lo > 0 or hi < 0) else ''))

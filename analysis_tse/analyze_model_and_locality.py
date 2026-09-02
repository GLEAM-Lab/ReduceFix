#!/usr/bin/env python3
"""Two questions a practitioner asks after deciding to reduce.

First, which models benefit. If the gain is concentrated in models with small
context or weak reasoning, reduction is a fix for a capacity limit and will fade
as models grow; if it is uniform, it is about the evidence rather than the
model. The four archived models differ by an order of magnitude in strength, so
the answer is already in the data.

Second, whether a reduced test changes where the patch lands. Repair success
says a patch passed; it does not say the model was working on the right part of
the program. The locality snapshot records, per candidate, how far the repaired
file is from the faulty one and how much of it is retained, which is a
behavioural signal independent of whether the suite passed.
"""
import collections
import csv
import json
import os
import random
import statistics

os.chdir('C:/Users/Administrator/ReduceFix/ReduceFix')
random.seed(20260810)


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


# ----------------------------------------------------------- 1. across models
rows = []
with open('analysis_tse/output/visible_evidence_rows.csv', encoding='utf-8') as fh:
    for r in csv.DictReader(fh):
        try:
            r['delta'] = float(r['delta_reduced_origin'])
            r['dnt'] = float(r['delta_reduced_no_test'])
            r['ot'] = float(r['orig_tc_correct'])
            r['rt'] = float(r['reduced_tc_correct'])
            r['nt'] = float(r['no_tc_correct'])
        except (ValueError, KeyError):
            continue
        r['trunc'] = r['origin_truncated'].strip().lower() == 'true'
        rows.append(r)

print('=' * 76)
print('1. DOES REDUCTION HELP EVERY MODEL, OR ONLY THE WEAK ONES')
print('%-28s %8s %10s %-24s %8s' % ('model', 'no-test', 'origin', 'reduced minus origin',
                                    'trunc.'))
by_model = collections.defaultdict(list)
for r in rows:
    by_model[r['model']].append(r)
order = sorted(by_model, key=lambda m: statistics.mean([x['nt'] for x in by_model[m]]))
for mdl in order:
    grp = by_model[mdl]
    nt = 10 * statistics.mean([r['nt'] for r in grp])
    ot = 10 * statistics.mean([r['ot'] for r in grp])
    m, lo, hi = boot([(r['task'], 100 * r['delta']) for r in grp])
    tr = 100.0 * sum(1 for r in grp if r['trunc']) / len(grp)
    print('%-28s %7.1f%% %9.1f%% %+6.2f [%+6.2f, %+6.2f]%s %7.0f%%'
          % (mdl[:28], nt, ot, m, lo, hi, ' *' if (lo > 0 or hi < 0) else '  ', tr))

print('\n  capability and benefit, in the same order as above:')
caps = [(10 * statistics.mean([r['nt'] for r in by_model[m]]),
         statistics.mean([100 * r['delta'] for r in by_model[m]])) for m in order]
print('  no-test success %s' % ' '.join('%5.1f' % c for c, _ in caps))
print('  reduction gain  %s' % ' '.join('%+5.2f' % g for _, g in caps))

# ------------------------------------------------------------ 2. patch locality
snap = json.load(open('paper_tse_overleaf/artifact_snapshot/'
                      'lftbench_patch_locality_rq2.json', encoding='utf-8'))
recs = snap['records']
print('\n' + '=' * 76)
print('2. DOES THE REDUCED TEST MOVE WHERE THE PATCH LANDS')
print('locality records: %d' % len(recs))
print('  fields: %s' % ', '.join(sorted(recs[0].keys())))

per = collections.defaultdict(dict)
for r in recs:
    k = (r['model'], r['case_key'])
    per[k][r['strategy']] = r

metrics = [f for f in ('aed', 'ccr', 'changed_lines') if f in recs[0]]
print('\n  paired reduced minus origin, over cases with both:')
for met in metrics:
    pairs = []
    for k, d in per.items():
        a, b = d.get('reduced_tc'), d.get('orig_tc')
        if a and b and a.get(met) is not None and b.get(met) is not None:
            pairs.append((k[1].split('/')[0], a[met] - b[met]))
    if pairs:
        m, lo, hi = boot(pairs)
        print('    %-14s n=%-5d %+8.2f  [%+8.2f, %+8.2f]%s'
              % (met, len(pairs), m, lo, hi,
                 '  significant' if (lo > 0 or hi < 0) else ''))

print('\n  restricted to candidates that actually passed the suite:')
for met in metrics:
    pairs = []
    for k, d in per.items():
        a, b = d.get('reduced_tc'), d.get('orig_tc')
        if not (a and b):
            continue
        if not (a.get('passed') and b.get('passed')):
            continue
        if a.get(met) is None or b.get(met) is None:
            continue
        pairs.append((k[1].split('/')[0], a[met] - b[met]))
    if pairs:
        m, lo, hi = boot(pairs)
        print('    %-14s n=%-5d %+8.2f  [%+8.2f, %+8.2f]%s'
              % (met, len(pairs), m, lo, hi,
                 '  significant' if (lo > 0 or hi < 0) else ''))

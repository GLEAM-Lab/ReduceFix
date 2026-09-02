#!/usr/bin/env python3
"""What is the noise floor, measured without a confound?

The figure used so far compared ev_full against the archived reduced-test run.
Those two present the same content but are produced by different generators: one
assembles a header, evidence blocks and a footer, the other fills a single
template. Their difference therefore mixes resampling with wording, and cannot
bound what a within-script contrast can establish.

ev_full was run twice by the same generator, at ten candidates and at forty, on
the same programs with the same prompt. That difference is resampling alone, and
it is the number a padding contrast has to clear.
"""
import collections
import json
import os
import random
import statistics

os.chdir('C:/Users/Administrator/ReduceFix/ReduceFix/analysis_tse')
random.seed(20260810)


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


deep = {}
for r in load('validated_deep40.jsonl'):
    if r.get('status') == 'done':
        deep.setdefault(r['condition'], {})[key(r)] = r
fac = {}
for r in load('validated_factorial.jsonl'):
    if r.get('status') == 'done':
        fac.setdefault(r['condition'], {})[key(r)] = r
arch = {key(r): r for r in load('validated_repair.jsonl')
        if r.get('condition') == 'reducefix' and r.get('versions')}

a, b = fac.get('ev_full', {}), deep.get('ev_full', {})
ks = sorted(set(a) & set(b))
print('programs with ev_full run twice by the same generator: %d' % len(ks))
if ks:
    print('  first run  %.2f%% candidate success over %d candidates'
          % (statistics.mean([cand(a[k]) for k in ks]),
             statistics.median([len(a[k]['versions']) for k in ks])))
    print('  second run %.2f%% over %d candidates'
          % (statistics.mean([cand(b[k]) for k in ks]),
             statistics.median([len(b[k]['versions']) for k in ks])))
    m, lo, hi = boot([(k[0], cand(b[k]) - cand(a[k])) for k in ks])
    print('  same script, same condition: %+6.2f  [%+6.2f, %+6.2f]%s'
          % (m, lo, hi, '  significant' if (lo > 0 or hi < 0) else ''))
    print('  THIS is the floor a within-script contrast must clear.')

ka = [k for k in ks if k in arch]
if ka:
    m, lo, hi = boot([(k[0], cand(b[k]) - cand(arch[k])) for k in ka])
    print('\nfor contrast, across generators (mixes wording with resampling):')
    print('  ev_full minus archived:      %+6.2f  [%+6.2f, %+6.2f]%s'
          % (m, lo, hi, '  significant' if (lo > 0 or hi < 0) else ''))

pad = deep.get('len_long_output_matched', {})
kp = sorted(set(b) & set(pad))
if kp:
    print('\nthe padding contrast, both arms from the same generator at 40 candidates:')
    m, lo, hi = boot([(k[0], cand(b[k]) - cand(pad[k])) for k in kp])
    print('  unpadded minus padded:       %+6.2f  [%+6.2f, %+6.2f]%s'
          % (m, lo, hi, '  significant' if (lo > 0 or hi < 0) else ''))

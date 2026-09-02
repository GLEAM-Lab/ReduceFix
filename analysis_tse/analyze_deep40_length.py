#!/usr/bin/env python3
"""Does the length effect survive four times the sampling?

At ten candidates the padding contrast on these programs was -4.13 points of
candidate success net of regression to the mean, with an interval whose upper
bound sat at -0.27, so the sign rested on very little. Quadrupling the
candidates quarters the sampling variance of each cell mean without changing
anything else: same programs, same prompts, same model.

ev_full is the same prompt content as the archived reduced-test run, so the
comparison between them measures nothing but resampling and is reported as the
floor any real effect has to clear.
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

ten = {}
for f in ('validated_matched.jsonl', 'validated_factorial.jsonl'):
    if os.path.exists(f):
        for r in load(f):
            if r.get('status') == 'done':
                ten.setdefault(r['condition'], {})[key(r)] = r
arch = {key(r): r for r in load('validated_repair.jsonl')
        if r.get('condition') == 'reducefix' and r.get('versions')}

full = deep.get('ev_full', {})
pad = deep.get('len_long_output_matched', {})
ks = sorted(set(full) & set(pad))
print('programs with both cells at 40 candidates: %d' % len(ks))
print('candidates per cell: %d\n'
      % statistics.median([len(full[k]['versions']) for k in ks]))

print('%-34s %10s' % ('condition', 'candidate success'))
print('%-34s %9.2f%%' % ('unpadded witness (ev_full)',
                         statistics.mean([cand(full[k]) for k in ks])))
print('%-34s %9.2f%%' % ('outputs padded to Origin scale',
                         statistics.mean([cand(pad[k]) for k in ks])))

print('\npadding effect at 40 candidates')
pairs = [(k[0], cand(full[k]) - cand(pad[k])) for k in ks]
m, lo, hi = boot(pairs)
w = sum(1 for _, v in pairs if v > 0)
l = sum(1 for _, v in pairs if v < 0)
print('  unpadded minus padded  %+6.2f  [%+6.2f, %+6.2f]  w/t/l %d/%d/%d%s'
      % (m, lo, hi, w, len(pairs) - w - l, l,
         '  significant' if (lo > 0 or hi < 0) else ''))

if 'len_long_output_matched' in ten and 'ev_full' in ten:
    t_full, t_pad = ten['ev_full'], ten['len_long_output_matched']
    tk = [k for k in ks if k in t_full and k in t_pad]
    if tk:
        p2 = [(k[0], cand(t_full[k]) - cand(t_pad[k])) for k in tk]
        m2, lo2, hi2 = boot(p2)
        print('  the same contrast at 10 candidates on the same programs')
        print('                         %+6.2f  [%+6.2f, %+6.2f]  (n=%d)'
              % (m2, lo2, hi2, len(tk)))
        print('  interval width: %.2f at 10 candidates, %.2f at 40'
              % (hi2 - lo2, hi - lo))

ak = [k for k in ks if k in arch]
if ak:
    print('\nnoise floor: the same prompt content, a separate run')
    p3 = [(k[0], cand(full[k]) - cand(arch[k])) for k in ak]
    m3, lo3, hi3 = boot(p3)
    print('  new run minus archived %+6.2f  [%+6.2f, %+6.2f]  (n=%d)%s'
          % (m3, lo3, hi3, len(ak),
             '  significant' if (lo3 > 0 or hi3 < 0) else ''))
    print('  a padding effect is only interpretable if it clears this.')

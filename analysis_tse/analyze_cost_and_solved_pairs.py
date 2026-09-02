#!/usr/bin/env python3
"""Candidate statistics-only contributions, computed from the archive."""
import gzip
import json
import random
import statistics as st
from collections import defaultdict
from itertools import combinations
from pathlib import Path

REPO = Path(r'C:\Users\Administrator\ReduceFix\ReduceFix')
rows = [json.loads(l) for l in gzip.open(REPO / 'analysis_tse/output/analysis_manifest.jsonl.gz', 'rt', encoding='utf-8')]
RNG = random.Random(7)

# per (task, sub, model, condition): passes, prompt bytes
passed = defaultdict(lambda: defaultdict(list))
pbytes = defaultdict(lambda: defaultdict(list))
shown = {}
for r in rows:
    k = (r['task'], str(r['submission']), r['model'])
    passed[k][r['condition']].append(bool(r['passed']))
    p = REPO / r['prompt_path'] if r.get('prompt_path') else None
    if p and p.is_file():
        pbytes[k][r['condition']].append(p.stat().st_size)
    if r['condition'] == 'orig_tc':
        shown[k] = (r.get('shown_form'), r.get('shown_input_path'), r.get('reduced_input_path'))

# ---------------- (1) prompt cost per validator-passing patch
print('== (1) prompt bytes per candidate and per passing patch, by condition')
for cond in ('no_tc', 'orig_tc', 'reduced_tc'):
    tot_b = sum(sum(v[cond]) for v in pbytes.values() if cond in v)
    n_c = sum(len(v[cond]) for v in pbytes.values() if cond in v)
    n_pass = sum(sum(v[cond]) for v in passed.values() if cond in v)
    print(f'  {cond:11} bytes/candidate {tot_b / max(1, n_c):9,.0f}   passing {n_pass:4d}   bytes per passing patch {tot_b / max(1, n_pass):11,.0f}')

# ---------------- (2) is the gain a property of the program? cross-model agreement
print('\n== (2) cross-model agreement of the per-program gain (reduced - origin, candidate points)')
delta = defaultdict(dict)
for k, c in passed.items():
    if c.get('reduced_tc') and c.get('orig_tc'):
        delta[k[:2]][k[2]] = (sum(c['reduced_tc']) / len(c['reduced_tc']) - sum(c['orig_tc']) / len(c['orig_tc'])) * 100
models = sorted({m for d in delta.values() for m in d})
progs = [p for p, d in delta.items() if len(d) == len(models)]
print('  programs with all models:', len(progs))
def rank(xs):
    s = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0] * len(xs)
    for i, j in enumerate(s): r[j] = i
    return r
def spearman(a, b):
    ra, rb = rank(a), rank(b); n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** .5; vb = sum((y - mb) ** 2 for y in rb) ** .5
    return cov / (va * vb) if va and vb else float('nan')
for a, b in combinations(models, 2):
    print(f'  rho({a[:14]:14}, {b[:14]:14}) = {spearman([delta[p][a] for p in progs], [delta[p][b] for p in progs]):+.2f}')
agree = defaultdict(int)
for p in progs:
    pos = sum(delta[p][m] > 0 for m in models); neg = sum(delta[p][m] < 0 for m in models)
    agree[(pos, neg)] += 1
print('  programs by (#models gaining, #models losing):', dict(sorted(agree.items())))
print('  programs gaining on >=3 models:', sum(v for (p, n), v in agree.items() if p >= 3),
      ' losing on >=3:', sum(v for (p, n), v in agree.items() if n >= 3))

# ---------------- (3) does the visible prefix contain the evidence the failure needs?
print('\n== (3) reduced witness within the visible prefix of the original test')
def is_subseq(small, big):
    it = iter(big)
    return all(ch in it for ch in small)
inside = outside = unchecked = 0
by_form = defaultdict(lambda: [0, 0])
seen = set()
for k, (form, sp, rp) in shown.items():
    key = k[:2]
    if key in seen or not form or form == 'full' or not sp or not rp:
        continue
    seen.add(key)
    spath, rpath = REPO / sp, REPO / rp
    if not (spath.is_file() and rpath.is_file()):
        unchecked += 1; continue
    prefix = spath.read_bytes(); red = rpath.read_bytes()
    toks_red = red.split(); toks_pre = prefix.split()
    ok = is_subseq(toks_red, toks_pre)
    if ok: inside += 1
    else: outside += 1
    by_form[form][0 if ok else 1] += 1
print(f'  truncated cases checked: {inside + outside}  witness tokens all inside prefix: {inside}  need material beyond prefix: {outside}  unchecked: {unchecked}')
for f, (i, o) in by_form.items():
    print(f'    {f}: inside {i}, beyond {o}')

# ---------------- (4) expected candidates to first success
print('\n== (4) expected number of candidates to the first passing patch (solved programs only)')
for cond in ('no_tc', 'orig_tc', 'reduced_tc'):
    ps = [sum(c[cond]) / len(c[cond]) for c in passed.values() if c.get(cond) and any(c[cond])]
    exp = [1 / p for p in ps]
    print(f'  {cond:11} solved pairs {len(ps):4d}   mean p {st.mean(ps):.3f}   median E[candidates] {st.median(exp):.1f}   mean {st.mean(exp):.1f}')

#!/usr/bin/env python3
"""Where does reduction pay off? Paired reduced-minus-origin candidate
success, task-clustered bootstrap, stratified along dimensions the paper
does not yet report: difficulty, input family, original input size,
reduced witness size, and whether the no-test baseline already solved
the program."""
import gzip
import json
import random
import statistics as st
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RNG = random.Random(20260902)

FAMILY = {}
for fam, tasks in {
    'single sequence': ['abc361c', 'abc367d', 'abc368c', 'abc369d', 'abc370d', 'abc373e', 'abc377c', 'abc377f'],
    'multiple sequences': ['abc374e', 'abc375c', 'abc376c', 'abc376e'],
    'dependent sequences': ['abc364d', 'abc366c', 'abc372e', 'abc371d'],
    '2-D matrix': ['abc363e'], 'graph': ['abc362d', 'abc376d'], 'string': ['abc365d']}.items():
    for t in tasks:
        FAMILY[t] = fam

def difficulty(task):
    return {'c': 'C', 'd': 'D'}.get(task[-1], 'E&F')

orig_size = {}
for l in (REPO / 'lftbench/metadata/cpp_submissions.jsonl').read_text(encoding='utf-8').splitlines():
    if l.strip():
        r = json.loads(l)
        size = r.get('original_input_size_bytes') or (r.get('test_input_summary') or {}).get('size_bytes')
        if not size:
            f = REPO / 'lftbench' / r['original_test_input_path']
            size = f.stat().st_size if f.is_file() else None
        orig_size[(r['problem_id'], str(r['submission_id']))] = size

rows = [json.loads(l) for l in gzip.open(REPO / 'analysis_tse/output/analysis_manifest.jsonl.gz', 'rt', encoding='utf-8')]
passed = defaultdict(lambda: defaultdict(list))
red_bytes = {}
for r in rows:
    k = (r['task'], str(r['submission']), r['model'])
    passed[k][r['condition']].append(bool(r['passed']))
    if r['condition'] == 'reduced_tc' and r.get('reducefix_reduced_bytes') is not None:
        red_bytes[k] = r['reducefix_reduced_bytes']
    if k[:2] not in orig_size and r.get('original_input_path'):
        p = REPO / r['original_input_path']
        if p.is_file():
            orig_size[k[:2]] = p.stat().st_size

pairs = []
for k, c in passed.items():
    red, org, base = c.get('reduced_tc'), c.get('orig_tc'), c.get('no_tc')
    if not red or not org:
        continue
    d = (sum(red) / len(red) - sum(org) / len(org)) * 100
    pairs.append(dict(key=k, task=k[0], d=d, base_solved=bool(base and any(base)),
                      orig_solved=any(org), osize=orig_size.get(k[:2]), rsize=red_bytes.get(k)))
print(len(pairs), 'pairs')

def boot(rs, n=10000):
    by = defaultdict(list)
    for p in rs:
        by[p['task']].append(p['d'])
    ts = list(by)
    out = []
    for _ in range(n):
        v = [x for t in (RNG.choice(ts) for _ in ts) for x in by[t]]
        out.append(sum(v) / len(v))
    out.sort()
    return out[int(.025 * n)], out[int(.975 * n)]

def report(title, groups):
    print(f'\n== {title}')
    print(f'{"stratum":24}{"n":>5}{"tasks":>6}{"W/T/L":>12}{"mean":>8}{"95% CI":>18}')
    for name, rs in groups:
        if not rs:
            continue
        w = sum(p['d'] > 0 for p in rs); l = sum(p['d'] < 0 for p in rs); t = len(rs) - w - l
        ntask = len({p['task'] for p in rs})
        lo, hi = boot(rs)
        print(f'{name:24}{len(rs):5d}{ntask:6d}{f"{w}/{t}/{l}":>12}{st.mean(p["d"] for p in rs):+8.2f}'
              f'   [{lo:+5.2f}, {hi:+5.2f}]')

def by(fn, order=None):
    g = defaultdict(list)
    for p in pairs:
        g[fn(p)].append(p)
    keys = order or sorted(g)
    return [(k, g[k]) for k in keys if k in g]

report('difficulty', by(lambda p: difficulty(p['task']), ['C', 'D', 'E&F']))
report('input family', by(lambda p: FAMILY[p['task']],
                          ['single sequence', 'multiple sequences', 'dependent sequences', '2-D matrix', 'graph', 'string']))

sizes = sorted(p['osize'] for p in pairs if p['osize'])
q1, q2 = sizes[len(sizes) // 3], sizes[2 * len(sizes) // 3]
print(f'\noriginal size tertile cuts: {q1:,} B, {q2:,} B; pairs without a size: {sum(p["osize"] is None for p in pairs)}')
report('original input size', by(lambda p: 'unknown' if p['osize'] is None else 'small' if p['osize'] < q1 else 'medium' if p['osize'] < q2 else 'large',
                                 ['small', 'medium', 'large']))

def rbin(p):
    s = p['rsize']
    if s is None: return 'unreduced'
    return '<=32 B' if s <= 32 else '33-256 B' if s <= 256 else '>256 B'
report('reduced witness size', by(rbin, ['<=32 B', '33-256 B', '>256 B', 'unreduced']))

report('no-test baseline', by(lambda p: 'baseline solved' if p['base_solved'] else 'baseline unsolved',
                              ['baseline unsolved', 'baseline solved']))
report('baseline x origin', by(lambda p: f"base {'Y' if p['base_solved'] else 'N'} / origin {'Y' if p['orig_solved'] else 'N'}"))

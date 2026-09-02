#!/usr/bin/env python3
"""Where in the original test does the material of the reduced witness lie?

For each program whose reduced witness is a whitespace-token subsequence
of the original input, match the witness tokens greedily at their earliest
positions (a conservative, front-most placement) and record where those
tokens sit as a fraction of the file. Report first/last positions,
the quintile histogram of matched tokens, and how many witnesses need
material past given prefixes."""
import gzip
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(r'C:\Users\Administrator\ReduceFix\ReduceFix')
rows = [json.loads(l) for l in gzip.open(REPO / 'analysis_tse/output/analysis_manifest.jsonl.gz', 'rt', encoding='utf-8')]
cases = {}
for r in rows:
    if r['condition'] == 'reduced_tc' and r.get('reduced_input_path') and r.get('original_input_path'):
        cases[(r['task'], str(r['submission']))] = (REPO / r['original_input_path'], REPO / r['reduced_input_path'])
print('cases with a reduced witness path:', len(cases))

def tokens_with_offsets(data):
    out, i, n = [], 0, len(data)
    while i < n:
        while i < n and data[i:i + 1].isspace():
            i += 1
        j = i
        while j < n and not data[j:j + 1].isspace():
            j += 1
        if j > i:
            out.append((data[i:j], i))
        i = j
    return out

first, last, span, quint, past = [], [], [], Counter(), Counter()
per_case = []
closure = 0
for key, (op, rp) in cases.items():
    if not (op.is_file() and rp.is_file()):
        continue
    orig = op.read_bytes(); red = rp.read_bytes()
    otoks = tokens_with_offsets(orig); rtoks = [t for t, _ in tokens_with_offsets(red)]
    if not rtoks or len(orig) == 0:
        continue
    # greedy earliest subsequence match
    pos, k = [], 0
    for tok, off in otoks:
        if k < len(rtoks) and tok == rtoks[k]:
            pos.append(off / len(orig)); k += 1
            if k == len(rtoks):
                break
    if k < len(rtoks):
        continue  # rewritten witness, not a subsequence
    closure += 1
    first.append(pos[0]); last.append(pos[-1]); span.append(pos[-1] - pos[0])
    for p in pos:
        quint[min(4, int(p * 5))] += 1
    for cap in (20480, 40960):
        if any(int(p * len(orig)) >= cap for p in pos):
            past[cap] += 1
    per_case.append((key, len(orig), pos[0], pos[-1], len(rtoks)))

n = closure
print(f'witnesses that are token subsequences of the original: {n}')
print(f'first needed token: median {st.median(first):.1%} of file;  last needed token: median {st.median(last):.1%}, mean {st.mean(last):.1%}')
print(f'span from first to last needed token: median {st.median(span):.1%} of the file')
print('last needed token lies in file quintile:', {q: sum(1 for p in last if min(4, int(p * 5)) == q) for q in range(5)})
print('all matched witness tokens by quintile:', dict(sorted(quint.items())), ' total', sum(quint.values()))
print('witnesses whose last needed token lies beyond 50% of the file:', sum(p > .5 for p in last), f'({sum(p > .5 for p in last) / n:.1%})')
print('witnesses whose last needed token lies beyond 90%:', sum(p > .9 for p in last), f'({sum(p > .9 for p in last) / n:.1%})')
for cap, c in sorted(past.items()):
    big = sum(1 for _, sz, *_ in per_case if sz > cap)
    print(f'witness needs material past {cap:,} bytes: {c} of the {big} files longer than that cap ({c / max(1, big):.1%})')
print('\nfirst-token position quintiles:', {q: sum(1 for p in first if min(4, int(p * 5)) == q) for q in range(5)})

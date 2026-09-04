#!/usr/bin/env python3
"""Position and padding-side contrasts on the 158-program population at 10
candidates per cell, with the same task-clustered bootstrap and the unbiased
pass@k estimator used everywhere else.

Position: the padded counterexample at the head (reduced_padded), middle
(reduced_middle), or tail (reduced_tail) of the prompt.
Side: original-test length carried by the input (len_long_input) or by both
shown outputs matched to the padded-input token count (len_long_output_matched).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_mechanism_full158 import bootstrap, pass_at_k  # noqa: E402


def load(name):
    out = {}
    for line in (HERE / name).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        versions = r.get('versions') or []
        if r.get('status') != 'done' or not versions:
            continue
        key = (r['problem_id'], str(r['submission_id']))
        out.setdefault(r['condition'], {})[key] = (len(versions), sum(1 for v in versions if v.get('passed')))
    return out


def report(cells, treatment, control, label):
    a, b = cells.get(treatment, {}), cells.get(control, {})
    shared = sorted(set(a) & set(b))
    if not shared:
        print(f'  {label}: no shared programs')
        return
    for metric, fn in (('candidate success', lambda n, c: 100.0 * c / n),
                       ('pass@5', lambda n, c: pass_at_k(n, c, 5)),
                       ('pass@10', lambda n, c: pass_at_k(n, c, 10))):
        paired = {k: fn(*a[k]) - fn(*b[k]) for k in shared}
        mean, lo, hi, T = bootstrap(paired)
        ma = sum(fn(*a[k]) for k in shared) / len(shared)
        mb = sum(fn(*b[k]) for k in shared) / len(shared)
        print(f'  {label:34s} {metric:17s} {ma:5.1f} vs {mb:5.1f}  diff {mean:+5.1f} [{lo:+5.1f}, {hi:+5.1f}]  n={len(shared)} T={T}')


ctrl = load('validated_ctrl.jsonl')
print('position (padded counterexample at head / middle / tail), 10 candidates')
report(ctrl, 'reduced_middle', 'reduced_padded', 'middle vs head')
report(ctrl, 'reduced_tail', 'reduced_padded', 'tail vs head')
report(ctrl, 'reduced_tail', 'reduced_middle', 'tail vs middle')

matched = load('validated_matched.jsonl')
full = load('validated_factorial.jsonl').get('ev_full', {})
matched['ev_full'] = full
print('\npadding side against the unpadded counterexample, 10 candidates')
report(matched, 'len_long_input', 'ev_full', 'input-side padding vs unpadded')
report(matched, 'len_long_output_matched', 'ev_full', 'output-side padding vs unpadded')
report(matched, 'len_long_input', 'len_long_output_matched', 'input-side vs output-side')

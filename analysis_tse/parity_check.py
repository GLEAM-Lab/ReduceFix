#!/usr/bin/env python3
"""Token parity between the placebo and the real witness prompts, per case."""
import json
from pathlib import Path

D = Path('/root/autodl-tmp')


def toks(pat):
    out = {}
    for f in sorted((D / 'gen_mech').glob(pat)):
        for line in open(f, encoding='utf-8'):
            if line.strip():
                r = json.loads(line)
                out[(r['problem_id'], str(r['submission_id']))] = r['prompt_tokens']
    return out


a = toks('gen_ev_full_deep40_shard*.jsonl')
b = toks('gen_ev_placebo_deep40_shard*.jsonl')
ks = sorted(set(a) & set(b))
diffs = [100.0 * abs(a[k] - b[k]) / a[k] for k in ks]
within = sum(1 for d in diffs if d <= 2.0)
print('cases: %d' % len(ks))
print('prompt-token difference: median %.3f%%, max %.3f%%' %
      (sorted(diffs)[len(diffs) // 2], max(diffs)))
print('within 2%%: %d/%d' % (within, len(ks)))

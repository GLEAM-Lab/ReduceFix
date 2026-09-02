#!/usr/bin/env python3
"""Verify size parity first, then recompute the length contrast.

The previous version of this contrast reported a significant harm from padding
the outputs, but its two arms differed by a median of 10% in prompt tokens, so
the effect could not be separated from prompt size. This run pads the outputs to
each case's own padded-input token count. Parity is therefore a precondition,
not an assumption: if the achieved counts do not agree, the contrast is reported
as failed rather than interpreted.

Usage: analyze_matched_padding.py <gen_mech_dir> <validated.jsonl> [base.jsonl]
"""
import json
import random
import statistics
import sys
from pathlib import Path

random.seed(20260809)

PARITY_TOL = 0.02   # a pair counts as matched within 2% of prompt tokens
PARITY_MIN = 0.90   # at least this fraction of pairs must clear it


def load(path):
    return [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]


def key(r):
    return (r['problem_id'], r['submission_id'])


def boot(vals, n=10000):
    if not vals:
        return (float('nan'),) * 3
    means = []
    for _ in range(n):
        means.append(sum(random.choice(vals) for _ in vals) / len(vals))
    means.sort()
    return (statistics.mean(vals), means[int(.025 * n)], means[int(.975 * n)])


def main():
    gen_dir = Path(sys.argv[1])
    validated = load(sys.argv[2])
    base_path = sys.argv[3] if len(sys.argv) > 3 else None

    by_cond = {}
    for r in validated:
        by_cond.setdefault(r.get('condition'), {})[key(r)] = r

    inp = by_cond.get('len_long_input', {})
    out = by_cond.get('len_long_output_matched', {})
    print('len_long_input rows: %d ; len_long_output_matched rows: %d'
          % (len(inp), len(out)))

    # ---- parity gate ----
    pairs = [k for k in inp if k in out
             and inp[k].get('prompt_tokens') and out[k].get('prompt_tokens')]
    rel = sorted(abs(out[k]['prompt_tokens'] - inp[k]['prompt_tokens'])
                 / inp[k]['prompt_tokens'] for k in pairs)
    if not rel:
        print('no comparable pairs; nothing to report')
        return
    matched = sum(1 for r in rel if r <= PARITY_TOL)
    print('\nsize parity over %d pairs: median %.2f%%  p90 %.2f%%  within %d%%: %d (%.0f%%)'
          % (len(rel), 100 * rel[len(rel) // 2], 100 * rel[int(len(rel) * .9)],
             100 * PARITY_TOL, matched, 100.0 * matched / len(rel)))
    if matched < PARITY_MIN * len(rel):
        print('PARITY FAILED: fewer than %.0f%% of pairs are matched; '
              'the contrast is not size-controlled and must not be interpreted.'
              % (100 * PARITY_MIN))
        return
    print('PARITY OK')

    # ---- effect, on the matched pairs only ----
    if not base_path:
        print('\nno base file given; parity check only')
        return
    base = {key(r): r for r in load(base_path) if r.get('condition') == 'reducefix'}
    usable = [k for k in pairs
              if abs(out[k]['prompt_tokens'] - inp[k]['prompt_tokens'])
              <= PARITY_TOL * inp[k]['prompt_tokens']
              and inp[k].get('status') == 'done' and out[k].get('status') == 'done'
              and k in base and base[k].get('pass@10') is not None]
    print('\nusable matched triples: %d' % len(usable))
    for name, f in (('pad the outputs vs base',
                     lambda k: out[k]['pass@10'] - base[k]['pass@10']),
                    ('pad the input vs base',
                     lambda k: inp[k]['pass@10'] - base[k]['pass@10']),
                    ('outputs vs input padding',
                     lambda k: out[k]['pass@10'] - inp[k]['pass@10'])):
        d = [100 * f(k) for k in usable]
        m, lo, hi = boot(d)
        wins = sum(1 for x in d if x > 0)
        losses = sum(1 for x in d if x < 0)
        print('  %-26s %+6.2f  [%+6.2f, %+6.2f]  w/t/l %d/%d/%d%s'
              % (name, m, lo, hi, wins, len(d) - wins - losses, losses,
                 '  significant' if (lo > 0 or hi < 0) else ''))


if __name__ == '__main__':
    main()

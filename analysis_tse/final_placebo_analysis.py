#!/usr/bin/env python3
"""The placebo verdict: does a digit-randomized witness repair as well as the
real one?

Three arms on the same 46 programs at 40 candidates: no evidence, the real
witness, and a placebo that matches it in length, layout and digit widths but
carries no semantics. If the placebo tracks the real witness, the witness's
value is its presence and shape; if it tracks no-evidence, the model extracts
content. Also extends the targeting analysis to the placebo arm: placebo
candidates should fix the real witness case no more often than no-evidence
candidates.
"""
import hashlib
import json
import multiprocessing as mp
import random
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

D = Path('/root/autodl-tmp')
SEED = 20260811
sys.path.insert(0, str(D))
from validate_repair_candidates import extract_cpp


def load_validated(path, conds):
    by = {}
    for line in open(path, encoding='utf-8'):
        r = json.loads(line)
        if r['condition'] in conds and r.get('status') == 'done':
            by[(r['condition'], r['problem_id'], str(r['submission_id']))] = r
    return by


def cand(r):
    v = r.get('versions') or []
    return 100.0 * sum(1 for x in v if x.get('passed')) / len(v) if v else 0.0


def boot(pairs, n=10000):
    by = defaultdict(list)
    for t, v in pairs:
        by[t].append(v)
    ts = list(by)
    rng = random.Random(SEED)
    m = []
    for _ in range(n):
        vals = []
        for _ in ts:
            vals.extend(by[rng.choice(ts)])
        m.append(sum(vals) / len(vals))
    m.sort()
    flat = [v for vs in by.values() for v in vs]
    return sum(flat) / len(flat), m[int(.025 * n)], m[int(.975 * n)]


deep = load_validated(D / 'validated_deep40.jsonl',
                      {'ev_full', 'ev_none', 'ev_input_only', 'ev_outputs_only'})
plac = load_validated(D / 'validated_placebo.jsonl', {'ev_placebo'})

keys = sorted(set(k[1:] for k in deep if k[0] == 'ev_full')
              & set(k[1:] for k in plac))
print('programs with all arms: %d' % len(keys))

rates = {}
for arm, src in (('ev_none', deep), ('ev_placebo', plac), ('ev_full', deep)):
    vals = [cand(src[(arm,) + k]) for k in keys]
    rates[arm] = statistics.mean(vals)
    print('%-12s candidate success %6.2f%%' % (arm, rates[arm]))

print()
for label, a, sa, b, sb in (
        ('placebo minus none   ', 'ev_placebo', plac, 'ev_none', deep),
        ('full minus placebo   ', 'ev_full', deep, 'ev_placebo', plac),
        ('full minus none      ', 'ev_full', deep, 'ev_none', deep)):
    pairs = [(k[0], cand(sa[(a,) + k]) - cand(sb[(b,) + k])) for k in keys]
    m, lo, hi = boot(pairs)
    w = sum(1 for _, v in pairs if v > 0)
    l = sum(1 for _, v in pairs if v < 0)
    print('%s %+6.2f [%+6.2f, %+6.2f]  W/T/L %d/%d/%d'
          % (label, m, lo, hi, w, len(pairs) - w - l, l))

# ---- targeting on the placebo arm ------------------------------------------
gens = {}
for f in sorted((D / 'gen_mech').glob('gen_ev_placebo_deep40_shard*.jsonl')):
    for line in open(f, encoding='utf-8'):
        if line.strip():
            r = json.loads(line)
            gens.setdefault((r['problem_id'], str(r['submission_id'])), []) \
                .extend(r.get('responses') or [])

WORK = Path(tempfile.mkdtemp(prefix='ptarget_'))


def norm(out):
    lines = [l.rstrip() for l in out.replace('\r\n', '\n').split('\n')]
    while lines and lines[-1] == '':
        lines.pop()
    return '\n'.join(lines)


def compile_cpp(src_path, out_path):
    r = subprocess.run(['g++', '-O2', '-std=gnu++17', '-o', str(out_path), str(src_path)],
                       capture_output=True, timeout=120)
    return r.returncode == 0


def find_reference(pid):
    for pat in ('lftbench/data/ground_truth/%s.cpp' % pid,
                'lftbench/data/ground_truth/%s/*.cpp' % pid,
                'lftbench/data/ground_truth/cpp/%s.cpp' % pid,
                'lftbench/data/ground_truth/%s*' % pid):
        hits = [h for h in sorted(D.glob(pat))
                if h.is_file() and h.suffix in ('.cpp', '.cc', '.cxx')]
        if hits:
            return hits[0]
    return None


def run_on(bin_path, text, timeout=10):
    try:
        r = subprocess.run([str(bin_path)], input=text.encode('utf-8', 'replace'),
                           capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    return r.stdout.decode('utf-8', 'replace') if r.returncode == 0 else None


def eval_one(job):
    key, code, witness, expected = job
    sha = hashlib.sha256(code.encode('utf-8', 'replace')).hexdigest()
    b = WORK / ('c_' + sha[:24])
    if not b.exists():
        src = b.with_suffix('.cpp')
        src.write_text(code, encoding='utf-8')
        try:
            if not compile_cpp(src, b):
                return key, False
        except Exception:
            return key, False
    out = run_on(b, witness)
    return key, (out is not None and norm(out) == expected)


prep = {}
for pid, sid in keys:
    witness = (D / 'results' / pid / sid / 'reduced_input.txt').read_text(
        encoding='utf-8', errors='replace')
    ref = find_reference(pid)
    rb = WORK / ('ref_' + pid)
    if not rb.exists():
        assert compile_cpp(ref, rb)
    prep[(pid, sid)] = (witness, norm(run_on(rb, witness, timeout=30)))

jobs = []
for (pid, sid), responses in gens.items():
    if (pid, sid) not in prep:
        continue
    w, e = prep[(pid, sid)]
    for i, resp in enumerate(responses):
        code = extract_cpp(resp) if resp else None
        if code:
            jobs.append((((pid, sid), i), code, w, e))

fix = 0
per = defaultdict(lambda: [0, 0])
with mp.Pool(24) as pool:
    for (case, _i), ok in pool.imap_unordered(eval_one, jobs, chunksize=8):
        per[case][1] += 1
        if ok:
            per[case][0] += 1
            fix += 1
print('\nplacebo arm witness-fix: %d/%d = %.2f%% (real witness case, '
      'prompt contained only the scrambled one)' % (fix, len(jobs), 100.0 * fix / len(jobs)))

with open(D / 'placebo_analysis.json', 'w', encoding='utf-8') as f:
    json.dump({'rates': rates,
               'witness_fix_placebo': {'fix': fix, 'total': len(jobs)},
               'per_case': {('%s/%s' % k): v for k, v in per.items()}}, f, indent=1)
print('written: placebo_analysis.json')

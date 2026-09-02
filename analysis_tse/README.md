# TSE mechanism analyses

This directory contains provenance-first analyses for the TSE extension. The
scripts read existing LFTBench artifacts and never generate repair candidates.

Run the visible-evidence and paired-repair audit from the repository root:

```bash
python3 analysis_tse/build_lft_manifest.py
```

The command writes all derived files to `analysis_tse/output/`:

- `analysis_manifest.jsonl`: one immutable row per task, submission, model,
  prompt condition, and candidate version, with source paths and SHA-256 hashes;
- `visible_evidence_rows.csv`: case/model summaries of the test input actually
  shown to the repair model;
- `visible_evidence_summary.json`: truncation and prompt-coherence aggregates;
- `paired_repair_stats.json`: paired pass@k, wins/ties/losses, and task-clustered
  bootstrap confidence intervals;
- `provenance_audit.json`: reducer and ddmin-repair source consistency checks.

The ddmin repair result is intentionally excluded from effectiveness claims
until `provenance_audit.json` no longer reports a source conflict.

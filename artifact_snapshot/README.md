# Manuscript result snapshots

This directory contains compact machine-readable summaries for reported results that are referenced by the manuscript and supplementary material.

Files:

- `oss_fuzz_ge4k_complete10_deep_stats.json`: summary for the 167-case OSS-Fuzz cohort, including the cohort-selection rule, reduction rates, repair pass@k, solved-case counts, relative gains, and patch-locality aggregates.
- `oss_fuzz_case_study_snapshot.json`: traceability snapshot for the OSS-Fuzz motivating example and case studies, including cohort membership, reduction sizes, and per-strategy correct-patch counts.
- `sqlancer_sqlite_main_current_cleanup_summary.json`: summary for the 78-case SQLite SQLancer reduction experiment, including per-approach CR, reduced size, and paired comparisons.
- `lftbench_core_results.json`: compact summary for the LFTBench reducer, repair, prompt-composition, ChatRepair/CREF integration, and reported pass@10 sign-test numbers used in RQ-1 through RQ-4.
- `lftbench_patch_locality_rq2.json`: AED/CCR patch-locality summary for RQ-2 over the LFTBench repair results.
- `check_snapshot_numbers.py`: dependency-free script that prints and sanity-checks the key table numbers, result-paragraph numbers, reported paired sign tests, manuscript-source spot checks, source-hygiene gates, figure-description coverage, LaTeX structure, submission word-count gates, citation/BibTeX consistency and required metadata, and snapshot hashes.

These are summary snapshots for result traceability. They support checking the manuscript numbers and do not replace the full experiment artifact.

To check the snapshot values:

```bash
python3 artifact_snapshot/check_snapshot_numbers.py
```

SHA256:

- `faac0ff64fdf2b2676248d319ce0a89839ba3c6252763b117c37c512a6088c68  oss_fuzz_case_study_snapshot.json`
- `20b7d633bf55dd316abc3a0b2535c58041032222c2887a104c997de15d3f7b9c  lftbench_patch_locality_rq2.json`
- `4d593914e926dc590963b0dd6561462db7b5f2fc32492672ac7f4c7671a91e6d  lftbench_core_results.json`
- `0e613859971d99ddb0ea7b951ea377bdb680f46a85ac8729bf2daef4875abb6e  oss_fuzz_ge4k_complete10_deep_stats.json`
- `b1e58b9d8a6da92bd2c5486d7c15cd89f900763a3a32e73c92fcfc2e8305f7fa  sqlancer_sqlite_main_current_cleanup_summary.json`
- `b045c20a03d5bf6c3c88e631fae358a3ec99cab15cb2cdef87a853803f82e579  check_snapshot_numbers.py`
- `1431c536bd9d673af88f7354567f166a302c8a2c294357c0eb58957dec03c353  reducer_search_log.jsonl`

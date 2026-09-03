# Results inventory

The journal-version numbers the manuscript reports, with the script that
computes each and the data it reads. Bootstrap resampling is seeded, so
re-running a script reproduces the reported intervals. Run scripts from the
repository root unless the script's usage line says otherwise.

## Data files

| File | What it holds |
| --- | --- |
| `output/analysis_manifest.jsonl.gz` | One row per task, submission, model, prompt condition, and candidate: source paths, SHA-256 hashes, the input actually shown to the model, and the validation outcome. Built by `build_lft_manifest.py`. |
| `output/visible_evidence_rows.csv` | Per case-model summaries of the shown input (complete or head-only prefix) and per-condition candidate success. |
| `output/paired_repair_stats.json`, `output/provenance_audit.json`, `output/visible_evidence_summary.json` | Aggregates written by `build_lft_manifest.py`. |
| `failure_fidelity/lft_failure_fidelity.jsonl` | For each reduced LFTBench witness, whether it induces the same failure signature as the original input, and execution similarity. |
| `validated_repair.jsonl` | Reduced and Origin arms over 200 programs, 10 candidates each, re-validated locally with Qwen2.5-Coder-7B-Instruct. |
| `validated_deep40.jsonl` | The mechanism cohort: 5 conditions over the 46 programs (`deep_programs.txt`) the local model repairs under some condition, 40 candidates each. |
| `validated_factorial.jsonl`, `validated_matched.jsonl`, `validated_mech.jsonl` | Evidence-decomposition cells, length-matched input/output padding, and head/middle/tail position arms. |
| `validated_placebo.jsonl`, `placebo_analysis.json`, `target_analysis.json` | The digit-scrambled arm at exact per-case token parity, its three-arm comparison, and the targeting probe. |
| `lftbench/metadata/cpp_submissions.jsonl` (repository) | Difficulty, input family, and original input size per program. |

## Claims and the scripts that produce them

### RQ-1, effectiveness

| Claim | Script |
| --- | --- |
| Paired gain +1.6 [+0.4, +2.8], W/T/L 166/530/104; fit strata +1.9 / +0.3 | `build_lft_manifest.py` (paired_repair_stats.json) |
| Per-model gains and patch locality | `analyze_model_and_locality.py` |
| Gain by difficulty, input family, original test size, witness size, and Baseline x Origin | `analyze_gain_by_stratum.py` |
| Prompt bytes per candidate and per passing patch | `analyze_cost_and_solved_pairs.py` |
| Repaired combinations 295/308/327; transfer 269/58/26/447; candidate success on the shared 269 (60.7% vs 63.7%, +3.0 [+0.1, +5.9]) | `analyze_repair_transfer.py` |

### RQ-2, reducer reliability

Search behaviour (median failure checks, bytes removed per check, advancing share, accepted moves) is recomputed from `artifact_snapshot/reducer_search_log.jsonl` by `artifact_snapshot/check_snapshot_numbers.py`.

### RQ-3, when to supply a reduced test

| Claim | Script |
| --- | --- |
| Signature preservation x prompt fit over 760 pairs; branch-recall thirds | `analyze_when_to_reduce.py` |

### RQ-4, what helps and what hurts

| Claim | Script |
| --- | --- |
| Evidence decomposition: input, outputs, both, interaction | `analyze_io_contribution.py validated_deep40.jsonl` |
| Padding to Origin-Test scale | `analyze_deep40_length.py` |
| Run-to-run reproducibility benchmark (+0.8) | `analyze_true_noise_floor.py` |
| Matched padding, input side against output side | `analyze_matched_padding.py` |
| Position arms | `analyze_prompt_controls.py` (output/prompt_controls.json) |
| Scrambled arm against the full witness; scrambled short against genuine long | `final_placebo_analysis.py` |
| Token parity of scrambled and real prompts | `parity_check.py` |

Analyses kept in the repository but not reported in the article (prompt-budget audit, counterexample position) are omitted from this index.

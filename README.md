# ReduceFix

ReduceFix is an automated program repair (APR) system that leverages LLM-generated reducers to minimize failure-inducing test inputs before using them to guide repair generation. This repository contains the implementation and experimental scripts for reproducing the results presented in our paper.

> **Prompt Formats**: We have organized all prompt formats used in the paper into the `prompt_formats/` directory for easy reference. See [Prompt Formats](#prompt-formats) for details.

## Overview

ReduceFix consists of three main phases:
1. **Reducer Generation**: Prompts a code LLM once to generate a customized reducer script that can automatically reduce failure-inducing inputs for the specific task
2. **Input Reduction**: Executes the generated reducer script to shrink the failure-inducing input i₀ into a reduced test input i* while preserving the failure
3. **Patch Generation**: Embeds ⟨P, $s_w$, i*⟩ in a repair prompt, samples candidate patches, and validates each one against the entire test suite until a correct program is found

The pipeline receives five inputs: the task description P, a correct reference solution A, a faulty submission $s_w$, the hidden test suite I, and one failure-inducing input i₀.

## Prerequisites

- Python 3.8+
- Access to LLM APIs (Qwen-Plus, DeepSeek-V3, etc.) with API keys configured in `config.py`

## Quick Start

1. **Setup Configuration**:
   ```bash
   # Configure your API keys in config.py
   # Edit config.py with your actual API credentials
   ```

2. run the following scripts:

```bash
./rq1.sh
./rq2.sh
./rq3.sh
./rq4.sh
./rq5.sh
```

3. The LFTBench (including C++ and Python versions) is located in the `lftbench` sub-directory.

For the current journal manuscript, the compact result snapshots used to check
the reported tables are in `artifact_snapshot/`:

```bash
python3 artifact_snapshot/check_snapshot_numbers.py
```

### Mapping to the journal article

The scripts keep the numbering of the conference version. The journal article
renumbers its research questions, so each script maps as follows.

| Script | Journal article | Conference version |
|---|---|---|
| `rq1.sh` | RQ-3: Reducer Reliability and Compression | RQ-1 |
| `rq2.sh` | RQ-1: Effectiveness of ReduceFix (LFTBench and LFTBench-Py) | RQ-2 |
| `rq3.sh` | RQ-4: prompt-composition comparison inside the mechanism question | RQ-3 |
| `rq4.sh` | RQ-1: plug-in integration into ChatRepair and CREF | RQ-4 |
| `rq5.sh` | RQ-5: Repository-Level OSS-Fuzz Evaluation | RQ-5 |

The journal article's RQ-2 (when a reduced test helps) and the controlled prompt
experiments of its RQ-4 are analyses over the archived runs; the scripts that
produce every number they report are in `analysis_tse/`, indexed by
`analysis_tse/RESULTS_INVENTORY.md`.

## Repository Structure

```bash
ReduceFix/
├── lftbench/                  # LFTBench dataset
│   ├── data/                  # Ground truth and submissions
│   │   ├── ground_truth/      # AC (Accepted) solutions
│   │   │   ├── cpp/           # C++ AC codes
│   │   │   └── python/        # Python AC codes
│   │   └── submissions/       # WA (Wrong Answer) submissions
│   │       ├── cpp/           # C++ submissions
│   │       └── python/        # Python submissions
│   ├── metadata/              # Problem metadata
│   │   ├── problems.json      # Problem descriptions, samples
│   │   ├── cpp_submissions.jsonl
│   │   └── python_submissions.jsonl
│   ├── tests/                 # Full test suites
│   │   ├── abc361/C/in/       # Test inputs for each problem
│   │   └── ...
│   └── README.md              # Dataset documentation
│
├── results/                   # Experiment artifacts
│   ├── abc361c/               # Per-problem directory
│   │   ├── reducer.py         # Generated reducer
│   │   ├── ac.cpp             # AC code
│   │   ├── 68123456_cpp/      # Per-submission artifacts
│   │   └── ...
│   └── ...
│
├── oss_fuzz_results/          # OSS-Fuzz evaluation data
│   ├── cases_data/            # Case-by-case data
│   ├── experiment_results/    # Experiment statistics
│   └── compute_*.py           # OSS-Fuzz analysis scripts
├── dbms_results/              # SQLancer SQLite compact-reproducer experiment
├── artifact_snapshot/         # Compact snapshots and checker for manuscript numbers
├── prompt_formats/
│   ├── repair.prompt          # Prompt format of repair on LFTBench (C++)
│   ├── repair-py.prompt       # Prompt format of repair on LFTBench-Py (Python)
│   ├── repair-ossfuzz.prompt  # Prompt format of repair on OSS-Fuzz
│   ├── repair-diffline.prompt # Prompt format of repair with Diff Lines strategy
│   ├── reducer.prompt         # Prompt format of reducer generation for LFTBench
│   ├── reducer-ossfuzz.prompt # Prompt format of reducer generation for OSS-Fuzz
├── result_reducer_*.json      # Minimized reduction results (RQ1)
├── result_repair_*.json       # Minimized repair results (RQ2, RQ3)
├── result_chatrepair.json     # ChatRepair results (RQ4)
├── result_cref.json           # CREF results (RQ4)
│
├── rq1.sh                     # RQ1: Reducer effectiveness
├── rq2.sh                     # RQ2: Repair with reduced tests
├── rq3.sh                     # RQ3: Prompt composition
├── rq4.sh                     # RQ4: ChatRepair & CREF integration
├── rq5.sh                     # RQ5: OSS-Fuzz evaluation
│
├── reducer_builder.py         # Generate problem-specific reducers
├── reducer_test.py            # Test reducers on submissions
├── retest_single.py           # Single submission testing (RQ1 demo)
│
├── evaluate_repair.py         # Repair evaluation (main)
├── evaluate_repair_main.py    # Repair evaluation (RQ3)
├── evaluate_repair_with_chatrepair.py  # ChatRepair evaluation
│
├── analyze_*.py               # Statistical analysis for each RQ
├── compare_rq1_methods.py     # RQ1 comparison table
├── summarize_*.py             # Result summarization scripts
│
├── llm.py                     # LLM API interface
├── tutor.py                   # API client configuration
├── config.py                  # API keys and configuration
├── lftbench_utils.py          # Dataset access utilities
├── tools.py                   # Utility functions
└── README.md                  # This file
```

### Key Components

- **`lftbench/`**: Self-contained benchmark dataset with problems, solutions, submissions, and test suites
- **`results/`**: Generated reducers and per-problem/per-submission artifacts
- **`rq*.sh`**: Main entry points for reproducing each research question
- **`result_*.json`**: Consolidated experimental results (minimized for portability)
- **`artifact_snapshot/`**: Compact machine-readable snapshots for the current manuscript tables
- **`dbms_results/`**: SQLancer SQLite reduction harness, data, and current result summaries
- **`temp/`**: Full-version result files with detailed metadata (not for distribution)
- **Core scripts**: `reducer_builder.py`, `reducer_test.py`, `evaluate_repair*.py`
- **Analysis scripts**: `analyze_*.py`, `summarize_*.py` for statistical analysis
- **`prompt_formats/`**: Prompt templates used in the paper (see [Prompt Formats](#prompt-formats))

## Prompt Formats

The `prompt_formats/` directory contains all prompt format templates used in the paper for easy reference and reproduction:

### Repair Prompts

1. **`repair.prompt`** - Standard repair prompt for LFTBench (C++)
   - Contains: problem description, faulty code, reduced test case (input/output)
   - Used in: RQ2 as ReduceFix's main repair strategy

2. **`repair-py.prompt`** - Repair prompt for LFTBench-Py (Python)
   - Same structure as `repair.prompt`, but for Python code
   - Used in: RQ2 for cross-language validation

3. **`repair-ossfuzz.prompt`** - Repair prompt for OSS-Fuzz
   - Contains: crash info, stack trace, annotated source code, reduced test case (hex format)
   - Output format: SEARCH/REPLACE style patches
   - Used in: RQ5 for real-world project repairs

4. **`repair-diffline.prompt`** - Prompt for Diff Lines strategy
   - Shows only the first 10 lines of output differences, without full input
   - Used in: RQ3 to test the impact of information selection

### Reducer Generation Prompts

5. **`reducer.prompt`** - LFTBench reducer generation prompt
   - Input: problem description, example reducer code
   - Output: problem-specific reducer.py script
   - Used in: RQ1, RQ2, RQ3, RQ4 to generate reducers for LFTBench problems

6. **`reducer-ossfuzz.prompt`** - OSS-Fuzz reducer generation prompt
   - Input: project info, file format analysis, example reducer code
   - Output: format-aware `generated_reduce()` function
   - Used in: RQ5 to generate reducers for various file formats (PDF, fonts, images, etc.)

### Usage Notes

- All `{variable_name}` placeholders in prompt files will be replaced with actual values during execution
- For complete prompt construction logic, refer to:
  - Repair: `generate_llm_repair()` function in `evaluate_repair.py`
  - Reducer (LFTBench): `build_generation_prompt()` function in `reducer_builder.py`
  - Reducer (OSS-Fuzz): `build_generation_prompt()` function in `oss_fuzz_results/reducer_builder.py`

## Reproducing Research Questions

### RQ-1: Effectiveness of LLM-generated Reducers (journal RQ-3)

This research question evaluates the reliability and effectiveness of LLM-generated reducers at shrinking failure-inducing inputs. We compare three reduction approaches:

1. **ReduceFix** (LLM-generated reducer + ddmin): Our approach that generates task-specific reducers
2. **DDmin-only**: Pure ddmin baseline without custom reduction logic
3. **Pure LLM**: Direct LLM-based reduction without ddmin refinement

**Key metrics:**
- **Success Rate**: Percentage of cases where reduction succeeds (reduced size < original size)
- **Compression Ratio**: Average reduction in input size (higher = better compression)

Run the command of RQ-1:

```bash
./rq1.sh
```

For details and options, see the script content.


You can run a demo for RQ-1:

```bash
./rq1.sh --retest abc376e 66915962
```

#### Figure: Statistics of Compression Rate.

The violin plot in the following figure confirms this pattern: most points cluster near the median (100%), while a long lower tail for hard tasks (i.e., difficulty group E and F) highlights a few cases with modest shrinkage that lower the mean.

![](violin.png)

#### Figure: Summary of Generated Reducers.

The figure below is a summary chart of all 20 automatically synthesized task-specific reducers, highlighting for each one the structural decomposition it applies and the semantic invariants it enforces beyond plain ddmin.

![](reducers.png)

### RQ-2: Effectiveness of Reduced Test Cases for Repair (journal RQ-1)

This research question evaluates whether reduced test cases can improve automated program repair effectiveness. We test ReduceFix's repair approach across four different LLM models on C++ submissions, and validate cross-language portability on Python submissions.

**Models evaluated:**
- **Qwen2.5-Coder-7B-instruct**: Small open-source model (7B parameters)
- **GLM-4-9B-chat**: Another small open-source model (9B parameters)
- **Qwen-Plus**: Large commercial model (cloud API)
- **DeepSeek-V3**: Large commercial model (cloud API)

**Prompting strategies compared:**
1. **Baseline** (no test case): Only problem description and faulty code
2. **Origin Test**: Full failure-inducing input/output pair
3. **Reduced Test** (ReduceFix): Reduced input/output pair from our reducer

**Datasets:**
- **LFTBench (C++)**: 200 faulty C++ submissions across 20 problems, evaluated with all 4 LLMs
- **LFTBench (Python)**: 20 faulty Python submissions, evaluated with Qwen-Plus for cross-language validation

**Evaluation metric:** pass@k (k ∈ {1, 5, 10}) - probability that at least one of k generated patches is correct

**Baseline comparison:** We also evaluate an end-to-end ddmin-only baseline that uses the reduced input when ddmin succeeds, otherwise falls back to the original failure-inducing test

#### Prompt Format of _ReduceFix_

The following prompt format shows the exact prompt template. If truncation occurred,
the ellipsis token appears inside the fenced block to signal omitted
lines. No other explanatory text is added, keeping the prompt well
below typical context limits even on compact LLMs.

~~~
### Your Incorrect Code
```cpp
{wa_code}
```
### Failing Case
Input:
```
{reduced_failing_input}
```
Your Output:
```
{wa_output}
```
Expected Output:
```
{expected_output}
```
### Your Task
Fix the C++ code to pass ALL test cases (including hidden ones).
### Critical Guidelines
1. Focus on algorithmic correctness - NO hard-coded values
2. Keep complexity reasonable (target $O(N\log N)$ where possible)
3. Handle edge cases (empty input, single element, max constraints)
4. Use standard C++20 and avoid non-portable extensions
### Output Format
Provide ONLY the complete fixed C++ program inside a single cpp block.
~~~

Run the command of RQ-2:

```bash
./rq2.sh
```

For details and options, see the script content.

### RQ-3: Influence of Prompt Composition (journal RQ-4)

This research question investigates the distinct influence of two factors within ReduceFix: (i) **length reduction** (fewer tokens to keep fault-relevant text within the model's attention span) and (ii) **information selection** (retaining minimal concrete evidence that still exposes the fault). We compare five prompt strategies on Qwen2.5-Coder-7B-instruct:

1. **Baseline** (~3.2KB, ~130 lines): Problem + faulty code only
2. **Origin Test** (~30.5KB, ~2381 lines): + full failure-inducing input/output pair
3. **Diff Lines** (~3.2KB, ~133 lines): + up to 10 mismatched output lines (sparse evidence, same length as Baseline)
4. **Reduced Test** (~6.6KB, ~514 lines): + reduced input/output pair (ReduceFix's default, joint action of length control and full information)
5. **Reduced + Origin** (~36.4KB, ~2638 lines): + both reduced and full tests (redundant information, maximum length)

**Key insight:** The conjunction of compact length and complete counterexample information is important in this setting. Reduced Test has the highest observed overall pass@10 among these variants (25.5%), compared with Diff Lines (20.0%) and Origin Test (19.0%).

#### Prompt Format of _Diff Lines_

The **Diff Lines** strategy stays the same length as Baseline but appends up to 10 mismatched output lines, providing sparse evidence without increasing prompt size. This comparison evaluates whether minimal failure information alone (without full input/output) can guide repair.

~~~
### Problem Description
{full problem text}
### Your Incorrect Code
```cpp
{faulty code here}
```
### Failure Evidence (diff only)
Line 1: Got '42', Expected '43'
Line 2: Got '...', Expected '...'
...
### Your Task
Fix the code so that the diff disappears on all tests.
Return only the complete corrected C++ program in a ```cpp block.
~~~

Run the command of RQ-3:

```bash
./rq3.sh
```

For details and options, see the script content.

### RQ-4: Integration with ChatRepair and CREF (journal RQ-1)

This research question checks whether ReduceFix can be inserted into existing APR pipelines as a pre-repair evidence step. We replace only the failure-inducing test input while keeping patch generation and validation unchanged, using the same 10-sample budget across settings.

**Systems evaluated:**
1. **ChatRepair**: Conversational repair framework that alternates between user proxy and LLM with feedback
   - **Settings**: MAX_RETRY=1 (one feedback round), length=2 (conversation window)
   - First turn: task description + faulty code + failure-inducing test
   - Second turn: test verdict (pass/fail) from harness
   
2. **CREF**: Context-aware reference-based repair with retrieval augmentation
   - **Settings**: Two-turn setup using AtCoder editorial
   - First turn: official editorial as high-level solution description
   - Second turn: failure-inducing test case after validating first-turn patch

**Comparison:**
- **Original**: Using full failure-inducing input (Origin Test)
- **+ ReduceFix**: Using reduced input from our reducer (Reduced Test)

**Key results:** 
- **ChatRepair**: Overall pass@1/5/10 changes from 9.2/22.6/30.5 to 12.1/29.0/37.0.
- **CREF**: Overall pass@1/5/10 changes from 13.9/31.6/39.0 to 14.7/32.7/40.0.

Run the command of RQ-4:

```bash
./rq4.sh
```

For details and options, see the script content.

### RQ-5: Evaluation on OSS-Fuzz (journal RQ-5)

This research question evaluates ReduceFix on repository-level crash-inducing inputs from OSS-Fuzz. The journal experiment uses a 167-case complete-run subset from the frozen >=4KB manifest where Baseline, Origin Test, and Reduced Test all have the same 10-candidate repair budget.

**Evaluation dimensions:**
1. **Test case reduction**: Success rate and compression ratio across three approaches (DDmin-only, ReduceFix, Pure LLM)
2. **Repair effectiveness**: pass@k (k ∈ {1, 5, 10}) for three prompting strategies (Baseline, Origin Test, Reduced Test)

**Key findings:** ReduceFix reduces 83.2% of crash inputs, with 46.5%/51.3% average/median end-to-end compression rate when unsuccessful reductions count as 0. DDmin-only reaches 43.7% success and 37.5%/0.0% average/median end-to-end compression rate; Pure LLM reduction reaches 37.1% success and 33.2%/0.0%. Under Docker-grounded Qwen2.5-Plus validation, Reduced Test reaches 14.4% observed pass@10, compared with 11.4% for Origin Test and 12.0% for Baseline.

Legacy pilot command:

```bash
./rq5.sh
```

This command belongs to the earlier small OSS-Fuzz pilot. The journal-scale RQ-5 reported in the manuscript is the 167-case complete-run cohort summarized above. Use `artifact_snapshot/oss_fuzz_ge4k_complete10_deep_stats.json` to check the reported tables and `oss_fuzz_results/journal_manifests/ossfuzz_journal_ge4k_cases_filtered_reviewer_v1.json` for the fixed 167-case cohort.

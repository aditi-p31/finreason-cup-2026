# finreason-solution 0.1

Exact solver induction for Task 1 of the FinReason Cup at IEEE BigData 2026.

This package answers FinReason Task 1 questions with a deterministic,
exact-arithmetic pipeline. For each of the 290 question templates that come
with labelled data, it derives a small arithmetic program from the eleven
solved instances the cup releases per template, keeps each part of that
program only if it reproduces all eleven gold values, and runs it on new draws
of the same template. The pipeline itself calls no language model, neither
when it builds the solvers nor when it runs the hidden-stratum forms or makes
predictions. The 116 forms it ships were transcribed with AI assistance under
the author's review (`HIDDEN-FORMS.md`, [Acknowledgments](#acknowledgments)).
There is no randomness
and no network access in the pipeline, and the runtime uses only the Python
standard library. Every score, validation and submission archive is produced
by the organizers' own code, run unmodified from your checkout of the cup
repository.

It accompanies the paper *Executable Financial Reasoning in the FinReason Cup:
Program Induction and Rule-Based Audit Verification* (Aditi Patodiya, team
"Patodiya Research").

## What is and is not in this release

Released after the test-submission deadline (25 October 2026, 23:59 AoE).

- **In:** the solver source, the tests, the analysis scripts, and the solver
  artifacts needed to predict without a rebuild (`artifacts/solvers.json`,
  `shape_index.json`, `fallback_model.json`), plus the dev-split predictions
  and the measurement reports the paper's numbers come from.
- **Not in:** the cup data. The pipeline reads it from your own checkout (see
  [Inputs](#inputs)). By default the leaderboard and test predictions and the
  two submission archives are not included either; `./run.sh` regenerates
  them, and their sha256 digests are listed under
  [Expected outputs](#expected-outputs). One file carries test and
  leaderboard values: `tests/test_degeneracy.py` checks the stage-5 reference
  forms against answers worked out by hand for ten unlabelled draws (six test
  and four leaderboard cases), so it names those cases with their expected
  final and trace values.
- **Hidden stratum.** The test split has 348 cases whose templates have no
  labelled instance anywhere. This package includes per-template forms for
  them, behind the `--hidden-forms` switch (see `HIDDEN-FORMS.md`). With the
  switch off, the default, those cases get the fallback guess described below,
  and the test predictions whose digest is listed under
  [Expected outputs](#expected-outputs) were made that way. With it on, the
  pipeline reproduces the ranked test submission (accepted 21 October 2026):
  `scripts/reproduce_ranked.sh` rebuilds it and checks its sha256.
- **Development history.** The build and submission logs and the working
  notes are not part of this release. They are available from the author on
  request.

## Requirements

- Python 3.11 (tested with CPython 3.11.15) on macOS or Linux, with `bash`.
- No third-party runtime packages. The tests need `pytest`, pinned with its
  dependencies in `requirements.lock.txt`.
- A checkout of the cup repository at dataset version `task1-v4`.
- Predicting, scoring and packaging from the shipped solvers takes seconds.
  A full solver rebuild is CPU-bound: the induction search spends 24,198
  seconds of solver time in total (median 11 s per template, one template
  2,545 s), run in parallel worker processes. The widest search stage caps
  itself at five workers to stay within 16 GB of memory.

## Inputs

### FinReason Cup Task 1 data and tools (required)

```
git clone https://github.com/The-FinAI/IEEE-bigdata-cup.git
git -C IEEE-bigdata-cup checkout 4c38c72c07f23ce50178eb4590ca6a0f2892f912
```

Put the checkout next to this directory (`../IEEE-bigdata-cup`, the default)
or point `FINREASON_CUP_REPO` at it. The shipped artifacts were built from
commit `4c38c72`; every file the pipeline reads is byte-identical at the later
commit `089a2a3`. To check your copy, run from the cup checkout:

```
shasum -a 256 -c /path/to/finreason-cup-2026/task1/docs/inputs.sha256
```

`docs/inputs.sha256` lists the eleven Task 1 data files the pipeline and its
tests read (dataset version `task1-v4`, test release
`task1-v4-test-questions-20260901-r2`) and the six organizer tool files they
run or import. The data are licensed CC BY 4.0 by the organizers; see
[Licence](#licence).

### FinChain (optional, reading only)

The stage-4 generator forms in `src/finreason_solver/genforms.py` were
transcribed from the FinChain generators, and the stage-5 reference forms in
`refforms.py` consulted them where the question wording left a choice. The
tree read is commit `146eaa8`,
the commit the cup's provenance notice pins. FinChain is not a build input
and nothing here executes it. To read the same source:

```
git clone https://github.com/mbzuai-nlp/finchain.git
git -C finchain checkout 146eaa8225bf867fe7386c2d4727b59e03170235
```

### Environment variables

| variable | default | meaning |
| --- | --- | --- |
| `FINREASON_CUP_REPO` | `../IEEE-bigdata-cup` | cup checkout (data and organizer tools) |
| `FINREASON_ARTIFACTS` | `./artifacts` | where solvers, predictions and reports are read and written |
| `FINREASON_HOLDOUT_DEV` | unset | `1` builds solvers from the train split only, so `score-dev` is held out |
| `FINREASON_FINCHAIN_REPO` | `../finchain` | recorded for reference; never read |
| `PY` | `.venv/bin/python` | interpreter used by `run.sh` |

## Setup

With [uv](https://docs.astral.sh/uv/):

```
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.lock.txt
```

With plain pip:

```
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
```

`run.sh` performs the same setup on first use (uv if available, otherwise
`python3.11 -m venv`).

## Run

**The ranked Task 1 entry: one command.** From the package root, after the
setup above:

```
scripts/reproduce_ranked.sh
```

This is the authoritative command for the submitted final version, the test
archive accepted on 21 October 2026. It rebuilds that archive from the shipped
solvers with the `--hidden-forms` switch on, in a new output directory
(`OUT=<empty dir>` to choose it), and checks both files:

| file | sha256 |
| --- | --- |
| `test_predictions.jsonl` | `3f0bec6f039e66b49365af039ab0ab41902c3274dab43b8d02fb3c6a16c4a2d4` |
| `test_submission.zip` | `b786d1e5b8b7284b762e8dbbd2248692cfe4af87348d69f1eb8f464a85dc0991` |

It prints `VERDICT: MATCH` and exits 0 only when both hashes match and the
predictions are byte-identical to `accepted_20261021/test_predictions.jsonl`;
otherwise it prints `VERDICT: MISMATCH` and exits 1.
`scripts/reproduce_ranked.sh --full` first rebuilds every solver artifact from
the cup data (hours) and then makes the same check. `HIDDEN-FORMS.md` shows
the steps it runs.

The pipeline's full rebuild of every artifact, with the switch off (its test
archive is the 14 September 2026 one):

```
./run.sh
```

It runs `build-index`, `build-solvers` (stages 1 to 5 below),
`build-fallback`, `score-dev`, and `package` for the leaderboard and test
splits, writing into `artifacts/`. It exits 0 only when every stage succeeds;
the first failing stage stops the run and its non-zero exit code is returned.

Without a rebuild, from the shipped solvers:

```
export PYTHONPATH=src
.venv/bin/python -m finreason_solver score-dev                 # dev predictions + organizers' scorer
.venv/bin/python -m finreason_solver package --split leaderboard
.venv/bin/python -m finreason_solver package --split test
.venv/bin/python -m finreason_solver predict --split test --out /tmp/test_predictions.jsonl
```

`score-dev` writes `artifacts/dev_predictions.jsonl` and
`artifacts/dev_score.json`. `package` writes `<split>_predictions.jsonl`,
`<split>_submission.zip` (built by the organizers' packager) and
`<split>_package.json`; for the leaderboard split it also runs the organizers'
admission check. `--no-fallback` before the command disables the guess
policy.

Tests:

```
.venv/bin/python -m pytest
```

489 tests in this package: the 446 of the core pipeline and the 43
hidden-stratum route tests in `tests/test_hiddenforms.py` (two of those need
`hidden/templates.json`, which is not shipped, and skip). They replay every
shipped component against gold, pin
serialisation and the answer policy against the organizers' own functions,
check every reference form against its eleven instances, and validate the
prediction files with the official tooling. Tests that need the solver
artifacts skip cleanly when `artifacts/solvers.json` is absent.

## Expected outputs

Predicting, scoring and packaging from the shipped solvers, with the
`--hidden-forms` switch off, reproduces these files byte for byte (sha256).
The ranked test archive, made with the switch on, is listed in
`HIDDEN-FORMS.md`:

| file | sha256 |
| --- | --- |
| `artifacts/dev_predictions.jsonl` (290 cases) | `eda131683572461613240c8bda541a9641b208e30c2de7d65418860809c13a8c` |
| `artifacts/leaderboard_predictions.jsonl` (580 cases) | `e079900c213fe463e353a2c6900da51ead5da8a18181fae158fe37ac9ed5c634` |
| `artifacts/test_predictions.jsonl` (928 cases) | `d1007b775c5b047712d540dfbeb4156177fa19b8216390028d7a0855a1db0828` |
| `artifacts/leaderboard_submission.zip` | `eb3e8f627e8d3d7ac39580b90893fa31aa7534a2814cb250a9306783e2372d88` |
| `artifacts/test_submission.zip` | `42111f7f1d139b86904036bcfc43ef3ed1be2f5b0281ab4e761bcd101bdea221` |

With the switch off, this test archive is byte for byte the one accepted on
14 September 2026. It is not the ranked Task 1 entry. The ranked entry,
accepted on 21 October 2026, is the archive made with the switch on;
`scripts/reproduce_ranked.sh` rebuilds it and checks its sha256 (see
[Run](#run)).

The shipped solver artifacts:

| file | sha256 |
| --- | --- |
| `artifacts/solvers.json` | `e510b3e4389e2a6273ef99c40707b977829713db825b4c9cbce14853a25ed0a6` |
| `artifacts/shape_index.json` | `1c70c8af155e10c8a762a8c37c0bb05b9f00660d2f58106597f52bd743d48f66` |
| `artifacts/fallback_model.json` | `8279d5a2226ab91d1f1d11257a5d229b14613ebc68e03a306db3252e54bbc2f3` |

A rebuild re-derives `solvers.json` with the same programs; its per-template
`seconds` field records wall-clock time and is the one field that changes
between runs. Reports record the paths they were written to, so their
`*_path` values change with the directory you run from.

Scores from the organizers' scorer on the 290-case practice (dev) split, in
`docs/results/`:

| report | `seen_fac` | `seen_checkpoint` |
| --- | --- | --- |
| `dev_score.json`: shipped solvers (in-sample by construction: dev supplies one of the eleven instances) | 1 | 1 |
| `dev_score_no_fallback.json`: same, guess policy off | 1 | 1 |
| `dev_score_holdout.json`: solvers built from train only (`FINREASON_HOLDOUT_DEV=1`, 2026-09-05 code, before stages 4 and 5) | 0.9493 | 0.9820 |

Both archives pass the organizers' packaging check, the leaderboard archive
passes their admission check, and every case in all three prediction files
carries a final answer. `docs/results/README.md` describes each report.

## How it works

```
question text
  -> shape match        numbers masked out, look up template_id    (shapes.py)
  -> solver             exact program over the question's numbers   (derive.py, expr.py)
  -> serialisation      cup-legal decimals and a/b rationals        (numbers.py)
  -> predictions.jsonl  -> organizers' validate / package / score-dev (official.py)
```

**Template identification.** Every number in a question is replaced by `<N>`.
The resulting shape is looked up in an index built from the 3,190 labelled
cases (2,900 train and 290 dev): exact shape first, then a relaxed key, then a
fuzzy match above 0.93. The number tokeniser is rational-aware, so `-3/17` is
one number.

**The five build stages.** Each stage is spent only on the templates the
previous ones left unsolved, except stage 5, which revisits solved ones.

1. **Base search** (`induction.py`, `derive.py`). The ordered numbers of the
   question become parameters `p0..pk`. Exact-arithmetic expressions over
   them are enumerated bottom-up and deduplicated by their value vector across
   the eleven instances; a meet-in-the-middle step inverts the target through
   one more operator. Trace slots are solved in order and each solved slot
   becomes a leaf for the next. The smallest expression reproducing every gold
   value wins. Enum outputs are derived as decision lists of sign tests.
   208 templates ship from this stage.
2. **Wide search.** The same search with one more multiplicative level.
   19 templates.
3. **Stage-3 search** (`stage3.py`, `textrules.py`). Target transforms, sum
   peeling for three- and four-term sums of products, geometric sums and
   derived exponents for compounding, and piecewise conditionals. Four
   word-keyed KYC templates are read by rules parsed from each question's own
   text at prediction time. 20 templates.
4. **Generator forms** (`genforms.py`). Eleven closed forms, transcribed once
   from the published FinChain generators in the same expression language,
   cover templates whose arithmetic the search may not close within its fixed
   work budget. A form fills only what the earlier stages left unsolved, and
   only if it reproduces all eleven gold instances. 7 templates ship from this
   stage; the search closes the other four first.
5. **Reference forms** (`refforms.py`). On some templates the eleven labelled
   draws share a relation the unlabelled draws do not (a weight that is always
   1, two rates that are always equal), so a wrong program can reproduce every
   gold value. `scripts/degeneracy_audit.py` finds them; for those templates
   the recipe stated in the question text replaces the search's program,
   provided it passes the same eleven-instance gate. 36 templates.

**Ship gate.** `derive.contract_test` replays every solver against all eleven
gold instances, per component: a trace slot is used only if it reproduced all
eleven gold values, and the final answer only if it reproduced all eleven
under the scorer's canonicalisation. All 290 templates pass in full (518 of
518 trace slots).

**Answer policy.** The organizers' scorer gives a `null` and a wrong value the
same zero, while one invalid record rejects the whole submission. So
`predict.py` always emits a value when it serialises legally. Cases whose
template is unmatched (the hidden stratum) get the guess in `fallback.py`:
the nearest description-conditioned arithmetic skeleton for decimal outputs,
and for enum outputs the first allowed label, in sorted order, that the
question's own decision list does not mark as its residual arm.

**Serialisation.** Terminating values are written as finite decimals and
non-terminating ones as irreducible `a/b` rationals, as the cup contract
requires; final answers are rounded half-up to the case's `answer_spec`.

## Repository layout

| path | contents |
| --- | --- |
| `run.sh` | full rebuild of every artifact with the switch off (its test archive is the 14 September 2026 one): venv setup, then `finreason_solver all` |
| `src/finreason_solver/cli.py` | `build-index`, `build-solvers`, `apply-genforms`, `build-fallback`, `predict`, `score-dev`, `package`, `all` |
| `src/finreason_solver/config.py` | input and output locations, environment variables |
| `src/finreason_solver/dataio.py`, `numbers.py`, `shapes.py` | data loading, exact numbers and serialisation, template identification |
| `src/finreason_solver/expr.py`, `induction.py`, `derive.py`, `stage3.py`, `textrules.py` | expression language and stages 1 to 3 |
| `src/finreason_solver/genforms.py`, `refforms.py` | stage 4 generator forms and stage 5 reference forms |
| `src/finreason_solver/build_solvers.py` | parallel build, ship gate, persistence |
| `src/finreason_solver/fallback.py`, `predict.py`, `official.py` | guess policy, prediction files, organizer CLI wrapper |
| `tests/` | the test suite |
| `scripts/` | measurement scripts behind the paper's numbers (baselines, fallback and enum-prior estimates, tokeniser ablation, generator-form evidence, degeneracy audit, hidden-stratum route counts) and `compare_artifacts.py` |
| `artifacts/` | shipped solver artifacts, dev predictions, measurement reports |
| `docs/results/` | pipeline reports with paths made relative to the package root |
| `docs/inputs.sha256` | checksums of every cup file the pipeline and its tests read or run |
| `REPRODUCE.md` | step-by-step reproduction and verification |
| `scripts/reproduce_ranked.sh`, `HIDDEN-FORMS.md` | the one command for the ranked entry, and the hidden-stratum route it switches on |
| `src/finreason_solver/hiddenforms/`, `hidden/` | the route, the 116 reviewed forms and their tooling |
| `accepted_20261021/test_predictions.jsonl` | the ranked test predictions, for the byte comparison |
| `LICENSE`, `NOTICE`, `CITATION.cff` | licence, third-party attribution, citation metadata |

## Acknowledgments

The author conceived this work, selected the target competition and the
solution approach, directed the implementation, verified all reported results
against the raw data and primary sources, and takes full responsibility for
the content. AI assistance (Claude, Anthropic) was used to implement this
package and to draft its documentation under the author's direction, and an
AI assistant transcribed the 116 hidden-stratum forms under the author's
review (`HIDDEN-FORMS.md`).

## Licence

Copyright 2026 Aditi Patodiya. Licensed under the Apache License, Version 2.0;
see `LICENSE`. `NOTICE` carries the attributions for the third-party material
this package reads or transcribes from:

- the FinReason Cup Task 1 data, CC BY 4.0, by the FinReason Cup organizers
  (https://the-finai.github.io/IEEE-bigdata-cup/task1/). The data files are
  not redistributed; the shipped solver artifacts are derived from them, with
  changes (numbers masked, text tokenised, gold values replaced by fitted
  programs);
- the FinChain generator source, Apache-2.0, read at commit `146eaa8` for the
  transcribed forms;
- the organizers' scoring, validation and packaging tools, Apache-2.0, which
  are run from your checkout and not included here.

## Citation

If you use this package, please cite the paper:

```
@misc{patodiya2026executable,
  author = {Aditi Patodiya},
  title  = {Executable Financial Reasoning in the {FinReason} Cup: Program Induction and Rule-Based Audit Verification},
  year   = {2026},
  note   = {FinReason Cup 2026 working notes, Tasks 1 and 3, IEEE International Conference on Big Data (BigData 2026)}
}
```

The organizers ask that work on Task 1 cite FinChain, the FinReason Cup
overview and the Task 1 overview, using their BibTeX and citation keys
(https://the-finai.github.io/IEEE-bigdata-cup/#paper-references). The overview
entries below are the organizers' drafts of 5 October 2026; refresh them from
that page before use.

```
@inproceedings{xie-etal-2026-finchain,
    title = "{F}in{C}hain: A Symbolic Benchmark for Verifiable Chain-of-Thought Financial Reasoning",
    author = "Xie, Zhuohan  and
      Orel, Daniil  and
      Thareja, Rushil  and
      Sahnan, Dhruv  and
      Madmoun, Hachem  and
      Zhang, Fan  and
      Banerjee, Debopriyo  and
      Georgiev, Georgi Nenkov  and
      Peng, Xueqing  and
      Qian, Lingfei  and
      Huang, Jimin  and
      Su, Jinyan  and
      Singh, Aaryamonvikram  and
      Xing, Rui  and
      Elbadry, Rania  and
      Xu, Chen  and
      Li, Haonan  and
      Koto, Fajri  and
      Koychev, Ivan  and
      Chakraborty, Tanmoy  and
      Wang, Yuxia  and
      Lahlou, Salem  and
      Stoyanov, Veselin  and
      Ananiadou, Sophia  and
      Nakov, Preslav",
    editor = "Liakata, Maria  and
      Moreira, Viviane P.  and
      Zhang, Jiajun  and
      Jurgens, David",
    booktitle = "Proceedings of the 64th Annual Meeting of the {A}ssociation for {C}omputational {L}inguistics (Volume 1: Long Papers)",
    month = jul,
    year = "2026",
    address = "San Diego, California, United States",
    publisher = "Association for Computational Linguistics",
    url = "https://aclanthology.org/2026.acl-long.662/",
    doi = "10.18653/v1/2026.acl-long.662",
    pages = "14529--14553",
    ISBN = "979-8-89176-390-6"
}

@unpublished{finreason2026overview,
 author = {Xie, Zhuohan and Wang, Yan and Jiang, Yuechen and Peng, Xueqing and Qian, Lingfei and Cao, Yupeng and Chen, Yankai and Liu, Xue (Steve) and Nakov, Preslav},
 title = {Overview of the {FinReason Cup 2026}: Agentic Financial Reasoning, Hedging, and Audit Verification},
 year = {2026},
 note = {Manuscript in preparation; proposed author list and order},
 url = {https://the-finai.github.io/IEEE-bigdata-cup/}
}

@unpublished{finreason2026task1overview,
 author = {Xie, Zhuohan and Wang, Yan and Jiang, Yuechen and Peng, Xueqing and Qian, Lingfei and Cao, Yupeng and Chen, Yankai and Liu, Xue (Steve) and Nakov, Preslav},
 title = {Overview of the {FinReason Cup 2026} Task 1: Verifiable Financial Chain Reasoning},
 year = {2026},
 note = {Manuscript in preparation; proposed author list and order},
 url = {https://the-finai.github.io/IEEE-bigdata-cup/task1/}
}
```

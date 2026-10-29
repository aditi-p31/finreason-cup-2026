# Reproducing the results

Every command below runs from the package root (the directory holding
`run.sh`). Steps 1 to 5 take minutes and step 6 (tests) about fifteen minutes
on a laptop. Steps 7 and 8 are full rebuilds and are CPU-bound for hours.
Nothing here calls a language model, and after the one-time setup nothing
touches the network.

## 0. The ranked Task 1 entry: one command

After steps 1 and 2 (inputs and environment):

```
scripts/reproduce_ranked.sh
```

This is the authoritative command for the submitted final version, the test
archive accepted on 21 October 2026. It writes into a new directory (or
`OUT=<empty dir>`), runs the pipeline on the shipped solvers with the
`--hidden-forms` switch on, and checks

```
3f0bec6f039e66b49365af039ab0ab41902c3274dab43b8d02fb3c6a16c4a2d4  test_predictions.jsonl
b786d1e5b8b7284b762e8dbbd2248692cfe4af87348d69f1eb8f464a85dc0991  test_submission.zip
```

It ends with `VERDICT: MATCH` and exit status 0 only when both hashes match
and the predictions are byte-identical to
`accepted_20261021/test_predictions.jsonl`; otherwise `VERDICT: MISMATCH` and
exit status 1. `scripts/reproduce_ranked.sh --full` first rebuilds every
solver artifact (step 7 with the switch on). The steps below check the
pipeline with the switch off, its default; step 4 then rebuilds the test
archive accepted on 14 September 2026 (`42111f7f...`), which the ranked one
replaced.

## 1. Inputs

The cup checkout defaults to `../IEEE-bigdata-cup`. If yours lives elsewhere,
set `FINREASON_CUP_REPO` to its path before this step; every command here and
below then uses it.

```
CUP="${FINREASON_CUP_REPO:-../IEEE-bigdata-cup}"
git clone https://github.com/The-FinAI/IEEE-bigdata-cup.git "$CUP"
git -C "$CUP" checkout 4c38c72c07f23ce50178eb4590ca6a0f2892f912
(cd "$CUP" && shasum -a 256 -c "$OLDPWD/docs/inputs.sha256")
```

Skip the clone if the checkout already exists. All seventeen lines must print
`OK`: eleven Task 1 data files at dataset version `task1-v4` (the ten the
pipeline reads, plus `dev_targets.jsonl`, which the tests score) and the six
organizer tool files the pipeline runs or imports.

## 2. Environment

```
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.lock.txt
export PYTHONPATH=src
```

Without uv: `python3.11 -m venv .venv` and
`.venv/bin/python -m pip install -r requirements.lock.txt`. The lock file pins
the test dependencies only; the pipeline itself uses the standard library.

## 3. Predictions from the shipped solvers

```
OUT=$(mktemp -d)
for split in dev leaderboard test; do
  .venv/bin/python -m finreason_solver predict --split $split --out "$OUT/${split}_predictions.jsonl"
done
shasum -a 256 "$OUT"/*.jsonl
```

Expected:

```
eda131683572461613240c8bda541a9641b208e30c2de7d65418860809c13a8c  dev_predictions.jsonl
e079900c213fe463e353a2c6900da51ead5da8a18181fae158fe37ac9ed5c634  leaderboard_predictions.jsonl
d1007b775c5b047712d540dfbeb4156177fa19b8216390028d7a0855a1db0828  test_predictions.jsonl
```

`predict --out` writes only the named file.

## 4. Official scoring and packaging

`score-dev` and `package` write their outputs next to the solvers, so run them
against a copy to leave `artifacts/` as shipped:

```
W=$(mktemp -d)
cp artifacts/solvers.json artifacts/shape_index.json artifacts/fallback_model.json "$W"/
FINREASON_ARTIFACTS="$W" .venv/bin/python -m finreason_solver score-dev
FINREASON_ARTIFACTS="$W" .venv/bin/python -m finreason_solver package --split leaderboard
FINREASON_ARTIFACTS="$W" .venv/bin/python -m finreason_solver package --split test
shasum -a 256 "$W"/*.zip
```

Expected: `score-dev` reports `seen_fac` 1 and `seen_checkpoint` 1 (290 of
290 final answers, 518 of 518 trace slots; in-sample, since the dev instance
is one of the eleven each solver was derived from). Both packages report
`status: PASS`, the leaderboard admission check reports `PASS`, and the
archives hash to

```
eb3e8f627e8d3d7ac39580b90893fa31aa7534a2814cb250a9306783e2372d88  leaderboard_submission.zip
42111f7f1d139b86904036bcfc43ef3ed1be2f5b0281ab4e761bcd101bdea221  test_submission.zip
```

The reports written to `$W` match `docs/results/dev_score.json`,
`leaderboard_package.json` and `test_package.json` apart from their `*_path`
values. `scripts/compare_artifacts.py` makes that comparison:

```
.venv/bin/python scripts/compare_artifacts.py "$W" docs/results --only dev_score.json leaderboard_package.json test_package.json
```

## 5. Fallback ablation

`--no-fallback` turns the guess policy off. `score-dev` writes
`dev_predictions.jsonl` and `dev_score.json` whatever the flag, so use a
second copy:

```
W2=$(mktemp -d)
cp artifacts/solvers.json artifacts/shape_index.json artifacts/fallback_model.json "$W2"/
FINREASON_ARTIFACTS="$W2" .venv/bin/python -m finreason_solver --no-fallback score-dev
```

Expected: the same 1 and 1 as step 4, with byte-identical dev predictions
(`eda13168...`). Every dev case is covered by a validated solver, so the
fallback never fires on dev. The stored report is
`docs/results/dev_score_no_fallback.json`.

## 6. Tests

```
.venv/bin/python -m pytest
```

489 tests in this package: the 446 of the core pipeline and 43 in
`tests/test_hiddenforms.py`. 487 pass and 2 skip; the two need
`hidden/templates.json`, which is not shipped. Tests that need the solver
artifacts skip when `artifacts/solvers.json` is absent.

## 7. Full rebuild

```
FINREASON_ARTIFACTS="$PWD/rebuild" ./run.sh
```

This runs every stage into `rebuild/` and exits non-zero if any stage fails.
Compare the result with the shipped files:

```
.venv/bin/python scripts/compare_artifacts.py rebuild artifacts --only solvers.json shape_index.json fallback_model.json dev_predictions.jsonl
shasum -a 256 rebuild/*_predictions.jsonl rebuild/*.zip
```

`solvers.json` should compare `EQUIVALENT (only seconds differs)`: the
per-template `seconds` field is wall-clock build time. The other files should
be identical bytes, and the prediction files and archives should hash to the
values in steps 3 and 4.

`scripts/reproduce_ranked.sh --full` runs this rebuild with the
`--hidden-forms` switch on and then checks the ranked archive (step 0).

## 8. Held-out rebuild

The shipped solvers use all eleven labelled instances per template, including
the dev one, so the dev score is in-sample. To score dev as held-out data,
build from the train split only:

```
FINREASON_HOLDOUT_DEV=1 FINREASON_ARTIFACTS="$PWD/artifacts_holdout" ./run.sh
cat artifacts_holdout/dev_score.json
```

`docs/results/dev_score_holdout.json` is that measurement for the 2026-09-05
code, before stages 4 and 5 existed (`seen_fac` 0.9493, `seen_checkpoint`
0.9820). The current code adds those two stages, so a fresh held-out build is
not expected to reproduce that report exactly.

The two 5 September builds themselves, and the test archive the first one
produced, are archived in `docs/holdout/`. `scripts/holdout_comparison.py`
recomputes the paper's coincidence counts from them (Table III and Section
IV-C) without a rebuild; `docs/holdout/README.md` gives the command and the
expected output.

## 9. Measurement scripts

Each script under `scripts/` regenerates one report and states its output in
its docstring. The scripts read the solvers from `FINREASON_ARTIFACTS` and
write their reports there, so run them against a copy to leave the shipped
reports in `artifacts/` as they are:

```
X=$(mktemp -d)
cp artifacts/solvers.json artifacts/shape_index.json artifacts/fallback_model.json "$X"/
for s in reproduce_baselines solver_report genform_validation evaluate_fallback \
         evaluate_enum_prior tokeniser_ablation measure_stated_formula_ceiling \
         measure_hidden_routes project_hidden_fac; do
  FINREASON_ARTIFACTS="$X" .venv/bin/python scripts/$s.py > /dev/null
done
for f in baselines enum_prior_loo tokeniser_ablation stated_formula_ceiling hidden_fac_projection; do
  cmp "$X/$f.json" "artifacts/$f.json" && echo "$f.json identical"
done
```

| script | report |
| --- | --- |
| `reproduce_baselines.py` | `baselines.json`: the organizers' B0 and B1 baselines rerun through their scorer, against the published numbers |
| `solver_report.py` | `solver_report.json`: per-template validation summary |
| `genform_validation.py` | `genform_validation.json`: per-template evidence for the stage-4 forms |
| `evaluate_fallback.py` | `fallback_loto.json`: leave-one-template-out value of the guess policy |
| `evaluate_enum_prior.py` | `enum_prior_loo.json`: leave-one-instance-out value of the enum prior |
| `tokeniser_ablation.py` | `tokeniser_ablation.json`: rational-aware against naive number tokeniser |
| `measure_stated_formula_ceiling.py` | `stated_formula_ceiling.json` |
| `measure_hidden_routes.py`, `project_hidden_fac.py` | `hidden_routes.json`, `hidden_fac_projection.json` |
| `degeneracy_audit.py` | stage-5 evidence: labelled-only parameter relations and the components that depend on them (command below) |

The degeneracy audit checks a test archive against the reference forms. Run it
after step 4, which builds `$W/test_submission.zip`:

```
.venv/bin/python scripts/degeneracy_audit.py --build shipped=artifacts/solvers.json \
    --with-fixes --archive test="$W/test_submission.zip"
```

It prints a summary to stdout (`--out FILE` also writes the full report). It
should show 0 degenerate components and 0 reference gate failures for both
`shipped` and `shipped+fixes`, and no wrong values from trusted components in
the test archive.

The shipped reports are the ones the paper's numbers were read from. Five of
them reproduce byte for byte from the shipped solvers: `baselines.json`,
`enum_prior_loo.json`, `tokeniser_ablation.json`, `stated_formula_ceiling.json`
and `hidden_fac_projection.json`. The other four were written by earlier code
or an earlier build, so a rerun reflects the current code and differs as
follows:

- `fallback_loto.json` (2026-09-04, before the enum rule of 2026-09-10): 39 of
  290 finals over the full split and 9 of 174 on intermediate and advanced
  templates. A rerun gives 41 of 290 and 10 of 174, with 290 finals guessed
  instead of 289; the slot counts are unchanged.
- `genform_validation.json` (2026-09-10, measured against the build from
  stages 1 to 3, before the forms were added): `templates_validated_before`
  279 and `before.final_perfect` false for all eleven forms. The shipped
  solvers already contain the forms, so a rerun reads 290 and true there,
  `slot_definitions_validated_delta` drops from 7 to 0, and
  `templates_validated_after` (301) counts the eleven forms a second time. The
  contract tests and held-out dev checks (11 of 11 finals, 27 of 27 slots) are
  unchanged.
- `hidden_routes.json` (2026-09-10 solvers): in route 2, the 0.50 to 0.80
  similarity bucket goes from 5 to 7 hits of 10, and `int_adv_all_11_exact`
  from 11 to 13 of 169. The buckets below 0.30 (0 hits of 107) and routes 1
  and 3 are unchanged.
- `solver_report.json` (2026-09-05 build, before stages 4 and 5): 279 of 290
  templates and 511 of 518 trace slots validated. A rerun gives 290 of 290 and
  518 of 518, with the current stage and build seconds per template.

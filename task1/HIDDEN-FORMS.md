# Hidden-stratum forms

This repository includes the per-template forms for the hidden stratum: the 348 test cases
(116 templates of three draws each) that no labelled template matches. Apart
from its hidden-stratum note, the README describes the pipeline with the
route off, in which these cases get the fallback guess.

The route is off unless it is asked for. With it off, every output is
byte-identical to the README's expected outputs.

## Reproduce the ranked submission: one command

The ranked Task 1 entry is the test archive accepted on 21 October 2026.
From the package root, after
the setup in the README (cup checkout and venv):

```
scripts/reproduce_ranked.sh
```

It writes into a new temporary directory (or into `OUT=<empty dir>`), runs
the route on the shipped solver artifacts, and checks both files:

```
3f0bec6f039e66b49365af039ab0ab41902c3274dab43b8d02fb3c6a16c4a2d4  test_predictions.jsonl
b786d1e5b8b7284b762e8dbbd2248692cfe4af87348d69f1eb8f464a85dc0991  test_submission.zip
```

It ends with `VERDICT: MATCH` and exit status 0 only when both hashes match
and the predictions are byte-identical to
`accepted_20261021/test_predictions.jsonl`; otherwise `VERDICT: MISMATCH`
and exit status 1. `scripts/reproduce_ranked.sh --full` first rebuilds every
solver artifact from the cup data (`./run.sh --hidden-forms`, about 2.5 hours)
and then makes the same check. The sections below show what the script does
step by step.

## How the forms were written

The paper says, in its section on the hidden-stratum programs:

> For the 116 hidden templates, the author directed the work throughout: an
> AI assistant transcribed each question's stated calculation into a small
> deterministic program, and the author reviewed every program before
> submission, revising those her review questioned. Each program was also
> checked by two independent model readings, an adjudication step and a
> blind audit. The prediction path itself calls no model.

`hidden/README.md` is the working brief that transcription followed, shipped
as it was used with a dated release note at its top. Its rule 1 ("You are the
transcriber") is addressed to the assistant.

## What the hidden-stratum route adds

| path | contents |
| --- | --- |
| `src/finreason_solver/hiddenforms/__init__.py` | the route: shape router, form loader, serialisation |
| `src/finreason_solver/hiddenforms/forms/HNNN.py` | one form per hidden template (116) |
| `src/finreason_solver/hiddenforms/hlib.py` | the extraction and arithmetic helper the forms import |
| `src/finreason_solver/hiddenforms/routes.json` | each template's route shape, and the sha256 of every form and of the helper |
| `hidden/forms/final/HNNN.py`, `hidden/hlib.py` | the reviewed forms and helper; the package copies are byte-identical |
| `hidden/README.md` | how the forms were written and checked |
| `hidden/run_forms.py`, `hidden/compare.py` | the form runner (with its static lint) and the run comparison |
| `hidden/build_templates.py`, `hidden/build_candidate.py`, `hidden/export_forms.py` | template grouping, the script that built the accepted archive, the copy into the package |
| `tests/test_hiddenforms.py` | routing, pins, flag handling, byte identity with the route off and on |
| `scripts/reproduce_ranked.sh` | the one command above: rebuilds the ranked archive and checks its sha256 |
| `accepted_20261021/test_predictions.jsonl` | test predictions of the submission accepted on 21 October 2026 (ranked) |

`hidden/templates.json` is not included. It holds the organizers' test
questions verbatim, and the cup data are not redistributed. The scripts that
read it are here for reference; the route does not need them.

## How the route works

`--hidden-forms` (or `FINREASON_HIDDEN_FORMS=1`) applies to `predict`,
`score-dev`, `package` and `all`, before or after the command name. A question
that the shape index leaves unmatched is routed by its shape: numbers masked
as `<N>`, each literal `true` or `false` as `<B>`, whitespace collapsed. If
that shape is a template's shape in `routes.json`, the template's form gets the
question body and returns the final answer and the trace slots it fills,
computed with exact arithmetic. A slot the form leaves out keeps the fallback
guess. No case id is looked up, and matched questions never reach the forms.
A template is used only if its form succeeds on every routed question;
otherwise all its questions keep the fallback, and the coverage report names
it. The loader refuses any form or helper file whose sha256 differs from its
pin in `routes.json`.

## Reproduce the ranked archive by hand

What `scripts/reproduce_ranked.sh` runs, from the package root:

```
export PYTHONPATH=src
W=$(mktemp -d)
cp artifacts/solvers.json artifacts/shape_index.json artifacts/fallback_model.json "$W"/
FINREASON_ARTIFACTS="$W" .venv/bin/python -m finreason_solver --hidden-forms package --split test
shasum -a 256 "$W"/test_predictions.jsonl "$W"/test_submission.zip
cmp "$W"/test_predictions.jsonl accepted_20261021/test_predictions.jsonl && echo identical
```

Expected:

```
3f0bec6f039e66b49365af039ab0ab41902c3274dab43b8d02fb3c6a16c4a2d4  test_predictions.jsonl
b786d1e5b8b7284b762e8dbbd2248692cfe4af87348d69f1eb8f464a85dc0991  test_submission.zip
```

The archive is built by the organizers' packager (`status: PASS`). In
`$W/test_package.json`, `coverage.hidden_forms` reports 348 questions routed
and answered across 116 templates, with 456 trace slots from the forms. The
580 matched test records are byte-identical to the default predictions. The
flag leaves the dev and leaderboard predictions unchanged, because none of
their questions is unmatched.

A full rebuild with the route on (what `--full` runs):

```
FINREASON_ARTIFACTS="$PWD/rebuild" ./run.sh --hidden-forms
```

Compare as in REPRODUCE.md step 7. With the route on, `rebuild/test_predictions.jsonl`
and `rebuild/test_submission.zip` should hash to the two values above.

The earlier accepted archives are not the ranked entry: 14 Sep 2026
(`42111f7f...`) is the route-off output of this package (README, REPRODUCE.md),
2 Oct 2026 (`cce2d3dd...`) and 3 Oct 2026 (`3e7779ac...`) were superseded on 21 Oct
2026. The 3 Oct archive differs from the ranked one in six records: H031, whose haircut
it read as a subtraction (the ranked form applies it proportionally, as the 2 Oct
archive did), and the H091 slot `attrition_case_ebitda_checkpoint` (recurring EBITDA
R - d in the ranked form, R + S - d before). The change followed a blind re-solve
of all 116 templates by AI models, a blind panel of three AI model referees, and
the author's decision.

## Tests

`.venv/bin/python -m pytest` collects 489 tests in this package: the 446 of the
README plus 43 in `tests/test_hiddenforms.py`. Two of the 43 need
`hidden/templates.json` and skip without it.

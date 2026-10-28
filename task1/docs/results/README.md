# Pipeline reports

These are the JSON reports the pipeline writes into `artifacts/`, stored here
with their `*_path` values made relative to the package root. Apart from
those values, each file is exactly what the pipeline wrote.

| file | written by | provenance |
| --- | --- | --- |
| `dev_score.json` | `score-dev` | regenerated for this release from the shipped solvers; identical to the report shipped with them apart from `predictions_path` |
| `dev_score_no_fallback.json` | `--no-fallback score-dev` | regenerated for this release from the shipped solvers; its dev predictions are byte-identical to `artifacts/dev_predictions.jsonl` (sha256 `eda13168...`) because the fallback never fires on dev |
| `leaderboard_package.json` | `package --split leaderboard` | regenerated for this release; the organizers' packager and admission check both report PASS, and the archive hash equals the shipped one |
| `test_package.json` | `package --split test` | regenerated for this release; the organizers' packager reports PASS, and the archive hash equals the shipped one |
| `build_summary.json` | `build-solvers` | from the clean-state rebuild of 2026-09-10, which ran stages 1 to 4 (290 templates, 290 validated, 0 errors); stage 5 was applied afterwards with `apply-genforms`, which does not rewrite this file and left 290 of 290 validated |
| `dev_score_holdout.json` | `FINREASON_HOLDOUT_DEV=1 ... score-dev` | the held-out measurement of 2026-09-05: solvers built from the 2,900 train cases only, before stages 4 and 5; its predictions file is not shipped |

# Archived 5 September builds: the held-out comparison

These files let you check the paper's coincidence counts (Section IV-C and
Table III) without rerunning the search. They are an optional supplement: the
ranked entry and everything in `REPRODUCE.md` use the current build in
`artifacts/`, not these files.

| file | what it is | sha256 |
| --- | --- | --- |
| `solvers_eleven_20260905.json` | the search of 5 September 2026 (stages 1 to 3), fitted on all eleven labelled instances per template, practice included | `ef9a9ad445d86596eb02b10bd1bf701753132461d5a0da99b5aef951db17e524` |
| `solvers_ten_20260905.json` | the same search fitted on the ten training instances only, practice held out (`FINREASON_HOLDOUT_DEV=1`) | `503dd7b1741b05c4189a12b93143684b51ef78aad0fb957c61e0d78a48b0225d` |
| `test_predictions_20260907.jsonl` | the test archive accepted on 7 September, built from the first file before stages 4 and 5 existed; not the ranked entry | `bfd2cd6da0a3593e137b4e3bcf1fa9267cbb5f270d5aa5177557693b094f60d4` |

The two solver files are byte copies of the builds the paper measured. The
current code adds stages 4 and 5, so a fresh held-out rebuild is not expected
to reproduce the second file exactly (`REPRODUCE.md`, section 8).

## One command

With the environment and cup inputs of `REPRODUCE.md` sections 1 and 2:

```
PYTHONPATH=src .venv/bin/python scripts/holdout_comparison.py
```

Expected output:

```
eleven  templates 38  components 82  reproduce practice 82
ten     templates 39  components 86  reproduce practice 76
archive 2026-09-07  finals 53  slots 78  templates 36
```

For each build the script runs `scripts/degeneracy_audit.py`, which compares
every shipped component with its reference form on all unlabelled
leaderboard and test draws. A coincidence-fitted component passes its build's
gate (all eleven instances, or the ten training ones in the held-out build) but
disagrees with its reference on at least one such draw. The script then replays each of those components on its template's
practice instance with the organizers' `value_matches`. In the eleven-instance
build all 82 reproduce the practice value, as they must, since that instance
was fitted. In the held-out build 76 of 86 still reproduce it, so the withheld
draw exposes only 10, in five templates. The last line counts the values of
the 7 September archive that came from coincidence-fitted components and
disagree with the reference forms: 53 final answers and 78 trace slots in 36
of the 38 templates.

No gold exists for the leaderboard and test draws, so these are agreement
counts against the reference forms, not scores. Add `--out FILE` to write the
per-component rows.

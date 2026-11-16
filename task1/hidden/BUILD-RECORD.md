# Build record of the hidden-template forms

This file records how the 116 forms in `forms/final/` were built, checked and
revised: the workflow runs, the models, the agreement and audit outcomes, the
later re-check and the author's review. The prompts of every run are in
`PROMPTS.md`, verbatim. Numbers come from the local workflow records (start
time, duration, agent count, recorded model per agent, total tokens and tool
calls) and from the local transcription record the build wrote; neither is
part of this release. Times are UTC.

## Runs

All agents were Claude models run as workflow agents. In the scripts,
`'opus'` resolved to `claude-opus-5-5` (Claude Opus 5.5) and `'sonnet'` to
`claude-sonnet-5` (Claude Sonnet 5). No script set a sampling parameter, and
none was recorded. Agents within a run worked in parallel, so wall clock is
the run's elapsed time, not the sum over agents. Tokens are the run's
recorded total over all its agents.

| # | run | started | agents by role and model | wall clock | tokens | tool calls |
| --- | --- | --- | --- | ---: | ---: | ---: |
| 1 | main transcription build | 2026-09-28 03:17 | 56: 1 infra, 15 reader A, 15 adjudicators, 1 build, 8 auditors and 1 finalize on Claude Opus 5.5; 15 reader B on Claude Sonnet 5 | 64.1 min | 6,003,384 | 1,191 |
| 2 | flagged audit | 2026-09-28 04:22 | 3: 2 auditors and 1 resolver, Claude Opus 5.5 | 8.1 min | 276,940 | 47 |
| 3 | audit of the remaining 48 | 2026-10-02 15:17 | 8: 6 auditors, 1 resolver and 1 verifier, Claude Opus 5.5 | 27.7 min | 701,413 | 171 |
| 4 | blind re-solve of all 116 | 2026-10-19 04:58 | 29 solvers, Claude Opus 5.5 | 19.8 min | 2,006,446 | 243 |
| 5 | referee panel on 4 templates | 2026-10-19 05:20 | 12 referees (4 templates, 3 lenses), Claude Opus 5.5 | 5.6 min | 686,172 | 33 |

Runs 1 to 3 together: 67 agents, 100.0 min of wall clock, 6,981,737 tokens
(runs 2 and 3: 35.9 min and 978,353 tokens). Runs 4 and 5 together: 41
agents, 25.4 min, 2,692,618 tokens. A first start of run 3 on 2026-10-02 at
15:16 used a wrong key list and was stopped after 18.8 s; its output folder was
set aside, and run 3's prompt tells its agents to ignore it.

The 21-template pilot of 2026-09-16 (Claude Opus 5) is not in the table. The
adjudicators were allowed to consult its forms only as a third opinion, after
forming their own view.

The local transcription record states that no paid API call was made in
runs 1 and 2, and the rules of runs 1 to 3 forbid LLM API spend. The forms and
the prediction path call no model.

## Transcription and adjudication (run 1)

The hidden stratum groups into 116 templates (28 enum, 88 decimal), 348 cases
and 456 trace slots, read in 15 batches. Reader A (Claude Opus 5.5) was told
to implement each recipe literally, clause by clause; reader B (Claude Sonnet
5) to restate it as numbered symbolic steps first. Neither saw the other's
forms. An adjudicator per batch re-read every template, agreed ones included.

| outcome | templates | keys |
| --- | ---: | --- |
| agreed on every final and slot of all three draws, reading confirmed by the adjudicator | 107 | |
| adjudicated | 9 | H012, H017, H031, H040, H058, H068, H073, H082, H091 |
| of those: only a slot differed | 5 | H017, H040, H073, H082, H091 |
| of those: the finals differed | 3 | H012, H058, H068 |
| of those: the adjudicator overruled a reading shared by both readers and the pilot | 1 | H031 |
| uncertain or failed | 0 | |

## Blind audits (runs 1, 2 and 3)

Each auditor worked the answer and every slot from the question text before
looking at the form's output. Together the three passes cover all 116
templates.

| pass | templates | outcome |
| --- | --- | --- |
| first audit, run 1, 2026-09-28 | 61: all 28 enum, all 9 adjudicated and every third agreed template | 59 confirmed, 2 unsure (one slot each in H091 and H109), 0 wrong; finals match on 183 of 183 cases, slot cells on 222 of 228 |
| flagged audit, run 2, 2026-09-28 | 7 with a plausibility flag: H004, H011, H013, H019, H034, H095, H106; two auditors each | all 21 finals and 27 slot cells match in both audits; 5 confirmed by both, H013 and H019 unsure for one auditor |
| remaining 48, run 3, 2026-10-02 | the 48 not yet audited | 47 confirmed, 1 unsure (H112, one slot on one draw), 0 wrong; no form changed because of the audit |
| total | 61 + 7 + 48 = 116 | 111 confirmed, 5 unsure and resolved, 0 wrong |

How the five unsure verdicts were resolved:

- H109 and H112: form kept. The auditor named no clause the form misreads, and
  the finals match either way.
- H013 and H019: form kept. One draw of each breaks the question's own premise,
  and the literal stated formula is the accepted reading.
- H091: held on the fallback in the first candidate; included with its slot
  from 2026-10-02; its slot was switched to the auditor's reading on
  2026-10-19, in the archive accepted on 2026-10-21 (next section).

## Re-check of 2026-10-19 and the resulting changes (runs 4 and 5)

Run 4 solved all 116 templates again from scratch; each solver was told to
read only the question texts and specs of its templates, and no form or
prediction. Against the archive ranked at the time (accepted 2026-10-03), it
agreed on 795 of 804 values (348 finals and 456
slots). The 9 differences sat in four templates, all four contested before.
Run 5 gave each of them to three blind referees, who saw the two readings
under random labels.

| template | difference | panel | author's decision (2026-10-19) |
| --- | --- | --- | --- |
| H031 | 1 final and 3 slots: haircut applied by subtraction (form since 2026-10-02) or proportionally (re-solve) | 3-0 for the re-solve | proportional; the code reviewed on 2026-10-02 before the subtraction change was restored |
| H091 | 3 slots: recurring EBITDA R + S - d (form) or R - d (re-solve and the first audit) | 3-0 for the re-solve | slot switched to R - d |
| H058 | 1 final: unfloored (form) or floored at zero (re-solve) | 3-0 for the re-solve | form kept |
| H082 | 1 slot on the draw whose availability flag is false: filled (form) or 0 (re-solve) | 2-1 for the re-solve | form kept |

The archive accepted on 2026-10-21, the ranked entry, differs from the
2026-10-03 one in six records (1 final, 6 slots) and agrees with the re-solve
on 802 of 804 values. Its official hidden-stratum final-answer score is
1.000000: all 348 hidden finals are correct. Slot scores per stratum are not
published.

## Author review

- 2026-10-02: the author reviewed all 116 forms on a review sheet.
- 2026-10-02: she re-reviewed the two forms that changed that day. H031 changed
  on her decision (subtraction reading). On H082 she asked for its explanation
  to be corrected; the docstring was rewritten, with code and outputs
  unchanged.
- 2026-10-19: after runs 4 and 5 she decided the four contested templates as
  in the table above. The archive with those changes was accepted on
  2026-10-21.

## Prediction time

`scripts/reproduce_ranked.sh` rebuilds the ranked test archive from the shipped
solver artifacts and checks its sha256: it answers all 928 test cases,
including the 348 hidden ones through these forms, and builds the archive
with the organizers' packager. It takes about 1 to 2.4 s of wall clock on an
Apple M2 laptop (measured 2026-11-16) and calls no model.

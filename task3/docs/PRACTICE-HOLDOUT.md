# Practice estimate and holdout overlap

## The split

The 332 public practice cases (110 DQC_US_0015, 120 DQC_US_0117, 102
DQC_US_0126) were split once, before any engine work, by
`tools/make_split.py`: within each rule the case ids are ordered by
sha256("finreason-task3-split-v1:" + id), and the first two thirds form the
build set (DEVSET, 221 cases) and the rest the holdout (HOLDOUT, 111 cases).
The script reads only the practice inputs, never the answers. `split.json`
holds both id lists and the derived subsets. The holdout answers were scored
once, after the engine was frozen; no rule was changed after that.

## Scores (organizers' deterministic judge)

| subset | n | correct | ACC |
| --- | ---: | ---: | ---: |
| all practice | 332 | 187 | 56.33 |
| DEVSET | 221 | 128 | 57.92 |
| HOLDOUT | 111 | 59 | 53.15 |
| HOLDOUT, complete instance document | 47 | 44 | 93.62 |
| DEVSET, complete instance document | 100 | 96 | 96.00 |

The organizers' rule baseline (`baselines/rule_baseline.py --mode full` of the
kit) scores 6.31 on HOLDOUT. Most practice instance documents are cut at
32,768 characters (185 of 332), and in many of those the asked-for fact is no
longer in the text, which caps any method; the ranked development and test
files are not cut.

## Overlap between HOLDOUT and DEVSET

The split is by case id, not by filer, so the two sets share filers, and some
cases repeat. `python3 tools/holdout_overlap.py` computes every count below
from `split.json` and the practice inputs alone. The filer of a case is the
CIK in its instance document's `<identifier>` element; every practice case has
exactly one.

| count | value |
| --- | ---: |
| distinct filers: DEVSET / HOLDOUT / in both / total | 93 / 63 / 43 / 113 |
| HOLDOUT cases whose filer also files a DEVSET case | **88** of 111 (0015: 30, 0117: 38, 0126: 20) |
| HOLDOUT cases whose filer is not in DEVSET | 23 (0015: 7, 0117: 2, 0126: 14); the list `holdout_unseen_filer` in `split.json` |
| HOLDOUT cases whose whole query is byte-identical to a DEVSET case | **22** (0015: 12, 0117: 10, 0126: 0) |
| of those 22: filer shared / complete instance document | 22 / 0 |
| HOLDOUT cases whose question alone matches a DEVSET question | 45 (0015: 13, 0117: 21, 0126: 11) |

An identical query means the same filing excerpt and the same question. It
happens because the practice set keeps one case per rule finding, and a filing
can have several findings for the same concept and period (for example several
negative facts of one element). Across all 332 practice cases there are 21
such groups (58 cases; 17 groups of DQC_US_0015, 4 of DQC_US_0117); in 14 of
them every case has a different expected answer. Of the 22 HOLDOUT cases with
an identical query, 8 also have the same expected answer as a DEVSET case
(exact duplicates; counting them needs the answers, so only `--score` reports
them).

## Does the overlap raise the estimate?

No. `python3 tools/holdout_overlap.py --score <practice predictions>`:

| HOLDOUT subset | n | correct | ACC |
| --- | ---: | ---: | ---: |
| filer also in DEVSET | 88 | 45 | 51.14 |
| filer not in DEVSET | 23 | 14 | 60.87 |
| query identical to a DEVSET case | 22 | 5 | 22.73 |
| query not identical to any DEVSET case | 89 | 54 | 60.67 |
| exact duplicate of a DEVSET case (query and answer) | 8 | 2 | 25.00 |
| all but the exact duplicates | 103 | 57 | 55.34 |
| all | 111 | 59 | 53.15 |

The engine is a fixed set of rules with no fitted parameters, and it does
better on the holdout cases that share nothing with the build set: without the
8 exact duplicates the holdout estimate rises from 53.15 to 55.34. The 22
identical-query cases score lowest because all of them are cut files, and
because the engine gives one answer per query, so in a group with different
expected answers it can match at most one of them.

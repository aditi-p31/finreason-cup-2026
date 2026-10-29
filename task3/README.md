# finreason-task3-engine 0.1

A deterministic rule engine for Task 3 (Financial Audit Verification) of the
FinReason Cup at IEEE BigData 2026.

Each Task 3 case is one filing excerpt (schema, linkbases, instance document,
taxonomy excerpt) and a question about one concept in one period. The answer
is a pair: the value the filing reports, and the value the filing's own
relationships say it should be. The engine re-runs the three public XBRL US
data-quality rules behind the task (DQC_US_0015 negative values, DQC_US_0117
dimensional cross check, DQC_US_0126 calculation check) on the text of the
case, inside each rule's own scope and tolerance, and reports the finding.
It reads only the case's `query` string, which carries the filing excerpt
(instance document and linkbases) as well as the question. It calls no
language model, uses no network and needs only the Python standard library.

It is the Task 3 entry of team "Patodiya Research" (Aditi Patodiya) and
accompanies the team's FinReason Cup working-notes paper.

Released after the test-submission deadline (25 October 2026, 23:59 AoE).
Final test result under the official judge: 96.62%, rank 5 of 23 teams
(<https://the-finai.github.io/IEEE-bigdata-cup/task3/leaderboard/>).

## Reproduce the submitted files: one command

After the inputs are in place (see [Inputs](#inputs)):

```
python3 reproduce.py
```

This rebuilds the final entry, variant **V1**, and checks it:

| file | sha256 |
| --- | --- |
| `reproduced/V1/test/predictions.jsonl` (680 cases, the ranked Test submission of 3 October 2026) | `72c1e909bf3011256bce5a035a1d7afd5946c47e41b87375d6e4afd22f428577` |
| `reproduced/V1/development/predictions.jsonl` (680 cases, the Development upload of 3 October 2026) | `2bebfed560c15cdead1ba707936bd608bcb59554ba41e6d526d3fdb79265aa2f` |

It runs the engine's self-test, checks the published sha256 of both input
files, runs the engine twice per file (the runs must be byte-identical), checks
the strict submission format, runs the organizers' validator, and compares
both outputs with the digests above. It prints `VERDICT: MATCH` and exits 0
only when every check passes, and takes well under a minute. REPRODUCE.md has
the details, the earlier variants (`--variant`, `--all`) and the practice-set
checks.

## Inputs

Not included here (see NOTICE):

- the organizers' Task 3 starter kit: folder `finreason_task3/` of
  <https://github.com/The-FinAI/IEEE-bigdata-cup> (MIT), placed or linked at
  `./kit` (or given with `--kit`);
- the ranked input files `development_inputs.jsonl` and `test_inputs.jsonl`
  from the Hugging Face dataset `YanAdjeNole/FinReason-Task3`, revision
  `f32033b1dc0c1b0ef080740ed5ee02ef6b04c931` (CC BY 4.0), in `kit/data/`;
- for the practice-set checks only: the 332 practice cases from
  `TheFinAI/FinMR` (CC BY 4.0), prepared into `kit/data/` by the kit's
  `scripts/prepare_public_dev.py`.

REPRODUCE.md step 1 gives the commands and the sha256 of each file.

## Requirements

- Python 3.9 or newer (tested with CPython 3.9.6 and 3.11.15) on macOS or
  Linux. The engine and `reproduce.py` use the standard library only.
- The organizers' validator, which `reproduce.py` runs, also uses only the
  standard library. Scoring the practice set with the kit's judge
  (`tools/score_split.py`) needs the kit's own requirements.

## How it works

1. **Parse the case.** Split the query into its sections; read the target
   concept and period from the question, and the contexts, units, facts
   (exact decimals), calculation arcs and dimensional tables from the filing.
2. **Run each rule inside its scope**, as the public rule source (XULE)
   defines it:
   - DQC_US_0126 (`calc`): on financial-statement networks without a table,
     the weighted sum of the target's calculation children against the parent
     fact, with the rule's choice among duplicate facts and its tolerance.
     Answer: (parent fact, sum).
   - DQC_US_0117 (`dim`): on statement tables, monetary facts and the rule's
     eleven axes, the sum of the members of the axis's domain tree against
     the total, with the rule's tolerance and its FASB 606 revenue exception.
     Answer: (total or 0, member sum). The final entry also runs the rule's
     second assertion (10093), a one-member total against its breakdown on a
     second axis, when the case has no other rule finding in scope.
   - DQC_US_0015 (`neg`): a negative value of an element on the rule's
     public list of elements that should not be negative, outside its member
     and axis exclusions. Answer: (negative fact, its magnitude).
3. **Decide by evidence tier.** A rule finding inside that rule's scope comes
   first (tier 1); weaker evidence (a difference outside the rule's networks,
   a difference within tolerance, a negative value no rule reports) is used
   only when there is no tier-1 finding, and the trace marks it. With no
   evidence at all the answer is the filed value and its negation, (E, -E),
   and with no filed value it is ("0", "0"). No practice, development or test
   case reaches the (E, -E) branch (REPRODUCE.md, section 6).

`engine/run.py --trace` writes the mechanism, evidence tier and detail of
every answer.

## Practice estimate

The 332 public practice cases were split once, by a salted hash of the case id
within each rule, into a build set (221) and a holdout (111) that was scored
once, after the engine was frozen. With the organizers' deterministic judge
the engine scores 53.15% on the holdout (the organizers' rule baseline: 6.31%)
and 93.62% on the 47 holdout cases whose instance document is complete; the
practice files are cut at 32,768 characters, so in most of the others the
asked-for fact is missing from the text. The split is by case, not by filer:
88 of the 111 holdout cases share a filer with the build set, and 22 have a
query byte-identical to a build-set case (8 of them also the same expected
answer). Those overlaps do not raise the estimate: the engine scores 60.87% on
the 23 holdout cases with an unseen filer, 22.73% on the 22 identical-query
cases, and 55.34% on the holdout without the 8 exact duplicates. Details:
`docs/PRACTICE-HOLDOUT.md`.

Some practice cases cannot be told apart from their input at all: 17 groups of
byte-identical queries (32 cases under DQC_US_0015, 15 under DQC_US_0117) carry
different gold pairs, so no deterministic system that reads only the query can
match more than 308 of the 332 exactly (92.77%). `tools/query_identifiability.py`
computes this bound; it concerns the practice inputs and exact matching of both
numbers, not the development or test sets.

## Compliance

- At prediction time the engine reads only each case's `query` (the `id` is
  echoed back). It reads no external source of data-quality findings, no
  answer key and no record keyed to a filing, company or case id.
- Its only external input is the public XBRL US DQC rule logic: the rule
  source, read and re-implemented, and the DQC_US_0015 element list in
  `engine/resources/` (see NOTICE for its licence).
- No model call at any stage, no network, no randomness.
- The choice of the final variant used Development-phase feedback: one upload
  per variant, aggregate scores only (REPRODUCE.md, section 4).

## Layout

| path | contents |
| --- | --- |
| `reproduce.py` | the one command: rebuild and check the submitted files |
| `engine/engine.py`, `engine/xbrl.py` | the rules, the decision and the parser |
| `engine/run.py` | command line: `--input`, `--output`, `--trace`, `--variant` (default V1, the final entry) |
| `engine/selftest.py` | 53 synthetic cases built from the rule logic, no data needed |
| `engine/resources/` | the DQC_US_0015 element list and the DQC licence |
| `tools/score_split.py` | practice scoring with the kit's deterministic judge |
| `tools/make_split.py`, `split.json` | the build/holdout split of the practice set |
| `tools/holdout_overlap.py` | holdout overlap counts (and per-subset scores) |
| `tools/query_identifiability.py` | identical practice queries with different gold, and the bound they set |
| `docs/PRACTICE-HOLDOUT.md` | the practice estimate and the overlap counts |
| `REPRODUCE.md` | inputs, the one command, earlier variants, checks |
| `LICENSE`, `NOTICE` | Apache-2.0; third-party attribution and licences |
| `MANIFEST.txt` | sha256 of every file in this package |

`engine/engine.py`, `engine/xbrl.py`, `engine/selftest.py` and the element
list `engine/resources/dqc_0015_non_negative_elements.txt` are byte-identical
to the engine that built the submitted files; this was checked against
their pinned sha256 when the release was cut. `engine/run.py` is that engine's command line with one change,
which the release build applies to the pinned file and checks: with no
`--variant`, `--fix` or `--neg-policy` it runs V1, the final entry, where the
submission-time copy ran V0 (REPRODUCE.md, section 3).
`engine/resources/DQC-LICENSE.md` is added for this release.

## Licence

Copyright 2026 Aditi Patodiya. Licensed under the Apache License, Version 2.0
(LICENSE). The DQC element list in `engine/resources/` and the rule logic the
engine re-implements are also subject to the DQC licence
(`engine/resources/DQC-LICENSE.md`); NOTICE gives the required notice.

## Citation

If you use this package, please cite the working-notes paper:

```
@misc{patodiya2026executable,
  author = {Aditi Patodiya},
  title  = {Executable Financial Reasoning in the {FinReason} Cup: Program Induction and Rule-Based Audit Verification},
  year   = {2026},
  note   = {FinReason Cup 2026 working notes, Tasks 1 and 3, IEEE International Conference on Big Data (BigData 2026)}
}
```

The organizers ask that work on Task 3 cite the FinReason Cup overview, the
Task 3 overview, Herculean and FinAuditing, using their BibTeX and citation
keys (https://the-finai.github.io/IEEE-bigdata-cup/#paper-references). The
overview entries below are the organizers' drafts; refresh them from that page
before use.

```
@unpublished{finreason2026overview,
 author = {Xie, Zhuohan and Wang, Yan and Jiang, Yuechen and Peng, Xueqing and Qian, Lingfei and Cao, Yupeng and Chen, Yankai and Liu, Xue (Steve) and Nakov, Preslav},
 title = {Overview of the {FinReason Cup 2026}: Agentic Financial Reasoning, Hedging, and Audit Verification},
 year = {2026},
 note = {Manuscript in preparation; proposed author list and order},
 url = {https://the-finai.github.io/IEEE-bigdata-cup/}
}

@inproceedings{finreason2026task3overview,
  author = {Wang, Yan and Xie, Zhuohan and Jiang, Yuechen and Qian, Lingfei and Peng, Xueqing and Cao, Yupeng and Chen, Yankai and Liu, Xue (Steve) and Nakov, Preslav},
  title = {Overview of the {FinReason Cup 2026} Task 3:
           Financial Audit Verification},
  booktitle = {2026 IEEE International Conference on Big Data (BigData)},
  year = {2026},
  address = {Phoenix, Arizona, USA},
  note = {Manuscript in preparation; proposed author list and order},
  url = {https://the-finai.github.io/IEEE-bigdata-cup/task3/}
}

@misc{peng2026herculeanagenticbenchmarkfinancial,
  title = {{Herculean}: An Agentic Benchmark for Financial Intelligence},
  author = {Xueqing Peng and
    Zhuohan Xie and
    Yupeng Cao and
    Haohang Li and
    Lingfei Qian and
    Yan Wang and
    Vincent Jim Zhang and
    Huan He and
    Xuguang Ai and
    Linhai Ma and
    Ruoyu Xiang and
    Yueru He and
    Yi Han and
    Shuyao Wang and
    Yuqing Guo and
    Mingyang Jiang and
    Yilun Zhao and
    Youzhong Dong and
    Xiaoyu Wang and
    Yankai Chen and
    Ye Yuan and
    Qiyuan Zhang and
    Fuyuan Lyu and
    Haolun Wu and
    Yonghan Yang and
    Zichen Zhao and
    Yuyang Dai and
    Fan Zhang and
    Rania Elbadry and
    Ayesha Gull and
    Muhammad Usman Safder and
    Nuo Chen and
    Fengbin Zhu and
    Tianshi Cai and
    Zimu Wang and
    Polydoros Giannouris and
    Yuechen Jiang and
    Zhiwei Liu and
    Mohsinul Kabir and
    Yuyan Wang and
    Yixiang Zheng and
    Yangyang Yu and
    Weijin Liu and
    Wenbo Cao and
    Anke Xu and
    Peng Lu and
    Jerry Huang and
    Mingquan Lin and
    Prayag Tiwari and
    Yijia Zhao and
    Víctor Gutiérrez-Basulto and
    Xiao-Yang Liu and
    Kaleb E Smith and
    Jiahuan Pei and
    Arman Cohan and
    Jimin Huang and
    Yuehua Tang and
    Alejandro Lopez-Lira and
    Xi Chen and
    Xue Liu and
    Junichi Tsujii and
    Jian-Yun Nie and
    Sophia Ananiadou},
  year = {2026},
  eprint = {2605.14355},
  archivePrefix = {arXiv},
  primaryClass = {cs.AI},
  url = {https://arxiv.org/abs/2605.14355}
}
```

The Task 3 practice set is FinMR, one of the three tasks of the FinAuditing
benchmark. The organizers' kit asks users of the data to cite the FinAuditing
paper:

```
@inproceedings{10.1145/3805712.3808578,
author = {Wang, Yan and Wang, Keyi and Yang, Shanshan and Patel, Jaisal and Zhao, Jeff and Mo, Fengran and Peng, Xueqing and Qian, Lingfei and Chen, Yankai and Guti{\'e}rrez-Basulto, V{\'i}ctor and Huang, Jimin and Xiong, Guojun and Liu, Xiao-Yang and Nie, Jian-Yun},
title = {FinAuditing: A Financial Taxonomy-Structured Multi-Document Benchmark for Evaluating LLMs},
year = {2026},
isbn = {9798400725999},
publisher = {Association for Computing Machinery},
address = {New York, NY, USA},
url = {https://doi.org/10.1145/3805712.3808578},
doi = {10.1145/3805712.3808578},
booktitle = {Proceedings of the 49th International ACM SIGIR Conference on Research and Development in Information Retrieval},
pages = {3456--3463},
numpages = {8},
keywords = {xbrl auditing, benchmark, large language model, information retrieval, information extraction, question answering},
location = {Australia},
series = {SIGIR '26}
}
```

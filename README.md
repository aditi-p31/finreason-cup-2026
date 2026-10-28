# Executable financial reasoning for the FinReason Cup 2026

Code and artifacts for the Working Notes paper **"Executable Financial Reasoning in the
FinReason Cup: Program Induction and Rule-Based Audit Verification"** by Aditi Patodiya
(team Patodiya Research), FinReason Cup, IEEE BigData 2026 Cup.

Both entries answer every case by executing a program or a rule. Neither calls a language
model at prediction time.

| Folder | Task | What it does | Reproduce |
| --- | --- | --- | --- |
| [`task1/`](task1/) | Task 1, verifiable financial chain reasoning | Identifies each question's template from its number-masked text and runs that template's exact-fraction program. For the 290 public templates the program is found by search over the released solved instances, with some components written from the question's stated recipe or from the public FinChain generator source, and every component reproduces all eleven released instances. For the 116 hidden templates the program was transcribed with AI assistance and reviewed by the author. Answers are serialised to the scorer's contract | `cd task1 && scripts/reproduce_ranked.sh` regenerates the ranked test archive byte for byte |
| [`task3/`](task3/) | Task 3, financial audit verification | Executes selected checks of three XBRL US data-quality rules (DQC_US_0015, DQC_US_0117, DQC_US_0126) on each filing in exact decimal arithmetic | `cd task3 && python3 reproduce.py` regenerates the final development and test files byte for byte |

Each folder is a self-contained package with its own README, REPRODUCE.md, LICENSE,
NOTICE and MANIFEST.txt. Start there: they give the requirements, the setup, the exact
inputs and the expected hashes.

## Results under the organizers' evaluation

- Task 1: 1.000 final-answer and 1.000 reasoning-step score on the 580-case
  [development leaderboard](https://the-finai.github.io/IEEE-bigdata-cup/task1/leaderboard/),
  whose gold is withheld. Official test results will be added here when the organizers
  publish them.
- Task 3: 96.62% accuracy on the 680-case held-out test set under the official judge,
  rank 5 of 23 teams ([results](https://the-finai.github.io/IEEE-bigdata-cup/task3/leaderboard/)).

## Data

The competition data are not included; both packages read them from the organizers'
releases (CC BY 4.0). Task 1 uses a checkout of
[The-FinAI/IEEE-bigdata-cup](https://github.com/The-FinAI/IEEE-bigdata-cup). Task 3 uses the
organizers' starter kit from the same repository together with the Hugging Face dataset
`YanAdjeNole/FinReason-Task3`. The task READMEs pin the exact versions.

## How the hidden-template programs were made

The 116 programs in `task1/hidden/forms/final/` answer the Task 1 templates that no
released instance covers. An AI assistant transcribed each question's stated calculation
into a small deterministic program under the author's direction, and the author reviewed
every program. `task1/HIDDEN-FORMS.md` documents the checks and the one command that
reproduces the ranked archive from them.

## Licence

Code: Apache-2.0 (`LICENSE`; each package carries its own `LICENSE` and `NOTICE`).
`task3/engine/resources/DQC-LICENSE.md` covers the XBRL US data-quality rule material the
Task 3 engine re-implements. Forms written from the public FinChain generator source
(Apache-2.0) are credited in `task1/NOTICE`.

## Citation

Please cite the paper (see `CITATION.cff`), and the FinReason Cup overviews, FinChain,
Herculean and FinAuditing as the organizers request (BibTeX in the task READMEs).

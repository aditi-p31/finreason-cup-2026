# Reproducing the Task 3 files

Every command runs from the package root (the directory holding
`reproduce.py`). Nothing here calls a language model, and after the inputs are
downloaded nothing touches the network.

## 1. Inputs

The organizers' starter kit, at `./kit` (any other place works with
`--kit DIR` or `FINREASON_TASK3_KIT=DIR`):

```
git clone https://github.com/The-FinAI/IEEE-bigdata-cup.git cup
git -C cup checkout 11f8673e3645c4a00fb47f668b71fa1cf270159f
cp -R cup/finreason_task3 kit
```

The two ranked input files, from the Hugging Face dataset
`YanAdjeNole/FinReason-Task3` at its 28 September 2026 revision:

```
REV=f32033b1dc0c1b0ef080740ed5ee02ef6b04c931
for f in development_inputs.jsonl test_inputs.jsonl; do
  curl -L -o "kit/data/$f" "https://huggingface.co/datasets/YanAdjeNole/FinReason-Task3/resolve/$REV/$f"
done
shasum -a 256 kit/data/development_inputs.jsonl kit/data/test_inputs.jsonl
```

Expected:

```
592f66f6b6de3b6cbb4db16422d2fd33c6c2dc80239f090c17a6d42cac666964  kit/data/development_inputs.jsonl
22301f5d087a0ebea90346faa3c12f83d97ce26d77880c32d3baa32078d4db70  kit/data/test_inputs.jsonl
```

Only for the practice-set checks (sections 5 and 7): the 332 practice cases,
built by the kit from `TheFinAI/FinMR` (this step needs the kit's own
requirements, `kit/requirements.txt`):

```
(cd kit && python3 scripts/prepare_public_dev.py)
shasum -a 256 kit/data/public_dev_inputs.jsonl kit/data/public_dev.jsonl
```

Expected:

```
fa3da7e55f66a62a290d630b7b80cdb2a26318f275047b23fe4cb00c707f5cde  kit/data/public_dev_inputs.jsonl
cfdd41aeef2406633ba96f139d63aa5313b0476086ef47f7f5b2feee7a9b79ab  kit/data/public_dev.jsonl
```

## 2. The submitted files: one command

```
python3 reproduce.py
```

This is the authoritative check. It rebuilds the final entry, variant V1, into
`reproduced/V1/` and prints:

```
OK      V1    development 2bebfed560c15cdead1ba707936bd608bcb59554ba41e6d526d3fdb79265aa2f  (680 rows; ...; (E,-E) fallback 0)
OK      V1    test        72c1e909bf3011256bce5a035a1d7afd5946c47e41b87375d6e4afd22f428577  (680 rows; ...; (E,-E) fallback 0)
VERDICT: MATCH (final entry V1: test 72c1e909..., development 2bebfed5...; ...)
```

| file | what it is | sha256 |
| --- | --- | --- |
| `reproduced/V1/test/predictions.jsonl` | the Test file uploaded on 3 October 2026, the ranked Task 3 submission | `72c1e909bf3011256bce5a035a1d7afd5946c47e41b87375d6e4afd22f428577` |
| `reproduced/V1/development/predictions.jsonl` | the Development file uploaded on 3 October 2026 | `2bebfed560c15cdead1ba707936bd608bcb59554ba41e6d526d3fdb79265aa2f` |

What it checks, in order (any failure prints `VERDICT: MISMATCH` and exits 1;
missing inputs or kit exit 2):

1. the engine's self-test (`engine/selftest.py`, 53 synthetic cases) passes;
2. each input file has its published sha256 (section 1);
3. the engine runs twice on each file, and the two outputs are byte-identical;
4. the output has exactly the input ids in input order, UTF-8 without BOM, LF
   line ends, the keys `id`, `extracted_value`, `calculated_value`, and every
   value a finite decimal string with no exponent and no `-0`, readable by
   the judge's own number parser;
5. no case raised inside the engine, and every ranked case got a rule answer
   (no `unresolved` case);
6. the organizers' validator (`kit/scripts/validate_submission.py`) prints
   `RESULT: VALID`;
7. the sha256 equals the value above.

`reproduced/reproduce_report.json` records every digest, the mechanism and
evidence-tier counts, and the validator's verdict. Options: `--out DIR`,
`--kit DIR`, `--data-dir DIR`, `--no-validator` (skips step 6 only),
`--practice` (section 5), `--variant NAME` and `--all` (section 4), `--list`.

## 3. Using the engine directly

```
python3 engine/run.py --input kit/data/test_inputs.jsonl \
    --output my_predictions.jsonl --trace my_trace.jsonl
```

With no `--variant`, `--fix` or `--neg-policy`, `engine/run.py` runs V1, the
final entry, so this command writes the submitted test file
(`72c1e909...`); `--variant V1` gives the same bytes. Every earlier variant
runs only when it is named, for example `--variant V0` for the engine of the
first Development upload (section 4).

This default is the release's one change to the engine that built the
submitted files. In the working tree that built them, the command line ran
V0 when no switch was given, so a command without `--variant` in the
development history corresponds to `--variant V0` here. The release build
applied the change to the pinned submission-time `engine/run.py` (sha256
`6922268736f098bb39bddb4b96bfc9ad33ff7874d27e29a1566698b1dda1fd63`) and
checked every other engine file against its pin when the release was cut.

## 4. Earlier variants (historical)

The engine carries every variant behind a switch, so each one stays
reproducible. Only V1 is the final entry; the others are history and are
built only when named:

```
python3 reproduce.py --variant V0       # one variant (repeatable)
python3 reproduce.py --all              # all ten
python3 reproduce.py --list             # names, engine switches, status
```

| variant | engine switches | change against V0 | status | development sha256 | test sha256 |
| --- | --- | --- | --- | --- | --- |
| **V1** | no switch, or `--variant V1` (`--fix a10093`) | DQC_US_0117 assertion 10093 when no other rule finding is in scope | **final**: Test and Development, 3 Oct 2026 | `2bebfed5...9265aa2f` | `72c1e909...2f428577` |
| V0 | `--variant V0` | the engine as first frozen | Development, 2 Oct 2026; its Test file was replaced by V1 | `575b6067...72f9c5c3` | `af0e1288...685f6c78` |
| V1M1 | `--fix a10093 --neg-policy none,last` | V1, and among several qualifying negative facts the last in document order | Development probe, 2 Oct 2026, not adopted | `7e531d6e...caf47056` | `e03ce44b...c04b7137` |
| V1M2 | `--fix a10093 --neg-policy none,maxabs` | V1, and the largest negative fact | Development probe, 2 Oct 2026, not adopted | `b15419d1...d82e2f69` | `59d8c635...ffc56dbe` |
| V2 | `--variant V2` | V1, and assertion 9574 needs a reported total | built, not uploaded | `1d3a2009...65540564` | `72c1e909...2f428577` (= V1) |
| M1, M2, M3 | `--variant M1` / `M2` / `M3` | V0 with the last / largest / smallest negative fact | built, not uploaded | in `reproduce.py` | in `reproduce.py` |
| V2M1, V2M2 | `--fix a10093 --fix total_required --neg-policy none,last` / `none,maxabs` | V2 with the last / largest negative fact | built, not uploaded | in `reproduce.py` | in `reproduce.py` |

`reproduce.py` holds the full sha256 of every file in this table. How V1 was
chosen: the switches come from the public rule source (V1, V2) or are
measurement probes of a choice the rule leaves open (M1 to M3: which of
several qualifying negative facts a DQC_US_0015 case keeps). Development
uploads gave one aggregate score per uploaded file. Under the organizers'
deterministic judge V0 scored 660 of 680, both probes scored fewer (659 and
658), and V1 scored 661; V1 was therefore kept, the probes were not, and the
V1 test file was uploaded as the final entry.

## 5. Practice set

```
python3 reproduce.py --practice
```

adds the 332 practice cases. V1 gives
`3582b7ff96cba3b5109af09774e35270195138409bce09f64db2b01f09675193` (the same
file as V0 and V2: the 10093 switch changes no practice answer). In practice,
133 cases end as ("0", "0") (mechanism `unresolved`): in 127 of them the
practice instance document is cut at 32,768 characters and the asked-for fact
is gone, and the other 6 have a complete instance that gives the engine no
finding and no non-dimensional value of the target for that period. The
ranked files are not cut, and no ranked case ends that way.

Scoring with the organizers' deterministic judge (needs the kit's
requirements):

```
python3 tools/score_split.py --predictions reproduced/V1/practice_predictions.jsonl --subset all
python3 tools/score_split.py --predictions reproduced/V1/practice_predictions.jsonl --subset holdout
```

`--subset` takes `all`, `devset`, `holdout`, `holdout_unseen_filer`,
`devset_untruncated` or `holdout_untruncated` (lists in `split.json`).
Expected ACC: all 56.33, devset 57.92, holdout 53.15, holdout_unseen_filer
60.87, holdout_untruncated 93.62, devset_untruncated 96.00.
`docs/PRACTICE-HOLDOUT.md` explains the split and its overlap.

## 6. The (E, -E) fallback branch

`engine.predict` answers in a fixed order: a rule finding inside the rule's
scope (tier 1); a relational difference beyond tolerance outside the rule's
networks (tier 2); a relational difference within tolerance (tier 3); a
negative value of an element not on the DQC_US_0015 list (tier 4) or inside
one of its exclusions (tier 5). Only when none of these exists does it reach
the last two lines of `engine/engine.py`:

- if the filing reports no non-dimensional value E of the target concept for
  the target period, the answer is ("0", "0"), mechanism `unresolved`;
- otherwise the answer is (E, -E), mechanism `fallback`, tier 6.

The (E, -E) branch is a last resort with no rule behind it: it is used only
when the filing shows the target value but no rule evidence of any tier. It
is never reached on the inputs of this task. For every one of the ten
variants, the trace of every practice (332), development (680) and test (680)
case has mechanism `calc`, `dim` or `neg`, plus `unresolved` for the 133
practice cases of section 5; `fallback` occurs 0 times. `reproduce.py` prints and
records this count for every file it builds (`fallback_E_minus_E_cases` in
`reproduce_report.json`), so `python3 reproduce.py --all --practice` checks
the claim.

## 7. Holdout overlap

```
python3 tools/holdout_overlap.py
python3 tools/holdout_overlap.py --score reproduced/V1/practice_predictions.jsonl
```

The first command reads only the practice inputs and `split.json` (no
answers) and prints the counts in `docs/PRACTICE-HOLDOUT.md`; the second adds
the deterministic judge on each subset.

## 8. Self-test and determinism

`python3 engine/selftest.py` runs 53 synthetic cases built from the rule logic
(no data needed): rule scopes, both tolerance functions, the DQC_US_0015
exclusions, duplicate facts, nested members, the FASB 606 exception, the
evidence tiers, every variant switch, and the 29 original cases rerun under
V1 and V2. The engine has no randomness: the same input gives the same bytes
on every run, which step 3 of `reproduce.py` checks each time.

## 9. Not in this package

The development history (build log, variant analysis, submission log, the
engine report written before the first upload, and the analysis scripts under
`dev/`, `verify/` and `verify2/` of the working tree) is not included. It is
available from the author on request. The prediction files themselves are not
included either: `reproduce.py` regenerates them and checks their sha256.

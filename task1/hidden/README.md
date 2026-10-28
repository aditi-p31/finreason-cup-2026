# Hidden-stratum transcription workspace

> **Release note (added 2026-10-03).** This is the working brief the forms
> were transcribed under, shipped as it was used. For the release only this
> note and a dated remark in rule 3 were added; pointers to working notes that
> do not ship were removed, and the introduction's sentence on whether the
> forms would be used was cut. The status sections are dated; section 10 is the current state:
> the ranked Task 1 entry is the archive accepted on 2026-10-21. The readers
> the brief addresses were AI assistants working under the author's review
> (`../HIDDEN-FORMS.md`, "How the forms were written"). Several paths named
> below were working files and are not in this release: `templates.json`
> (the organisers' test questions verbatim), `forms/<reader>/`,
> `forms/pilot/`, the `forms/final/*.pre-*` copies, `runs/`,
> `verify_pilot_port.py`, `../accepted_20260914/`, `../accepted_20261002/`,
> `../artifacts_hidden_v1/`, `../artifacts_hidden_probe/`,
> `../scripts/hidden_probe/` and the `analysis/` notes; of
> `../accepted_20261021/` only `test_predictions.jsonl` ships. The release
> has `forms/final/` (the 116 forms), `hlib.py`, `run_forms.py`, `compare.py`,
> `build_templates.py`, `build_candidate.py` and `export_forms.py`; the
> scripts that read `templates.json` or the accepted archives are here for
> reference.

This directory holds the tooling for transcribing the **hidden stratum** of the
FinReason Task 1 test split: the 348 test cases (116 templates x 3 draws) that
no published template matches. Each hidden question states its own computation
in prose. A reader turns that stated recipe into a small deterministic Python
**form**. The form runs on all three draws, and the results go into a candidate
archive built on top of the accepted one.

This is **preparation only**. Nothing here uploads, submits, emails or posts
anything. The candidate archive is for review.

The 2026-09-16 pilot was kept in `../scripts/hidden_probe/` and
`../artifacts_hidden_probe/`, which do not ship.

---

## 1. Binding rules for every reader

1. **Zero LLM API spend.** You are the transcriber. A form is plain
   deterministic Python with exact `Fraction` arithmetic. It makes no model
   call, no network call and reads no file.
2. **Never upload, submit, email or post anything.**
3. **Never write into** `../artifacts/` or `../accepted_20260914/`. The
   accepted, currently ranked archive lives there (as of 2026-09-27; the
   ranked archive is now the 2026-10-21 one, section 10). The sha256 of
   `accepted_20260914/test_submission.zip` must stay
   `42111f7f1d139b86904036bcfc43ef3ed1be2f5b0281ab4e761bcd101bdea221`.
   Do not modify anything under `../src/`. You may import from it.
   Write only inside `hidden/` and `../artifacts_hidden_v1/`.
4. **Source of truth.** For a hidden question, the only source of truth is its
   own text plus its `answer_spec` / `trace_spec`, as they appear in
   `templates.json`, which is copied verbatim from
   `IEEE-bigdata-cup/public/task1/data/test/test_questions.jsonl`. The test
   split has no gold. **Never** search the web, the organisers' repo history
   or any other source for answers. The cup's terms call an entry built on an
   answer read from an external record invalid.
   **Do not look at the shipped fallback predictions for hidden cases**
   (`accepted_20260914/test_predictions.jsonl`, `artifacts/test_predictions.jsonl`,
   or the `shipped_guess` fields in `artifacts_hidden_probe/q4_*`).
5. **Exact arithmetic.** Parse numbers with `parse_number`. Every hlib
   extractor already does this, and it handles `3209/67` and `1,234.5`.
   Compute in `Fraction` and never use floats. Round nothing yourself:
   `run_forms` rounds the final value and the slots exactly as the shipped
   solver does, following each spec (the questions say "exact arithmetic
   through all intermediate steps, round only the final value").
6. **Units exactly as stated.** Percent and ratio are different units: when
   the question says "report as a percentage", multiply the ratio by 100. USD
   and USD millions are different too: if the text already gives amounts in
   USD millions and asks for USD millions, do not rescale. The `unit` in the
   spec is the unit of the value you return.
7. **Enums.** Return exactly one of `allowed_values`, spelled exactly the same.
   Apply every stated tie rule, precedence rule and "otherwise" arm. Apply each
   inclusive or exclusive comparison exactly as worded:

   | wording | comparison |
   | --- | --- |
   | at least, reaches, meets, no less than, not below | `>=` |
   | at most, does not exceed, no more than, within, not above | `<=` |
   | exceeds, more than, above, strictly greater | `>` |
   | below, less than, under, strictly less | `<` |
   | "including exact equality" | inclusive |

   If a phrase is not in this table, decide from the sentence itself and put
   the reason in the form's docstring.
8. **Independence.** Transcribe from the question alone. Do not open another
   reader's forms for a template before your own form for it is finished and
   run. Disagreements are settled by `compare.py` plus adjudication.
9. **No hard-coding.** A form must compute from the body text it receives.
   It must never branch on a case id, never embed an answer, never read
   files, and never pick among candidate formulas by what the three draws
   produce. The three draws exist to check that the extraction reads all of
   them, not to select a formula.
10. Run anything that could hang through a Python subprocess with a timeout
    (`run_forms` already applies a per-case time limit).

---

## 2. Files

| path | what it is |
| --- | --- |
| `templates.json` | the 116 templates: key, case ids, type, answer_spec, slots, the three full question texts and bodies, batch, pilot origin |
| `build_templates.py` | regenerates `templates.json` from the organisers' test file (read only) |
| `hlib.py` | extraction, arithmetic and enum helpers that forms import |
| `forms/<reader>/HNNN.py` | one form per template per reader |
| `forms/pilot/` | the 21 pilot transcriptions, ported to this format |
| `forms/final/` | adjudicated forms that go into the candidate (empty until adjudication) |
| `run_forms.py` | runs forms on all three draws and writes a run file |
| `compare.py` | compares two run files template by template |
| `verify_pilot_port.py` | checks that the ported pilot forms reproduce the pilot's recorded finals |
| `build_candidate.py` | builds `../artifacts_hidden_v1/` from `forms/final/` and runs the organisers' validate and package |
| `runs/` | run files and comparison files |

### How templates were formed

The rule is the pilot's `bshape`: mask numbers with `numbers.mask_numbers`,
replace the literal words `true`/`false` with `<B>`, and collapse whitespace.
Result: exactly **116 templates x 3 cases = 348**, of which 28 are enum
templates (84 cases) and 88 are decimal templates (264 cases), with 456
trace slots in total. All slots are decimal and half-up. Keys `H001` to
`H116` follow the sorted order of each template's first case id. The three
cases of every template share an identical `answer_spec` and `trace_spec`.

### Batches

There are 15 batches of 7 or 8 templates. The enum templates are dealt
round-robin, so 13 batches carry 2 enum templates and 2 carry 1. See
`templates.json["batches"]`, or run with `--keys batch:N`.

---

## 3. The form format

A form is one file, `forms/<reader>/HNNN.py`:

```python
"""HNNN (type, unit): one-line title.

The reading: the recipe as the question states it, in your own words, plus
every comparison direction and tie rule, and why each slot is what its
description asks for.  If a slot is left out, say why.
"""
from hlib import num, pct, flag, ipow, pick_two, first_true, F

KEY = "HNNN"           # must equal the file name


def solve(b):          # b = the question body (the text before "Answer format:")
    ...
    return {
        "final": <Fraction | int>  or  <str label from allowed_values>,
        "slots": {"<slot_id>": <Fraction | int>, ...},   # optional, any subset
        "info":  {"name": value, ...},                    # optional diagnostics
    }
```

* `final` is required. For a decimal template return the **exact** value as a
  `Fraction` or an `int`, unrounded. For an enum template return the label
  string.
* `slots` maps a `slot_id` from the template to its exact value. Fill a slot
  only when the question text determines it with certainty. A slot left out
  keeps the fallback value in the candidate and is reported as unfilled.
  Unknown slot ids are errors.
* `info` is free-form diagnostics, such as a margin to a stated threshold or
  both candidate values of a two-option rule. It is recorded in the run file
  and never scored. Use it for boundary corroboration: when a computed
  quantity lands very close to the threshold the question states, that
  supports the reading.
* The form receives **only the body text**. It gets no case id and no spec.

Serialisation belongs to `run_forms.py`, not the form. It uses
`numbers.render_for_spec`, the same `fraction_to_decimal` half-up /
`render_exact` branch as `derive.evaluate_solver`, and screens the result with
the shipped `predict._legal_value`. So a form never rounds, and never formats
a number as a string.

### Lint (enforced before a form runs)

`run_forms` parses the form, and a form that fails any of these checks is
**not executed**:

* no float literals (`0.5` is an error; write `F("0.5")` or `Fraction(1, 2)`)
* no `float()`, `open()`, `eval()`, `exec()`, `compile()`, `__import__()` or `input()`
* no imports of `os`, `sys`, `subprocess`, `socket`, `urllib`, `http`,
  `requests`, `anthropic`, `openai`, `json`, `pathlib`, `io`, `random`,
  `time` and similar modules (see `FORBIDDEN_MODULES`)
* no `math.*` except exact integer helpers (`floor`, `ceil`, `isqrt`, `gcd`, ...)
* no string containing a case id
* a top-level `def solve(b)` must exist

It also **warns** on `**` with a non-literal exponent. `Fraction ** Fraction`
silently returns a float when the exponent is not an integer, so use
`ipow(base, n)`, which fails loudly instead.

---

## 4. hlib API

All extractors take the body `b` and a **literal template**. Outside the
holes, text matches literally: regex metacharacters are escaped for you, and
any whitespace run matches any whitespace run. Holes:

| hole | captures | returned as |
| --- | --- | --- |
| `{N}` | one number (`-3`, `0.25`, `1,234.5`, `3209/67`) | `Fraction` via `parse_number` |
| `{B}` | literal `true` / `false` | `bool` |
| `{W}` | one word token | `str` |

Every extractor requires the template to match **exactly once**. Zero matches,
or more than one, raises `ExtractionError`, which `run_forms` records as a
failed case. When the text genuinely repeats a phrase, make the template
longer (preferred) or pass `nth=k` (0-based).

| function | returns |
| --- | --- |
| `num(b, "clean price {N}, settlement cost {N}")` | `Fraction`, or a tuple when there are several `{N}` |
| `num_re(b, r"raw regex with " + NUM)` | same, for a raw regex (use `NUM` for each group) |
| `pct(b, "a rate of {N}%")` | captured number / 100 |
| `flag(b, "suspicious activity {B}")` | `bool` |
| `word(b, "label {W}")` | `str` |
| `has(b, "literal phrase")` | `bool` |
| `numbers_in(b)` | every number in order (last resort only) |
| `F(x)` | exact `Fraction` from an int, a str (`"0.1"`, `"3/7"`) or a Fraction; floats rejected |
| `ipow(base, n)` | exact power; `n` must be integral (negative allowed) |
| `clamp(x, lo, hi)`, `pos(x)` (= `max(x, 0)`) | `Fraction` |
| `floor_int(x)`, `ceil_int(x)`, `as_int(x)` | `int` (`as_int` raises unless x is integral) |
| `pct_to_ratio(p)`, `ratio_to_pct(r)` | / 100, x 100 |
| `sqrt`, `nth_root`, `ln`, `exp`, `bisect(f, lo, hi)` | Fraction to about 100 significant digits (exact roots come back exact). **Flagged** `non_rational:<op>`. Use only when the stated recipe needs a root, log, exponential or an equation with no closed form |
| `first_true([(cond, label), ...], otherwise=label)` | first label whose condition holds: a stated decision list, in stated precedence order |
| `pick_two(ok_a, ok_b, score_a, score_b, a=, b=, neither=, better="higher"/"lower", tie=)` | the recurring rule "choose the qualifying option with the better metric, X on a tie, the sole qualifier, else neither". `tie` is required and must be read off the question |
| `require_label(label, allowed)` | guard |

`min`, `max`, `abs`, `+ - * /` and the comparisons work on `Fraction` directly
and stay exact.

---

## 5. Workflow

```bash
cd task1   # the package root

# 1. read your batch (texts, specs and slots are all in templates.json)
.venv/bin/python -c "import json;d=json.load(open('hidden/templates.json'));print(d['batches']['3'])"

# 2. write hidden/forms/<you>/HNNN.py for each key, then run them
.venv/bin/python hidden/run_forms.py --reader r1 --keys batch:3 --out hidden/runs/r1_b3.json
.venv/bin/python hidden/run_forms.py --reader r1 --keys H005,H018 --out hidden/runs/r1_some.json
.venv/bin/python hidden/run_forms.py --reader r1 --keys all --out hidden/runs/r1_all.json

# 3. a second reader does the same batch independently, then compare
.venv/bin/python hidden/compare.py hidden/runs/r1_b3.json hidden/runs/r2_b3.json --out hidden/runs/cmp_b3.json

# 4. adjudicate every DISAGREE from the question text, then copy the agreed form
#    into hidden/forms/final/HNNN.py

# 5. build the candidate (organisers' validate + package run inside)
.venv/bin/python hidden/build_candidate.py                       # forms/final -> artifacts_hidden_v1/
.venv/bin/python hidden/build_candidate.py --exclude H003,H017   # leave some on the fallback
```

### What a run file records

For each template it records `status` (`OK` means the form loaded, passed
lint, and produced a legal final on all three draws with no error), `slots_unfilled`,
`flags`, `lint_errors`, `lint_warnings`, and, for each case, the `final`
string, every `slots` string (`null` = unfilled), `errors`, `flags` and `info`.

Plausibility flags are prompts to re-read, not errors:

* `negative_where_nonneg_implied(...)`: negative, where the unit or wording
  (probability, factor, price, cost, shares, minimum, required, ...) suggests a
  non-negative quantity. A signed quantity can legitimately be negative.
* `percent_magnitude_over_1000`, `ratio_magnitude_over_100` (and `multiple_...`,
  `dimensionless_...`)
* `probability_outside_0_1`, `exact_zero`, `non_rational:<op>`
* `enum_constant_across_draws`: the same label on all three draws. The pilot
  found the label varies in every template it checked, so a constant label is
  worth a second look.

### compare.py

A template is **AGREE** only when both runs have it, every final is identical
and non-null on all three cases, and every slot string is identical (a slot
that both runs left unfilled counts as identical and is listed). Otherwise it
is **DISAGREE**, listing every differing value, or **MISSING_A** /
**MISSING_B**.

### build_candidate.py

* The base is `accepted_20260914/test_predictions.jsonl`, read only.
* A hidden case is replaced only when its template has a form in
  `--forms-dir`, is not in `--exclude`, and runs with status `OK` on all three
  draws. A failing form is listed under `rejected_keys` and stays on the fallback.
* In a replaced record, the final comes from the form. Each slot comes from
  the form when the form filled it, and otherwise keeps the base value. The
  record is re-serialised the way `predict.write_predictions` writes it.
  Every other record is copied byte for byte.
* The organisers' own `task1_cli.py validate` and `package` then run, with the
  same CLI and arguments as `finreason_solver.official` and a timeout.
* It asserts that the 580 seen records are byte-identical to the base, that
  every untouched hidden record is byte-identical, and that the accepted zip
  still has its sha256.
* It writes `test_predictions.jsonl`, `test_submission.zip` and
  `build_report.json` into `--out`. It refuses any `--out` outside `hidden/`
  and `artifacts_hidden_v1/`.

---

## 6. Worked example: H009

The question body of the first draw (`t1_2qo73ablqa6d5jdwyi3ps`), from
`templates.json`:

> A transfer of 153 USD may use Network A or Network B. Compute both candidate
> route receipts before applying the routing rule. Network A deducts fee ratio
> 8999/30000 and then fixed fee 6 USD. Network B deducts fee ratio 0.4, then
> fixed fee 9 USD, and finally increases the post-fee amount by bonus ratio 0.4.
> Using unrounded intermediate amounts, use Network A if its net receipt is at
> least 94 USD, including exact equality; otherwise use Network B. What net
> receipt is selected? Carry all arithmetic exactly and round only the selected
> receipt half up to two decimal places in USD.

The spec is `answer_spec = {type: decimal, unit: usd, rounding: half_up 2}`,
with one slot, `network_b_after_ratio_fee_checkpoint`: "Report Network B's
receipt after its proportional fee and before its fixed fee and bonus."
(half_up 2, usd).

The reading:

* Network A receipt = amount x (1 - fee_A) - fixed_A.
* Network B receipt = (amount x (1 - fee_B) - fixed_B) x (1 + bonus). The bonus
  applies to the post-fee amount, after both fees.
* Choose A when receipt_A >= threshold. "At least ... including exact
  equality" makes this inclusive. Otherwise choose B.
* The slot is amount x (1 - fee_B): after the proportional fee, before the
  fixed fee and the bonus.
* The unit is USD throughout, and there is no percent conversion.

The form (`forms/pilot/H009.py`; the file's docstring also names its pilot origin):

```python
"""H009 (decimal, usd): routed network receipt.

A = amount * (1 - fee_A) - fixed_A; B = (amount * (1 - fee_B) - fixed_B) * (1 + bonus).
Use A if A >= threshold (inclusive, "including exact equality"), else B.
Slot: Network B after its proportional fee = amount * (1 - fee_B).
"""
from hlib import num

KEY = "H009"


def solve(b):
    amt = num(b, "A transfer of {N} USD")
    fa, ka = num(b, "Network A deducts fee ratio {N} and then fixed fee {N} USD")
    fb, kb = num(b, "Network B deducts fee ratio {N}, then fixed fee {N} USD, and finally")
    bon = num(b, "bonus ratio {N}")
    thr = num(b, "net receipt is at least {N} USD")
    ra = amt * (1 - fa) - ka
    rb = (amt * (1 - fb) - kb) * (1 + bon)
    return {"final": ra if ra >= thr else rb,
            "slots": {"network_b_after_ratio_fee_checkpoint": amt * (1 - fb)},
            "info": {"receipt_a": ra, "receipt_b": rb, "threshold": thr}}
```

Notes on the choices:

* `"then fixed fee {N} USD"` alone would match twice, once for A and once for
  B. It would raise `ExtractionError` (2 matches), so each template carries its
  own network's lead-in.
* `8999/30000` parses exactly as a rational, and so does `0.4`
  (`Fraction(2, 5)`).
* The form returns the exact `Fraction`. `run_forms` renders `101.1051` as
  `"101.11"` under half_up 2.

Run it:

```bash
.venv/bin/python hidden/run_forms.py --reader pilot --keys H009 --out hidden/runs/example.json
# H009 OK   finals=['101.11', '99.60', '122.26'] unfilled=[] flags=[]
```

In the run file, draw 2 records `receipt_a = 99.6` against `threshold = 99`,
a margin of 0.6%. These generators often place draws near a stated boundary.
Here `>=` and `>` give the same answer. A draw that lands exactly on the
threshold is where the inclusive or exclusive reading decides the label, so
look through `info` for exact ties.

---

## 7. Status on 2026-09-27

* `templates.json`: 116 templates, 348 cases, 28 enum, 88 decimal, 456 slots, 15 batches.
* `forms/pilot/`: the 21 pilot templates, ported. They reproduce the pilot's
  63 recorded finals exactly (`runs/pilot_port_check.json`). 20 of the 21
  also fill their slots from the question text. The pilot `H031` leaves
  `stressed_ratio_checkpoint` unfilled and reads "reduce the base appetite by
  the downturn haircut" as subtraction. That reading was overruled in
  adjudication: `forms/final/H031.py` applied the haircut proportionally and
  filled the slot. Section 9: the author's review on 2026-10-02 switched it to
  subtraction (the earlier form is kept as `forms/final/H031.py.pre-subtraction`).
* `forms/final/`: 116 adjudicated forms (the initial empty-dir build is kept in
  `../artifacts_hidden_v1/baseline_empty/`, byte-identical to the accepted archive).
* Candidate built from `forms/final/` with `--exclude H091`: 115 templates, 345
  hidden cases replaced, 449 of 456 slots from forms (H091's 6 and one H082
  slot stay on the fallback), organisers' validate and package PASS. The
  sha256 is in `../artifacts_hidden_v1/build_report.json`. The first build
  (which also excluded H017 and H031) is kept in
  `../artifacts_hidden_v1/superseded_build1_excl_H017_H031_H091/`.
  NOT for upload at that time.

## 8. Status on 2026-10-02

* The archive built from `forms/final/` (116 of 116 templates, 348 hidden
  cases, 456 of 456 slots) was accepted as the test submission on
  2026-10-02 (sha256 `cce2d3dd...`; `../accepted_20261002/`).
* The forms are part of the solver pipeline as an optional route:
  `src/finreason_solver/hiddenforms/` holds byte-for-byte copies of
  `forms/final/HNNN.py` and `hlib.py`, refreshed by `export_forms.py`, and
  `python -m finreason_solver --hidden-forms package --split test` reproduces
  the accepted predictions and archive byte for byte. The route is off by
  default, and the default release does not include it.

## 9. Status on 2026-10-03

* The ranked test submission is the archive accepted on 2026-10-03 (sha256
  `3e7779ac...`, predictions `27db4171...`; `../accepted_20261003/`). It
  differs from the 2026-10-02 archive in the three H031 records only: after
  reviewing the forms, the author read "reduce the base appetite by the
  downturn haircut" as subtraction, a - h (see the `H031.py` docstring).
  H082's docstring was also rewritten after that review (code, finals and
  slots unchanged; old text in `forms/final/H082.py.pre-doc-fix`).
* `forms/final/H031.py` had its docstring reworded on 2026-10-03 so that it
  names no person (previous bytes in `forms/final/H031.py.pre-name-scrub`).
  Only the docstring changed: the code tokens are identical, the package copy
  and its pin in `routes.json` were refreshed by `export_forms.py`, and the
  route-on test predictions and archive are byte-identical before and after.
* `../scripts/reproduce_ranked.sh` rebuilds the ranked archive and checks its
  sha256 (see `../HIDDEN-FORMS.md`).

## 10. Status on 2026-10-21

* The ranked test submission is now the archive accepted on 2026-10-21
  (zip sha256 `b786d1e5...`,
  predictions `3f0bec6f...`; `../accepted_20261021/`). It supersedes the
  2026-10-03 archive (section 9) in six records.
* Why: a blind re-solve of all 116 templates by AI models that saw only the
  question texts agreed with the 2026-10-03 predictions on 795 of 804
  values; the disagreements sat in H031, H058, H082 and H091. A blind
  panel of three AI model referees then chose the re-solve's reading 3-0 on H031, H058
  and H091 and 2-1 on H082. The author switched H031 (proportional haircut,
  the reviewed `H031.py.pre-subtraction` code restored) and the H091 slot
  (R - d), and kept H058 and H082.

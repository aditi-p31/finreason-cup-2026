# Recorded prompts of the hidden-template workflows

This file holds the prompt texts that produced, audited and later re-checked the
116 hidden-stratum forms in `forms/final/`. They are the **original recorded
prompts**, not reconstructions: each block below is copied from the `script`
field of the local workflow record of that run, the workflow script the
orchestrator executed. Nothing in the blocks is paraphrased. The only changes
are the redactions listed at the end, which replace local absolute paths with
placeholders. Model transcripts and agent outputs are not included.

How to read the blocks:

* Each workflow script is JavaScript. A prompt is a template literal passed to
  `agent(...)`; `${...}` interpolations (keys, paths, earlier results) are kept
  exactly as recorded and were filled in at run time.
* The blocks of one workflow are consecutive slices of its script. Joined in
  order they give the whole recorded script (after redaction; blank lines at
  the cut points are dropped), so the output
  schemas and the control flow that decide which agent sees what are included
  too. The section headings are added here; they are not part of the scripts.
* `RULES` is prepended to every agent prompt of its workflow. In the main
  build, `TEMPLATE_API` is also prepended to the reader, adjudicator and
  finalize prompts.
* Models: each record stores a workflow default model and, per agent, the
  model the agent ran on. A script option `model: 'opus'` resolved to
  `claude-opus-5-5` (Claude Opus 5.5) and `model: 'sonnet'` to
  `claude-sonnet-5` (Claude Sonnet 5), as the recorded agent models show.
* Sampling settings: the scripts set none (no temperature, top-p, top-k,
  maximum output length, effort or thinking setting), and none were recorded.

The readers' working brief that these prompts point to (`${HID}/README.md`) is
`README.md` in this folder. Run statistics and outcomes are in
`BUILD-RECORD.md`.

| # | workflow | started (UTC) | agents |
| --- | --- | --- | ---: |
| 1 | `finreason-hidden-transcription` | 2026-09-28 03:17 UTC | 56 |
| 2 | `finreason-flagged-audit` | 2026-09-28 04:22 UTC | 3 |
| 3 | `finreason-task1-audit48-h031` | 2026-10-02 15:17 UTC | 8 |
| 4 | `finreason-hidden-resolve` | 2026-10-19 04:58 UTC | 29 |
| 5 | `finreason-hidden-adjudicate` | 2026-10-19 05:20 UTC | 12 |

## 1. Main transcription build

* Workflow name: `finreason-hidden-transcription` (local run `wf_485a8d7d-2a8`, status completed).
* Date: started 2026-09-28 03:17 UTC, ended 2026-09-28 04:21 UTC.
* Purpose: Two independent readers transcribe the stated recipe of each of the 116 hidden templates into a form, an adjudicator per batch settles every template (agreed ones included), a build agent assembles and validates a candidate archive with the organizers' tools, eight auditors re-derive a sample of 61 templates blind, and a finalize agent applies the audit and writes the record. Nothing was uploaded by the workflow.
* Models as recorded:
  * Workflow default model: `claude-opus-5-5` (Claude Opus 5.5).
  * Reader B calls carry the per-agent option `model: 'sonnet'`; all 15 reader B agents are recorded as `claude-sonnet-5` (Claude Sonnet 5).
  * Every other agent (infra, reader A, adjudicators, build, auditors, finalize) has no per-agent model option and is recorded as `claude-opus-5-5`.
  * Agents by script label: infra 1 (`claude-opus-5-5`); readerA 15 (`claude-opus-5-5`); readerB 15 (`claude-sonnet-5`); adjudicate 15 (`claude-opus-5-5`); build 1 (`claude-opus-5-5`); audit 8 (`claude-opus-5-5`); finalize 1 (`claude-opus-5-5`).
* Sampling settings: none set by the script, none recorded.

### Workflow metadata and local paths

~~~js
export const meta = {
  name: 'finreason-hidden-transcription',
  description: 'Transcribe the stated recipe of every hidden FinReason test template with two independent readers, adjudicate disagreements, build and validate a candidate archive (no upload), then audit a sample',
  phases: [
    { title: 'Infra', detail: 'template list, harness, validator-backed candidate builder; port pilot' },
    { title: 'Transcribe', detail: 'per batch: reader A and reader B independently, then adjudicate' },
    { title: 'Build', detail: 'assemble candidate, organizers validate + package, 580 seen records byte-identical' },
    { title: 'Audit', detail: 'third blind reading of a deterministic sample' },
    { title: 'Finalize', detail: 'apply audit outcomes, rebuild, report' },
  ],
}

const SOL = '<LOCAL>/finreason/solution'
const HID = `${SOL}/hidden`
const OUTD = `${SOL}/artifacts_hidden_v1`
const QFILE = '<CUP_REPO>/public/task1/data/test/test_questions.jsonl'
~~~

### Shared RULES (prepended to every agent prompt in this workflow)

~~~js
const RULES = `
BINDING RULES (every agent):
- ZERO LLM API spend. You are the transcriber; the solver you write must be plain deterministic Python with exact Fraction arithmetic, no model calls, no network.
- NEVER upload, submit, email or post anything.
- NEVER write into ${SOL}/artifacts/ or ${SOL}/accepted_20260914/ (the accepted, currently ranked archive lives there; sha256 of accepted_20260914/test_submission.zip must stay 42111f7f1d139b86904036bcfc43ef3ed1be2f5b0281ab4e761bcd101bdea221). Do not modify any existing file under ${SOL}/src/ (import from it only). Write only inside ${HID}/ and ${OUTD}/.
- Source of truth for a hidden question is ONLY its own text and its answer_spec / trace_spec in ${QFILE}. There is no gold for the test split. Never search the web, the organizers' repo history, or any other source for answers; reading an answer from an external record is exactly what the cup's terms call an invalid entry. Do not look at the shipped fallback predictions for hidden cases.
- Exact arithmetic: parse numbers with finreason_solver.numbers.parse_number (it handles fractions like 3209/67 and thousands separators), compute in Fraction, never float. Round only as each answer_spec / result_spec says (the questions say: exact arithmetic through all intermediate steps, round only the final value). Respect units exactly as the spec and text say (percent vs ratio, USD vs USD millions). Enum answers must be exactly one of allowed_values, applying every stated tie rule and inclusive/exclusive comparison exactly as worded.
- Run shell commands that could hang through a Python subprocess with a timeout.
`
~~~

### TEMPLATE_API (transcription format; used by readers, adjudicators and finalize)

~~~js
const TEMPLATE_API = `
TRANSCRIPTION FORMAT (defined by the infra step; follow ${HID}/README.md exactly once it exists): one file per template per reader at ${HID}/forms/<reader>/<KEY>.py defining solve(question_text) returning {"final": Fraction or enum string, "slots": {slot_id: Fraction or string}}, using the extraction helpers in ${HID}/hlib.py. Run your forms with ${HID}/run_forms.py (it applies rounding/serialization identical to the shipped solver and writes to a path you pass, e.g. ${HID}/runs/<reader>_<batch>.json), and it reports extraction failures, enum validity and plausibility flags.
`
~~~

### Infra agent: output schema and prompt

~~~js
// ---------------- Phase 1: infra ----------------
phase('Infra')
const INFRA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    templates_total: { type: 'integer' },
    enum_templates: { type: 'integer' },
    decimal_templates: { type: 'integer' },
    batches: { type: 'array', items: { type: 'array', items: { type: 'string' } }, description: 'template keys per batch, about 8 per batch, enum and decimal mixed evenly' },
    pilot_ported: { type: 'integer' },
    pilot_reproduced: { type: 'boolean' },
    baseline_candidate_ok: { type: 'boolean', description: 'building a candidate from zero transcriptions reproduces the accepted test predictions byte for byte and passes organizers validate+package' },
    notes: { type: 'string' },
  },
  required: ['ok', 'templates_total', 'enum_templates', 'decimal_templates', 'batches', 'pilot_reproduced', 'baseline_candidate_ok', 'notes'],
}
const infra = await agent(`${RULES}
TASK: Build the infrastructure for transcribing the hidden stratum of the FinReason Task 1 test set. Read first: ${SOL}/../../analysis/finreason-hidden-stratum.md, ${SOL}/scripts/hidden_probe/ (probe01..05 and PROVENANCE.txt: the 2026-09-16 pilot, which transcribed 21 templates), ${SOL}/artifacts_hidden_probe/*.json, ${SOL}/src/finreason_solver/ (numbers.py, dataio.py, config.py, and the serialization / answer policy used to write predictions, plus whatever probe05 uses as 'official' validate/package).

Build, all inside ${HID}/ unless stated:
1. templates.json: the hidden stratum grouped into TEMPLATES by the boolean-masked shape (mask numbers with mask_numbers, then replace true/false with <B>, collapse whitespace) exactly as the pilot's bshape did. Expect 116 templates x 3 cases = 348 cases (verify; report the real counts). Give each a stable key H001.. in sorted order of first case_id. For each: key, case_ids, answer_spec, trace_spec slots (slot_id, description, result_spec, position), the three full question texts, type (enum/decimal), and batch number. Make about 15 batches of about 8 templates, spreading enum templates evenly.
2. hlib.py: extraction helpers (regex number capture returning Fraction via parse_number, helpers for percent phrases, enum helpers) that forms import.
3. run_forms.py: CLI taking --reader, --keys (comma list or 'all'), --out. Imports each form, runs it on all 3 questions of the template, serializes final and slots with EXACTLY the shipped solver's rounding/formatting path for the given result spec, and records per case: final string, slot strings, errors. Checks: extraction success on all 3; enum value in allowed_values; every trace slot filled; plausibility flags (negative where the unit/wording implies non-negative, percent magnitude over 1000, ratio magnitude over 100, non-finite). Never raises on a single bad form: records the error.
4. compare.py: CLI taking two run files; per template: AGREE if every final and every slot string is identical on all 3 cases, else DISAGREE with the differing values.
5. build_candidate.py: CLI taking --forms-dir (default ${HID}/forms/final), --exclude (keys to leave on fallback), --out ${OUTD}. Base = ${SOL}/accepted_20260914/test_predictions.jsonl. Replace ONLY hidden cases whose template has a final form, keep every other record byte-identical, write test_predictions.jsonl into --out, run the organizers' own validate and package into --out/test_submission.zip, assert the 580 seen records are byte-identical to the base, assert accepted_20260914/test_submission.zip is unchanged, and write a JSON report (included keys, excluded keys, validate/package results, zip sha256).
6. README.md: the exact transcription format and rules for readers (the RULES above plus the API), with one fully worked example form.
7. Port the pilot's 21 transcriptions into forms/pilot/<KEY>.py in the new format (they may be finals only; add slots only if you can do so from the question text with certainty, otherwise leave slots out and let run_forms report them unfilled). Run run_forms on them and confirm the finals reproduce the pilot's recorded values in artifacts_hidden_probe/q4_*_pilot.json.
8. Sanity: run build_candidate.py with an EMPTY forms dir and confirm the output test_predictions.jsonl is byte-identical to the base and the organizers' validate+package pass.
Return the structured result, with the batches list.`, { label: 'infra', phase: 'Infra', schema: INFRA })

if (!infra || !infra.ok || !infra.batches || !infra.batches.length) {
  log('Infra step did not complete; stopping before any transcription.')
  return { infra }
}
log(`Infra ready: ${infra.templates_total} templates (${infra.enum_templates} enum, ${infra.decimal_templates} decimal) in ${infra.batches.length} batches; pilot reproduced: ${infra.pilot_reproduced}`)
~~~

### Reader and adjudicator output schemas

~~~js
// ---------------- Phase 2: transcribe ----------------
const READ = {
  type: 'object',
  properties: {
    written: { type: 'array', items: { type: 'string' } },
    failed: { type: 'array', items: { type: 'object', properties: { key: { type: 'string' }, reason: { type: 'string' } }, required: ['key', 'reason'] } },
    notes: { type: 'string' },
  },
  required: ['written', 'failed'],
}
const ADJ = {
  type: 'object',
  properties: {
    results: { type: 'array', items: { type: 'object', properties: {
      key: { type: 'string' },
      type: { type: 'string', enum: ['enum', 'decimal'] },
      status: { type: 'string', enum: ['agreed', 'adjudicated', 'uncertain', 'failed'] },
      confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
      slots_complete: { type: 'boolean' },
      note: { type: 'string' },
    }, required: ['key', 'type', 'status', 'confidence', 'slots_complete'] } },
  },
  required: ['results'],
}
~~~

### Reader prompt (`readerPrompt`), METHOD_A and METHOD_B

~~~js
const readerPrompt = (who, keys, method) => `${RULES}
${TEMPLATE_API}
You are reader ${who}, one of two INDEPENDENT readers. Do NOT open ${HID}/forms/ of any other reader, ${HID}/forms/pilot/, or ${HID}/forms/final/. Read ${HID}/README.md and ${HID}/templates.json first.
Your templates: ${keys.join(', ')}.
Method: ${method}
For each template write ${HID}/forms/${who}/<KEY>.py covering the final answer AND every trace slot (read each slot's description and map it to the exact intermediate quantity it names). Then run: run_forms.py --reader ${who} --keys ${keys.join(',')} --out ${HID}/runs/${who}_${keys[0]}.json . Fix every extraction failure and every plausibility flag you can justify from the text. A plausibility flag is not an error if the text genuinely implies the value; say so in notes.
Return which keys you wrote and which you could not transcribe, with reasons.`

const METHOD_A = 'Read the question, identify each named quantity and the regex that captures it robustly across all three draws, then implement the stated recipe literally, clause by clause, in the order the question states it.'
const METHOD_B = 'Before writing any code, restate the recipe in your own words as numbered steps with symbols (inputs, each intermediate, the final, each slot), checking every definition, tie rule, inclusive/exclusive bound and unit against the text. Then implement those steps. Pay particular attention to what each trace slot description asks for.'
~~~

### Per-batch calls: reader A, reader B (`model: 'sonnet'`) and the adjudicator prompt

~~~js
const perBatch = await pipeline(
  infra.batches,
  (keys, _item, i) => parallel([
    () => agent(readerPrompt('A', keys, METHOD_A), { label: `readerA:b${i + 1}`, phase: 'Transcribe', schema: READ }),
    () => agent(readerPrompt('B', keys, METHOD_B), { label: `readerB:b${i + 1}`, phase: 'Transcribe', schema: READ, model: 'sonnet' }),
  ]),
  (readers, keys, i) => agent(`${RULES}
${TEMPLATE_API}
You are the ADJUDICATOR for batch ${i + 1}: ${keys.join(', ')}.
Reader A report: ${JSON.stringify(readers[0])}
Reader B report: ${JSON.stringify(readers[1])}
Run compare.py on ${HID}/runs/A_${keys[0]}.json and ${HID}/runs/B_${keys[0]}.json (re-run run_forms for either reader first if a run file is missing).
For each template:
- AGREE on every final and slot on all 3 cases: copy reader A's form to ${HID}/forms/final/<KEY>.py. Still read the question once yourself and confirm the shared reading is right; two readers can share a misreading. If you find a shared error, fix it and mark adjudicated.
- DISAGREE: read the question text yourself, decide which reading is right clause by clause (or write a corrected form), put the result in forms/final/<KEY>.py, re-run it, and mark adjudicated. If ${HID}/forms/pilot/<KEY>.py exists you may consult it as a third opinion AFTER forming your own view.
- If you cannot resolve it with confidence, still write your best form to forms/final/ but mark uncertain with low confidence and say why.
- If no reader produced a working form and you cannot either, mark failed and write nothing to final.
Then run run_forms.py --reader final --keys ${keys.join(',')} --out ${HID}/runs/final_${keys[0]}.json and confirm every final form runs on all 3 cases with no extraction errors.
Return one result per template.`, { label: `adjudicate:b${i + 1}`, phase: 'Transcribe', schema: ADJ }),
)
~~~

### Status tally and the hold rule for enum templates (control flow, no prompt)

~~~js
const results = perBatch.filter(Boolean).flatMap(r => r.results || [])
const byStatus = s => results.filter(r => r.status === s).map(r => r.key)
log(`Transcribed ${results.length} templates: agreed ${byStatus('agreed').length}, adjudicated ${byStatus('adjudicated').length}, uncertain ${byStatus('uncertain').length}, failed ${byStatus('failed').length}`)

// Enum templates carry downside (fallback scores about 1/3 there): keep fallback unless confidence is high.
const riskyEnums = results.filter(r => r.type === 'enum' && (r.status === 'uncertain' || r.confidence !== 'high')).map(r => r.key)
if (riskyEnums.length) log(`Enum templates held on fallback pending audit: ${riskyEnums.join(', ')}`)
~~~

### Build agent: output schema and prompt

~~~js
// ---------------- Phase 3: build ----------------
phase('Build')
const BUILD = {
  type: 'object',
  properties: {
    included: { type: 'array', items: { type: 'string' } },
    excluded: { type: 'array', items: { type: 'string' } },
    hidden_cases_replaced: { type: 'integer' },
    validate_pass: { type: 'boolean' },
    package_pass: { type: 'boolean' },
    seen_byte_identical: { type: 'boolean' },
    accepted_zip_unchanged: { type: 'boolean' },
    zip_sha256: { type: 'string' },
    notes: { type: 'string' },
  },
  required: ['included', 'excluded', 'validate_pass', 'package_pass', 'seen_byte_identical', 'accepted_zip_unchanged', 'zip_sha256'],
}
const build1 = await agent(`${RULES}
Run ${HID}/build_candidate.py --forms-dir ${HID}/forms/final --exclude ${riskyEnums.join(',') || '""'} --out ${OUTD}. Confirm every check in its report. Return the structured result.`, { label: 'build:1', phase: 'Build', schema: BUILD })
~~~

### Audit sample selection, auditor schema and auditor prompt

~~~js
// ---------------- Phase 4: audit ----------------
phase('Audit')
const adjudicated = results.filter(r => r.status !== 'agreed').map(r => r.key)
const agreed = results.filter(r => r.status === 'agreed').map(r => r.key)
const everyThird = agreed.filter((_, i) => i % 3 === 0)
const auditKeys = Array.from(new Set([...adjudicated, ...everyThird, ...results.filter(r => r.type === 'enum').map(r => r.key)]))
const chunks = []
for (let i = 0; i < auditKeys.length; i += 8) chunks.push(auditKeys.slice(i, i + 8))
log(`Auditing ${auditKeys.length} of ${results.length} templates (all non-agreed, all enum, every third agreed) in ${chunks.length} groups`)
const AUD = {
  type: 'object',
  properties: {
    checked: { type: 'array', items: { type: 'object', properties: {
      key: { type: 'string' },
      verdict: { type: 'string', enum: ['confirmed', 'wrong', 'unsure'] },
      detail: { type: 'string' },
    }, required: ['key', 'verdict', 'detail'] } },
  },
  required: ['checked'],
}
const audits = await parallel(chunks.map((keys, i) => () => agent(`${RULES}
You are an independent AUDITOR. Templates: ${keys.join(', ')}.
For each: WITHOUT opening any file in ${HID}/forms/, read the question text of its first case in ${HID}/templates.json and work the answer and every trace slot from the text alone, writing your arithmetic out step by step with exact fractions (you may write a scratch script under ${HID}/audit/). Only AFTER you have your own values, read ${HID}/runs/final_*.json (or run run_forms.py --reader final --keys <KEY> --out ${HID}/audit/final_<KEY>.json) and compare. Then repeat the comparison on the other two cases using the final form's outputs if your first case matched.
Verdict: confirmed if your independent values match on the case(s) you worked; wrong if they differ and you can point to the clause the form misreads (say exactly which); unsure otherwise.`, { label: `audit:${i + 1}`, phase: 'Audit', schema: AUD })))
const audited = audits.filter(Boolean).flatMap(a => a.checked)
const wrong = audited.filter(a => a.verdict === 'wrong')
const unsure = audited.filter(a => a.verdict === 'unsure')
log(`Audit: ${audited.filter(a => a.verdict === 'confirmed').length} confirmed, ${wrong.length} wrong, ${unsure.length} unsure`)
~~~

### Finalize prompt and the workflow's return value

~~~js
// ---------------- Phase 5: finalize ----------------
phase('Finalize')
const final = await agent(`${RULES}
${TEMPLATE_API}
Finalize the hidden-stratum candidate.
Adjudication results: ${JSON.stringify(results)}
Audit results: ${JSON.stringify(audited)}
Enum templates currently held on fallback: ${JSON.stringify(riskyEnums)}
First build report: ${JSON.stringify(build1)}
1. For each audit verdict 'wrong': read the auditor's detail and the question; if the auditor is right, fix forms/final/<KEY>.py and re-run it; if the form is right, keep it; if unresolvable, exclude the template (fallback). For an enum template, exclude unless you are confident.
2. For held enum templates: include one only if the audit confirmed it; otherwise keep it excluded.
3. Rebuild: build_candidate.py --forms-dir ${HID}/forms/final --exclude <final exclude list> --out ${OUTD}. All checks must pass.
4. Write ${SOL}/../../analysis/finreason-hidden-transcription.md (dated 2026-09-27): method (two independent readers on different models, adjudication, blind audit), counts by status and type, the audit agreement rate, every excluded template and why, the candidate zip sha256 and path, what was NOT verified (no gold exists; every accuracy statement is agreement between independent readings, not an organizer score), and the upload instruction: <UPLOAD TIMING NOTE>; the upload is Aditi's action; after upload, record the receipt in SUBMISSION-LOG.md. Also note that the solver pipeline (src/, run.sh) does not yet include these forms and must be integrated before the paper's one-command rebuild claim covers them.
Return a plain summary: counts, audit rate, excluded list, candidate sha256, validation results.`, { label: 'finalize', phase: 'Finalize' })

return { infra: { templates: infra.templates_total, enum: infra.enum_templates, decimal: infra.decimal_templates, pilot_reproduced: infra.pilot_reproduced }, statusCounts: { agreed: byStatus('agreed').length, adjudicated: byStatus('adjudicated').length, uncertain: byStatus('uncertain').length, failed: byStatus('failed').length }, riskyEnums, build1, auditSummary: { total: audited.length, wrong: wrong.map(w => w.key), unsure: unsure.map(u => u.key) }, final }
~~~

## 2. Flagged audit

* Workflow name: `finreason-flagged-audit` (local run `wf_2d90ba9e-1a5`, status completed).
* Date: started 2026-09-28 04:22 UTC, ended 2026-09-28 04:30 UTC.
* Purpose: Two blind auditors with different lenses (forward reading; sign and domain first) re-derive the 7 templates that carried a plausibility flag and were outside the first audit sample; a resolver settles any template either auditor did not confirm and rebuilds the candidate.
* Models as recorded:
  * Workflow default model: `claude-opus-5-5`.
  * No agent call sets a model option; all 3 agents (2 auditors, 1 resolver) are recorded as `claude-opus-5-5`.
  * Agents by script label: audit 2 (`claude-opus-5-5`); resolve 1 (`claude-opus-5-5`).
* Sampling settings: none set by the script, none recorded.

### Workflow metadata, local paths, template keys and RULES

~~~js
export const meta = {
  name: 'finreason-flagged-audit',
  description: 'Blind audit of the 7 plausibility-flagged hidden templates the first audit did not cover, fix any confirmed misreading, and rebuild the candidate',
  phases: [
    { title: 'Audit', detail: 'two independent blind auditors per template, sign and clamp clauses first' },
    { title: 'Resolve', detail: 'fix confirmed misreadings, rebuild and revalidate' },
  ],
}
const SOL = '<LOCAL>/finreason/solution'
const HID = `${SOL}/hidden`
const OUTD = `${SOL}/artifacts_hidden_v1`
const KEYS = ['H004', 'H011', 'H013', 'H019', 'H034', 'H095', 'H106']
const RULES = `Rules: ZERO LLM API spend; no uploads, emails or posts; never write into ${SOL}/artifacts/, ${SOL}/accepted_20260914/ or ${SOL}/src/. The only source of truth is each question's own text and answer_spec/trace_spec in ${HID}/templates.json; no gold exists, never consult any external source. Exact Fraction arithmetic. Run long commands via Python subprocess with a timeout.`
~~~

### Auditor output schema

~~~js
const AUD = {
  type: 'object',
  properties: { checked: { type: 'array', items: { type: 'object', properties: {
    key: { type: 'string' }, verdict: { type: 'string', enum: ['confirmed', 'wrong', 'unsure'] },
    sign_clause: { type: 'string', description: 'quote any clause about floors, clamps, none-needed, absolute value, or direction; or "none"' },
    detail: { type: 'string' },
  }, required: ['key', 'verdict', 'sign_clause', 'detail'] } } },
  required: ['checked'],
}
~~~

### Auditor lenses and auditor prompt

~~~js
phase('Audit')
const lensA = 'Work each template forward from the text: identify every input, every definition, and the exact quantity asked for, then compute it.'
const lensB = 'Be adversarial about SIGN and DOMAIN first: the current form outputs a negative number (or exact zero) where the wording may imply a non-negative quantity. Before computing, search the question for any clause that floors, clamps, caps, takes a magnitude, defines direction (shortfall vs surplus, increase vs decrease, required vs excess), or says what to report when nothing is needed. Then compute.'
const audits = await parallel([lensA, lensB].map((lens, i) => () => agent(`${RULES}
You are blind auditor ${i + 1} for templates ${KEYS.join(', ')}. ${lens}
For each template: WITHOUT opening ${HID}/forms/, read its three question texts in ${HID}/templates.json and compute the final answer and every trace slot for all three cases yourself (a scratch script under ${HID}/audit_flagged/a${i + 1}/ is fine). Only then run python ${HID}/run_forms.py --reader final --keys <KEY> --out ${HID}/audit_flagged/a${i + 1}/final_<KEY>.json and compare on all three cases.
Verdict per template: confirmed if all finals and slots match; wrong if they differ and you can quote the exact clause the form misreads; unsure otherwise. Always fill sign_clause.`, { label: `audit:${i === 0 ? 'forward' : 'sign-first'}`, phase: 'Audit', schema: AUD })))
const all = audits.filter(Boolean).flatMap(a => a.checked.map(c => ({ ...c })))
const disputed = KEYS.filter(k => all.some(c => c.key === k && c.verdict !== 'confirmed'))
log(`Disputed after two blind audits: ${disputed.length ? disputed.join(', ') : 'none'}`)
~~~

### Resolver prompt

~~~js
let resolve = null
if (disputed.length) {
  phase('Resolve')
  resolve = await agent(`${RULES}
Two blind auditors checked templates ${KEYS.join(', ')}. Results: ${JSON.stringify(all)}
For each disputed template (${disputed.join(', ')}): read the question text clause by clause and the auditors' quoted clauses. If an auditor identified a real misreading, fix ${HID}/forms/final/<KEY>.py (save the old version as ${HID}/forms/final/<KEY>.py.pre-flagged-audit first) and re-run run_forms on it. If the form is right, keep it and say why. If you cannot resolve it with confidence, add the key to the exclude list (fallback).
Then rebuild: python ${HID}/build_candidate.py --forms-dir ${HID}/forms/final --exclude H091<,any newly excluded keys> --out ${OUTD}. Confirm organizers' validate and package PASS, 580 seen records byte-identical, accepted_20260914/test_submission.zip still sha256 42111f7f1d139b86904036bcfc43ef3ed1be2f5b0281ab4e761bcd101bdea221. Append a dated section to ${SOL}/../../analysis/finreason-hidden-transcription.md recording this audit and any change. Return: per disputed template, the decision and why; the final exclude list; the new zip sha256; all validation results.`, { label: 'resolve', phase: 'Resolve' })
}
return { audits: all, disputed, resolve }
~~~

## 3. Audit of the remaining 48 templates (and the 2026-10-02 H031 change)

* Workflow name: `finreason-task1-audit48-h031` (local run `wf_0dec0775-c03`, status completed).
* Date: started 2026-10-02 15:17 UTC, ended 2026-10-02 15:44 UTC.
* Purpose: Six blind auditors re-derive the 48 templates that neither earlier audit covered; a single writer applies the author's 2026-10-02 decision on H031, resolves audit findings, rebuilds and validates candidate v3 and refreshes the package copies; an independent verifier checks the result.
* Models as recorded:
  * Workflow default model: `claude-opus-5-5`.
  * No agent call sets a model option; all 8 agents (6 auditors, 1 resolver, 1 verifier) are recorded as `claude-opus-5-5`.
  * Agents by script label: audit 6 (`claude-opus-5-5`); resolve 1 (`claude-opus-5-5`); verify 1 (`claude-opus-5-5`).
* Sampling settings: none set by the script, none recorded.
* Run arguments as recorded (`args`):

~~~json
{"keys": ["H001", "H002", "H005", "H008", "H009", "H010", "H015", "H021", "H022", "H024", "H025", "H028", "H033", "H035", "H037", "H039", "H042", "H044", "H046", "H047", "H048", "H052", "H053", "H054", "H056", "H057", "H062", "H066", "H070", "H074", "H075", "H077", "H080", "H084", "H087", "H088", "H092", "H093", "H096", "H098", "H099", "H100", "H105", "H108", "H111", "H112", "H115", "H116"]}
~~~

### Workflow metadata, local paths and RULES

~~~js
export const meta = {
  name: 'finreason-task1-audit48-h031',
  description: 'Blind-audit the 48 hidden-stratum forms not yet audited (computed list), apply the approved H031 subtraction reading, resolve any audit findings, rebuild and validate candidate v3, refresh the integrated copies, and report what changed for Aditi to re-mark',
  phases: [
    { title: 'Audit', detail: 'blind third readings of the 48 unaudited templates' },
    { title: 'Resolve', detail: 'single writer: H031 change, audit fixes, rebuild v3, refresh pipeline copies' },
    { title: 'Verify', detail: 'independent check of v3 and the integration' },
  ],
}
const SOL = '<LOCAL>/finreason/solution'
const H = `${SOL}/hidden`
const RULES = `Rules: ZERO LLM API spend; no uploads, emails or posts. Never write into ${SOL}/accepted_*/, ${SOL}/artifacts/, ${SOL}/artifacts_hidden_v1/ or artifacts_hidden_v2/. The only source of truth for a hidden question is its own text and answer_spec/trace_spec in ${H}/templates.json; no gold exists; never consult any external source. Exact Fraction arithmetic. Run long commands via Python subprocess with a timeout. Do not touch ${SOL}/../paper/ or ${SOL}/../task3/. A detached clean rebuild (PID 35804) is running in a scratch copy elsewhere; do not interfere with it. Ignore ${H}/audit48_aborted_wrong_keylist/ (an aborted earlier run with a wrong key list).`
~~~

### Template keys (from the run arguments above) and chunking

~~~js
const KEYS = args.keys
if (!Array.isArray(KEYS) || KEYS.length !== 48) throw new Error('expected exactly 48 keys')
const chunks = []
for (let i = 0; i < KEYS.length; i += 8) chunks.push(KEYS.slice(i, i + 8))
~~~

### Auditor output schema and auditor prompt

~~~js
phase('Audit')
const AUD = {
  type: 'object',
  properties: { checked: { type: 'array', items: { type: 'object', properties: {
    key: { type: 'string' }, verdict: { type: 'string', enum: ['confirmed', 'wrong', 'unsure'] }, detail: { type: 'string' },
  }, required: ['key', 'verdict', 'detail'] } } },
  required: ['checked'],
}
const audits = await parallel(chunks.map((keys, i) => () => agent(`${RULES}
You are an independent blind AUDITOR for templates ${keys.join(', ')}. For each: WITHOUT opening anything in ${H}/forms/ or ${SOL}/src/finreason_solver/hiddenforms/, read all three question texts in ${H}/templates.json and compute the final answer and every trace slot yourself from the text alone (scratch scripts under ${H}/audit48/a${i + 1}/). Only then run python ${H}/run_forms.py --reader final --keys <KEY> --out ${H}/audit48/a${i + 1}/final_<KEY>.json and compare all three cases, finals and slots.
Verdict: confirmed if everything matches; wrong if something differs and you can quote the exact clause the form misreads; unsure otherwise. Where a draw breaks the question's own premise (a value outside its natural domain), the literal stated formula is the accepted reading: do not mark it wrong for that alone.`, { label: `audit:${i + 1}`, phase: 'Audit', schema: AUD })))
const checked = audits.filter(Boolean).flatMap(a => a.checked)
const missing = KEYS.filter(k => !checked.some(c => c.key === k))
if (missing.length) log(`Audit returned no verdict for: ${missing.join(', ')}`)
const notConfirmed = checked.filter(c => c.verdict !== 'confirmed')
log(`Audit of ${checked.length}/48: ${checked.length - notConfirmed.length} confirmed, ${notConfirmed.length} not confirmed`)
~~~

### Resolver (single writer) prompt

~~~js
phase('Resolve')
const resolve = await agent(`${RULES}
You are the SINGLE WRITER on ${H}/forms/final/ and the candidate build.
Audit results for the 48 previously unaudited templates: ${JSON.stringify(checked)}
Templates the audit returned no verdict for (audit them yourself blind before resolving): ${JSON.stringify(missing)}
1. H031 (Aditi's decision, 2026-10-02): switch "Reduce the base appetite by the downturn haircut" from the proportional reading base*(1-haircut) to the SUBTRACTION reading (base - haircut), applied to the final and the stressed_ratio_checkpoint slot. Save the old form as ${H}/forms/final/H031.py.pre-subtraction first, and update its docstring with the reason: the test draws put base at exactly the haircut (0.5) and at 0.500001, edge tests that only make sense when the haircut is subtracted, and 3 of 5 independent readings chose subtraction.
2. For every audit verdict 'wrong' or 'unsure': read the question and the auditor's detail. If the auditor found a real misreading, fix the form (save a .pre-audit48 copy first) and say exactly what changed. If the form is right, keep it and say why. Do not "repair" draws that break their own premise: the literal stated formula stays.
3. Extend WRITABLE_ROOTS in ${H}/build_candidate.py to include ${SOL}/artifacts_hidden_v3, then build: python ${H}/build_candidate.py --forms-dir ${H}/forms/final --exclude "" --out ${SOL}/artifacts_hidden_v3. Confirm organizers' validate and package pass, 580 seen records byte-identical to accepted_20260914, all 348 hidden cases and 456 slots from forms, accepted zips unchanged.
4. Diff v3 against ${SOL}/accepted_20261002/test_predictions.jsonl: list every changed record by template key and what changed (final and/or which slots). The expected changes are H031 plus any audit fixes; anything else is a bug.
5. Refresh the integrated pipeline copies with python ${H}/export_forms.py (then --check), rerun the test suite, and prove the flag-on pipeline regenerates the v3 test predictions byte for byte (into scratch).
6. Append a dated note to ${SOL}/SUBMISSION-LOG.md: v3 candidate path and sha256, the changes vs the ranked 2 Oct archive, and that it awaits Aditi's re-review of the changed forms and her upload.
Return: per-template decisions, the v3 sha256, the full diff list vs the 2 Oct archive, validation and test results, and the exact list of form keys whose code changed since Aditi's review on 2026-10-02 (must include H082 and H031).`, { label: 'resolve', phase: 'Resolve' })
~~~

### Verifier prompt

~~~js
phase('Verify')
const verify = await agent(`${RULES}
Independent verifier, read-only (write only under ${H}/verify_v3/). Resolver report: ${resolve}
Check: v3 zip passes organizers' validate+package; the diff vs accepted_20261002 contains exactly the changes the resolver lists; H031's new outputs equal the subtraction reading on all three cases (compute it yourself from the question text); every form the resolver changed has a .pre-* backup; the integrated copies match forms/final byte for byte (export_forms.py --check); the full test suite passes. Report problems with evidence.`, { label: 'verify', phase: 'Verify' })
return { audit: checked, missing, resolve, verify }
~~~

## 4. Blind re-solve of all 116 templates (2026-10-19)

* Workflow name: `finreason-hidden-resolve` (local run `wf_6490a74c-830`, status completed).
* Date: started 2026-10-19 04:58 UTC, ended 2026-10-19 05:18 UTC.
* Purpose: 29 solver agents, 4 templates each, run at most 3 at a time, solve every hidden template from scratch. Each agent is told to read only the input file of each of its templates (the three question texts, the answer spec and the slot descriptions) and nothing else on the machine.
* Models as recorded:
  * Workflow default model: `claude-opus-5-5`.
  * Every agent call sets `model: 'opus'`; all 29 agents are recorded as `claude-opus-5-5`.
  * Agents by script label: resolve 29 (`claude-opus-5-5`).
* Sampling settings: none set by the script, none recorded.

### Workflow metadata, input folder, grouping and output schema

~~~js
export const meta = {
  name: 'finreason-hidden-resolve',
  description: 'Blind independent re-solve of the 116 Task 1 hidden templates (348 cases) by Opus agents, at most 3 at a time',
  phases: [{ title: 'Re-solve', detail: '29 agents x 4 templates, chunks of 3', model: 'opus' }],
}
const O = '<LOCAL>/finreason/paper/gates/2026-10-18-optionA'
const keys = []
for (let i = 1; i <= 116; i++) keys.push('H' + String(i).padStart(3, '0'))
const groups = []
for (let i = 0; i < keys.length; i += 4) groups.push(keys.slice(i, i + 4))
const SCHEMA = { type: 'object', properties: { templates: { type: 'array', items: { type: 'object', properties: {
  key: { type: 'string' }, status: { type: 'string', enum: ['solved', 'failed'] },
  ambiguity: { type: 'string' }, notes: { type: 'string' } }, required: ['key', 'status'] } } }, required: ['templates'] }
~~~

### Solver prompt

~~~js
const prompt = (g) => `You are an independent financial-calculation solver. Solve these templates of a financial word-problem benchmark from scratch: ${g.join(', ')}.
STRICT ISOLATION: read ONLY ${O}/inputs/<KEY>.json for your keys, and write ONLY ${O}/solutions/<KEY>.py and ${O}/solutions/<KEY>.result.json. Do not open, list or search any other file or directory on this machine (in particular nothing under bigdata-cup-2026/finreason/solution, hidden, artifacts, accepted_*, task3, paper other than your inputs, and no other solutions file). No network access. This must be a blind, independent solution.
Each input file holds one template with 3 cases: case_id, the full question text, answer_spec (final answer type: decimal with rounding decimal_places/half_up, or enum with allowed_values) and trace_spec (named intermediate slots, each with a description and a decimal result_spec with its rounding).
For each template:
1. Read the question wording carefully and literally. Determine the calculation it states for the final answer and for every trace slot (use each slot's description to know exactly what quantity it is). Where the wording leaves a genuine choice, take the most standard finance-textbook reading and record the ambiguity and the alternative.
2. Write ${O}/solutions/<KEY>.py: a Python 3 program using fractions.Fraction (no floats anywhere in the arithmetic) with a function solve(question_text) that PARSES the numbers from the question text with regular expressions (do not hand-copy numbers) and returns {"final": value, "slots": {slot_id: value}}. Decimal values must be exact Fractions BEFORE rounding (do not round). If a root, logarithm or exponential is truly required, compute it with the decimal module at 60 significant digits and convert to Fraction, and say so in notes. Enum finals return the exact allowed label. Include a main block that loads ${O}/inputs/<KEY>.json, runs solve on each case and writes ${O}/solutions/<KEY>.result.json as {case_id: {"final": "p/q" or label, "slots": {slot_id: "p/q"}}} with Fractions written as "numerator/denominator".
3. Run it (python3 ${O}/solutions/<KEY>.py), check it ran on all 3 cases, and sanity-check magnitudes against the question (units, percent vs ratio, signs).
Return one entry per key: status (solved or failed), ambiguity (empty if none; otherwise the exact wording that admits two readings and what the other reading would change), and short notes.`
~~~

### Run loop (`model: 'opus'`)

~~~js
phase('Re-solve')
const results = []
for (let i = 0; i < groups.length; i += 3) {
  const chunk = groups.slice(i, i + 3)
  const out = await parallel(chunk.map((g, j) => () => agent(prompt(g), { label: `resolve:${g[0]}-${g[g.length - 1]}`, phase: 'Re-solve', model: 'opus', schema: SCHEMA })))
  out.forEach((o, j) => results.push(o ? o : { templates: chunk[j].map(k => ({ key: k, status: 'failed', notes: 'agent returned null' })) }))
  log(`${Math.min(i + 3, groups.length)}/${groups.length} groups done`)
}
return results.flatMap(r => r.templates)
~~~

## 5. Three-lens referee panel (2026-10-19)

* Workflow name: `finreason-hidden-adjudicate` (local run `wf_0a6f923d-73f`, status completed).
* Date: started 2026-10-19 05:20 UTC, ended 2026-10-19 05:25 UTC.
* Purpose: For the four templates where the blind re-solve disagreed with the submitted programs (H031, H058, H082, H091), three referees per template, each with one lens (literal text, generator, finance convention), choose between two readings labelled X and Y in random order.
* Models as recorded:
  * Workflow default model: `claude-opus-5-5`.
  * Every agent call sets `model: 'opus'`; all 12 agents are recorded as `claude-opus-5-5`.
  * Agents by script label: literal 4 (`claude-opus-5-5`); generator 4 (`claude-opus-5-5`); domain 4 (`claude-opus-5-5`).
* Sampling settings: none set by the script, none recorded.

### Workflow metadata, input folder and template keys

~~~js
export const meta = {
  name: 'finreason-hidden-adjudicate',
  description: 'Three-lens blind referee panel on the four hidden templates where the independent re-solve disagrees with the submitted programs',
  phases: [{ title: 'Adjudicate', detail: '4 templates x 3 lenses, 3 at a time', model: 'opus' }],
}
const A = '<LOCAL>/finreason/paper/gates/2026-10-18-optionA'
const KEYS = ['H031', 'H058', 'H082', 'H091']
~~~

### The three lenses

~~~js
const LENSES = [
  { id: 'literal', text: 'LITERAL-TEXT lens: decide purely from the exact wording of the question and the slot descriptions. Which reading does the text literally state? Quote the decisive words.' },
  { id: 'generator', text: 'GENERATOR lens: these questions come from a parametric program generator that computes gold answers with a formula and then draws numbers. Look at all three draws: which formula would a generator author most plausibly have coded, given the wording and the specific numbers drawn (for example, values placed exactly at a boundary that only one formula makes critical, or premise violations the formula must handle)? Explain what the number pattern implies.' },
  { id: 'domain', text: 'FINANCE-CONVENTION lens: as a senior practitioner (risk, valuation, compliance), which reading follows standard professional convention for this calculation, and would a careful examiner mark the other reading wrong?' },
]
~~~

### Referee output schema

~~~js
const SCHEMA = { type: 'object', properties: {
  template: { type: 'string' },
  components: { type: 'array', items: { type: 'object', properties: {
    component: { type: 'string' }, choice: { type: 'string', enum: ['X', 'Y', 'neither', 'cannot_tell'] },
    confidence: { type: 'number' }, reason: { type: 'string' } }, required: ['component', 'choice', 'confidence', 'reason'] } },
  overall_choice: { type: 'string', enum: ['X', 'Y', 'neither', 'cannot_tell'] },
  overall_confidence: { type: 'number' }, summary: { type: 'string' } },
  required: ['template', 'components', 'overall_choice', 'overall_confidence', 'summary'] }
~~~

### Referee prompt

~~~js
const prompt = (k, lens) => `You are one referee on a blind panel deciding which of two readings of a financial word-problem template matches the benchmark's hidden answer key. Template ${k}.
Files you may read (and nothing else on this machine; no network): ${A}/inputs/${k}.json (the three questions, answer spec and trace-slot descriptions), ${A}/adjudicate/${k}.reading_X.py and ${A}/adjudicate/${k}.reading_Y.py (two programs implementing different readings; they use a helper num() that extracts the number at each {N} hole of the quoted sentence), and ${A}/adjudicate/${k}.diff.json (the values on which the two readings differ, after the answer spec's rounding). You may run small Python snippets to check arithmetic. The two readings are labelled X and Y in random order; neither label implies anything.
${lens.text}
Decide, for each differing component listed in diff.json (final answer and/or named trace slots), which reading the answer key most likely uses, with a confidence between 0.5 and 1.0, and give the decisive reason. Then give an overall choice for the template. Be adversarial with yourself: state the strongest argument for the reading you reject before rejecting it.`
~~~

### Run loop (`model: 'opus'`)

~~~js
phase('Adjudicate')
const out = []
for (const k of KEYS) {
  const r = await parallel(LENSES.map(l => () => agent(prompt(k, l), { label: `${k}:${l.id}`, phase: 'Adjudicate', model: 'opus', schema: SCHEMA }).then(v => v ? { lens: l.id, ...v } : null)))
  out.push({ key: k, votes: r.filter(Boolean) })
  log(`${k} done`)
}
return out
~~~

## Redactions

Every substitution made in the blocks above, and where:

| recorded text | replaced by | where |
| --- | --- | --- |
| the absolute path of the organizers' repository checkout on the author's machine (it contains the local user name) | `<CUP_REPO>` | workflow 1, constant `QFILE` |
| the absolute path of the author's local project folder (it contains the local user name), as the prefix of every other path | `<LOCAL>` | workflows 1, 2 and 3, constant `SOL` (`<LOCAL>/finreason/solution`); workflows 4 and 5, constants `O` and `A` (`<LOCAL>/finreason/paper/gates/2026-10-18-optionA`) |
| one clause on when the candidate archive could be uploaded (a working note about timing, not part of any method) | `<UPLOAD TIMING NOTE>` | workflow 1, finalize prompt, step 4 |

`<LOCAL>/finreason/solution` is the author's working copy of the Task 1
package. Its released subset is this package, so `${SOL}/hidden` there
corresponds to `task1/hidden` here, and `${SOL}/src` to `task1/src`. Most
other folders the prompts name (for example `accepted_20260914/`,
`artifacts_hidden_v1/`, `forms/A/`, `forms/B/`, `runs/`, the audit folders and
the `analysis/` notes) were working files and are not in this release; the
release note at the top of `README.md` lists the main ones.

Not reproduced from the records: the script file path, task id and agent ids,
the agent transcripts, and every agent output. The scripts were searched for
email addresses, credentials, tokens, submission-system details and
organizer correspondence; they contain none, so nothing else was removed
beyond the rows above. The
words "upload", "email" and "post" in the prompts are prohibitions, and the
sha256 digest they name is that of the 14 September 2026 archive, which
`HIDDEN-FORMS.md` already names.

# SPDX-License-Identifier: Apache-2.0
"""Compare two artifact directories produced by ./run.sh.

    .venv/bin/python scripts/compare_artifacts.py CLEAN_ARTIFACTS SHIPPED_ARTIFACTS

Every file ./run.sh writes is checked.  A file passes if it is byte-identical,
or, for the files that legitimately carry run-specific data, if it is
identical after removing exactly that data and nothing else:

* ``solvers.json``: each template's ``seconds`` is wall-clock build time,
  written by ``build_solvers._one`` (and summed for a merged template).  It is
  not a function of the inputs.
* ``build_summary.json``, ``dev_score.json``, ``*_package.json``: the
  ``*_path`` keys hold absolute paths into the tree that produced them.

Anything else that differs is reported at the level that matters: per template
and component for ``solvers.json``, per case and slot for predictions, per
member for zip archives.  Exit status is 0 only if every run.sh output
matches under those rules.
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

RUN_SH_OUTPUTS = (
    "shape_index.json",
    "solvers.json",
    "build_summary.json",
    "fallback_model.json",
    "dev_predictions.jsonl",
    "dev_score.json",
    "leaderboard_predictions.jsonl",
    "leaderboard_submission.zip",
    "leaderboard_package.json",
    "test_predictions.jsonl",
    "test_submission.zip",
    "test_package.json",
)
VOLATILE_SOLVER_KEYS = frozenset({"seconds"})


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strip_paths(node):
    if isinstance(node, dict):
        return {k: _strip_paths(v) for k, v in node.items() if not k.endswith("_path")}
    if isinstance(node, list):
        return [_strip_paths(v) for v in node]
    return node


def _json_diff(a, b, prefix: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out: list[str] = []
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                out.append(f"{prefix}/{key}: only in {'A' if key in a else 'B'}")
            else:
                out += _json_diff(a[key], b[key], f"{prefix}/{key}")
        return out
    if a != b:
        return [f"{prefix}: {json.dumps(a)[:100]} != {json.dumps(b)[:100]}"]
    return []


def _shippable(payload: dict) -> bool:
    report = payload.get("contract_test") or {}
    return bool(report.get("final_perfect")) and bool(report.get("slots_perfect"))


def compare_solvers(path_a: Path, path_b: Path) -> tuple[bool, list[str]]:
    a = {p["template_id"]: p for p in json.loads(path_a.read_text())}
    b = {p["template_id"]: p for p in json.loads(path_b.read_text())}
    lines = [
        f"templates A={len(a)} B={len(b)}; shippable A="
        f"{sum(map(_shippable, a.values()))} B={sum(map(_shippable, b.values()))}"
    ]
    differing = 0
    for tid in sorted(set(a) | set(b)):
        if tid not in a or tid not in b:
            lines.append(f"  {tid}: missing from {'A' if tid not in a else 'B'}")
            differing += 1
            continue
        x = {k: v for k, v in a[tid].items() if k not in VOLATILE_SOLVER_KEYS}
        y = {k: v for k, v in b[tid].items() if k not in VOLATILE_SOLVER_KEYS}
        if x == y:
            continue
        differing += 1
        keys = sorted(k for k in set(x) | set(y) if x.get(k) != y.get(k))
        lines.append(
            f"  {tid}: stage {x.get('stage')} vs {y.get('stage')}; keys {keys}"
        )
        ta, tb = x.get("text") or {}, y.get("text") or {}
        if ta.get("final") != tb.get("final"):
            lines.append(f"      final A: {ta.get('final')}")
            lines.append(f"      final B: {tb.get('final')}")
        slots_a, slots_b = ta.get("slots") or {}, tb.get("slots") or {}
        for slot in sorted(set(slots_a) | set(slots_b)):
            if slots_a.get(slot) != slots_b.get(slot):
                lines.append(f"      {slot} A: {slots_a.get(slot)}")
                lines.append(f"      {slot} B: {slots_b.get(slot)}")
        if (x.get("trusted_final"), x.get("trusted_slots")) != (
            y.get("trusted_final"),
            y.get("trusted_slots"),
        ):
            lines.append(
                f"      trust A: {x.get('trusted_final')} {x.get('trusted_slots')}"
                f" | B: {y.get('trusted_final')} {y.get('trusted_slots')}"
            )
    lines.insert(1, f"templates differing after dropping {sorted(VOLATILE_SOLVER_KEYS)}: {differing}")
    return differing == 0, lines


def compare_jsonl(path_a: Path, path_b: Path) -> tuple[bool, list[str]]:
    def rows(path: Path) -> dict[str, dict]:
        out = {}
        for line in path.read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                out[record["case_id"]] = record
        return out

    a, b = rows(path_a), rows(path_b)
    lines = [f"cases A={len(a)} B={len(b)}"]
    differing = [cid for cid in sorted(set(a) | set(b)) if a.get(cid) != b.get(cid)]
    lines.append(f"cases differing: {len(differing)}")
    for cid in differing[:10]:
        lines += [f"  {cid}", f"    A: {json.dumps(a.get(cid))[:300]}", f"    B: {json.dumps(b.get(cid))[:300]}"]
    return not differing, lines


def compare_zip(path_a: Path, path_b: Path) -> tuple[bool, list[str]]:
    with zipfile.ZipFile(path_a) as za, zipfile.ZipFile(path_b) as zb:
        names_a, names_b = za.namelist(), zb.namelist()
        lines = [f"members A={names_a} B={names_b}"]
        same = names_a == names_b
        for name in sorted(set(names_a) | set(names_b)):
            if name not in names_a or name not in names_b:
                lines.append(f"  {name}: only in {'A' if name in names_a else 'B'}")
                same = False
                continue
            if za.read(name) != zb.read(name):
                lines.append(f"  {name}: content differs")
                same = False
        if same:
            lines.append("member contents identical; bytes differ only in zip metadata")
    return same, lines


def compare_json(path_a: Path, path_b: Path) -> tuple[bool, list[str]]:
    a = _strip_paths(json.loads(path_a.read_text()))
    b = _strip_paths(json.loads(path_b.read_text()))
    diffs = _json_diff(a, b)
    return not diffs, (["identical after dropping *_path keys"] if not diffs else diffs[:40])


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("dir_a", type=Path)
    parser.add_argument("dir_b", type=Path)
    parser.add_argument(
        "--only",
        nargs="+",
        default=None,
        help="compare just these run.sh outputs (e.g. --only solvers.json)",
    )
    args = parser.parse_args(argv)
    dir_a, dir_b = args.dir_a, args.dir_b
    names = tuple(args.only) if args.only else RUN_SH_OUTPUTS
    print(f"A = {dir_a}\nB = {dir_b}\n")
    ok_all = True
    for name in names:
        path_a, path_b = dir_a / name, dir_b / name
        if not path_a.exists() or not path_b.exists():
            print(f"[MISSING] {name}: A exists={path_a.exists()} B exists={path_b.exists()}")
            ok_all = False
            continue
        sha_a, sha_b = _sha(path_a), _sha(path_b)
        if sha_a == sha_b:
            print(f"[IDENTICAL BYTES] {name}  sha256={sha_a}")
            continue
        if name == "solvers.json":
            ok, lines = compare_solvers(path_a, path_b)
            verdict = "EQUIVALENT (only `seconds` differs)" if ok else "DIFFERENT"
        elif name.endswith(".jsonl"):
            ok, lines = compare_jsonl(path_a, path_b)
            verdict = "EQUIVALENT" if ok else "DIFFERENT"
        elif name.endswith(".zip"):
            ok, lines = compare_zip(path_a, path_b)
            verdict = "EQUIVALENT (contents)" if ok else "DIFFERENT"
        else:
            ok, lines = compare_json(path_a, path_b)
            verdict = "EQUIVALENT (only *_path differs)" if ok else "DIFFERENT"
        ok_all &= ok
        print(f"[{verdict}] {name}  A={sha_a[:16]} B={sha_b[:16]}")
        for line in lines:
            print(f"    {line}")
    extra = sorted(
        p.name
        for directory in (dir_a, dir_b)
        for p in directory.iterdir()
        if p.is_file() and p.name not in RUN_SH_OUTPUTS
    )
    if extra:
        print(f"\nnot run.sh outputs (not compared): {sorted(set(extra))}")
    print("\nVERDICT:", "MATCH" if ok_all else "MISMATCH")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Extraction and arithmetic helpers for hidden-stratum transcription forms.

A form is a deterministic function of ONE question body.  Everything numeric is
an exact ``fractions.Fraction`` parsed with the shipped ``parse_number`` (so
``3209/67`` and ``1,234.5`` parse exactly).  Floats are never produced here.

Extraction
----------
``num(b, "literal text with {N} holes")``  -> Fraction, or a tuple for several {N}
``num_re(b, raw_regex_with_groups)``       -> same, but the pattern is a raw regex
``pct(b, "... {N}% ...")``                -> captured number / 100
``flag(b, "... suspicious activity {B} ...")`` -> bool from a literal true/false
``word(b, "... label {W} ...")``           -> one captured word token
``has(b, "literal phrase")``               -> bool

Literal templates: everything outside a ``{N}`` / ``{B}`` / ``{W}`` hole is matched
literally (regex metacharacters are escaped for you), and any run of whitespace
matches any run of whitespace.  Every extractor insists the template matches the
body EXACTLY ONCE (pass ``nth=k`` to take the k-th match, 0-based, when the text
genuinely repeats the phrase).  A missing or ambiguous match raises
``ExtractionError``, which run_forms records as a failed case.

Arithmetic
----------
``F(x)`` exact Fraction from int / str / Fraction (floats rejected).
``ipow(base, n)`` exact power, n must be integral.
``clamp``, ``pos`` (= max(x, 0)), ``floor_int``, ``ceil_int``, ``as_int``.
``pct_to_ratio`` / ``ratio_to_pct``.

Non-rational operations (use ONLY when the question's stated recipe requires a
root, logarithm, exponential or an equation with no closed form):
``sqrt``, ``nth_root``, ``ln``, ``exp``, ``bisect``.  They return a Fraction
accurate to ~100 significant digits (roots that are exact come back exact) and
they mark the case with a ``non_rational:<op>`` flag in the run file.

Enum decisions
--------------
``first_true([(cond, label), ...], otherwise=label)``  a stated decision list.
``pick_two(ok_a, ok_b, score_a, score_b, a=, b=, neither=, better=, tie=)``
    the recurring "choose the qualifying option with the better metric" rule.
``require_label(label, allowed)`` sanity guard.
"""
from __future__ import annotations

import math
import re
import sys
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterable, Sequence

_SOLUTION = Path(__file__).resolve().parent.parent
if str(_SOLUTION / "src") not in sys.path:
    sys.path.insert(0, str(_SOLUTION / "src"))

from finreason_solver.numbers import parse_number  # noqa: E402

__all__ = [
    "NUM", "BOOLW", "ExtractionError", "NonRationalError",
    "num", "num_re", "pct", "flag", "word", "has", "numbers_in",
    "F", "ipow", "clamp", "pos", "floor_int", "ceil_int", "as_int",
    "pct_to_ratio", "ratio_to_pct",
    "sqrt", "nth_root", "ln", "exp", "bisect",
    "first_true", "pick_two", "require_label",
    "Fraction",
]

# Same number token as the shipped tokeniser (numbers.NUMBER_RE), as a capture
# group, guarded so it cannot start in the middle of another number.
NUM = r"(?<![\d.,/])(-?\d+(?:,\d+)*(?:\.\d+)?(?:/\d+(?:,\d+)*(?:\.\d+)?)?)(?!\d)"
BOOLW = r"\b(true|false)\b"
_WORD = r"([A-Za-z][A-Za-z0-9_\-]*)"
_HOLE = re.compile(r"\{([NBW])\}")


class ExtractionError(ValueError):
    """The template did not match the body exactly once."""


class NonRationalError(ValueError):
    """An exact-only helper was handed a value it cannot keep exact."""


# ------------------------------------------------------------------ patterns
def _compile_literal(template: str) -> str:
    out: list[str] = []
    pos_ = 0
    for m in _HOLE.finditer(template):
        out.append(_escape_ws(template[pos_:m.start()]))
        out.append({"N": NUM, "B": BOOLW, "W": _WORD}[m.group(1)])
        pos_ = m.end()
    out.append(_escape_ws(template[pos_:]))
    return "".join(out)


def _escape_ws(text: str) -> str:
    parts = re.split(r"(\s+)", text)
    return "".join(r"\s+" if p and p.isspace() else re.escape(p) for p in parts)


def _one_match(body: str, regex: str, nth: int | None, what: str) -> re.Match:
    matches = list(re.finditer(regex, body))
    if not matches:
        raise ExtractionError(f"no match for {what}")
    if nth is None:
        if len(matches) != 1:
            raise ExtractionError(f"{len(matches)} matches for {what} (pass nth=)")
        return matches[0]
    if not 0 <= nth < len(matches):
        raise ExtractionError(f"nth={nth} but only {len(matches)} matches for {what}")
    return matches[nth]


def _numbers_from(m: re.Match, scale: Fraction = Fraction(1)):
    vals = tuple(parse_number(g) * scale for g in m.groups() if g is not None)
    if len(vals) != len(m.groups()):
        raise ExtractionError("a capture group did not participate in the match")
    return vals[0] if len(vals) == 1 else vals


def num(body: str, template: str, *, nth: int | None = None):
    """Numbers at the ``{N}`` holes of a literal template."""

    if "{N}" not in template:
        raise ExtractionError("template has no {N} hole")
    if "{B}" in template or "{W}" in template:
        raise ExtractionError("num() takes only {N} holes; use flag()/word()")
    return _numbers_from(_one_match(body, _compile_literal(template), nth, repr(template)))


def num_re(body: str, regex: str, *, nth: int | None = None):
    """Numbers captured by every group of a raw regex (use ``NUM`` for groups)."""

    m = _one_match(body, regex, nth, repr(regex))
    if not m.groups():
        raise ExtractionError("regex has no capture group")
    return _numbers_from(m)


def pct(body: str, template: str, *, nth: int | None = None):
    """Like ``num`` but each captured number is divided by 100."""

    if "{N}" not in template:
        raise ExtractionError("template has no {N} hole")
    m = _one_match(body, _compile_literal(template), nth, repr(template))
    return _numbers_from(m, Fraction(1, 100))


def flag(body: str, template: str, *, nth: int | None = None) -> bool:
    """A literal ``true``/``false`` at the single ``{B}`` hole."""

    if template.count("{B}") != 1 or "{N}" in template or "{W}" in template:
        raise ExtractionError("flag() needs exactly one {B} hole and no other")
    m = _one_match(body, _compile_literal(template), nth, repr(template))
    return m.group(1) == "true"


def word(body: str, template: str, *, nth: int | None = None) -> str:
    if template.count("{W}") != 1 or "{N}" in template or "{B}" in template:
        raise ExtractionError("word() needs exactly one {W} hole and no other")
    return _one_match(body, _compile_literal(template), nth, repr(template)).group(1)


def has(body: str, phrase: str) -> bool:
    return re.search(_escape_ws(phrase), body) is not None


def numbers_in(body: str) -> list[Fraction]:
    """Every number of the body in order.  Last resort; prefer anchored templates."""

    return [parse_number(m.group(1)) for m in re.finditer(NUM, body)]


# ---------------------------------------------------------------- arithmetic
def F(x) -> Fraction:
    if isinstance(x, bool):
        raise TypeError("bool is not a number here")
    if isinstance(x, float):
        raise TypeError("floats are not allowed; pass a string such as '0.1'")
    if isinstance(x, str):
        return parse_number(x.strip())
    if isinstance(x, (int, Fraction)):
        return Fraction(x)
    raise TypeError(f"cannot make an exact Fraction from {type(x).__name__}")


def as_int(x) -> int:
    x = F(x)
    if x.denominator != 1:
        raise NonRationalError(f"{x} is not an integer")
    return x.numerator


def ipow(base, n) -> Fraction:
    """Exact ``base ** n`` for integral n (negative allowed)."""

    return F(base) ** as_int(n)


def clamp(x, lo, hi) -> Fraction:
    lo, hi = F(lo), F(hi)
    if lo > hi:
        raise ValueError("clamp with lo > hi")
    return min(max(F(x), lo), hi)


def pos(x) -> Fraction:
    return max(F(x), Fraction(0))


def floor_int(x) -> int:
    return math.floor(F(x))


def ceil_int(x) -> int:
    return math.ceil(F(x))


def pct_to_ratio(p) -> Fraction:
    return F(p) / 100


def ratio_to_pct(r) -> Fraction:
    return F(r) * 100


# ---------------------------------------------------- non-rational (flagged)
_PREC = 110
NONRATIONAL_USED: list[str] = []


def _mark(op: str) -> None:
    NONRATIONAL_USED.append(op)


def _dec(x: Fraction) -> Decimal:
    return Decimal(x.numerator) / Decimal(x.denominator)


def _iroot(v: int, n: int) -> int:
    """Floor of the n-th root of a non-negative int, by integer Newton steps."""

    if v < 2:
        return v
    x = 1 << ((v.bit_length() + n - 1) // n)
    while True:
        y = ((n - 1) * x + v // x ** (n - 1)) // n
        if y >= x:
            return x
        x = y


def _exact_root(x: Fraction, n: int) -> Fraction | None:
    if x < 0:
        return None
    a, b = _iroot(x.numerator, n), _iroot(x.denominator, n)
    if a ** n == x.numerator and b ** n == x.denominator:
        return Fraction(a, b)
    return None


def nth_root(x, n) -> Fraction:
    x, n = F(x), as_int(n)
    if n <= 0:
        raise ValueError("root order must be positive")
    exact = _exact_root(x, n)
    if exact is not None:
        return exact
    if x < 0:
        raise NonRationalError("root of a negative number")
    _mark(f"nth_root({n})")
    with localcontext() as ctx:
        ctx.prec = _PREC
        return Fraction(_dec(x) ** (Decimal(1) / Decimal(n)))


def sqrt(x) -> Fraction:
    return nth_root(x, 2)


def ln(x) -> Fraction:
    x = F(x)
    if x <= 0:
        raise ValueError("ln of a non-positive number")
    if x == 1:
        return Fraction(0)
    _mark("ln")
    with localcontext() as ctx:
        ctx.prec = _PREC
        return Fraction(_dec(x).ln())


def exp(x) -> Fraction:
    x = F(x)
    if x == 0:
        return Fraction(1)
    _mark("exp")
    with localcontext() as ctx:
        ctx.prec = _PREC
        return Fraction(_dec(x).exp())


def bisect(f: Callable[[Fraction], Fraction], lo, hi, *, digits: int = 60) -> Fraction:
    """Root of a sign-changing f on [lo, hi] by exact Fraction bisection.

    Returns the bracket midpoint once the bracket is narrower than 10**-digits.
    An exact zero at a probe point is returned exactly.
    """

    lo, hi = F(lo), F(hi)
    flo, fhi = F(f(lo)), F(f(hi))
    if flo == 0:
        return lo
    if fhi == 0:
        return hi
    if (flo > 0) == (fhi > 0):
        raise ValueError("bisect: f(lo) and f(hi) have the same sign")
    _mark("bisect")
    tol = Fraction(1, 10 ** digits)
    for _ in range(100000):
        if hi - lo < tol:
            break
        mid = (lo + hi) / 2
        fm = F(f(mid))
        if fm == 0:
            return mid
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


# -------------------------------------------------------------------- enums
def first_true(rules: Iterable[tuple[bool, str]], *, otherwise: str) -> str:
    """First label whose condition holds, else ``otherwise`` (a stated decision list)."""

    for cond, label in rules:
        if not isinstance(cond, bool):
            raise TypeError("decision-list conditions must be real bools")
        if cond:
            return label
    return otherwise


def pick_two(ok_a: bool, ok_b: bool, score_a, score_b, *, a: str, b: str,
             neither: str, better: str, tie: str) -> str:
    """Two-option rule: if both qualify take the better score, else the one that
    qualifies, else ``neither``.  ``better`` is 'higher' or 'lower'; ``tie`` is the
    label returned on an exact score tie (read it off the question's own wording).
    Scores are only compared when both options qualify.
    """

    if better not in ("higher", "lower"):
        raise ValueError("better must be 'higher' or 'lower'")
    if tie not in (a, b):
        raise ValueError("tie must be label a or label b")
    if ok_a and ok_b:
        sa, sb = F(score_a), F(score_b)
        if sa == sb:
            return tie
        if better == "higher":
            return a if sa > sb else b
        return a if sa < sb else b
    if ok_a:
        return a
    if ok_b:
        return b
    return neither


def require_label(label: str, allowed: Sequence[str]) -> str:
    if label not in allowed:
        raise ValueError(f"{label!r} not in allowed values {list(allowed)}")
    return label

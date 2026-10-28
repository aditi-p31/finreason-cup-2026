# SPDX-License-Identifier: Apache-2.0
"""Programmatic derivation of a deterministic solver for each template.

The cup publishes 11 fully-solved instances per template (10 ``train`` + 1
``dev``) that carry the gold final answer *and* the gold value of every
intermediate trace slot.  That is enough to recover the arithmetic by search
rather than by hand: we enumerate exact-arithmetic expressions over the numbers
lifted out of the question text and keep only an expression that reproduces
*every* gold value on *every* instance.

The search is bottom-up with observational equivalence (candidates are keyed by
their value vector across all instances), then a meet-in-the-middle step that
inverts the target through one more operator.  Slots are solved in order and a
solved slot becomes a leaf for later slots and for the final answer, which
mirrors how the benchmark's own generators build a reasoning chain.
"""

from __future__ import annotations

import bisect

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Iterable, Sequence

from . import expr as E
from .numbers import fraction_to_decimal, gold_fraction

Vector = tuple[Fraction, ...]

DEFAULT_CONSTANTS: tuple[Fraction, ...] = tuple(
    Fraction(value)
    for value in (
        0, 1, 2, 3, 4, 5, 6, 10, 12, 24, 30, 52, 100, 250, 252, 360, 365,
        1000, 10000, 1000000, -1,
    )
) + (Fraction(1, 2),)

BINARY_OPS: tuple[str, ...] = ("+", "-", "*", "/")

# Cap on how many pool entries a single inversion window may return before the
# window is judged uninformative and skipped.
MAX_INTERVAL_CANDIDATES = 80

# The left-hand side of an inversion is capped to the shallow end of the pool
# (insertion order is depth order), so a wide pool costs a bounded search.
MAX_INVERSION_LEFT = 12_000

# Hard ceiling on how many full candidate checks one rounded search may run.
# Without it a wide pool crossed with a wide interval turns a search into tens
# of millions of Fraction operations, and the build stops being reproducible in
# reasonable wall time.
MAX_ROUNDED_CHECKS = 250_000


def _combine(op: str, left: Fraction, right: Fraction) -> Fraction | None:
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "min":
        return min(left, right)
    if op == "max":
        return max(left, right)
    if right == 0:
        return None
    return left / right


class Pool:
    """Value-vector -> smallest expression producing it."""

    __slots__ = ("by_key", "order", "n", "marks")

    def __init__(self, n: int) -> None:
        self.by_key: dict[Vector, list[Any]] = {}
        self.order: list[Vector] = []
        self.n = n
        # Named (start, stop) ranges into ``order`` recording which build pass
        # produced which entries; the stage-3 searches use them to iterate the
        # deep-but-relevant entries (powers, wide products, geometric sums)
        # without walking the whole pool.
        self.marks: dict[str, tuple[int, int]] = {}

    def mark(self, name: str, start: int) -> None:
        self.marks[name] = (start, len(self.order))

    def marked(self, *names: str) -> list[Vector]:
        vectors: list[Vector] = []
        for name in names:
            start, stop = self.marks.get(name, (0, 0))
            vectors.extend(self.order[start:stop])
        return vectors

    def add(self, vector: Vector, expression: list[Any]) -> bool:
        previous = self.by_key.get(vector)
        if previous is None:
            self.by_key[vector] = expression
            self.order.append(vector)
            return True
        if E.size(expression) < E.size(previous):
            self.by_key[vector] = expression
        return False

    def __len__(self) -> int:
        return len(self.order)

    def get(self, vector: Vector) -> list[Any] | None:
        return self.by_key.get(vector)


def _vector_ok(vector: Iterable[Fraction]) -> bool:
    for value in vector:
        if E.too_big(value):
            return False
    return True


def _apply(
    op: str, left: Vector, right: Vector, n: int
) -> Vector | None:
    values: list[Fraction] = []
    for index in range(n):
        value = _combine(op, left[index], right[index])
        if value is None or E.too_big(value):
            return None
        values.append(value)
    return tuple(values)


def _pairwise(
    pool: Pool,
    left_items: Sequence[Vector],
    right_items: Sequence[tuple[Vector, list[Any]]],
    ops: Sequence[str],
    n: int,
    max_pool: int,
) -> list[Vector]:
    """Combine every left vector with every right leaf under ``ops``."""

    # Adds are interleaved with production (same order as materialising the
    # whole product list first, so the result is identical) because a late
    # wide pass over a large pool would otherwise hold millions of candidate
    # tuples in memory before the cap could bite.
    fresh: list[Vector] = []
    for left_vector in left_items:
        if len(pool) > max_pool:
            break
        left_expr = pool.by_key[left_vector]
        for right_vector, right_expr in right_items:
            for op in ops:
                forward = _apply(op, left_vector, right_vector, n)
                if forward is not None:
                    if pool.add(forward, [op, left_expr, right_expr]):
                        fresh.append(forward)
                    if len(pool) > max_pool:
                        return fresh
                if op in ("-", "/"):
                    backward = _apply(op, right_vector, left_vector, n)
                    if backward is not None:
                        if pool.add(backward, [op, right_expr, left_expr]):
                            fresh.append(backward)
                        if len(pool) > max_pool:
                            return fresh
    return fresh


SHIFT_MAGNITUDE = Fraction(8)


def _expand_shifts(
    pool: Pool,
    vectors: Sequence[Vector],
    n: int,
    max_pool: int | None = None,
) -> list[Vector]:
    """Add ``1 + x``, ``1 - x`` and ``x - 1`` for rate-sized values.

    Growth and discount factors (``1 + rate``) sit one level deeper than the
    rate itself, and nearly every compounding template needs one, so this pass
    buys the depth where it actually pays.  Restricting it to values of rate
    magnitude keeps the pool from tripling for no gain: shifting a dollar
    balance by one is never the missing step.
    """

    one = E.const(Fraction(1))
    ones = (Fraction(1),) * n
    fresh: list[Vector] = []
    for vector in list(vectors):
        if max_pool is not None and len(pool) > max_pool:
            break
        if any(abs(value) > SHIFT_MAGNITUDE for value in vector):
            continue
        expression = pool.by_key[vector]
        for op, left, right, left_expr, right_expr in (
            ("+", ones, vector, one, expression),
            ("-", ones, vector, one, expression),
            ("-", vector, ones, expression, one),
        ):
            result = _apply(op, left, right, n)
            if result is not None and pool.add(result, [op, left_expr, right_expr]):
                fresh.append(result)
    return fresh


MINMAX_PAIR_LIMIT = 140
MINMAX_PAIR_MAGNITUDE = Fraction(1000)


def _expand_minmax_pairs(pool: Pool, n: int, max_pool: int) -> None:
    """Add ``min``/``max`` between pairs of shallow, score-sized expressions.

    Enum templates state their rule as a precedence chain -- "high_risk when
    the composite score is at least 8 *or* the override flag is true" -- which
    is exactly ``max(score - 8, flag - 1) >= 0`` once the flag is lifted into
    the parameter vector as 1/0.  Both operands are themselves depth-2
    expressions, so leaf-to-leaf min/max is not enough.  The pass is restricted
    to shallow, small-magnitude entries and only runs for templates that
    actually have an enum output.
    """

    small = [
        vector
        for vector in pool.order
        if all(abs(value) <= MINMAX_PAIR_MAGNITUDE for value in vector)
    ][:MINMAX_PAIR_LIMIT]
    additions: list[tuple[Vector, list[Any]]] = []
    for index, left in enumerate(small):
        left_expr = pool.by_key[left]
        for right in small[index + 1 :]:
            right_expr = pool.by_key[right]
            for op in ("min", "max"):
                vector = _apply(op, left, right, n)
                if vector is not None:
                    additions.append((vector, [op, left_expr, right_expr]))
    for vector, expression in additions:
        pool.add(vector, expression)
        if len(pool) > max_pool:
            return


def _expand_clamps(pool: Pool, vectors: Sequence[Vector], n: int) -> list[Vector]:
    """Add ``max(x, 0)`` and ``min(x, 0)``.

    A large family of cup templates is explicitly "the larger of X and zero"
    (shortfalls, excesses, taxable income floors).  Only mixed-sign vectors
    are clamped: for a single-sign vector both clamps are either the vector
    itself or the zero constant, which the pool already holds, so skipping
    them changes nothing except the wasted hashing.
    """

    zero = E.const(Fraction(0))
    zeros = (Fraction(0),) * n
    fresh: list[Vector] = []
    for vector in list(vectors):
        any_negative = False
        any_positive = False
        for value in vector:
            if value.numerator < 0:
                any_negative = True
            elif value.numerator > 0:
                any_positive = True
        if not (any_negative and any_positive):
            continue
        expression = pool.by_key[vector]
        for op in ("max", "min"):
            result = _apply(op, vector, zeros, n)
            if result is not None and pool.add(result, [op, expression, zero]):
                fresh.append(result)
    return fresh


RATE_MAGNITUDE = Fraction(8)
MAX_RATE_QUOTIENTS = 3_000


def _expand_rate_quotients(
    pool: Pool,
    quantity_items: Sequence[tuple[Vector, list[Any]]],
    n: int,
) -> list[Vector]:
    """Add rate-sized ``q1 / (q2 * q3)`` chains before the shift/power passes.

    Semi-annual and quarterly compounding write their per-period rate as
    ``r / 100 / m``: three numbers deep, which depth-2 pairwise cannot reach,
    and it must exist *before* the shift pass or ``1 + r/(100 m)`` is never a
    power base.  Restricted to rate-magnitude results.
    """

    hundred = (Fraction(100),) * n
    hundred_expr = E.const(Fraction(100))
    divisors = list(quantity_items) + [(hundred, hundred_expr)]
    fresh: list[Vector] = []
    for numerator_vector, numerator_expr in quantity_items:
        for i, (d1_vector, d1_expr) in enumerate(divisors):
            if any(value == 0 for value in d1_vector):
                continue
            for d2_vector, d2_expr in divisors[i:]:
                if any(value == 0 for value in d2_vector):
                    continue
                product = _apply("*", d1_vector, d2_vector, n)
                if product is None or any(value == 0 for value in product):
                    continue
                vector = _apply("/", numerator_vector, product, n)
                if vector is None:
                    continue
                if any(abs(value) > RATE_MAGNITUDE for value in vector):
                    continue
                expression = ["/", numerator_expr, ["*", d1_expr, d2_expr]]
                if pool.add(vector, expression):
                    fresh.append(vector)
                if len(fresh) >= MAX_RATE_QUOTIENTS:
                    return fresh
    return fresh


MAX_GEOMETRIC_BASES = 400
MAX_GEOMETRIC_POWER = 6
GEOMETRIC_LOW = Fraction(1, 20)
GEOMETRIC_HIGH = Fraction(5, 2)


def _geometric_eligible(vector: Vector) -> bool:
    # A single instance may legitimately sit at exactly 1 (a zero-percent
    # discount rate draw), so only an all-ones vector is rejected as trivial.
    return all(
        GEOMETRIC_LOW <= abs(value) <= GEOMETRIC_HIGH for value in vector
    ) and not all(value == 1 for value in vector)


def _expand_geometric(
    pool: Pool, base_vectors: Sequence[Vector], n: int
) -> list[Vector]:
    """Add ``x + x^2 + ... + x^k`` for discount-factor-sized ``x``.

    Level annuities ("USD 1265 at each year-end for four years") discount one
    cash flow by a geometric sum of the same factor; the sum never appears in a
    pairwise pool because every partial sum is one more addition deep.
    """

    seen: set[Vector] = set()
    bases: list[Vector] = []
    for vector in base_vectors:
        if vector in seen or not _geometric_eligible(vector):
            continue
        seen.add(vector)
        bases.append(vector)
        if len(bases) >= MAX_GEOMETRIC_BASES:
            break
    fresh: list[Vector] = []
    for base in bases:
        base_expr = pool.by_key[base]
        total = base
        total_expr = base_expr
        power = base
        power_expr = base_expr
        for _ in range(2, MAX_GEOMETRIC_POWER + 1):
            next_power = _apply("*", power, base, n)
            if next_power is None:
                break
            power = next_power
            power_expr = ["*", power_expr, base_expr]
            next_total = _apply("+", total, power, n)
            if next_total is None:
                break
            total = next_total
            total_expr = ["+", total_expr, power_expr]
            if pool.add(total, total_expr):
                fresh.append(total)
    return fresh


def _expand_shift_ratios(
    pool: Pool, shift_vectors: Sequence[Vector], n: int, cap: int = 60
) -> list[Vector]:
    """Add ratios of growth factors: ``(1 + g) / (1 + r)``.

    A growing forecast discounted at a different rate compounds by exactly this
    ratio, which is a quotient of two non-leaf entries and therefore outside
    both the pairwise and the wide passes.
    """

    candidates = [
        vector
        for vector in dict.fromkeys(shift_vectors)
        if _geometric_eligible(vector) or all(value == 1 for value in vector)
    ][:cap]
    fresh: list[Vector] = []
    for left in candidates:
        left_expr = pool.by_key[left]
        for right in candidates:
            if left is right or any(value == 0 for value in right):
                continue
            vector = _apply("/", left, right, n)
            if vector is None or not _geometric_eligible(vector):
                continue
            if pool.add(vector, ["/", left_expr, pool.by_key[right]]):
                fresh.append(vector)
    return fresh


MINMAX_LEAF_MAGNITUDE = Fraction(10) ** 9


def _expand_minmax_leaf(
    pool: Pool,
    quantity_items: Sequence[tuple[Vector, list[Any]]],
    source_vectors: Sequence[Vector],
    n: int,
    cap: int = 6_000,
) -> list[Vector]:
    """Add ``min/max(quantity, entry)`` pairs (caps and floors against limits)."""

    fresh: list[Vector] = []
    count = 0
    for vector in source_vectors:
        if count >= cap:
            break
        if any(abs(value) > MINMAX_LEAF_MAGNITUDE for value in vector):
            continue
        count += 1
        expression = pool.by_key[vector]
        for leaf_vector, leaf_expr in quantity_items:
            for op in ("min", "max"):
                result = _apply(op, vector, leaf_vector, n)
                if result is not None and pool.add(
                    result, [op, expression, leaf_expr]
                ):
                    fresh.append(result)
    return fresh


def leaf_items_for(
    pool: Pool,
    param_vectors: Sequence[Vector],
    slot_vectors: Sequence[Vector],
    constants: Sequence[Fraction] = DEFAULT_CONSTANTS,
) -> list[tuple[Vector, list[Any]]]:
    """The leaf set a pool was built from, for second-stage searches."""

    n = pool.n
    items: list[tuple[Vector, list[Any]]] = []
    seen: set[Vector] = set()
    for index, vector in enumerate(param_vectors):
        if vector not in seen:
            seen.add(vector)
            items.append((vector, E.param(index)))
    for index, vector in enumerate(slot_vectors):
        if vector not in seen:
            seen.add(vector)
            items.append((vector, E.slot(index)))
    for value in constants:
        vector = (value,) * n
        if vector not in seen:
            seen.add(vector)
            items.append((vector, E.const(value)))
    return items


def build_pool(
    param_vectors: Sequence[Vector],
    slot_vectors: Sequence[Vector],
    n: int,
    *,
    constants: Sequence[Fraction] = DEFAULT_CONSTANTS,
    depth: int = 2,
    powers: bool = True,
    wide: bool = False,
    minmax_pairs: bool = False,
    stage3: bool = False,
    max_pool: int = 300_000,
) -> Pool:
    """Enumerate a candidate pool of exact-arithmetic expressions.

    Stages: leaves -> pairwise arithmetic (``depth`` levels) -> min/max between
    leaves -> ``1 +/- x`` shifts -> ``max/min(x, 0)`` clamps -> integer and
    parameter powers.  Every stage is deterministic and order-stable.

    ``stage3`` reorders and extends the pipeline for the templates the wide
    pass missed: rate-quotient power bases and derived exponents before the
    powers, geometric sums and growth-factor ratios after them, the wide pass
    *after* the powers (prioritising power entries so discounted terms exist),
    then bounded ``min/max``-against-quantity, one additive level over the wide
    products and one further multiplicative level over that.  Every extension
    is capped, and each pass records its range in ``pool.marks``.
    """

    pool = Pool(n)
    leaves: list[tuple[Vector, list[Any]]] = []
    for index, vector in enumerate(param_vectors):
        leaves.append((vector, E.param(index)))
    for index, vector in enumerate(slot_vectors):
        leaves.append((vector, E.slot(index)))
    for value in constants:
        leaves.append(((value,) * n, E.const(value)))
    for vector, expression in leaves:
        pool.add(vector, expression)

    leaf_items = [
        (vector, pool.by_key[vector])
        for vector in dict.fromkeys(vector for vector, _ in leaves)
    ]
    quantity_leaves = [item for item in leaf_items if item[1][0] in ("p", "s")]

    frontier: list[Vector] = list(pool.order)
    for _ in range(depth - 1):
        if len(pool) > max_pool:
            break
        frontier = _pairwise(pool, frontier, leaf_items, BINARY_OPS, n, max_pool)

    leaf_vectors = [vector for vector, _ in leaf_items]
    _pairwise(pool, leaf_vectors, leaf_items, ("min", "max"), n, max_pool)

    if stage3:
        # Absolute budget checkpoints (not ``max_pool - k`` offsets): the early
        # power passes must be *capped* so the wide passes always get to run.
        powers_budget = min(max_pool, 130_000)
        power_shifts_budget = min(max_pool, 170_000)
        start = len(pool.order)
        _expand_rate_quotients(pool, quantity_leaves, n)
        pool.mark("rate_quotients", start)
        shift_fresh = _expand_shifts(pool, list(pool.order), n)
        start = len(pool.order)
        _extend_with_powers(
            pool,
            param_vectors,
            n,
            stage3=True,
            priority_bases=shift_fresh + pool.marked("rate_quotients"),
            max_pool=powers_budget,
        )
        pool.mark("powers", start)
        start = len(pool.order)
        shift_fresh2 = _expand_shifts(
            pool, pool.marked("powers"), n, max_pool=power_shifts_budget
        )
        pool.mark("power_shifts", start)
        start = len(pool.order)
        ratio_fresh = _expand_shift_ratios(pool, shift_fresh + shift_fresh2, n)
        geometric_bases = (
            pool.marked("powers") + ratio_fresh + shift_fresh + shift_fresh2
        )
        geom_fresh = _expand_geometric(pool, geometric_bases, n)
        _expand_shifts(pool, geom_fresh, n)
        pool.mark("geometric", start)
        # Wide pass, prioritised: discounted terms (powers x quantity) first so
        # the pool cap cannot starve them, then everything else.  Each pass has
        # an *absolute* ceiling that always leaves headroom for the ones after
        # it, so a saturating early pass cannot starve the additive and second
        # multiplicative levels.
        wide_priority_cap = max_pool + 60_000
        wide_cap = max_pool + 140_000
        additive_cap = max_pool + 190_000
        wide2_cap = max_pool + 260_000
        start = len(pool.order)
        priority = pool.marked("rate_quotients", "powers", "power_shifts", "geometric")
        _pairwise(
            pool, priority[:8_000], quantity_leaves, ("*", "/"), n, wide_priority_cap
        )
        pool.mark("wide_priority", start)
        start = len(pool.order)
        _pairwise(pool, list(pool.order), quantity_leaves, ("*", "/"), n, wide_cap)
        pool.mark("wide", start)
        if minmax_pairs:
            _expand_minmax_pairs(pool, n, wide_cap)
        start = len(pool.order)
        minmax_sources = pool.order[:6_000] + pool.marked("wide_priority")[:4_000]
        _expand_minmax_leaf(pool, quantity_leaves, minmax_sources, n)
        pool.mark("minmax_leaf", start)
        start = len(pool.order)
        additive_sources = (
            pool.order[:6_000]
            + pool.marked("wide_priority")[:6_000]
            + pool.marked("minmax_leaf")[:2_000]
        )
        _pairwise(
            pool,
            list(dict.fromkeys(additive_sources)),
            quantity_leaves,
            ("+", "-"),
            n,
            additive_cap,
        )
        pool.mark("additive", start)
        start = len(pool.order)
        _expand_clamps(pool, list(pool.order), n)
        pool.mark("clamps", start)
        start = len(pool.order)
        second_sources = (
            pool.marked("additive")[:6_000]
            + pool.marked("minmax_leaf")[:3_000]
            + pool.marked("clamps")[:3_000]
        )
        _pairwise(
            pool,
            list(dict.fromkeys(second_sources)),
            quantity_leaves,
            ("*", "/"),
            n,
            wide2_cap,
        )
        pool.mark("wide2", start)
        start = len(pool.order)
        _expand_minmax_leaf(
            pool, quantity_leaves, pool.marked("wide2")[:4_000], n, cap=4_000
        )
        pool.mark("minmax_leaf2", start)
        return pool

    # Growth and discount factors first, so the wide pass can multiply by them.
    _expand_shifts(pool, list(pool.order), n)
    if wide:
        # Products and quotients of three or more factors -- the shape of most
        # WACC, NPV and multi-factor risk formulas -- need one level more than
        # plain depth 2.  Restricting that level to * and / over the question's
        # own quantities keeps it about a tenth of the cost of a full depth-3
        # pool.
        _pairwise(
            pool, list(pool.order), quantity_leaves, ("*", "/"), n, max_pool
        )
    if minmax_pairs:
        _expand_minmax_pairs(pool, n, max_pool)
    if powers:
        _extend_with_powers(pool, param_vectors, n)
        # Compound interest is ``P * ((1 + r) ** n - 1)``: the "minus one" sits
        # on the *outside* of the power, so a single shift pass before the
        # powers cannot reach it.
        _expand_shifts(pool, list(pool.order), n)
    _expand_clamps(pool, list(pool.order), n)
    return pool


MAX_POWER_BASES = 30_000
# Stage 3 caps the power bases (a high-parameter question floods the pool with
# small integers) and raises ``base ** (m * n)`` and ``base ** (m + n)``
# exponents over growth-factor-shaped bases only, so the pass stays bounded.
MAX_STAGE3_POWER_BASES = 3_000
MAX_DERIVED_EXPONENT_BASES = 2_500
CONST_EXPONENTS = (2, 3, 4, -1, -2)
CONST_EXPONENTS_STAGE3 = (2, 3, 4, 5, 6, -1, -2, -3, -4, -5, -6)


def _power_vector(base_vector: Vector, exponents: Sequence[int], n: int) -> Vector | None:
    values: list[Fraction] = []
    for index in range(n):
        exponent = exponents[index]
        if abs(exponent) > 240:
            return None
        if base_vector[index] == 0 and exponent < 0:
            return None
        value = base_vector[index] ** exponent
        if E.too_big(value):
            return None
        values.append(value)
    return tuple(values)


def _extend_with_powers(
    pool: Pool,
    param_vectors: Sequence[Vector],
    n: int,
    *,
    stage3: bool = False,
    priority_bases: Sequence[Vector] = (),
    max_pool: int | None = None,
) -> None:
    """Add ``base ** k`` and ``base ** parameter`` terms.

    Compound-growth templates (``P * (1 + r) ** n``) are otherwise out of reach:
    the exponent is itself one of the question's numbers.  Stage 3 widens the
    constant exponents to +/-6 (five-year DCFs) and adds *derived* integer
    exponents ``m * n`` and ``m + n`` (quarterly compounding is
    ``(1 + r/400) ** (4n)``), restricted to growth-factor-sized bases.
    """

    integer_leaves: list[tuple[Vector, list[Any]]] = []
    for index, vector in enumerate(param_vectors):
        if all(value.denominator == 1 and abs(value) <= 240 for value in vector):
            integer_leaves.append((vector, E.param(index)))
    bases = [
        vector
        for vector in pool.order
        if all(value != 0 and abs(value) <= 16 for value in vector)
    ]
    if stage3:
        # With many parameters the pool is full of small integers, and raising
        # every one to every exponent buries the discount/growth factors this
        # pass actually exists for.  Rank genuine growth factors (values near
        # 1) first, then everything else, and cap the total.
        priority_set = set(priority_bases)

        def base_rank(vector: Vector) -> tuple[int, int]:
            growth = all(abs(value - 1) <= Fraction(1, 2) for value in vector)
            return (
                0 if vector in priority_set else (1 if growth else 2),
                E.size(pool.by_key[vector]),
            )

        bases = sorted(bases, key=base_rank)[:MAX_STAGE3_POWER_BASES]
    else:
        bases = bases[:MAX_POWER_BASES]
    const_exponents = CONST_EXPONENTS_STAGE3 if stage3 else CONST_EXPONENTS
    additions: list[tuple[Vector, list[Any]]] = []

    def flush() -> bool:
        """Add the pending batch; return False once the budget is spent."""

        for vector, expression in additions:
            pool.add(vector, expression)
        additions.clear()
        return max_pool is None or len(pool) <= max_pool

    for base_vector in bases:
        base_expr = pool.by_key[base_vector]
        for exponent_vector, exponent_expr in integer_leaves:
            for sign in (1, -1):
                vector = _power_vector(
                    base_vector,
                    [sign * int(exponent_vector[index]) for index in range(n)],
                    n,
                )
                if vector is None:
                    continue
                signed_expr = (
                    exponent_expr
                    if sign == 1
                    else ["neg", exponent_expr]
                )
                additions.append((vector, ["^", base_expr, signed_expr]))
        for exponent in const_exponents:
            vector = _power_vector(base_vector, [exponent] * n, n)
            if vector is not None:
                additions.append(
                    (vector, ["^", base_expr, E.const(Fraction(exponent))])
                )
        if len(additions) >= 4_000 and not flush():
            return
    if max_pool is not None and len(pool) > max_pool:
        flush()
        return
    if stage3 and len(integer_leaves) >= 2:
        derived: dict[Vector, list[Any]] = {}
        for i, (left_vector, left_expr) in enumerate(integer_leaves):
            for right_vector, right_expr in integer_leaves[i:]:
                for op in ("*", "+"):
                    combined = _apply(op, left_vector, right_vector, n)
                    if combined is None:
                        continue
                    if any(abs(value) > 240 for value in combined):
                        continue
                    if combined not in derived:
                        derived[combined] = [op, left_expr, right_expr]
        # Genuine growth factors (the shift pass's ``1 + r/(100 m)`` entries)
        # go first so constant-only junk cannot crowd them out of the cap.
        ordered = list(dict.fromkeys(list(priority_bases) + bases))
        growth_bases = [
            vector
            for vector in ordered
            if vector in pool.by_key
            and all(
                value != 0
                and abs(value) <= 16
                and abs(value - 1) <= Fraction(1, 2)
                for value in vector
            )
        ][:MAX_DERIVED_EXPONENT_BASES]
        for base_vector in growth_bases:
            base_expr = pool.by_key[base_vector]
            for exponent_vector, exponent_expr in derived.items():
                for sign in (1, -1):
                    vector = _power_vector(
                        base_vector,
                        [sign * int(exponent_vector[index]) for index in range(n)],
                        n,
                    )
                    if vector is None:
                        continue
                    signed_expr = (
                        exponent_expr if sign == 1 else ["neg", exponent_expr]
                    )
                    additions.append((vector, ["^", base_expr, signed_expr]))
            if len(additions) >= 4_000 and not flush():
                return
    flush()


def evaluate_vector(
    expression: Sequence[Any],
    param_vectors: Sequence[Vector],
    slot_vectors: Sequence[Vector],
    n: int,
) -> Vector | None:
    """Recompute an expression's value vector; ``None`` if it ever fails."""

    values: list[Fraction] = []
    for index in range(n):
        params = [vector[index] for vector in param_vectors]
        slots = [vector[index] for vector in slot_vectors]
        try:
            value = E.evaluate(expression, params, slots)
        except (E.Unevaluable, ZeroDivisionError, OverflowError, ValueError):
            return None
        if E.too_big(value):
            return None
        values.append(value)
    return tuple(values)


def search_exact(
    pool: Pool,
    target: Vector,
    verify=None,
    extra_lefts: Sequence[Vector] = (),
) -> list[Any] | None:
    """Find an expression equal to ``target`` on every instance."""

    direct = pool.get(target)
    if direct is not None and (verify is None or verify(direct) == target):
        return direct
    n = pool.n
    best: list[Any] | None = None
    lefts: list[Vector] = list(pool.order[:MAX_INVERSION_LEFT])
    if extra_lefts:
        lefts.extend(extra_lefts)
    for left_vector in lefts:
        left_expr = pool.by_key[left_vector]
        # target = left + y
        candidates: list[tuple[str, Vector | None, bool]] = []
        add_y = tuple(target[i] - left_vector[i] for i in range(n))
        candidates.append(("+", add_y, False))
        sub_y = tuple(left_vector[i] - target[i] for i in range(n))
        candidates.append(("-", sub_y, False))
        rsub_y = tuple(target[i] + left_vector[i] for i in range(n))
        candidates.append(("-", rsub_y, True))
        if all(value != 0 for value in left_vector):
            mul_y = tuple(target[i] / left_vector[i] for i in range(n))
            candidates.append(("*", mul_y, False))
            div_y = tuple(target[i] * left_vector[i] for i in range(n))
            candidates.append(("/", div_y, True))
        if all(value != 0 for value in target) and all(
            value != 0 for value in left_vector
        ):
            rdiv_y = tuple(left_vector[i] / target[i] for i in range(n))
            candidates.append(("/", rdiv_y, False))
        for op, wanted, reverse in candidates:
            if wanted is None or not _vector_ok(wanted):
                continue
            right_expr = pool.get(wanted)
            if right_expr is None:
                continue
            expression = (
                [op, right_expr, left_expr] if reverse else [op, left_expr, right_expr]
            )
            if verify is not None and verify(expression) != target:
                continue
            if best is None or E.size(expression) < E.size(best):
                best = expression
    return best


def search_predicate(
    pool: Pool,
    predicate: Callable[[Vector], bool],
    verify=None,
) -> list[Any] | None:
    """Scan the pool for any expression satisfying ``predicate``."""

    best: list[Any] | None = None
    for vector in pool.order:
        if not predicate(vector):
            continue
        expression = pool.by_key[vector]
        if verify is not None:
            recomputed = verify(expression)
            if recomputed is None or not predicate(recomputed):
                continue
        if best is None or E.size(expression) < E.size(best):
            best = expression
    return best


def search_rounded(
    pool: Pool,
    gold_values: Sequence[Fraction],
    places: int,
    leaf_items: Sequence[tuple[Vector, list[Any]]],
    verify=None,
    ops: Sequence[str] = ("+", "-", "*", "/"),
    extra_lefts: Sequence[Vector] = (),
) -> list[Any] | None:
    """Find an expression that *rounds* to the gold value on every instance.

    A final answer is scored after ``ROUND_HALF_UP`` quantisation, so the exact
    inversion used by :func:`search_exact` does not apply: the true value is
    only known to lie inside a half-ulp interval.  Stage one scans the pool
    directly; stage two walks ``pool x leaves`` but pre-filters on the first
    instance's interval, which is two Fraction comparisons instead of eleven
    decimal quantisations, and only then verifies the survivor properly.
    """

    from .numbers import fraction_to_decimal

    n = pool.n
    expected = []
    for value in gold_values:
        try:
            expected.append(fraction_to_decimal(value, places))
        except (ValueError, ArithmeticError):
            return None

    def matches(vector: Vector) -> bool:
        for value, want in zip(vector, expected):
            try:
                if fraction_to_decimal(value, places) != want:
                    return False
            except (ValueError, ArithmeticError):
                return False
        return True

    found = search_predicate(pool, matches, verify)
    if found is not None:
        return found

    half = Fraction(1, 2 * 10**places)
    low = gold_values[0] - half
    high = gold_values[0] + half

    order = sorted(pool.order, key=lambda vector: vector[0])
    firsts = [vector[0] for vector in order]

    def window(lower: Fraction, upper: Fraction) -> list[Vector]:
        if lower > upper:
            lower, upper = upper, lower
        start_index = bisect.bisect_left(firsts, lower)
        stop_index = bisect.bisect_right(firsts, upper)
        if stop_index - start_index > MAX_INTERVAL_CANDIDATES:
            return []
        return order[start_index:stop_index]

    best: list[Any] | None = None
    best_size = 10**9
    checks = 0

    def consider(op: str, first: Vector, second: Vector) -> None:
        nonlocal best, best_size, checks
        checks += 1
        expression = [op, pool.by_key[first], pool.by_key[second]]
        size = E.size(expression)
        if size >= best_size:
            return
        vector = _apply(op, first, second, n)
        if vector is None or not matches(vector):
            return
        if verify is not None:
            recomputed = verify(expression)
            if recomputed is None or not matches(recomputed):
                return
        best = expression
        best_size = size

    lefts: list[Vector] = list(pool.order[:MAX_INVERSION_LEFT])
    if extra_lefts:
        lefts.extend(extra_lefts)
    for left in lefts:
        if checks > MAX_ROUNDED_CHECKS or best_size <= 3:
            break
        value = left[0]
        for candidate in window(low - value, high - value):
            consider("+", left, candidate)
        for candidate in window(value - high, value - low):
            consider("-", left, candidate)
        if value != 0:
            for candidate in window(low / value, high / value):
                consider("*", left, candidate)
            for candidate in window(low * value, high * value):
                consider("/", candidate, left)
        if low > 0 or high < 0:
            if value != 0 and low != 0 and high != 0:
                for candidate in window(value / high, value / low):
                    consider("/", left, candidate)
    return best

# SPDX-License-Identifier: Apache-2.0
"""Stage-3 searches: target transforms, sum peeling and piecewise conditionals.

The stage-1/2 machinery finds any expression whose *last* operator can be
inverted into the candidate pool.  What it structurally cannot find is the
family this module targets:

* sums of three or more product terms (WACC ``wE*ke + wP*kp + wD*kd_at``,
  NPV ``sum of cf_t / (1+r)^t``), where both operands of the outer sum are
  themselves deep;
* targets that only become reachable after multiplying or dividing by a
  question quantity (``portfolio beta = sum(v_i b_i) / sum(v_i)``);
* conditionals with numeric branches ("return Q times the rebate rate when
  Q > T and zero otherwise").

Every candidate set here is constructed deterministically from the question's
own quantities and capped, every hit is re-verified by recomputing the
expression from scratch, and acceptance is always the caller's ``check``
(exact ``Fraction`` equality for trace slots, the scorer's half-up rounding
for final answers), so nothing in this module can weaken the ship gate.
"""

from __future__ import annotations

import bisect
from fractions import Fraction
from typing import Any, Callable, Sequence

from . import expr as E
from .induction import Pool, Vector, _apply

Interval = tuple[Fraction, Fraction]
Item = tuple[Vector, list[Any]]

# Caps.  All chosen so a single stage-3 template costs minutes, not hours.
MAX_TRANSFORMS = 420
TRANSFORM_LIGHT_LEFTS = 700
MAX_ONEPASS_TERMS = 90_000
MAX_PAIR_TERMS = 3_000
# The O(k^2) pair search works on a bounded prefix of the term set; the basic
# products a three-term sum peels sit at the front, so a modest prefix keeps
# the yield while turning a 9M-iteration scan into a fast one.
PAIR_WORKING_SET = 1_200
# The scaled pair search runs once per candidate global divisor, so its working
# set is smaller: the terms a weighted-average sum peels (basic products) sit at
# the very front of the term list.
SCALED_PAIR_WORKING_SET = 700
# Hard ceiling on how many global scales get the (expensive) pair search, so a
# large scale set cannot turn scaled-sum peeling into an hour-long scan.
MAX_SCALED_PAIR_SCALES = 18
MAX_TINY_TERMS = 260
# The third-term lookup window: a wide scaled interval over a large pool can
# hold many entries with the same first-instance value, so the cap must be
# generous (the all-instance interval check downstream filters false hits).
MAX_WINDOW = 400
MAX_PIECEWISE_MASKS = 64
PIECEWISE_SIGN_SCAN = 24_000
PIECEWISE_BRANCH_SCAN = 24_000
SHIFT_LIMIT = Fraction(8)
# Deterministic global work budget per solve() call: a fixed ceiling on the
# candidate combinations any one template may explore.  It bounds worst-case
# wall time without a clock, so the build stays reproducible -- the same
# inputs always explore the same first-N candidates in the same order.  Easy
# targets return long before the ceiling; only a genuine sum-of-many-products
# search (three-weight WACC) approaches it.
SOLVE_BUDGET = 45_000_000

# The piecewise search is *reserved*: it runs even after the shared budget is
# spent.  It is the only stage that can reach a conditional, it charges the
# shared budget nothing, and it is bounded on its own by MAX_PIECEWISE_MASKS,
# PIECEWISE_SIGN_SCAN and PIECEWISE_BRANCH_SCAN, so letting it run past
# exhaustion costs a fixed, small amount of work (measured: 0.8 s and 1.2 s on
# the two templates it recovers) and cannot make the build unbounded.  Without
# the reservation a template whose *sum* search saturates the budget loses its
# conditional search as collateral damage, which is a search-order artefact
# rather than a statement about the template.
PIECEWISE_IS_RESERVED = True

# Reserved budget for the structural-scale pre-pass (see
# `_search_structural_scales`): the three-term pair search under the literal
# 100 and 10^4, run *before* the derived scales and charged to this reserve
# instead of the shared SOLVE_BUDGET.  The shared budget is saved and restored
# around it, so every later stage sees exactly the budget it saw before the
# pre-pass existed: the pre-pass can add an answer, never remove one.  Four
# pair passes over a 700-term prefix charge about 1M units between them; the
# reserve leaves headroom for bucket hits on wide (half-up) intervals.
STRUCTURAL_SCALE_BUDGET = 6_000_000

ONE = Fraction(1)
HUNDRED = Fraction(100)


def _flip(low: Fraction, high: Fraction) -> Interval:
    return (low, high) if low <= high else (high, low)


def _to_float(value: Fraction) -> float | None:
    try:
        result = float(value)
    except (OverflowError, ValueError):
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


class Stage3Search:
    """One template's stage-3 search state, built lazily and reused per target."""

    def __init__(
        self,
        pool: Pool,
        param_vectors: Sequence[Vector],
        slot_vectors: Sequence[Vector],
        n: int,
        verify: Callable[[list[Any]], Vector | None],
    ) -> None:
        self.pool = pool
        self.n = n
        self.verify = verify
        self.qitems: list[Item] = []
        seen: set[Vector] = set()
        for index, vector in enumerate(param_vectors):
            if vector not in seen:
                seen.add(vector)
                self.qitems.append((vector, E.param(index)))
        for index, vector in enumerate(slot_vectors):
            if vector not in seen:
                seen.add(vector)
                self.qitems.append((vector, E.slot(index)))
        self._sorted = sorted(pool.order, key=lambda vector: (vector[0], vector[-1]))
        self._firsts = [vector[0] for vector in self._sorted]
        self._lasts = [vector[-1] for vector in self._sorted]
        # Float view of the pool's first-instance values, computed once: the
        # pair search's bucket prefilter rebuilds per call and this is its
        # dominant cost otherwise.
        self._firsts_f: list[float | None] = [
            _to_float(value) for value in self._firsts
        ]
        self._terms_iter: list[Item] | None = None
        self._terms_small: list[Item] | None = None
        self._shift_groups: list[list[Item]] | None = None
        self._pairsums: list[Item] | None = None
        self._transforms: list[Item] | None = None
        self._budget = SOLVE_BUDGET
        # True once a solve() has fallen through to the reserved piecewise
        # stage with the shared budget already spent.  Diagnostic only: it
        # records that the reservation mattered for this target.
        self.reserve_used = False

    # ------------------------------------------------------------------ util

    def _window(
        self,
        low: Fraction,
        high: Fraction,
        last_low: Fraction | None = None,
        last_high: Fraction | None = None,
    ) -> list[Vector]:
        low, high = _flip(low, high)
        start = bisect.bisect_left(self._firsts, low)
        stop = bisect.bisect_right(self._firsts, high)
        if stop - start > MAX_WINDOW:
            # A dense window (typically a first-instance value of exactly 0)
            # is refined by the *last* instance; the sort is (first, last), so
            # within an equal-first run a bisect on the last value is valid.
            if low != high or last_low is None or last_high is None:
                return []
            lasts = self._lasts[start:stop]
            inner_start = start + bisect.bisect_left(lasts, min(last_low, last_high))
            inner_stop = start + bisect.bisect_right(lasts, max(last_low, last_high))
            if inner_stop - inner_start > MAX_WINDOW:
                return []
            return self._sorted[inner_start:inner_stop]
        return self._sorted[start:stop]

    def _accept(
        self,
        expression: list[Any],
        check: Callable[[Vector], bool],
    ) -> list[Any] | None:
        recomputed = self.verify(expression)
        if recomputed is None or not check(recomputed):
            return None
        return expression

    # ----------------------------------------------------------- term sets

    def _shifty_items(self) -> list[Item]:
        """Values ``1+x``, ``1-x``, ``x-1`` for tax/discount shaped ``x``."""

        n = self.n
        ones = (ONE,) * n
        one_expr = E.const(ONE)
        hundred = (HUNDRED,) * n
        hundred_expr = E.const(HUNDRED)
        xs: list[Item] = []
        for vector, expression in self.qitems:
            xs.append((vector, expression))
            scaled = _apply("/", vector, hundred, n)
            if scaled is not None:
                xs.append((scaled, ["/", expression, hundred_expr]))
        for d_vector, d_expression in self.qitems:
            if not all(value == HUNDRED for value in d_vector):
                continue
            for q_vector, q_expression in self.qitems:
                if q_vector is d_vector:
                    continue
                scaled = _apply("/", q_vector, d_vector, n)
                if scaled is not None:
                    xs.append((scaled, ["/", q_expression, d_expression]))
        items: list[Item] = []
        seen: set[Vector] = set()
        for x_vector, x_expression in xs:
            if any(abs(value) > SHIFT_LIMIT for value in x_vector):
                continue
            for op, left, right, l_expr, r_expr in (
                ("+", ones, x_vector, one_expr, x_expression),
                ("-", ones, x_vector, one_expr, x_expression),
                ("-", x_vector, ones, x_expression, one_expr),
            ):
                vector = _apply(op, left, right, self.n)
                if vector is not None and vector not in seen:
                    seen.add(vector)
                    items.append((vector, [op, l_expr, r_expr]))
        return items

    def _build_terms(self) -> None:
        n = self.n
        hundred = (HUNDRED,) * n
        hundred_expr = E.const(HUNDRED)
        ten_thousand = (Fraction(10_000),) * n
        ten_thousand_expr = E.const(Fraction(10_000))
        seen: dict[Vector, list[Any]] = {}

        def put(store: list[Item], vector: Vector | None, expression: list[Any]) -> None:
            if vector is None or vector in seen:
                return
            seen[vector] = expression
            store.append((vector, expression))

        terms2: list[Item] = []
        for i, (a_vector, a_expression) in enumerate(self.qitems):
            for b_vector, b_expression in self.qitems[i:]:
                put(terms2, _apply("*", a_vector, b_vector, n), ["*", a_expression, b_expression])
            for b_vector, b_expression in self.qitems:
                put(terms2, _apply("/", a_vector, b_vector, n), ["/", a_expression, b_expression])

        terms3: list[Item] = []
        if len(self.qitems) <= 26:
            products = [
                item
                for item in terms2
                if item[1][0] == "*"
            ]
            for p_vector, p_expression in products:
                put(terms3, _apply("/", p_vector, hundred, n), ["/", p_expression, hundred_expr])
                put(
                    terms3,
                    _apply("/", p_vector, ten_thousand, n),
                    ["/", p_expression, ten_thousand_expr],
                )
                for q_vector, q_expression in self.qitems:
                    put(
                        terms3,
                        _apply("/", p_vector, q_vector, n),
                        ["/", p_expression, q_expression],
                    )
        triples: list[Item] = []
        if len(self.qitems) <= 15:
            # Lintner-style terms: speed * payout * average, over 100 or 10^4.
            for i, (a_vector, a_expression) in enumerate(self.qitems):
                for j in range(i, len(self.qitems)):
                    b_vector, b_expression = self.qitems[j]
                    ab = _apply("*", a_vector, b_vector, n)
                    if ab is None:
                        continue
                    ab_expression = ["*", a_expression, b_expression]
                    for c_vector, c_expression in self.qitems[j:]:
                        product = _apply("*", ab, c_vector, n)
                        if product is None:
                            continue
                        product_expression = ["*", ab_expression, c_expression]
                        put(triples, product, product_expression)
                        put(
                            triples,
                            _apply("/", product, hundred, n),
                            ["/", product_expression, hundred_expr],
                        )
                        put(
                            triples,
                            _apply("/", product, ten_thousand, n),
                            ["/", product_expression, ten_thousand_expr],
                        )

        shifty = self._shifty_items()
        tshift1: list[Item] = []
        for s_vector, s_expression in shifty:
            for q_vector, q_expression in self.qitems:
                put(tshift1, _apply("*", s_vector, q_vector, n), ["*", s_expression, q_expression])

        groups: list[list[Item]] = []
        tshift2: list[Item] = []
        if len(self.qitems) <= 26:
            for s_vector, s_expression in shifty:
                group: list[Item] = []
                for i, (a_vector, a_expression) in enumerate(self.qitems):
                    base = _apply("*", s_vector, a_vector, n)
                    if base is None:
                        continue
                    base_expression = ["*", s_expression, a_expression]
                    for b_vector, b_expression in self.qitems[i:]:
                        vector = _apply("*", base, b_vector, n)
                        if vector is None or vector in seen:
                            continue
                        expression = ["*", base_expression, b_expression]
                        seen[vector] = expression
                        item = (vector, expression)
                        tshift2.append(item)
                        group.append(item)
                if len(group) > 1:
                    groups.append(group)

        # min/max of two quantities, multiplied by a rate: tiered-fee shapes.
        minmax2: list[Item] = []
        minmax_leaves = self.qitems if len(self.qitems) <= 26 else []
        for i, (a_vector, a_expression) in enumerate(minmax_leaves):
            for b_vector, b_expression in self.qitems[i + 1 :]:
                for op in ("min", "max"):
                    m_vector = _apply(op, a_vector, b_vector, n)
                    if m_vector is None:
                        continue
                    m_expression = [op, a_expression, b_expression]
                    for q_vector, q_expression in self.qitems:
                        put(
                            minmax2,
                            _apply("*", m_vector, q_vector, n),
                            ["*", m_expression, q_expression],
                        )
                        scaled = _apply("/", q_vector, hundred, n)
                        if scaled is None:
                            continue
                        product = _apply("*", m_vector, scaled, n)
                        put(
                            minmax2,
                            product,
                            ["*", m_expression, ["/", q_expression, hundred_expr]],
                        )

        small = (terms2 + terms3 + triples + tshift1)[:MAX_PAIR_TERMS]
        big = (
            terms2 + terms3 + triples + tshift1 + minmax2 + tshift2
        )[:MAX_ONEPASS_TERMS]
        self._terms_small = small
        self._terms_iter = big
        self._shift_groups = groups

    def _terms(self) -> tuple[list[Item], list[Item], list[list[Item]]]:
        if self._terms_iter is None:
            self._build_terms()
        assert self._terms_iter is not None
        assert self._terms_small is not None
        assert self._shift_groups is not None
        return self._terms_iter, self._terms_small, self._shift_groups

    def _discount_powers(self) -> list[Item]:
        """Discount/growth factors ``(1 +/- x)^k`` for rate-shaped ``x``.

        Built directly from the rate-shaped shifts (``1 + r/100``, ``1 - T/100``)
        raised to +/-1..6, not fished out of the pool's 16k-entry power pass
        whose insertion order buries the real discount factor behind ratios of
        dollar amounts.  A term is kept only if its value varies across
        instances and stays factor-sized.
        """

        n = self.n
        bases: list[Item] = []
        seen_base: set[Vector] = set()
        for vector, expression in self._shifty_items():
            if vector in seen_base or len(set(vector)) == 1:
                continue
            if not all(Fraction(1, 2) <= value <= Fraction(2) for value in vector):
                continue
            seen_base.add(vector)
            bases.append((vector, expression))
        powers: list[Item] = []
        seen: set[Vector] = set()
        for base_vector, base_expression in bases:
            factor = base_vector
            factor_expr = base_expression
            inverse = tuple(Fraction(1) / value for value in base_vector)
            inverse_expr = ["^", base_expression, E.const(Fraction(-1))]
            for exponent in range(1, 7):
                power = tuple(value**exponent for value in base_vector)
                if all(Fraction(1, 8) <= abs(v) <= Fraction(8) for v in power):
                    key = power
                    if key not in seen:
                        seen.add(key)
                        powers.append(
                            (power, ["^", base_expression, E.const(Fraction(exponent))])
                        )
                ipower = tuple(value ** (-exponent) for value in base_vector)
                if all(Fraction(1, 8) <= abs(v) <= Fraction(8) for v in ipower):
                    if ipower not in seen:
                        seen.add(ipower)
                        powers.append(
                            (ipower, ["^", base_expression, E.const(Fraction(-exponent))])
                        )
        return powers

    def _tiny_pairsums(self) -> list[Item]:
        """Sums of two discounted terms, for four-term NPV chains.

        A discounted term is ``cf * (1 +/- x)^k`` for a rate-shaped shift; the
        pairwise sums of these are the shape an NPV forms one addition below
        the total, which no pairwise pool level reaches.
        """

        if self._pairsums is not None:
            return self._pairsums
        n = self.n
        tiny: list[Item] = []
        seen: set[Vector] = set()
        for p_vector, p_expression in self._discount_powers():
            for q_vector, q_expression in self.qitems:
                for op, expr in (
                    ("*", ["*", q_expression, p_expression]),
                ):
                    vector = _apply(op, q_vector, p_vector, n)
                    if vector is None or vector in seen:
                        continue
                    seen.add(vector)
                    tiny.append((vector, expr))
                    if len(tiny) >= MAX_TINY_TERMS:
                        break
                if len(tiny) >= MAX_TINY_TERMS:
                    break
            if len(tiny) >= MAX_TINY_TERMS:
                break
        sums: dict[Vector, list[Any]] = {}
        for i, (a_vector, a_expression) in enumerate(tiny):
            for b_vector, b_expression in tiny[i:]:
                vector = _apply("+", a_vector, b_vector, n)
                if vector is not None and vector not in sums:
                    sums[vector] = ["+", a_expression, b_expression]
        self._pairsums = list(sums.items())
        return self._pairsums

    def _transform_items(self) -> list[Item]:
        """Divisors/multipliers: quantities, sums of them, shifts and powers."""

        if self._transforms is not None:
            return self._transforms
        n = self.n
        items: list[Item] = []
        seen: set[Vector] = set()

        def put(vector: Vector | None, expression: list[Any]) -> None:
            if vector is None or vector in seen:
                return
            if any(value == 0 for value in vector):
                return
            seen.add(vector)
            items.append((vector, expression))

        put((HUNDRED,) * n, E.const(HUNDRED))
        put((Fraction(10_000),) * n, E.const(Fraction(10_000)))
        for vector, expression in self.qitems:
            put(vector, expression)
            put(
                _apply("/", vector, (HUNDRED,) * n, n),
                ["/", expression, E.const(HUNDRED)],
            )
        for i, (a_vector, a_expression) in enumerate(self.qitems):
            for b_vector, b_expression in self.qitems[i + 1 :]:
                put(_apply("+", a_vector, b_vector, n), ["+", a_expression, b_expression])
        if len(self.qitems) <= 12:
            for i, (a_vector, a_expression) in enumerate(self.qitems):
                for j in range(i + 1, len(self.qitems)):
                    b_vector, b_expression = self.qitems[j]
                    ab = _apply("+", a_vector, b_vector, n)
                    if ab is None:
                        continue
                    ab_expression = ["+", a_expression, b_expression]
                    for c_vector, c_expression in self.qitems[j + 1 :]:
                        put(
                            _apply("+", ab, c_vector, n),
                            ["+", ab_expression, c_expression],
                        )
        for vector, expression in self._shifty_items():
            put(vector, expression)
        for vector in self.pool.marked("powers", "geometric")[:200]:
            put(vector, self.pool.by_key[vector])
        self._transforms = items[:MAX_TRANSFORMS]
        return self._transforms

    # ------------------------------------------------------------- searches

    def solve(
        self,
        intervals: Sequence[Interval],
        check: Callable[[Vector], bool],
        allow_piecewise: bool = True,
    ) -> list[Any] | None:
        # Ordered cheapest-and-highest-yield first, so the common cases return
        # before the expensive last-resort scans ever start, and the shared
        # budget caps whatever remains.
        stages: list[Callable[[], list[Any] | None]] = [
            lambda: self._search_one_pass(intervals, check),
            lambda: self._search_transforms(intervals, check, invert=False),
            lambda: self._search_pairsums(intervals, check),
            lambda: self._search_scaled_sums(intervals, check),
            lambda: self._search_pairs(intervals, check),
            lambda: self._search_transforms(intervals, check, invert=True),
        ]
        for stage in stages:
            found = stage()
            if found is not None:
                return found
            if self._budget <= 0:
                break
        if not allow_piecewise:
            return None
        # Reserved stage: see PIECEWISE_IS_RESERVED.  A sum search that
        # saturates the shared budget must not silently cancel the conditional
        # search, which is separately capped and costs about a second.
        self.reserve_used = self._budget <= 0
        return self._search_piecewise(intervals, check)

    def _core_scales(self) -> tuple[list[Item], int]:
        """Global scales a whole sum is multiplied or divided by.

        ``(w1*s1 + w2*s2 + w3*s3) / 100``, ``sum(v_i b_i) / sum(v_i)``,
        ``wP * (... per-unit-of-wP sum ...)`` and a binomial's ``/(1 + r)``
        all need the sum peeled *after* undoing a global factor: the hundreds,
        the question's value sums (triples first: that is ``V = E + P + D``),
        the solved slots, then growth factors.  Returns the scales and how
        many of them earn the expensive pair-level search.
        """

        n = self.n
        items: list[Item] = [
            ((HUNDRED,) * n, E.const(HUNDRED)),
            ((Fraction(10_000),) * n, E.const(Fraction(10_000))),
        ]
        seen = {vector for vector, _ in items}

        def put(store: list[Item], vector: Vector, expression: list[Any], cap: int) -> None:
            if vector in seen or len(store) >= cap:
                return
            if any(value == 0 for value in vector):
                return
            seen.add(vector)
            store.append((vector, expression))

        slots: list[Item] = []
        for vector, expression in self.qitems:
            if expression[0] == "s":
                put(slots, vector, expression, 6)
        # Value sums (``V = E + P + D``): the denominator of a weighted average.
        # Built directly here, not via the transform list, so they exist even
        # when the parameter count is above the transform triple threshold, and
        # ordered so sums of the largest quantities (the balance-sheet values a
        # WACC divides by) come first.  Structural constants (the literal 100,
        # 10000, 1 a question writes for percentages) are never summed into a
        # value total, so excluding them keeps them from flooding the triples.
        structural = {Fraction(1), Fraction(100), Fraction(1_000), Fraction(10_000)}
        big_quantities = sorted(
            (
                (vector, expression)
                for vector, expression in self.qitems
                if all(value > 0 for value in vector)
                and not all(value in structural for value in vector)
            ),
            key=lambda item: -sum(abs(v) for v in item[0]),
        )[:8]
        pair_sums: list[Item] = []
        triples: list[Item] = []
        for i, (a_vector, a_expression) in enumerate(big_quantities):
            for j in range(i + 1, len(big_quantities)):
                b_vector, b_expression = big_quantities[j]
                ab = _apply("+", a_vector, b_vector, n)
                if ab is not None:
                    put(pair_sums, ab, ["+", a_expression, b_expression], 30)
                    ab_expr = ["+", a_expression, b_expression]
                    for k in range(j + 1, len(big_quantities)):
                        c_vector, c_expression = big_quantities[k]
                        abc = _apply("+", ab, c_vector, n)
                        if abc is not None:
                            put(triples, abc, ["+", ab_expr, c_expression], 60)
        shifty: list[Item] = []
        for vector, expression in self._shifty_items():
            put(shifty, vector, expression, 20)
        # Order the scales that earn the pair search by how likely they are to
        # be a weighted-average denominator: value totals first (triples, then
        # pairs), then the hundreds, then solved slots -- and cap how many run.
        # (The hundreds also get a reserved pre-pass of their own; see
        # `_search_structural_scales`.)
        priority = (triples + pair_sums + items + slots)[:MAX_SCALED_PAIR_SCALES]
        pair_enabled = len(priority)
        tail = shifty
        return priority + tail, pair_enabled

    def _search_structural_scales(
        self, intervals: Sequence[Interval], check: Callable[[Vector], bool]
    ) -> list[Any] | None:
        """Reserved pre-pass: the pair search under the literal 100 and 10^4.

        A percent-denominated weighted sum -- ``S = (w1*s1 + w2*s2 + w3*s3) /
        100``, which `var.multi_asset` states in those words -- is the commonest
        scaled-sum shape in the corpus.  On a template with many parameters the
        value-sum triples alone fill MAX_SCALED_PAIR_SCALES, so in the derived
        scale list the literal 100 never gets a pair search at all.

        Moving the hundreds to the front of that list is *not* safe: it spends
        shared budget before the value totals a three-weight WACC divides by,
        and a measured rebuild lost `wacc.preferred_capm_wacc` that way.  So the
        hundreds run here instead, on STRUCTURAL_SCALE_BUDGET, with the shared
        budget saved and restored around the pass.  Every stage after it sees
        the budget it saw before this pass existed; the pass can only add an
        answer, never cost one.
        """

        n = self.n
        shared = self._budget
        self._budget = STRUCTURAL_SCALE_BUDGET
        try:
            for constant in (HUNDRED, Fraction(10_000)):
                d_expression = E.const(constant)
                for mode, undo in (("*", "/"), ("/", "*")):
                    if mode == "*":
                        scaled = [
                            _flip(low * constant, high * constant)
                            for low, high in intervals
                        ]
                    else:
                        scaled = [
                            _flip(low / constant, high / constant)
                            for low, high in intervals
                        ]

                    def wrap(
                        expression: list[Any], d=d_expression, u=undo
                    ) -> list[Any]:
                        return [u, expression, d]

                    found = self._search_pairs(
                        scaled, check, wrap=wrap, limit=SCALED_PAIR_WORKING_SET
                    )
                    if found is not None:
                        return found
                    if self._budget <= 0:
                        return None
            return None
        finally:
            self.structural_spent = STRUCTURAL_SCALE_BUDGET - self._budget
            self._budget = shared

    def _search_scaled_sums(
        self, intervals: Sequence[Interval], check: Callable[[Vector], bool]
    ) -> list[Any] | None:
        """Sum peeling on ``T * D`` and ``T / D`` for global scales ``D``.

        Only the three-term pair search runs on the scaled target: a two-term
        scaled sum ``(a + b) / D`` distributes to ``a/D + b/D``, which the
        unscaled one-pass already finds, so running one-pass here as well is
        pure waste (and it cannot find a three-term sum anyway).
        """

        found = self._search_structural_scales(intervals, check)
        if found is not None:
            return found
        scales, pair_enabled = self._core_scales()
        for position, (d_vector, d_expression) in enumerate(scales):
            if position >= pair_enabled:
                break
            for mode, undo in (("*", "/"), ("/", "*")):
                if mode == "*":
                    scaled = [
                        _flip(low * d_vector[i], high * d_vector[i])
                        for i, (low, high) in enumerate(intervals)
                    ]
                else:
                    scaled = [
                        _flip(low / d_vector[i], high / d_vector[i])
                        for i, (low, high) in enumerate(intervals)
                    ]

                def wrap(
                    expression: list[Any], d=d_expression, u=undo
                ) -> list[Any]:
                    return [u, expression, d]

                found = self._search_pairs(
                    scaled, check, wrap=wrap, limit=SCALED_PAIR_WORKING_SET
                )
                if found is not None:
                    return found
                if self._budget <= 0:
                    return None
        return None

    def _search_transforms(
        self,
        intervals: Sequence[Interval],
        check: Callable[[Vector], bool],
        *,
        invert: bool,
    ) -> list[Any] | None:
        """Solve ``T * D`` or ``T / D`` instead of ``T``, then divide back.

        The cheap phase (``invert=False``) only looks the transformed target up
        directly; the expensive phase adds a light meet-in-the-middle inversion
        over a shallow left set.
        """

        n = self.n
        transforms = self._transform_items()
        lefts: list[Vector] = []
        if invert:
            lefts = (
                self.pool.order[:TRANSFORM_LIGHT_LEFTS]
                + self.pool.marked("powers")[:TRANSFORM_LIGHT_LEFTS]
                + self.pool.marked("geometric")[:200]
            )
            transforms = transforms[:180]
        for d_vector, d_expression in transforms:
            for mode in ("*", "/"):
                if mode == "*":
                    scaled = [
                        _flip(low * d_vector[i], high * d_vector[i])
                        for i, (low, high) in enumerate(intervals)
                    ]
                    undo = "/"
                else:
                    scaled = [
                        _flip(low / d_vector[i], high / d_vector[i])
                        for i, (low, high) in enumerate(intervals)
                    ]
                    undo = "*"

                def in_scaled(vector: Vector) -> bool:
                    return all(
                        scaled[i][0] <= vector[i] <= scaled[i][1] for i in range(n)
                    )

                low0, high0 = scaled[0]
                last_low, last_high = scaled[-1]
                if not invert:
                    for candidate in self._window(low0, high0, last_low, last_high):
                        if not in_scaled(candidate):
                            continue
                        expression = [undo, self.pool.by_key[candidate], d_expression]
                        accepted = self._accept(expression, check)
                        if accepted is not None:
                            return accepted
                    continue
                # Light inversion on the transformed target.
                self._budget -= len(lefts)
                if self._budget <= 0:
                    return None
                for left in lefts:
                    left_expression = self.pool.by_key[left]
                    value = left[0]
                    last = left[-1]
                    for candidate in self._window(
                        low0 - value, high0 - value, last_low - last, last_high - last
                    ):
                        combined = _apply("+", left, candidate, n)
                        if combined is None or not in_scaled(combined):
                            continue
                        expression = [
                            undo,
                            ["+", left_expression, self.pool.by_key[candidate]],
                            d_expression,
                        ]
                        accepted = self._accept(expression, check)
                        if accepted is not None:
                            return accepted
                    if value != 0 and all(v != 0 for v in left):
                        for candidate in self._window(
                            low0 / value,
                            high0 / value,
                            last_low / last,
                            last_high / last,
                        ):
                            combined = _apply("*", left, candidate, n)
                            if combined is None or not in_scaled(combined):
                                continue
                            expression = [
                                undo,
                                ["*", left_expression, self.pool.by_key[candidate]],
                                d_expression,
                            ]
                            accepted = self._accept(expression, check)
                            if accepted is not None:
                                return accepted
        return None

    def _search_one_pass(
        self,
        intervals: Sequence[Interval],
        check: Callable[[Vector], bool],
        wrap: Callable[[list[Any]], list[Any]] | None = None,
    ) -> list[Any] | None:
        """``T = term + pool`` and ``T = pool - term`` over the big term set."""

        n = self.n
        big, _, _ = self._terms()

        def in_target(vector: Vector) -> bool:
            return all(
                intervals[i][0] <= vector[i] <= intervals[i][1] for i in range(n)
            )

        low0, high0 = intervals[0]
        last_low, last_high = intervals[-1]
        best: list[Any] | None = None
        best_size = 10**9
        self._budget -= len(big)
        for a_vector, a_expression in big:
            value = a_vector[0]
            last = a_vector[-1]
            for op, low, high, w_last_low, w_last_high in (
                ("+", low0 - value, high0 - value, last_low - last, last_high - last),
                ("rsub", low0 + value, high0 + value, last_low + last, last_high + last),
            ):
                for candidate in self._window(low, high, w_last_low, w_last_high):
                    if op == "+":
                        combined = _apply("+", a_vector, candidate, n)
                        expression = ["+", a_expression, self.pool.by_key[candidate]]
                    else:
                        combined = _apply("-", candidate, a_vector, n)
                        expression = ["-", self.pool.by_key[candidate], a_expression]
                    if combined is None or not in_target(combined):
                        continue
                    size = E.size(expression)
                    if size >= best_size:
                        continue
                    accepted = self._accept(
                        expression if wrap is None else wrap(expression), check
                    )
                    if accepted is not None:
                        best = accepted
                        best_size = size
        return best

    def _search_pairsums(
        self, intervals: Sequence[Interval], check: Callable[[Vector], bool]
    ) -> list[Any] | None:
        """Four-term chains: two discounted terms + two discounted terms/pool."""

        n = self.n
        pairsums = self._tiny_pairsums()
        if not pairsums:
            return None
        sums_sorted = sorted(pairsums, key=lambda item: item[0][0])
        sum_firsts = [item[0][0] for item in sums_sorted]

        def in_target(vector: Vector) -> bool:
            return all(
                intervals[i][0] <= vector[i] <= intervals[i][1] for i in range(n)
            )

        low0, high0 = intervals[0]
        last_low, last_high = intervals[-1]
        for s_vector, s_expression in pairsums:
            low = low0 - s_vector[0]
            high = high0 - s_vector[0]
            for candidate in self._window(
                low, high, last_low - s_vector[-1], last_high - s_vector[-1]
            ):
                combined = _apply("+", s_vector, candidate, n)
                if combined is None or not in_target(combined):
                    continue
                expression = ["+", s_expression, self.pool.by_key[candidate]]
                accepted = self._accept(expression, check)
                if accepted is not None:
                    return accepted
            start = bisect.bisect_left(sum_firsts, low)
            stop = bisect.bisect_right(sum_firsts, high)
            if stop - start > MAX_WINDOW:
                continue
            for other_vector, other_expression in sums_sorted[start:stop]:
                combined = _apply("+", s_vector, other_vector, n)
                if combined is None or not in_target(combined):
                    continue
                expression = ["+", s_expression, other_expression]
                accepted = self._accept(expression, check)
                if accepted is not None:
                    return accepted
        return None

    def _search_pairs(
        self,
        intervals: Sequence[Interval],
        check: Callable[[Vector], bool],
        wrap: Callable[[list[Any]], list[Any]] | None = None,
        limit: int = PAIR_WORKING_SET,
    ) -> list[Any] | None:
        """Three-term sums: two terms from the small set, third from the pool."""

        n = self.n
        _, small, groups = self._terms()
        small = small[:limit]

        def in_target(vector: Vector) -> bool:
            return all(
                intervals[i][0] <= vector[i] <= intervals[i][1] for i in range(n)
            )

        low0, high0 = intervals[0]
        last_low, last_high = intervals[-1]
        width = high0 - low0

        # Float prefilter over the pool's first-instance values.
        target_low = _to_float(low0)
        width_f = _to_float(width)
        if target_low is None or width_f is None:
            return None
        scale = max(1.0, abs(target_low))
        bucket_size = max(scale * 1e-12, width_f)
        buckets: dict[int, bool] = {}
        inv_bucket = 1.0 / bucket_size
        for value_f in self._firsts_f:
            if value_f is None:
                continue
            quotient = value_f * inv_bucket
            if -9e15 < quotient < 9e15:
                buckets[int(quotient)] = True

        def annotate(items: Sequence[Item]) -> list[tuple[Vector, list[Any], float]]:
            annotated = []
            for vector, expression in items:
                first = _to_float(vector[0])
                if first is not None:
                    annotated.append((vector, expression, first))
            return annotated

        def run(
            pairs: Sequence[tuple[Vector, list[Any], float]]
        ) -> list[Any] | None:
            for i, (a_vector, a_expression, a_first) in enumerate(pairs):
                self._budget -= len(pairs) - i
                if self._budget <= 0:
                    return None
                remainder = target_low - a_first
                for b_vector, b_expression, b_first in pairs[i:]:
                    residual_f = remainder - b_first
                    quotient = residual_f / bucket_size
                    if not -9e15 < quotient < 9e15:
                        continue
                    key = int(quotient)
                    if not (
                        buckets.get(key)
                        or buckets.get(key - 1)
                        or buckets.get(key + 1)
                    ):
                        continue
                    # A bucket hit triggers the expensive exact path (window
                    # bisect + verify), so charge the budget more for it.
                    self._budget -= 40
                    partial = _apply("+", a_vector, b_vector, n)
                    if partial is None:
                        continue
                    low = low0 - partial[0]
                    high = high0 - partial[0]
                    for candidate in self._window(
                        low, high, last_low - partial[-1], last_high - partial[-1]
                    ):
                        combined = _apply("+", partial, candidate, n)
                        if combined is None or not in_target(combined):
                            continue
                        expression = [
                            "+",
                            ["+", a_expression, b_expression],
                            self.pool.by_key[candidate],
                        ]
                        accepted = self._accept(
                            expression if wrap is None else wrap(expression),
                            check,
                        )
                        if accepted is not None:
                            return accepted
            return None

        found = run(annotate(small))
        if found is not None:
            return found
        for group in groups:
            found = run(annotate(group))
            if found is not None:
                return found
        return None

    def _search_piecewise(
        self, intervals: Sequence[Interval], check: Callable[[Vector], bool]
    ) -> list[Any] | None:
        """``if cond > 0 -> A else -> B`` with a sign-separating condition."""

        n = self.n
        _, small, _ = self._terms()

        def matches_at(vector: Vector, index: int) -> bool:
            return intervals[index][0] <= vector[index] <= intervals[index][1]

        # Candidate branches: quantities, zero, small products.
        branch_items: list[Item] = list(self.qitems)
        branch_items.append(((Fraction(0),) * n, E.const(Fraction(0))))
        branch_items.extend(small[:1_000])
        for vector in self.pool.order[:PIECEWISE_BRANCH_SCAN]:
            branch_items.append((vector, self.pool.by_key[vector]))

        masks: dict[tuple[bool, ...], Item] = {}
        for vector, expression in branch_items:
            mask = tuple(matches_at(vector, index) for index in range(n))
            if not any(mask) or all(mask):
                continue
            if mask not in masks or E.size(expression) < E.size(masks[mask][1]):
                masks[mask] = (vector, expression)
            if len(masks) >= MAX_PIECEWISE_MASKS:
                break
        if not masks:
            return None

        # Sign-pattern index over a bounded prefix of the pool.
        sign_scan = (
            self.pool.order[:PIECEWISE_SIGN_SCAN]
            + self.pool.marked("additive")[:8_000]
            + self.pool.marked("minmax_leaf")[:4_000]
        )
        gt_index: dict[tuple[bool, ...], list[Any]] = {}
        ge_index: dict[tuple[bool, ...], list[Any]] = {}
        for vector in sign_scan:
            expression = self.pool.by_key[vector]
            gt_key = tuple(value > 0 for value in vector)
            ge_key = tuple(value >= 0 for value in vector)
            if gt_key not in gt_index or E.size(expression) < E.size(gt_index[gt_key]):
                gt_index[gt_key] = expression
            if ge_key not in ge_index or E.size(expression) < E.size(ge_index[ge_key]):
                ge_index[ge_key] = expression

        ordered = sorted(
            masks.items(), key=lambda item: (-sum(item[0]), E.size(item[1][1]))
        )
        for mask, (then_vector, then_expression) in ordered:
            inverted = tuple(not flag for flag in mask)
            other_indexes = [index for index in range(n) if not mask[index]]
            other: Item | None = None
            for vector, expression in branch_items:
                if all(matches_at(vector, index) for index in other_indexes):
                    if other is None or E.size(expression) < E.size(other[1]):
                        other = (vector, expression)
            if other is None:
                continue
            for head, index_map, key, swap in (
                ("ifgt", gt_index, mask, False),
                ("ifge", ge_index, mask, False),
                ("ifgt", gt_index, inverted, True),
                ("ifge", ge_index, inverted, True),
            ):
                condition = index_map.get(key)
                if condition is None:
                    continue
                then_branch = other[1] if swap else then_expression
                else_branch = then_expression if swap else other[1]
                expression = [head, condition, then_branch, else_branch]
                accepted = self._accept(expression, check)
                if accepted is not None:
                    return accepted
        return None

"""Deterministic rule engine for FinReason Task 3 (Financial Audit Verification).

Reads one case's ``query`` string and nothing else. No model calls, no
network, no lookup keyed to a filing, company, accession number or case id.
The engine never reads a DQC rule label: it re-runs the three public XBRL US
data-quality rules on the filing text it is given and reports the finding.

Rules (public XBRL US DQC rule logic, ``dqc_us_rules`` XULE source, US 2026):

* ``calc``  DQC_US_0126 (FS Calculation Check with Non Dimensional Data).
  Runs on "- Statement -" networks that are not statement tables and not
  equity-type statements ($STATEMENT_PRES_NETWORKS minus $STATEMENT_CUBES). The
  parent fact is the one whose decimals equal the statement's most frequent
  decimals; children are added non-dimensionally, weighted; the finding needs
  a difference beyond ``tolerance_for_decimals(parent, sum, addends + 1)``.
  extracted = parent fact, calculated = weighted sum of child facts.
* ``dim``   DQC_US_0117 (Financial Statement Tables Dimensional Cross Check).
  Runs on statement tables ($STATEMENT_CUBES), monetary facts, 11 checked axes.
  Members come from the table's own domain tree, nested members whose ancestor
  carries a value are skipped, the FASB 606 revenue exception applies, and the
  finding needs ``tolerance_for_decimals_comp(sum, total, min_decimals, 2)``.
  extracted = default (no-dimension) fact or 0, calculated = member sum.
* ``neg``   DQC_US_0015 (Negative Values). An element on the rule's
  non-negative list has a negative value outside the rule's member and axis
  exclusions. extracted = the negative fact, calculated = its magnitude.

Decision (``predict``): a rule finding inside that rule's scope wins (tier 1);
then evidence the rule scope or tolerance would not report (tiers 2 to 5); then
"0","0". The trace records the tier, so low-evidence answers are visible.

Variant switches (``configure``): with every switch off the engine is V0, the
engine whose files were uploaded on 2026-10-02, byte for byte. Each later fix
sits behind its own switch so that one Development upload measures it alone:

* ``a10093``          DQC_US_0117 assertion 10093 (a one-member total against
                      its breakdown on a second axis), used when the case has no
                      other rule finding in scope.
* ``total_required``  DQC_US_0117 assertion 9574 needs a reported total: its
                      rule focus is the total fact, so a breakdown whose total
                      is not reported is not a finding of that assertion.
* ``neg_policy``      which tested negative fact answers a DQC_US_0015 case when
                      several qualify. The rule reports every one of them and
                      gives no ranking, so this is a measurement switch, not a
                      rule fix. It is a pair (prefer, order): prefer is
                      ``nondim`` (the non-dimensional fact when it is negative),
                      ``dim`` (dimensional facts when there are any) or ``none``;
                      order picks among the rest: ``first`` or ``last`` in
                      document order, ``maxabs`` or ``minabs`` (largest or
                      smallest magnitude, first in document order on ties).
                      V0 is (nondim, first).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import re

from xbrl import (
    CalcArc,
    Context,
    DimensionalRole,
    Fact,
    Target,
    fmt_decimal,
    instance_namespaces,
    parse_calc,
    parse_contexts,
    parse_definition,
    parse_facts,
    parse_question,
    parse_taxonomy,
    role_titles,
    split_sections,
)

ZERO = Decimal(0)
INF = 99  # internal encoding of decimals="INF"

# --------------------------------------------------------------------------- rule constants
# DQC_US_0117: the checked axes (DQC_0117.xule, both assertions).
CHECKED_AXES = {
    "StatementClassOfStockAxis",
    "ProductOrServiceAxis",
    "PropertyPlantAndEquipmentByTypeAxis",
    "LongtermDebtTypeAxis",
    "RelatedPartyTransactionsByRelatedPartyAxis",
    "StatementBusinessSegmentsAxis",
    "FinancialInstrumentAxis",
    "LimitedPartnersCapitalAccountByClassAxis",
    "PartnerTypeOfPartnersCapitalAccountAxis",
    "FiniteLivedIntangibleAssetsByMajorClassAxis",
    "InformationByCategoryOfDebtSecurityAxis",
}
# DQC_US_0117 FASB 606 revenue exception (DQC_0117.xule, assertion 9574).
REVENUE_606 = {"RevenueFromContractWithCustomerExcludingAssessedTax",
               "RevenueFromContractWithCustomerIncludingAssessedTax"}

# $STATEMENT_CUBES (constant.xule): statement tables 0117 checks and 0126 skips.
CUBE_EXCLUDED_URI = ("parenthetical", "equity", "deficit", "stockholders", "capital", "investment", "changes",
                     "shareholder", "convertible", "preferred", "temporaryequity", "redeemable",
                     "netproceedsfromallsources", "membersinterest")
CUBE_EXCLUDED_DESC = ("schedule iii", "schedule iv")
CUBE_EXCLUDED_TABLES = {"ScheduleOfInvestmentsTable", "SummaryOfInvestmentHoldingsTable",
                        "InvestmentsSoldNotYetPurchasedTable", "OpenOptionContractsWrittenTable",
                        "OpenFuturesContractTable", "OpenForwardForeignCurrencyContractTable", "OpenSwapContractTable"}
# $STATEMENT_PRES_NETWORKS (constant.xule): the statements 0126 checks.
PRES_EXCLUDED_URI = ("parenthetical", "equity", "deficit", "stockholders", "capital", "investment", "change",
                     "shareholder", "convertible", "preferred", "temporaryequity", "redeemable",
                     "netproceedsfromallsources", "membersinterest", "membershipinterest", "highlights",
                     "employee", "ebp")
PRES_EXCLUDED_DESC = ("schedule iii", "schedule iv", "net worth")

# DQC_US_0015 exclusions (constant-us-gaap.xule): a negative value is allowed
# on these member-name substrings, members, axes and axis/member pairs.
NON_NEG_EXCLUDED_SUBSTRINGS = ("adjust", "consolidat", "eliminat", "netting", "reconcili", "reclass",
                               "basisswap", "unfunded")
NON_NEG_EXCLUDED_MEMBERS = {
    "CorporateNonSegmentMember",
    "FairValueConcentrationOfRiskMarketRiskManagementEffectsOnIncomeOrNetAssetsMember",
    "AccumulatedNetGainLossFromDesignatedOrQualifyingCashFlowHedgesMember",
    "AccumulatedNetUnrealizedInvestmentGainLossMember",
    "DeferredDerivativeGainLossMember",
    "AboveMarketLeasesMember",
    "NewAccountingPronouncementEarlyAdoptionEffectMember",
    "UnallocatedFinancingReceivablesMember",
    "DifferenceBetweenRevenueGuidanceInEffectBeforeAndAfterTopic606Member",
}
NON_NEG_EXCLUDED_AXES = {
    "StatementEquityComponentsAxis",
    "ErrorCorrectionsAndPriorPeriodAdjustmentsRestatementByRestatementPeriodAndAmountAxis",
    "AdjustmentsForChangeInAccountingPrincipleAxis",
    "AdjustmentsForNewAccountingPronouncementsAxis",
    "ProspectiveAdoptionOfNewAccountingPronouncementsAxis",
    "QuantifyingMisstatementInCurrentYearFinancialStatementsByNatureOfErrorAxis",
    "PartnerCapitalComponentsAxis",
    "ChangeInAccountingEstimateByTypeAxis",
    "PartnerTypeOfPartnersCapitalAccountAxis",
    "StatementBusinessSegmentsAxis",
    "InvestmentIdentifierAxis",
    "IncomeTaxEffectChangeInLawAxis",
}
NON_NEG_EXCLUDED_AXIS_MEMBERS = {
    "StatementBusinessSegmentsAxis": {"CorporateAndOtherMember", "CorporateMember", "AllOtherSegmentsMember"},
    "ConsolidatedEntitiesAxis": {"ParentCompanyMember", "SubsidiariesMember", "GuarantorSubsidiariesMember",
                                 "NonGuarantorSubsidiariesMember", "SubsidiaryIssuerMember"},
    "FairValueByMeasurementBasisAxis": {"ChangeDuringPeriodFairValueDisclosureMember"},
}
# The DQC_US_0015 list covers US GAAP and SRT elements only.
NON_NEG_NAMESPACES = ("fasb.org/us-gaap/", "fasb.org/srt/")

# --------------------------------------------------------------------------- variant switches
FIX_10093 = "a10093"
FIX_TOTAL_REQUIRED = "total_required"
KNOWN_FIXES = (FIX_10093, FIX_TOTAL_REQUIRED)
NEG_PREFER = ("nondim", "dim", "none")
NEG_ORDER = ("first", "last", "maxabs", "minabs")
NEG_V0 = ("nondim", "first")
# name -> (fixes, DQC_US_0015 choice policy). V0 is the uploaded engine.
# V1 and V2 are rule fixes (cumulative); M1..M3 are DQC_US_0015 measurement
# probes on top of V0 that have no rule basis (see VARIANTS.md): the last
# tested negative in document order, the largest and the smallest magnitude,
# each treating the non-dimensional fact like any other.
VARIANTS = {
    "V0": ((), NEG_V0),
    "V1": ((FIX_10093,), NEG_V0),
    "V2": ((FIX_10093, FIX_TOTAL_REQUIRED), NEG_V0),
    "M1": ((), ("none", "last")),
    "M2": ((), ("none", "maxabs")),
    "M3": ((), ("none", "minabs")),
}
FIXES: frozenset = frozenset()
NEG_POLICY = NEG_V0


def configure(fixes=(), neg_policy=NEG_V0) -> None:
    """Set the variant switches for this process (all off = V0)."""
    global FIXES, NEG_POLICY
    neg_policy = tuple(neg_policy)
    unknown = set(fixes) - set(KNOWN_FIXES)
    if unknown or len(neg_policy) != 2 or neg_policy[0] not in NEG_PREFER or neg_policy[1] not in NEG_ORDER:
        raise ValueError(f"unknown switch: {sorted(unknown) or neg_policy}")
    FIXES = frozenset(fixes)
    NEG_POLICY = neg_policy


def configure_variant(name: str) -> None:
    fixes, policy = VARIANTS[name]
    configure(fixes, policy)


_RES = Path(__file__).resolve().parent / "resources"


def _load_names(fn: str) -> frozenset:
    try:
        with open(_RES / fn, encoding="utf-8") as fh:
            return frozenset(l.strip() for l in fh if l.strip() and not l.startswith("#"))
    except OSError:
        return frozenset()


# Elements DQC_US_0015 treats as never negative (public rule resource lists).
NON_NEG_ELEMENTS = _load_names("dqc_0015_non_negative_elements.txt")


def non_neg_applies(ctx: Context) -> bool:
    """True when DQC_US_0015 would test a fact in this context (no exclusion hits)."""
    if not ctx.dims:
        return True
    for axis, member in ctx.dims:
        al, ml = axis.split(":")[-1], member.split(":")[-1]
        if member.startswith("typed:"):
            ml = ""
        if any(sub in ml.lower() for sub in NON_NEG_EXCLUDED_SUBSTRINGS):
            return False
        if ml in NON_NEG_EXCLUDED_MEMBERS or al in NON_NEG_EXCLUDED_AXES:
            return False
        if ml in NON_NEG_EXCLUDED_AXIS_MEMBERS.get(al, ()):
            return False
    return True


@dataclass
class Prediction:
    extracted_value: str
    calculated_value: str
    mechanism: str
    detail: str = ""
    tier: int = 0
    confidence: str = ""
    competing: str = ""


def _local(qname: str) -> str:
    return qname.split(":")[-1]


def _dec(text: Optional[str]) -> Optional[int]:
    """``decimals`` attribute as an int; INF is encoded as ``INF``."""
    if text is None:
        return None
    t = text.strip().upper()
    if t == "INF":
        return INF
    try:
        return int(t)
    except ValueError:
        return None


def _round(x: Decimal, places: int) -> Decimal:
    return x.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN) if -30 <= places < INF else x


def tolerance_for_decimals(left: Decimal, left_dec: Optional[int], right: Decimal, right_dec: Optional[int],
                           factor: int) -> bool:
    """lib/functions.xule ``tolerance_for_decimals``, used by DQC_US_0126.

    A missing left decimals counts as INF; a missing right decimals takes the
    left one (a computed sum carries no decimals). Both sides are rounded to
    the coarser decimals; True when they differ by more than factor x 10^-d."""
    ld = INF if left_dec is None else left_dec
    rd = ld if right_dec is None else right_dec
    d = min(ld, rd)
    if d >= INF:
        return left != right
    tol = Decimal(1).scaleb(-d) * factor
    return abs(_round(left, d) - _round(right, d)) > tol


def tolerance_for_decimals_comp(left: Decimal, left_dec: Optional[int], right: Decimal, right_dec: Optional[int],
                                min_decimals: Optional[int], factor: int) -> bool:
    """lib/functions.xule ``tolerance_for_decimals_comp``, used by DQC_US_0117.

    Missing or INF decimals on either side take ``min_decimals`` (capped at 5)."""
    adj = 5 if (min_decimals is None or min_decimals >= INF or min_decimals > 5) else min_decimals
    ld = adj if (left_dec is None or left_dec >= INF) else left_dec
    rd = adj if (right_dec is None or right_dec >= INF) else right_dec
    d = min(ld, rd)
    tol = Decimal(1).scaleb(-d) * factor
    return abs(_round(left, d) - _round(right, d)) > tol


# --------------------------------------------------------------------------- one case


class Case:
    """All parsed state for one query."""

    def __init__(self, query: str):
        self.sections = split_sections(query)
        self.target: Optional[Target] = parse_question(self.sections["question"])
        self.contexts: Dict[str, Context] = parse_contexts(self.sections["instance"])
        self.facts: List[Fact] = parse_facts(self.sections["instance"])
        self.ns: Dict[str, str] = instance_namespaces(self.sections["instance"])
        self.by_local: Dict[str, List[Fact]] = defaultdict(list)
        for f in self.facts:
            self.by_local[f.local].append(f)
        self._arcs: Optional[List[CalcArc]] = None
        self._droles: Optional[List[DimensionalRole]] = None
        self._titles: Optional[Dict[str, str]] = None
        self._fs_cache: Dict[str, Optional[int]] = {}

    # ---- concepts and facts

    def namespace_of(self, qname: str) -> Optional[str]:
        return self.ns.get(qname.split(":")[0]) if ":" in qname else None

    def same_concept(self, fact: Fact, qname: str) -> bool:
        """Local names match and, when both prefixes resolve on the instance
        root, so do the namespaces (an extension element that reuses a US GAAP
        local name is a different concept)."""
        if fact.local != _local(qname):
            return False
        a, b = self.namespace_of(fact.concept), self.namespace_of(qname)
        return a is None or b is None or a == b

    def period_facts(self, qname: str) -> List[Tuple[Fact, Context]]:
        """Numeric, non-nil facts of ``qname`` in contexts of the target period."""
        t = self.target
        out = []
        for f in self.by_local.get(_local(qname), ()):
            if f.nil or f.value is None or not self.same_concept(f, qname):
                continue
            c = self.contexts.get(f.context)
            if c is None or not c.matches(t):
                continue
            out.append((f, c))
        return out

    def nondim_period_facts(self, qname: str) -> List[Fact]:
        return [f for f, c in self.period_facts(qname) if not c.dims]

    # ---- networks

    @property
    def droles(self) -> List[DimensionalRole]:
        if self._droles is None:
            self._droles = parse_definition(self.sections["definition"])
        return self._droles

    @property
    def arcs(self) -> List[CalcArc]:
        if self._arcs is None:
            self._arcs = parse_calc(self.sections["calculation"])
        return self._arcs

    @property
    def titles(self) -> Dict[str, str]:
        """role URI -> description: the schema's roleType definition, else the
        title a linkbase gives the extended link (when the schema is absent)."""
        if self._titles is None:
            t = role_titles(self.sections["schema"], self.sections["calculation"])
            for sec, link in (("presentation", "presentationLink"), ("definition", "definitionLink")):
                for m in re.finditer(r"<(?:[\w-]+:)?%s\b([^>]*)>" % link, self.sections[sec]):
                    a = m.group(1)
                    role = re.search(r'xlink:role\s*=\s*"([^"]*)"', a)
                    title = re.search(r'xlink:title\s*=\s*"([^"]*)"', a)
                    if role and title:
                        t.setdefault(role.group(1), title.group(1))
            self._titles = t
        return self._titles

    def role_kind(self, uri: str) -> str:
        """'statement', 'other' or 'unknown' (no description anywhere)."""
        d = self.titles.get(uri)
        if d is None:
            return "unknown"
        return "statement" if "- Statement -" in d else "other"

    def is_statement_cube(self, dr: DimensionalRole) -> bool:
        """$STATEMENT_CUBES: a table on a statement network, outside the
        rule's equity-type, parenthetical and schedule exclusions."""
        if not dr.hypercubes or self.role_kind(dr.role) == "other":
            return False
        u, d = dr.role.lower(), (self.titles.get(dr.role) or "").lower()
        if any(s in u for s in CUBE_EXCLUDED_URI) or any(s in d for s in CUBE_EXCLUDED_DESC):
            return False
        return not any(_local(h) in CUBE_EXCLUDED_TABLES for h in dr.hypercubes)

    def in_0126_scope(self, uri: str) -> bool:
        """$STATEMENT_PRES_NETWORKS and not a statement table (DQC_0126.xule)."""
        if self.role_kind(uri) == "other":
            return False
        u, d = uri.lower(), (self.titles.get(uri) or "").lower()
        if any(s in u for s in PRES_EXCLUDED_URI) or any(s in d for s in PRES_EXCLUDED_DESC):
            return False
        return not any(dr.role == uri and self.is_statement_cube(dr) for dr in self.droles)

    def in_0117_scope(self, axis: str) -> bool:
        """The axis is a dimension of a statement table (DQC_0117.xule iterates
        $STATEMENT_CUBES and their dimensions). With no definition linkbase at
        all the table structure is unknown, so only the network type decides."""
        cubes = [dr for dr in self.droles if axis in dr.axes]
        if cubes:
            return any(self.is_statement_cube(dr) for dr in cubes)
        if self.definition_known:
            return False  # the definition linkbase declares no table with this axis
        uris = {a.role for a in self.arcs} | set(self.titles)
        if any(self.role_kind(u) == "other" for u in uris):
            return False
        return not any(s in u.lower() for u in uris for s in CUBE_EXCLUDED_URI)

    @property
    def definition_known(self) -> bool:
        """The case carries a definition linkbase (possibly with an empty
        extended link). Only when it is absent is the table structure unknown."""
        return bool(re.search(r"<(?:[\w-]+:)?(?:linkbase|definitionLink)\b", self.sections["definition"]))

    def dim_role_for(self, axis: str) -> Optional[DimensionalRole]:
        for dr in self.droles:
            if axis in dr.axes:
                return dr
        for dr in self.droles:
            if axis in dr.domains:
                return dr
        return None

    # ---- duplicates and decimals

    def fs_decimals(self, role: str) -> Optional[int]:
        """DQC_0126.xule $fs_decimals: the most frequent decimals among the
        non-dimensional facts (any period) of the network's calculation parents.
        Ties go to the value seen last in first-appearance order, as the rule's
        ``most_frequent`` builds a count -> value dictionary."""
        if role not in self._fs_cache:
            parents = {_local(a.parent) for a in self.arcs if a.role == role}
            counts: Dict[int, int] = {}
            for f in self.facts:
                if f.local not in parents or f.nil:
                    continue
                c = self.contexts.get(f.context)
                if c is None or c.dims:
                    continue
                d = _dec(f.decimals)
                if d is not None:
                    counts[d] = counts.get(d, 0) + 1
            if counts:
                by_count = {}
                for d, n in counts.items():
                    by_count[n] = d
                self._fs_cache[role] = by_count[max(by_count)]
            else:
                self._fs_cache[role] = None
        return self._fs_cache[role]

    @property
    def usual_decimals(self) -> Optional[int]:
        """Most frequent decimals across the calculation network's facts, used
        only to choose among inconsistent duplicates outside DQC_US_0126."""
        if not hasattr(self, "_usual"):
            concepts = {_local(a.parent) for a in self.arcs} | {_local(a.child) for a in self.arcs}
            tally: Dict[int, int] = defaultdict(int)
            for cl in concepts:
                for f in self.by_local.get(cl, ()):
                    d = _dec(f.decimals)
                    if d is not None and not f.nil:
                        tally[d] += 1
            self._usual = max(tally.items(), key=lambda kv: (kv[1], kv[0]))[0] if tally else None
        return self._usual

    def pick(self, facts: List[Fact], fs: Optional[int] = None) -> Optional[Fact]:
        """One fact among duplicates, the DQC_US_0126 way: decimals equal to
        ``fs``, else the first at least as precise, else the first. Consistent
        duplicates make the choice moot."""
        if not facts:
            return None
        if len({f.value for f in facts}) == 1:
            return facts[0]
        fs = self.usual_decimals if fs is None else fs
        if fs is not None:
            for f in facts:
                if _dec(f.decimals) == fs:
                    return f
            for f in facts:
                d = _dec(f.decimals)
                if d is not None and d >= fs:
                    return f
            return facts[0]
        return max(facts, key=lambda f: (_dec(f.decimals) if _dec(f.decimals) is not None else INF))


# --------------------------------------------------------------------------- candidates


@dataclass
class Candidate:
    rule: str  # calc | dim | neg
    extracted: Decimal
    calculated: Decimal
    fires: bool  # the rule's own test reports it (tolerance passed / listed element)
    in_scope: bool  # on a network (or element) the rule checks
    size: int  # members or addends present: larger breakdowns rank first
    detail: str


def _primary_concepts(dr: DimensionalRole) -> set:
    out, stack = set(), list(dr.primaries)
    while stack:
        n = stack.pop()
        if n in out:
            continue
        out.add(n)
        stack.extend(dr.children.get(n, []))
    return {_local(x) for x in out}


def _calc_descendants(case: Case, parent_local: str, role: str) -> set:
    kids: Dict[str, List[str]] = defaultdict(list)
    for a in case.arcs:
        if a.role == role:
            kids[_local(a.parent)].append(_local(a.child))
    out, stack = set(), list(kids.get(parent_local, []))
    while stack:
        n = stack.pop()
        if n in out:
            continue
        out.add(n)
        stack.extend(kids.get(n, []))
    return out


def _dim_breakdowns(case: Case, tfacts: List[Tuple[Fact, Context]]) -> Dict[str, Tuple[Dict[str, Fact], bool]]:
    """axis -> (member -> fact, members_from_table), for facts qualified by
    exactly one checked axis.

    DQC_US_0117 sums the members of the axis's domain tree in the statement
    table, and skips a member when one of its ancestors below the domain
    already carries a value. When the table's tree covers none of the reported
    members, all of them are kept but flagged as outside the rule's reach.
    """
    groups: Dict[str, Dict[str, Fact]] = defaultdict(dict)
    for f, c in tfacts:
        if len(c.dims) != 1:
            continue
        axis, member = c.dims[0]
        if _local(axis) not in CHECKED_AXES:
            continue
        groups[axis].setdefault(member, f)
    out: Dict[str, Tuple[Dict[str, Fact], bool]] = {}
    for axis, members in groups.items():
        dr = case.dim_role_for(axis)
        tree = dr.members(axis) if dr is not None else []
        if not tree:
            out[axis] = (members, dr is None and not case.definition_known)
            continue
        keep: Dict[str, Fact] = {}
        for m in tree:
            if m not in members:
                continue
            if any(a in members for a in dr.ancestors(axis, m)):
                continue
            keep[m] = members[m]
        out[axis] = (keep, True) if keep else (members, False)
    return out


def dim_candidates(case: Case, tfacts, total: Optional[Fact], monetary: bool) -> List[Candidate]:
    t = case.target
    E_out = total.value if total is not None else ZERO
    E_dec = _dec(total.decimals) if total is not None else None
    out = []
    for axis, (members, from_table) in _dim_breakdowns(case, tfacts).items():
        s = sum((f.value for f in members.values()), ZERO)
        if s == E_out:
            continue
        decs = [d for d in (_dec(f.decimals) for f in members.values()) if d is not None]
        md = min(decs) if decs else None
        fires = tolerance_for_decimals_comp(s, None, E_out, E_dec, md, 2)
        note = ""
        # FASB 606 exception (DQC_0117.xule): revenue broken down by product or service.
        dr = case.dim_role_for(axis)
        if fires and dr is not None and t.local in REVENUE_606 and _local(axis) == "ProductOrServiceAxis":
            prim = _primary_concepts(dr)
            if "NoninterestIncome" in prim:
                fires = s > E_out
                note = " 606-bank"
            elif s < E_out and "Revenues" in prim:
                rev = _calc_descendants(case, "Revenues", dr.role)
                if len(rev) > 1 and rev & REVENUE_606:
                    fires = False
                    note = " 606-mixed"
        in_scope = monetary and from_table and case.in_0117_scope(axis)
        if FIX_TOTAL_REQUIRED in FIXES and total is None:
            # Assertion 9574's rule focus is the total ($TotalDefault); the rule
            # documentation says the aggregate must be reported. Without it the
            # breakdown is evidence, not a finding of the rule.
            in_scope = False
            note += " no-total"
        out.append(Candidate("dim", E_out, s, fires, in_scope, len(members), _local(axis) + note))
    out.sort(key=lambda c: (not (c.fires and c.in_scope), not c.fires, -c.size))
    return out


def dim_10093_candidates(case: Case, tfacts, monetary: bool) -> List[Candidate]:
    """DQC_US_0117 assertion 10093 (DQC_0117.xule) on the target concept and period.

    In a statement table ($STATEMENT_CUBES), for each checked axis $dim and each
    member M of $dim that the target reports in facts with exactly two
    dimensions, the one-member fact ($dim = M, other dimensions default) is the
    total ($TotalDefault, which must exist) and the facts ($dim = M, D2 = any
    member) are summed, D2 being the first other axis of those facts. Skipped
    when D2 is LegalEntityAxis. A fact belongs to the table only when every axis
    is the table's and every member is in that axis's domain tree. Facts with
    three or more dimensions on M and D2 would enter the sum (covered-dims) and
    need the rule's subtotal check, so such a breakdown is left out (none occurs
    in the practice or ranked files). Finding: tolerance_for_decimals_comp(sum,
    total, min member decimals, 2). extracted = the one-member total, calculated
    = the D2 sum.
    """
    if not monetary:
        return []
    out = []
    for dr in case.droles:
        if not (dr.hypercubes and case.is_statement_cube(dr)):
            continue
        axes = dr.axes
        trees = {a: set(dr.members(a)) for a in axes}
        for dim in axes:
            if _local(dim) not in CHECKED_AXES:
                continue
            two, more = [], []
            for f, c in tfacts:
                d = dict(c.dims)
                if dim not in d or len(d) < 2:
                    continue
                if any(a not in trees or (trees[a] and m not in trees[a]) for a, m in d.items()):
                    continue  # not a fact of this table
                (two if len(d) == 2 else more).append((f, d))
            subs: List[str] = []
            for f, d in two:
                if d[dim] not in subs:
                    subs.append(d[dim])
            for sm in subs:
                rows = [(f, d) for f, d in two if d[dim] == sm]
                dim2 = next(a for a in rows[0][1] if a != dim)
                if _local(dim2) == "LegalEntityAxis":
                    continue
                if any(d.get(dim) == sm and dim2 in d for f, d in more):
                    continue
                totals = [f for f, c in tfacts if c.dims == ((dim, sm),)]
                if not totals:
                    continue  # exists($TotalDefault)
                total = case.pick(totals)
                members: Dict[str, Fact] = {}
                for f, d in rows:
                    if dim2 in d:
                        members.setdefault(d[dim2], f)  # duplicates in one context collapse
                s = sum((f.value for f in members.values()), ZERO)
                if s == total.value:
                    continue
                decs = [x for x in (_dec(f.decimals) for f in members.values()) if x is not None]
                fires = tolerance_for_decimals_comp(s, None, total.value, _dec(total.decimals),
                                                    min(decs) if decs else None, 2)
                out.append((total.order, Candidate("dim", total.value, s, fires, True, len(members),
                                                   f"{_local(dim)}={_local(sm)} by {_local(dim2)} (0117.10093)")))
    # Several findings can answer the same question: firing ones first, then the
    # one whose total comes first in document order.
    out.sort(key=lambda oc: (not oc[1].fires, oc[0]))
    return [c for _, c in out]


def calc_candidates(case: Case) -> List[Candidate]:
    """DQC_US_0126 per calculation network where the target is a parent."""
    t = case.target
    byrole: Dict[str, List[CalcArc]] = defaultdict(list)
    for a in case.arcs:
        if _local(a.parent) == t.local:
            byrole[a.role].append(a)
    chapter11 = bool(case.by_local.get("ReorganizationUnderChapter11OfUSBankruptcyCodeDisclosureTextBlock"))
    out = []
    for role, arcs in byrole.items():
        fs = case.fs_decimals(role)
        total, present, seen = ZERO, 0, set()
        for a in arcs:
            cl = _local(a.child)
            if cl in seen:
                continue
            seen.add(cl)
            f = case.pick(case.nondim_period_facts(a.child), fs)
            if f is None:
                continue
            total += a.weight * f.value
            present += 1
        if present == 0:
            continue
        if chapter11 and "LiabilitiesSubjectToCompromise" in seen:
            continue  # the rule skips this subtotal (DQC_0126.xule)
        parents = case.nondim_period_facts(t.concept)
        at_fs = [f for f in parents if fs is not None and _dec(f.decimals) == fs]
        if at_fs:
            parent = at_fs[0]
            fires = tolerance_for_decimals(parent.value, _dec(parent.decimals), total, None, present + 1)
        else:
            parent = case.pick(parents)  # the rule reads the parent at the statement's decimals only
            fires = False
        if parent is None or parent.value == total:
            continue
        out.append(Candidate("calc", parent.value, total, fires, case.in_0126_scope(role), present,
                             role.rsplit("/", 1)[-1] + ("" if at_fs else " (parent not at statement decimals)")))
    out.sort(key=lambda c: (not (c.fires and c.in_scope), not c.fires, -c.size))
    return out


def _is_monetary(case: Case, facts: List[Fact]) -> bool:
    """Monetary item: the taxonomy type says so, else the unit is one currency."""
    tax = parse_taxonomy(case.sections["taxonomy"], case.target.concept)
    if tax.item_type:
        return "monetary" in tax.item_type.lower()
    units = {}
    for m in re.finditer(r"<(?:[\w-]+:)?unit\b([^>]*)>(.*?)</(?:[\w-]+:)?unit>", case.sections["instance"], re.S):
        uid = re.search(r'id\s*=\s*"([^"]*)"', m.group(1))
        if uid:
            units[uid.group(1)] = m.group(2)
    for f in facts:
        body = units.get(f.unit or "", "")
        if "divide" not in body and "iso4217:" in body:
            return True
    return False


# --------------------------------------------------------------------------- decision

TIER_NAMES = {
    1: "rule finding in scope",
    2: "difference beyond tolerance, outside the rule's networks",
    3: "difference within tolerance",
    4: "negative value of an element not on the DQC_US_0015 list",
    5: "negative value inside a DQC_US_0015 exclusion",
    6: "no finding",
}


def predict(query: str) -> Prediction:
    case = Case(query)
    t = case.target
    if t is None:
        return Prediction("0", "0", "unparsed", tier=6, confidence="none")

    tfacts = case.period_facts(t.concept)
    total = case.pick([f for f, c in tfacts if not c.dims])
    E = total.value if total is not None else None
    monetary = _is_monetary(case, [f for f, _ in tfacts])

    dims = dim_candidates(case, tfacts, total, monetary)
    calcs = calc_candidates(case) if tfacts else []

    negs = [(f, c) for f, c in tfacts if f.value < 0]
    tested = [(f, c) for f, c in negs if non_neg_applies(c)]
    ns = case.namespace_of(t.concept)
    listed = t.local in NON_NEG_ELEMENTS and (ns is None or any(s in ns for s in NON_NEG_NAMESPACES))
    neg = []
    if tested:
        # Each tested negative fact is a separate DQC_US_0015 finding with the
        # same question; the rule does not rank them. V0: the non-dimensional
        # fact first, otherwise the first tested dimensional fact in document
        # order. Other policies exist only as measurement switches.
        prefer, order = NEG_POLICY
        if prefer == "nondim" and E is not None and E < 0:
            v = E
        else:
            pool = tested
            if prefer == "dim":
                pool = [(f, c) for f, c in tested if c.dims] or tested
            if order == "first":
                v = pool[0][0].value
            elif order == "last":
                v = pool[-1][0].value
            elif order == "maxabs":
                v = min(f.value for f, _ in pool)
            else:  # minabs
                v = max(f.value for f, _ in pool)
        neg.append(Candidate("neg", v, -v, listed, listed, 1, "nondim" if v == E else "dim"))

    d10093 = dim_10093_candidates(case, tfacts, monetary) if FIX_10093 in FIXES else []

    def emit(c: Candidate, tier: int, competing: List[str]) -> Prediction:
        conf = "low" if tier > 1 else ("medium" if competing else "high")
        detail = c.detail + ("" if c.fires else " (not reported by the rule)")
        return Prediction(fmt_decimal(c.extracted), fmt_decimal(c.calculated), c.rule, detail, tier, conf,
                          ",".join(competing))

    # Tier 1: findings inside the rule's own scope. 0126 and 0117 have disjoint
    # scopes (flat statements versus statement tables); a relational finding
    # ranks before a DQC_US_0015 one on the same concept.
    tier1 = [c for c in calcs[:1] + dims[:1] + neg if c.fires and c.in_scope]
    if tier1:
        return emit(tier1[0], 1, [c.rule for c in tier1[1:]])
    # Switch a10093: DQC_US_0117 assertion 10093 is a rule finding in scope too;
    # it is used only when no other rule finding is in scope.
    tier1 = [c for c in d10093[:1] if c.fires and c.in_scope]
    if tier1:
        return emit(tier1[0], 1, [])
    # Tier 2: relational differences beyond tolerance on networks the rule
    # does not check.
    tier2 = [c for c in dims[:1] + calcs[:1] if c.fires]
    if tier2:
        return emit(tier2[0], 2, [])
    # Tier 3: relational differences the rule's tolerance would absorb.
    tier3 = dims[:1] + calcs[:1]
    if tier3:
        return emit(tier3[0], 3, [])
    # Tiers 4 and 5: a negative value no rule reports.
    if neg:
        return emit(neg[0], 4, [])
    if negs:
        v = negs[0][0].value
        return emit(Candidate("neg", v, -v, False, False, 1, "dim-excluded"), 5, [])
    if E is None:
        return Prediction("0", "0", "unresolved", "", 6, "none")
    return Prediction(fmt_decimal(E), fmt_decimal(-E), "fallback", "", 6, "none")

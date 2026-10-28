#!/usr/bin/env python3
"""Synthetic checks of every decision path (no data files needed).

    python3 engine/selftest.py

Each case is built from the public DQC rule logic (XULE source), not from any
practice or ranked case: rule scope (statement networks, statement tables,
equity-type exclusions), the two tolerance functions, the DQC_US_0015
exclusions, duplicate-fact choice, nested members, the FASB 606 exception,
the evidence tiers, and two parser rules (dateTime period ends, namespaces).

Every case runs under a switch set (engine.configure): the first 29 under V0,
the engine uploaded on 2026-10-02; the later ones check each variant switch
(DQC_US_0117 assertion 10093, the 9574 reported-total requirement and the
DQC_US_0015 choice policies) and that V0 is unchanged on the same inputs.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine  # noqa: E402
from engine import predict  # noqa: E402

NS = ('xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2024" '
      'xmlns:srt="http://fasb.org/srt/2024" xmlns:abc="http://abc.example/20241231" '
      'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:iso4217="http://www.xbrl.org/2003/iso4217"')
SUM = "http://www.xbrl.org/2003/arcrole/summation-item"
DIM = "http://xbrl.org/int/dim/arcrole/"


def _query(concept, period, calc="", definition="", instance_facts="", contexts="", schema_role="",
           tax_type="xbrli:monetaryItemType", pres_role=""):
    start, _, end = period.partition(" to ")
    per = f"{start} to {end}" if end else start
    return f"""header
##Schema document
<schema>{schema_role}</schema>
##Presentation linkbase document
<link:linkbase>{pres_role}</link:linkbase>
##Calculation linkbase document
<link:linkbase>{calc}</link:linkbase>
##Definition linkbase document
<link:linkbase>{definition}</link:linkbase>
##Label linkbase document
<linkbase/>
##Instance document
<xbrli:xbrl {NS}>
{contexts}
<unit id="USD"><measure>iso4217:USD</measure></unit>
{instance_facts}
</xbrli:xbrl>
##US GAAP Taxonomy
[Concept Core]
ID: {concept}
Label: x
Type: {tax_type} | Balance: debit | PeriodType: duration | Abstract: False

Question1: What's the reported value of {concept} in the Instance document for the period {per}?
Question2: What's the actual value of {concept} in the Instance document for the period {per}, calculated based on the calculation relationship?
Answer:
"""


def _ctx(cid, dims=(), end="2024-12-31"):
    seg = ""
    if dims:
        seg = "<segment>" + "".join(
            f'<xbrldi:explicitMember dimension="{a}">{m}</xbrldi:explicitMember>' for a, m in dims) + "</segment>"
    return (f'<context id="{cid}"><entity><identifier scheme="x">1</identifier>{seg}</entity>'
            f"<period><startDate>2024-01-01</startDate><endDate>{end}</endDate></period></context>")


COS = "us-gaap:StatementClassOfStockAxis"
CTX = "\n".join([
    _ctx("D"),
    _ctx("DA", [(COS, "us-gaap:CommonStockMember")]),
    _ctx("DB", [(COS, "us-gaap:PreferredStockMember")]),
    _ctx("DE", [("us-gaap:StatementEquityComponentsAxis", "us-gaap:RetainedEarningsMember")]),
    _ctx("DX", [(COS, "abc:UnallocatedMember")]),
    _ctx("DP", [("srt:ProductOrServiceAxis", "abc:ProductAMember")]),
    _ctx("DQ", [("srt:ProductOrServiceAxis", "abc:ProductBMember")]),
    _ctx("P").replace("2024-01-01", "2023-01-01").replace("2024-12-31", "2023-12-31"),
])


def fact(concept, value, ctx="D", decimals="-3"):
    tag = concept
    return f'<{tag} contextRef="{ctx}" unitRef="USD" decimals="{decimals}">{value}</{tag}>'


def role_type(uri, definition):
    return f'<link:roleType roleURI="{uri}"><link:definition>{definition}</link:definition></link:roleType>'


def calc_link(role, parent, children):
    p = parent.replace(":", "_")
    locs = f'<link:loc xlink:label="p" xlink:href="x.xsd#{p}"/>'
    arcs = ""
    for i, (child, w) in enumerate(children):
        locs += f'<link:loc xlink:label="c{i}" xlink:href="x.xsd#{child.replace(":", "_")}"/>'
        arcs += f'<link:calculationArc xlink:arcrole="{SUM}" xlink:from="p" xlink:to="c{i}" weight="{w}"/>'
    return f'<link:calculationLink xlink:role="{role}" xlink:type="extended">{locs}{arcs}</link:calculationLink>'


def table_link(role, axis, domain, tree, line_items=("us-gaap:IncomeStatementAbstract",), table="us-gaap:StatementTable"):
    """A statement table: line items -all-> table -> axis -> domain -> members (tree: parent -> [children])."""
    names = {table, axis, domain, *line_items}
    for p, kids in tree.items():
        names.add(p)
        names.update(kids)
    locs = "".join(f'<link:loc xlink:label="{n.replace(":", "_")}" xlink:href="x.xsd#{n.replace(":", "_")}"/>'
                   for n in sorted(names))
    lab = lambda n: n.replace(":", "_")  # noqa: E731
    arcs = [("all", line_items[0], table), ("hypercube-dimension", table, axis), ("dimension-domain", axis, domain)]
    arcs += [("domain-member", line_items[0], li) for li in line_items[1:]]
    for p, kids in tree.items():
        arcs += [("domain-member", p, k) for k in kids]
    body = "".join(f'<link:definitionArc xlink:arcrole="{DIM}{r}" xlink:from="{lab(a)}" xlink:to="{lab(b)}" order="{i}"/>'
                   for i, (r, a, b) in enumerate(arcs))
    return f'<link:definitionLink xlink:role="{role}" xlink:type="extended">{locs}{body}</link:definitionLink>'


def table_link_multi(role, axes, line_items=("us-gaap:IncomeStatementAbstract",), table="us-gaap:StatementTable"):
    """A statement table with several axes: axes = [(axis, domain, {parent: [children]}), ...]."""
    names = {table, *line_items}
    for axis, domain, tree in axes:
        names.update({axis, domain})
        for p_, kids in tree.items():
            names.add(p_)
            names.update(kids)
    locs = "".join(f'<link:loc xlink:label="{n.replace(":", "_")}" xlink:href="x.xsd#{n.replace(":", "_")}"/>'
                   for n in sorted(names))
    lab = lambda n: n.replace(":", "_")  # noqa: E731
    arcs = [("all", line_items[0], table)]
    for axis, domain, tree in axes:
        arcs += [("hypercube-dimension", table, axis), ("dimension-domain", axis, domain)]
        for p_, kids in tree.items():
            arcs += [("domain-member", p_, k) for k in kids]
    arcs += [("domain-member", line_items[0], li) for li in line_items[1:]]
    body = "".join(f'<link:definitionArc xlink:arcrole="{DIM}{r}" xlink:from="{lab(a)}" xlink:to="{lab(b)}" order="{i}"/>'
                   for i, (r, a, b) in enumerate(arcs))
    return f'<link:definitionLink xlink:role="{role}" xlink:type="extended">{locs}{body}</link:definitionLink>'


IS = "http://abc.example/role/IncomeStatement"
IS_T = role_type(IS, "0002 - Statement - Income Statement")
OPEX_KIDS = [("us-gaap:SellingGeneralAndAdministrativeExpense", "1"), ("us-gaap:ResearchAndDevelopmentExpense", "1")]
OPEX_FACTS = (fact("us-gaap:OperatingExpenses", 500000) + fact("us-gaap:SellingGeneralAndAdministrativeExpense", 300000)
              + fact("us-gaap:ResearchAndDevelopmentExpense", 150000))
PERIOD = "2024-01-01 to 2024-12-31"


def cases():
    out = []

    def add(name, expect, **kw):
        concept = kw.pop("concept")
        out.append((name, expect, _query(concept, PERIOD, contexts=kw.pop("contexts", CTX), **kw), engine.VARIANTS["V0"]))

    # ---- DQC_US_0015
    add("0015 listed element, non-dimensional negative", ("-1284", "1284", "neg", 1),
        concept="us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
        instance_facts=fact("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", -1284, decimals="0"))
    add("0015 negative only on an excluded axis -> tier 5", ("-70", "70", "neg", 5),
        concept="us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
        instance_facts=fact("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", 900, decimals="0")
        + fact("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", -70, "DE", "0"))
    add("0015 tested dimensional negative when the total is positive", ("-5", "5", "neg", 1),
        concept="us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
        instance_facts=fact("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", 900, decimals="0")
        + fact("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", -70, "DE", "0")
        + fact("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", -5, "DP", "0"))
    add("element not on the 0015 list -> tier 4", ("-42", "42", "neg", 4),
        concept="us-gaap:NetIncomeLoss", instance_facts=fact("us-gaap:NetIncomeLoss", -42, decimals="0"))
    add("extension element reusing a listed local name is not the target", ("0", "0", "unresolved", 6),
        concept="us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
        instance_facts=fact("abc:PaymentsToAcquirePropertyPlantAndEquipment", -9, decimals="0"))

    # ---- DQC_US_0126
    add("0126 flat statement, children do not add up", ("500000", "450000", "calc", 1),
        concept="us-gaap:OperatingExpenses", schema_role=IS_T,
        calc=calc_link(IS, "us-gaap:OperatingExpenses", OPEX_KIDS), instance_facts=OPEX_FACTS)
    add("0126 difference inside tolerance (decimals -3, 2 addends: 3,000) -> tier 3", ("500000", "498000", "calc", 3),
        concept="us-gaap:OperatingExpenses", schema_role=IS_T,
        calc=calc_link(IS, "us-gaap:OperatingExpenses", OPEX_KIDS),
        instance_facts=fact("us-gaap:OperatingExpenses", 500000) + fact("us-gaap:SellingGeneralAndAdministrativeExpense", 300000)
        + fact("us-gaap:ResearchAndDevelopmentExpense", 198000))
    add("0126 tolerance uses the parent's decimals, not the coarser child's", ("500000", "496000", "calc", 1),
        concept="us-gaap:OperatingExpenses", schema_role=IS_T,
        calc=calc_link(IS, "us-gaap:OperatingExpenses", OPEX_KIDS),
        instance_facts=fact("us-gaap:OperatingExpenses", 500000) + fact("us-gaap:SellingGeneralAndAdministrativeExpense", 300000)
        + fact("us-gaap:ResearchAndDevelopmentExpense", 196000, decimals="-4"))
    eq = "http://abc.example/role/StatementOfStockholdersEquity"
    add("0126 does not check equity statements -> tier 2", ("500000", "450000", "calc", 2),
        concept="us-gaap:OperatingExpenses", schema_role=role_type(eq, "0005 - Statement - Stockholders Equity"),
        calc=calc_link(eq, "us-gaap:OperatingExpenses", OPEX_KIDS), instance_facts=OPEX_FACTS)
    disc = "http://abc.example/role/OpexDetails"
    add("0126 does not check disclosure networks -> tier 2", ("500000", "450000", "calc", 2),
        concept="us-gaap:OperatingExpenses", schema_role=role_type(disc, "0050 - Disclosure - Opex (Details)"),
        calc=calc_link(disc, "us-gaap:OperatingExpenses", OPEX_KIDS), instance_facts=OPEX_FACTS)
    add("0126 skips a statement table network -> tier 2", ("500000", "450000", "calc", 2),
        concept="us-gaap:OperatingExpenses", schema_role=IS_T,
        calc=calc_link(IS, "us-gaap:OperatingExpenses", OPEX_KIDS),
        definition=table_link(IS, COS, "us-gaap:ClassOfStockDomain", {"us-gaap:ClassOfStockDomain": ["us-gaap:CommonStockMember"]}),
        instance_facts=OPEX_FACTS)
    add("0126 parent duplicates: the one at the statement's usual decimals", ("500000", "450000", "calc", 1),
        concept="us-gaap:OperatingExpenses", schema_role=IS_T,
        calc=calc_link(IS, "us-gaap:OperatingExpenses", OPEX_KIDS),
        instance_facts=fact("us-gaap:OperatingExpenses", 500000) + fact("us-gaap:OperatingExpenses", 1000000, decimals="-6")
        + fact("us-gaap:OperatingExpenses", 480000, "P") + fact("us-gaap:SellingGeneralAndAdministrativeExpense", 300000)
        + fact("us-gaap:ResearchAndDevelopmentExpense", 150000))
    capex = "us-gaap:PaymentsToAcquireProductiveAssets"  # on the DQC_US_0015 list
    capex_kids = [("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", "1"), ("us-gaap:PaymentsToAcquireIntangibleAssets", "1")]
    capex_facts = (fact(capex, -500000) + fact("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", 300000)
                   + fact("us-gaap:PaymentsToAcquireIntangibleAssets", 150000))
    add("tier 1 competition: in-scope 0126 before a listed negative", ("-500000", "450000", "calc", 1),
        concept=capex, schema_role=IS_T, calc=calc_link(IS, capex, capex_kids), instance_facts=capex_facts)
    add("listed negative on a disclosure network beats out-of-scope 0126", ("-500000", "500000", "neg", 1),
        concept=capex, schema_role=role_type(disc, "0050 - Disclosure - Capex (Details)"),
        calc=calc_link(disc, capex, capex_kids), instance_facts=capex_facts)
    two_roles = IS_T + role_type(disc, "0050 - Disclosure - Opex (Details)")
    restr = OPEX_KIDS + [("us-gaap:RestructuringCharges", "1")]
    add("two networks: the statement's calculation is the one checked", ("500000", "450000", "calc", 1),
        concept="us-gaap:OperatingExpenses", schema_role=two_roles,
        calc=calc_link(IS, "us-gaap:OperatingExpenses", OPEX_KIDS) + calc_link(disc, "us-gaap:OperatingExpenses", restr),
        instance_facts=OPEX_FACTS + fact("us-gaap:RestructuringCharges", 20000))
    add("two networks: statement adds up, disclosure does not -> tier 2", ("500000", "450000", "calc", 2),
        concept="us-gaap:OperatingExpenses", schema_role=two_roles,
        calc=calc_link(IS, "us-gaap:OperatingExpenses", restr) + calc_link(disc, "us-gaap:OperatingExpenses", OPEX_KIDS),
        instance_facts=OPEX_FACTS + fact("us-gaap:RestructuringCharges", 50000))
    add("dateTime endDate at midnight closes the previous day", ("500000", "450000", "calc", 1),
        concept="us-gaap:OperatingExpenses", schema_role=IS_T, contexts=_ctx("D", end="2025-01-01T00:00:00"),
        calc=calc_link(IS, "us-gaap:OperatingExpenses", OPEX_KIDS), instance_facts=OPEX_FACTS)

    # ---- DQC_US_0117
    cs_tree = {"us-gaap:ClassOfStockDomain": ["us-gaap:CommonStockMember", "us-gaap:PreferredStockMember"]}
    cs_table = table_link(IS, COS, "us-gaap:ClassOfStockDomain", cs_tree)
    add("0117 statement table, members do not add up", ("135", "101", "dim", 1),
        concept="us-gaap:CommonStockValue", schema_role=IS_T, definition=cs_table,
        instance_facts=fact("us-gaap:CommonStockValue", 135, decimals="0") + fact("us-gaap:CommonStockValue", 1, "DA", "0")
        + fact("us-gaap:CommonStockValue", 100, "DB", "0"))
    add("0117 no default fact: extracted is 0", ("0", "101", "dim", 1),
        concept="us-gaap:CommonStockValue", schema_role=IS_T, definition=cs_table,
        instance_facts=fact("us-gaap:CommonStockValue", 1, "DA", "0") + fact("us-gaap:CommonStockValue", 100, "DB", "0"))
    add("0117 counts only members of the table's domain", ("135", "101", "dim", 1),
        concept="us-gaap:CommonStockValue", schema_role=IS_T, definition=cs_table,
        instance_facts=fact("us-gaap:CommonStockValue", 135, decimals="0") + fact("us-gaap:CommonStockValue", 1, "DA", "0")
        + fact("us-gaap:CommonStockValue", 100, "DB", "0") + fact("us-gaap:CommonStockValue", 34, "DX", "0"))
    nested = {"us-gaap:ClassOfStockDomain": ["us-gaap:CommonStockMember"],
              "us-gaap:CommonStockMember": ["us-gaap:PreferredStockMember"]}
    add("0117 skips a member whose ancestor carries a value", ("135", "100", "dim", 1),
        concept="us-gaap:CommonStockValue", schema_role=IS_T,
        definition=table_link(IS, COS, "us-gaap:ClassOfStockDomain", nested),
        instance_facts=fact("us-gaap:CommonStockValue", 135, decimals="0") + fact("us-gaap:CommonStockValue", 100, "DA", "0")
        + fact("us-gaap:CommonStockValue", 60, "DB", "0"))
    add("0117 difference inside tolerance (factor 2) -> tier 3", ("102", "101", "dim", 3),
        concept="us-gaap:CommonStockValue", schema_role=IS_T, definition=cs_table,
        instance_facts=fact("us-gaap:CommonStockValue", 102, decimals="0") + fact("us-gaap:CommonStockValue", 1, "DA", "0")
        + fact("us-gaap:CommonStockValue", 100, "DB", "0"))
    add("0117 needs a table: flat statement -> tier 2", ("135", "101", "dim", 2),
        concept="us-gaap:CommonStockValue", schema_role=IS_T,
        instance_facts=fact("us-gaap:CommonStockValue", 135, decimals="0") + fact("us-gaap:CommonStockValue", 1, "DA", "0")
        + fact("us-gaap:CommonStockValue", 100, "DB", "0"))
    add("0117 skips equity-type statement tables -> tier 2", ("135", "101", "dim", 2),
        concept="us-gaap:CommonStockValue", schema_role=role_type(eq, "0005 - Statement - Stockholders Equity"),
        definition=table_link(eq, COS, "us-gaap:ClassOfStockDomain", cs_tree),
        instance_facts=fact("us-gaap:CommonStockValue", 135, decimals="0") + fact("us-gaap:CommonStockValue", 1, "DA", "0")
        + fact("us-gaap:CommonStockValue", 100, "DB", "0"))
    add("0117 checks monetary facts only -> tier 2", ("135", "101", "dim", 2),
        concept="us-gaap:CommonStockSharesOutstanding", schema_role=IS_T, tax_type="xbrli:sharesItemType",
        definition=table_link(IS, COS, "us-gaap:ClassOfStockDomain", cs_tree),
        instance_facts=fact("us-gaap:CommonStockSharesOutstanding", 135, decimals="0")
        + fact("us-gaap:CommonStockSharesOutstanding", 1, "DA", "0") + fact("us-gaap:CommonStockSharesOutstanding", 100, "DB", "0"))
    add("listed negative beats a breakdown on a flat statement", ("-135", "135", "neg", 1),
        concept="us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", schema_role=IS_T,
        instance_facts=fact("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", -135, decimals="0")
        + fact("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", 1, "DA", "0"))
    p_tree = {"srt:ProductsAndServicesDomain": ["abc:ProductAMember", "abc:ProductBMember"]}
    rev = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
    rev_facts = fact(rev, 1000, decimals="0") + fact(rev, 400, "DP", "0") + fact(rev, 500, "DQ", "0")
    add("0117 FASB 606 exception (bank: NoninterestIncome, members below total) -> tier 3", ("1000", "900", "dim", 3),
        concept=rev, schema_role=IS_T,
        definition=table_link(IS, "srt:ProductOrServiceAxis", "srt:ProductsAndServicesDomain", p_tree,
                              line_items=("us-gaap:IncomeStatementAbstract", "us-gaap:NoninterestIncome", rev)),
        instance_facts=rev_facts)
    add("0117 606 revenue without the exception's conditions is reported", ("1000", "900", "dim", 1),
        concept=rev, schema_role=IS_T,
        definition=table_link(IS, "srt:ProductOrServiceAxis", "srt:ProductsAndServicesDomain", p_tree,
                              line_items=("us-gaap:IncomeStatementAbstract", rev)),
        instance_facts=rev_facts)

    # ---- no evidence
    add("nothing reported for the period", ("0", "0", "unresolved", 6),
        concept="us-gaap:OperatingExpenses", instance_facts=fact("us-gaap:OperatingExpenses", 5, "P", "0"))

    # ---- variant switches (each case names the switch set it runs under)
    SEG, CE, LE = "us-gaap:StatementBusinessSegmentsAxis", "srt:ConsolidatedEntitiesAxis", "srt:LegalEntityAxis"
    VIE = "us-gaap:VariableInterestEntityPrimaryBeneficiaryMember"
    ctx2 = CTX + "\n" + "\n".join([
        _ctx("S1", [(SEG, "abc:SegAMember")]), _ctx("S2", [(SEG, "abc:SegBMember")]),
        _ctx("S1V", [(SEG, "abc:SegAMember"), (CE, VIE)]), _ctx("S1N", [(SEG, "abc:SegAMember"), (CE, "abc:NonVieMember")]),
        _ctx("S1L", [(SEG, "abc:SegAMember"), (LE, "abc:SubsidiaryMember")]),
        _ctx("S1VP", [(SEG, "abc:SegAMember"), (CE, VIE), ("srt:ProductOrServiceAxis", "abc:ProductAMember")]),
    ])
    seg_axis = (SEG, "us-gaap:SegmentDomain", {"us-gaap:SegmentDomain": ["abc:SegAMember", "abc:SegBMember"]})
    ce_axis = (CE, "srt:ConsolidatedEntitiesDomain", {"srt:ConsolidatedEntitiesDomain": [VIE, "abc:NonVieMember"]})
    le_axis = (LE, "srt:LegalEntityDomain", {"srt:LegalEntityDomain": ["abc:SubsidiaryMember"]})
    ps_axis = ("srt:ProductOrServiceAxis", "srt:ProductsAndServicesDomain", {"srt:ProductsAndServicesDomain": ["abc:ProductAMember"]})
    seg_ce = table_link_multi(IS, [seg_axis, ce_axis])
    rv = "us-gaap:Revenues"
    adds_up = fact(rv, 1000, decimals="0") + fact(rv, 600, "S1", "0") + fact(rv, 400, "S2", "0")
    V1, V2 = engine.VARIANTS["V1"], engine.VARIANTS["V2"]

    def addv(name, expect, sw, **kw):
        concept = kw.pop("concept")
        out.append((name, expect, _query(concept, PERIOD, contexts=kw.pop("contexts", ctx2), **kw), sw))

    case_10093 = dict(concept=rv, schema_role=IS_T, definition=seg_ce, instance_facts=adds_up + fact(rv, 50, "S1V", "0"))
    addv("V0: 10093 shape is not modelled (9574 adds up, no finding)", ("1000", "-1000", "fallback", 6), engine.VARIANTS["V0"],
         **case_10093)
    addv("a10093: one-member total vs its second-axis breakdown", ("600", "50", "dim", 1), V1, **case_10093)
    addv("a10093: a 9574 finding in scope is kept", ("1000", "900", "dim", 1), V1,
         concept=rv, schema_role=IS_T, definition=seg_ce,
         instance_facts=fact(rv, 1000, decimals="0") + fact(rv, 600, "S1", "0") + fact(rv, 300, "S2", "0") + fact(rv, 50, "S1V", "0"))
    addv("a10093: second axis LegalEntityAxis is skipped", ("1000", "-1000", "fallback", 6), V1,
         concept=rv, schema_role=IS_T, definition=table_link_multi(IS, [seg_axis, le_axis]),
         instance_facts=adds_up + fact(rv, 50, "S1L", "0"))
    addv("a10093: needs the one-member total (exists)", ("1000", "-1000", "fallback", 6), V1,
         concept=rv, schema_role=IS_T, definition=seg_ce,
         instance_facts=fact(rv, 1000, decimals="0") + fact(rv, 50, "S1V", "0"))
    addv("a10093: difference inside tolerance (decimals -3, factor 2)", ("1000000", "-1000000", "fallback", 6), V1,
         concept=rv, schema_role=IS_T, definition=seg_ce,
         instance_facts=fact(rv, 1000000) + fact(rv, 600000, "S1") + fact(rv, 400000, "S2")
         + fact(rv, 300000, "S1V") + fact(rv, 299000, "S1N"))
    addv("a10093: second axis outside the table -> not a fact of the table", ("1000", "-1000", "fallback", 6), V1,
         concept=rv, schema_role=IS_T, definition=table_link_multi(IS, [seg_axis]),
         instance_facts=adds_up + fact(rv, 50, "S1V", "0"))
    addv("a10093: member with 3-dimension facts is left out", ("1000", "-1000", "fallback", 6), V1,
         concept=rv, schema_role=IS_T, definition=table_link_multi(IS, [seg_axis, ce_axis, ps_axis]),
         instance_facts=adds_up + fact(rv, 50, "S1V", "0") + fact(rv, 20, "S1VP", "0"))
    addv("a10093: not on a disclosure table", ("1000", "-1000", "fallback", 6), V1,
         concept=rv, schema_role=role_type(disc, "0050 - Disclosure - Revenue (Details)"),
         definition=table_link_multi(disc, [seg_axis, ce_axis]), instance_facts=adds_up + fact(rv, 50, "S1V", "0"))
    no_total = fact(rv, 600, "S1", "0") + fact(rv, 400, "S2", "0")
    addv("V1: a 9574 breakdown without a reported total is still tier 1", ("0", "1000", "dim", 1), V1,
         concept=rv, schema_role=IS_T, definition=seg_ce, instance_facts=no_total + fact(rv, 50, "S1V", "0"))
    addv("total_required: without a reported total, 10093 is the finding", ("600", "50", "dim", 1), V2,
         concept=rv, schema_role=IS_T, definition=seg_ce, instance_facts=no_total + fact(rv, 50, "S1V", "0"))
    addv("total_required: no other finding -> same answer at tier 2", ("0", "1000", "dim", 2), V2,
         concept=rv, schema_role=IS_T, definition=seg_ce, instance_facts=no_total)
    capex = "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment"
    negs = fact(capex, -10, decimals="0") + fact(capex, -5, "DP", "0") + fact(capex, -7, "DQ", "0")
    negs_dim = fact(capex, 900, decimals="0") + fact(capex, -5, "DP", "0") + fact(capex, -7, "DQ", "0")
    for pol, want in ((("nondim", "first"), "-10"), (("nondim", "last"), "-10"), (("dim", "first"), "-5"),
                      (("dim", "last"), "-7"), (("none", "first"), "-10"), (("none", "last"), "-7"),
                      (("none", "minabs"), "-5"), (("dim", "maxabs"), "-7")):
        addv(f"0015 policy {pol[0]},{pol[1]} (non-dimensional -10, then -5, -7)", (want, want[1:], "neg", 1), ((), pol),
             concept=capex, instance_facts=negs)
    for pol, want in ((("nondim", "first"), "-5"), (("nondim", "last"), "-7"), (("nondim", "maxabs"), "-7"),
                      (("nondim", "minabs"), "-5")):
        addv(f"0015 policy {pol[0]},{pol[1]} (total positive; -5, -7)", (want, want[1:], "neg", 1), ((), pol),
             concept=capex, instance_facts=negs_dim)
    return out


def main() -> int:
    fails = 0
    all_cases = cases()
    try:
        for name, (e, c, mech, tier), q, (fixes, policy) in all_cases:
            engine.configure(fixes, policy)
            p = predict(q)
            ok = (p.extracted_value, p.calculated_value, p.mechanism, p.tier) == (e, c, mech, tier)
            fails += not ok
            print(("ok  " if ok else "FAIL"), name, "" if ok else f"-> got {p}")
        # The 29 V0 cases under the rule-fix variants: V1 changes none of them (no
        # 10093 shape among them); V2 changes only the breakdown without a total,
        # which keeps its answer but drops to tier 2.
        moved = {"0117 no default fact: extracted is 0": ("0", "101", "dim", 2)}
        for vname in ("V1", "V2"):
            engine.configure(*engine.VARIANTS[vname])
            for name, expect, q, sw in all_cases[:29]:
                want = moved.get(name, expect) if vname == "V2" else expect
                p = predict(q)
                ok = (p.extracted_value, p.calculated_value, p.mechanism, p.tier) == want
                fails += not ok
                if not ok:
                    print("FAIL", f"{vname} on a V0 case:", name, f"-> got {p}")
    finally:
        engine.configure(*engine.VARIANTS["V0"])
    print("FAIL" if fails else "OK", f"({fails} failing of {len(all_cases)}, plus the 29 V0 cases rerun under V1 and V2)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

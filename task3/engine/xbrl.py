"""Linear-time parsing of one FinReason Task 3 case.

Everything here reads only the case's own ``query`` string: the instruction
header, the filing sections (schema, linkbases, instance) and the US GAAP
taxonomy excerpt. Nothing is looked up anywhere else.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

SECTION_HEADERS = (
    "##Schema document",
    "##Presentation linkbase document",
    "##Calculation linkbase document",
    "##Definition linkbase document",
    "##Label linkbase document",
    "##Instance document",
    "##US GAAP Taxonomy",
)
SECTION_KEYS = ("schema", "presentation", "calculation", "definition", "label", "instance", "taxonomy")


def split_sections(query: str) -> Dict[str, str]:
    """Cut the query at its fixed, ordered section headers."""
    positions: List[Tuple[int, str]] = []
    start = 0
    for header, key in zip(SECTION_HEADERS, SECTION_KEYS):
        i = query.find(header, start)
        if i >= 0:
            positions.append((i, key))
            start = i + len(header)
    q1 = query.rfind("Question1:")
    out: Dict[str, str] = {k: "" for k in SECTION_KEYS}
    for n, (i, key) in enumerate(positions):
        j = positions[n + 1][0] if n + 1 < len(positions) else (q1 if q1 > i else len(query))
        out[key] = query[i:j]
    out["question"] = query[q1:] if q1 >= 0 else ""
    return out


# --------------------------------------------------------------------- question

@dataclass(frozen=True)
class Target:
    concept: str  # prefix:Local as written in the question
    start: str
    end: Optional[str]  # None for an instant

    @property
    def local(self) -> str:
        return self.concept.split(":")[-1]

    @property
    def prefix(self) -> str:
        return self.concept.split(":")[0] if ":" in self.concept else ""

    @property
    def is_instant(self) -> bool:
        return self.end is None


_QUESTION = re.compile(
    r"Question1:.*?reported value of\s+([\w.-]+:[\w.-]+|[\w.-]+).*?"
    r"period\s+(\d{4}-\d{2}-\d{2})(?:\s+to\s+(\d{4}-\d{2}-\d{2}))?",
    re.S,
)


def parse_question(question: str) -> Optional[Target]:
    m = _QUESTION.search(question)
    if not m:
        return None
    return Target(m.group(1), m.group(2), m.group(3))


# --------------------------------------------------------------------- instance

@dataclass(frozen=True)
class Context:
    id: str
    start: Optional[str]
    end: Optional[str]
    instant: Optional[str]
    dims: Tuple[Tuple[str, str], ...]  # sorted (axis, member)

    def matches(self, target: Target) -> bool:
        if target.end is None:
            return self.instant == target.start
        return self.start == target.start and self.end == target.end


@dataclass
class Fact:
    concept: str  # prefix:Local as written in the instance
    local: str
    context: str
    unit: Optional[str]
    decimals: Optional[str]
    raw: str
    nil: bool
    order: int

    @property
    def value(self) -> Optional[Decimal]:
        return to_decimal(self.raw)


_CONTEXT_RE = re.compile(r"<(?:[\w-]+:)?context\b([^>]*)>(.*?)</(?:[\w-]+:)?context>", re.S)
_ATTR_RE = re.compile(r'([\w:.-]+)\s*=\s*"([^"]*)"')
_ATTR_RE_SQ = re.compile(r"([\w:.-]+)\s*=\s*'([^']*)'")
_START_RE = re.compile(r"<(?:[\w-]+:)?startDate>\s*([^<\s]+)\s*<")
_END_RE = re.compile(r"<(?:[\w-]+:)?endDate>\s*([^<\s]+)\s*<")
_INSTANT_RE = re.compile(r"<(?:[\w-]+:)?instant>\s*([^<\s]+)\s*<")
_EXPLICIT_RE = re.compile(r"<(?:[\w-]+:)?explicitMember\b([^>]*)>\s*([^<\s]+)\s*<")
_TYPED_RE = re.compile(r"<(?:[\w-]+:)?typedMember\b([^>]*)>(.*?)</(?:[\w-]+:)?typedMember>", re.S)
_FACT_OPEN_RE = re.compile(r"<([A-Za-z_][\w.-]*:[\w.-]+|[A-Za-z_][\w.-]*)\s([^<>]*?\bcontextRef\s*=\s*[\"'][^\"']*[\"'][^<>]*?)(/?)>")
_TAG_RE = re.compile(r"<[^>]*>")


def attrs_of(text: str) -> Dict[str, str]:
    d = dict(_ATTR_RE.findall(text))
    if "'" in text:
        for k, v in _ATTR_RE_SQ.findall(text):
            d.setdefault(k, v)
    return d


def _date_only(s: Optional[str]) -> Optional[str]:
    """Start dates: the calendar date of the value (a dateTime keeps its date)."""
    if s is None:
        return None
    return s[:10]


def _end_date(s: Optional[str]) -> Optional[str]:
    """End dates and instants, XBRL 2.1 section 4.7.2: a date-only value means the
    end of that day, while a dateTime at midnight (T00:00:00) means the end of
    the previous day. Both are reported here as the calendar date they close."""
    if s is None:
        return None
    if len(s) > 10 and s[10] == "T" and s[11:19] == "00:00:00":
        try:
            return (_dt.date.fromisoformat(s[:10]) - _dt.timedelta(days=1)).isoformat()
        except ValueError:
            return s[:10]
    return s[:10]


def parse_contexts(instance: str) -> Dict[str, Context]:
    out: Dict[str, Context] = {}
    for m in _CONTEXT_RE.finditer(instance):
        a = attrs_of(m.group(1))
        cid = a.get("id")
        if not cid:
            continue
        body = m.group(2)
        s = _START_RE.search(body)
        e = _END_RE.search(body)
        i = _INSTANT_RE.search(body)
        dims: List[Tuple[str, str]] = []
        for em in _EXPLICIT_RE.finditer(body):
            dims.append((attrs_of(em.group(1)).get("dimension", ""), em.group(2)))
        for tm in _TYPED_RE.finditer(body):
            val = _TAG_RE.sub("", tm.group(2)).strip()
            dims.append((attrs_of(tm.group(1)).get("dimension", ""), "typed:" + val))
        out[cid] = Context(
            cid,
            _date_only(s.group(1)) if s else None,
            _end_date(e.group(1)) if e else None,
            _end_date(i.group(1)) if i else None,
            tuple(sorted(dims)),
        )
    return out


def parse_facts(instance: str) -> List[Fact]:
    facts: List[Fact] = []
    n = 0
    for m in _FACT_OPEN_RE.finditer(instance):
        tag, attr_text, selfclose = m.group(1), m.group(2), m.group(3)
        if tag.endswith("context") or tag.endswith("unit"):
            continue
        a = attrs_of(attr_text)
        nil = a.get("xsi:nil", "").strip().lower() == "true"
        raw = ""
        if not selfclose:
            close = "</" + tag + ">"
            j = instance.find(close, m.end())
            if j < 0:
                continue  # truncated document: the value never arrives
            raw = instance[m.end():j]
            if "<" in raw:
                # nested markup (text blocks): never a number we need
                raw = _TAG_RE.sub("", raw)
            raw = raw.strip()
        local = tag.split(":")[-1]
        sign = a.get("sign")
        if sign == "-" and raw and not raw.startswith("-"):
            raw = "-" + raw
        facts.append(Fact(tag, local, a.get("contextRef", ""), a.get("unitRef"), a.get("decimals"), raw, nil, n))
        n += 1
    return facts


_ROOT_RE = re.compile(r"<(?:[\w-]+:)?xbrl\b([^>]*)>", re.S)
_XMLNS_RE = re.compile(r"""xmlns:([\w.-]+)\s*=\s*["']([^"']*)["']""")


def instance_namespaces(instance: str) -> Dict[str, str]:
    """prefix -> namespace URI declared on the instance root element (where XBRL
    instances declare them). Empty when no root element is found."""
    m = _ROOT_RE.search(instance)
    if not m:
        return {}
    return {p: u for p, u in _XMLNS_RE.findall(m.group(1))}


# --------------------------------------------------------------------- numbers

def to_decimal(raw: Optional[str]) -> Optional[Decimal]:
    if raw is None:
        return None
    t = raw.strip().replace(",", "").replace("−", "-")
    if not t:
        return None
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1]
    try:
        d = Decimal(t)
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite():
        return None
    return -d if neg else d


def fmt_decimal(d: Decimal) -> str:
    """Plain, full-scale rendering: no exponent, no trailing '.0'."""
    if d == 0:
        return "0"
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s in ("-0", ""):
        s = "0"
    return s


# --------------------------------------------------------------------- calculation linkbase

@dataclass
class CalcArc:
    parent: str  # prefix:Local
    child: str
    weight: Decimal
    order: Optional[str]
    role: str
    role_title: str


_LINK_RE = re.compile(r"<(?:[\w-]+:)?calculationLink\b([^>]*?)(/?)>", re.S)
_LOC_RE = re.compile(r"<(?:[\w-]+:)?loc\b([^>]*)/?>", re.S)
_ARC_RE = re.compile(r"<(?:[\w-]+:)?calculationArc\b([^>]*)/?>", re.S)


def concept_from_href(href: str) -> str:
    frag = href.split("#", 1)[-1]
    if "_" in frag:
        p, _, l = frag.partition("_")
        return p + ":" + l
    return frag


def parse_calc(calc: str) -> List[CalcArc]:
    arcs: List[CalcArc] = []
    links = list(_LINK_RE.finditer(calc))
    for n, lm in enumerate(links):
        if lm.group(2) == "/":
            continue
        body_end = calc.find("calculationLink>", lm.end())
        nxt = links[n + 1].start() if n + 1 < len(links) else len(calc)
        if body_end < 0 or body_end > nxt:
            body_end = nxt
        body = calc[lm.end():body_end]
        a = attrs_of(lm.group(1))
        role = a.get("xlink:role", "")
        title = a.get("xlink:title", "")
        locs: Dict[str, str] = {}
        for loc in _LOC_RE.finditer(body):
            la = attrs_of(loc.group(1))
            if "xlink:label" in la and "xlink:href" in la:
                locs[la["xlink:label"]] = concept_from_href(la["xlink:href"])
        prohibited = set()
        raw_arcs = []
        for am in _ARC_RE.finditer(body):
            aa = attrs_of(am.group(1))
            arcrole = aa.get("xlink:arcrole", "")
            if not arcrole.endswith("summation-item"):
                continue
            frm, to = aa.get("xlink:from"), aa.get("xlink:to")
            if frm not in locs or to not in locs:
                continue
            try:
                w = Decimal(aa.get("weight", "1"))
            except InvalidOperation:
                continue
            if aa.get("use") == "prohibited":
                prohibited.add((locs[frm], locs[to]))
                continue
            raw_arcs.append(CalcArc(locs[frm], locs[to], w, aa.get("order"), role, title))
        for arc in raw_arcs:
            if (arc.parent, arc.child) not in prohibited:
                arcs.append(arc)
    return arcs


def role_titles(schema: str, calc: str) -> Dict[str, str]:
    """role URI -> definition text ("0000005 - Statement - ...")."""
    out: Dict[str, str] = {}
    for m in re.finditer(r"<(?:[\w-]+:)?roleType\b([^>]*)>(.*?)</(?:[\w-]+:)?roleType>", schema, re.S):
        a = attrs_of(m.group(1))
        d = re.search(r"<(?:[\w-]+:)?definition>(.*?)</(?:[\w-]+:)?definition>", m.group(2), re.S)
        if a.get("roleURI") and d:
            out[a["roleURI"]] = d.group(1).strip()
    for lm in _LINK_RE.finditer(calc):
        a = attrs_of(lm.group(1))
        if a.get("xlink:role") and a.get("xlink:title"):
            out.setdefault(a["xlink:role"], a["xlink:title"])
    return out


# --------------------------------------------------------------------- taxonomy

@dataclass
class TaxonomyInfo:
    balance: Optional[str] = None
    item_type: Optional[str] = None
    period_type: Optional[str] = None
    label: Optional[str] = None
    std_children: List[Tuple[str, Decimal, str]] = field(default_factory=list)
    std_parents: List[Tuple[str, Decimal, str]] = field(default_factory=list)


def parse_taxonomy(tax: str, concept: str) -> TaxonomyInfo:
    info = TaxonomyInfo()
    m = re.search(r"ID:\s*" + re.escape(concept) + r"\s*\n(.*?)(?:\n\n|\Z)", tax, re.S)
    if m:
        block = m.group(1)
        b = re.search(r"Balance:\s*([\w-]+)", block)
        if b:
            info.balance = b.group(1).lower()
        t = re.search(r"Type:\s*([\w:.-]+)", block)
        if t:
            info.item_type = t.group(1)
        p = re.search(r"PeriodType:\s*([\w-]+)", block)
        if p:
            info.period_type = p.group(1)
        lab = re.search(r"Label:\s*([^\n]*)", block)
        if lab:
            info.label = lab.group(1).strip()
    cm = re.search(r"Calculation:\s*\n(.*?)(?:\nProvenance:|\n\n\[|\Z)", tax, re.S)
    if cm:
        mode = None
        for line in cm.group(1).splitlines():
            s = line.strip()
            if s.startswith("- As Parent"):
                mode = "p"
                continue
            if s.startswith("- As Child"):
                mode = "c"
                continue
            mm = re.match(r"(child|parent)=([\w:.-]+)\s*\|\s*weight=([-\d.]+)\s*\|\s*role=(\S+)", s)
            if mm:
                try:
                    w = Decimal(mm.group(3))
                except InvalidOperation:
                    continue
                if mm.group(1) == "child":
                    info.std_children.append((mm.group(2), w, mm.group(4)))
                else:
                    info.std_parents.append((mm.group(2), w, mm.group(4)))
    return info


# --------------------------------------------------------------------- definition linkbase

@dataclass
class DimensionalRole:
    """Dimensional structure of one definition network (extended link role)."""

    role: str
    hypercubes: Dict[str, List[str]] = field(default_factory=dict)  # hypercube -> axes
    primaries: Dict[str, List[str]] = field(default_factory=dict)   # primary item -> hypercubes (via 'all')
    children: Dict[str, List[str]] = field(default_factory=dict)    # domain-member / dimension-domain tree
    domains: Dict[str, List[str]] = field(default_factory=dict)     # axis -> domain heads
    defaults: Dict[str, str] = field(default_factory=dict)          # axis -> default member
    line_items: Dict[str, List[str]] = field(default_factory=dict)  # domain-member tree from primaries

    @property
    def axes(self) -> List[str]:
        out: List[str] = []
        for ax in self.hypercubes.values():
            for a in ax:
                if a not in out:
                    out.append(a)
        return out

    def members(self, axis: str) -> List[str]:
        """All descendants of the axis's domain(s), domain heads excluded."""
        out: List[str] = []
        seen = set()
        stack = list(reversed(self.domains.get(axis, [])))
        heads = set(self.domains.get(axis, []))
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            if node not in heads:
                out.append(node)
            for ch in reversed(self.children.get(node, [])):
                stack.append(ch)
        return out

    def ancestors(self, axis: str, member: str) -> List[str]:
        """Ancestors of ``member`` inside the axis's domain tree, domain heads excluded."""
        heads = set(self.domains.get(axis, []))
        parent_of: Dict[str, List[str]] = {}
        for p, chs in self.children.items():
            for c in chs:
                parent_of.setdefault(c, []).append(p)
        out: List[str] = []
        stack = list(parent_of.get(member, []))
        seen = set()
        while stack:
            p = stack.pop()
            if p in seen:
                continue
            seen.add(p)
            if p in heads:
                continue
            out.append(p)
            stack.extend(parent_of.get(p, []))
        return out


_DLINK_RE = re.compile(r"<(?:[\w-]+:)?definitionLink\b([^>]*?)(/?)>", re.S)
_DARC_RE = re.compile(r"<(?:[\w-]+:)?definitionArc\b([^>]*)/?>", re.S)


def parse_definition(defn: str) -> List[DimensionalRole]:
    out: List[DimensionalRole] = []
    links = list(_DLINK_RE.finditer(defn))
    for n, lm in enumerate(links):
        if lm.group(2) == "/":
            continue
        nxt = links[n + 1].start() if n + 1 < len(links) else len(defn)
        body_end = defn.find("definitionLink>", lm.end())
        if body_end < 0 or body_end > nxt:
            body_end = nxt
        body = defn[lm.end():body_end]
        dr = DimensionalRole(attrs_of(lm.group(1)).get("xlink:role", ""))
        locs: Dict[str, str] = {}
        for loc in _LOC_RE.finditer(body):
            la = attrs_of(loc.group(1))
            if "xlink:label" in la and "xlink:href" in la:
                locs[la["xlink:label"]] = concept_from_href(la["xlink:href"])
        arcs = []
        for am in _DARC_RE.finditer(body):
            aa = attrs_of(am.group(1))
            frm, to = locs.get(aa.get("xlink:from", "")), locs.get(aa.get("xlink:to", ""))
            if not frm or not to:
                continue
            order = aa.get("order")
            try:
                o = float(order) if order is not None else 0.0
            except ValueError:
                o = 0.0
            arcs.append((o, aa.get("xlink:arcrole", "").rsplit("/", 1)[-1], frm, to, aa.get("use")))
        arcs.sort(key=lambda x: x[0])
        for _, arcrole, frm, to, use in arcs:
            if use == "prohibited":
                continue
            if arcrole == "all":
                dr.primaries.setdefault(frm, []).append(to)
            elif arcrole == "hypercube-dimension":
                dr.hypercubes.setdefault(frm, []).append(to)
            elif arcrole == "dimension-domain":
                dr.domains.setdefault(frm, []).append(to)
            elif arcrole == "domain-member":
                dr.children.setdefault(frm, []).append(to)
            elif arcrole == "dimension-default":
                dr.defaults[frm] = to
        out.append(dr)
    return out


def local_name(qname: str) -> str:
    return qname.split(":")[-1]

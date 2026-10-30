"""Operating Plan (OP) file extraction: a plant's monthly plan file (Excel or
text PDF) -> proposed production_op_monthly values, for review on the OP
upload page (frontend/src/components/entry/op-plan-upload/Form.js) before
they are saved through POST /api/op-plan.

Every plant's plan file lists, per line, a label, the APP figure and the
month's plan (OP) figure, in its own layout and wording. Extraction:

1. read_lines: (label, app, op) for every line with two numbers after a
   label - PDF text lines, or the Item / APP / Plan columns of a sheet.
2. map_lines: the label names a production item through the plant's alias
   patterns (_PLANT_ALIASES, then _COMMON_ALIASES). The file's APP figure,
   compared with the APP already in the database for that item, picks
   between several candidates (BSP's several "Total" lines), confirms the
   match, and tells tonnes from '000 T per line (RSP sends tonnes).
3. Composite items the file splits into parts (DSP Billet Caster = Billet
   M/C-1 + M/C-2) are summed, and copies (RSP Finished = Saleable Steel)
   repeated.

Nothing is saved here; the page shows every line with its proposed item and
a status, and the user confirms what to save.
"""
import io
import re
from typing import Dict, List, Optional, Tuple

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
PLANTS = ("BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL")

# A label pattern (on the normalised label, see _norm) -> candidate items.
# Common patterns apply to every plant whose own patterns did not match.
_COMMON_ALIASES: List[Tuple[str, List[str]]] = [
    (r"\b(eq|equv|equivalent)\b.*push|oven push", ["Oven Pushing (nos/day)"]),
    (r"^(total |gross )?sinter$|^total sinter", ["Total Sinter"]),
    (r"^(total )?(hot metal|hm)$", ["Hot Metal"]),
    (r"^(cold )?pig iron$", ["Pig Iron"]),
    (r"^(total )?crude steel$", ["Total Crude Steel"]),
    (r"^(total )?finished( steel)?$", ["Finished Steel"]),
    (r"^(total |saleable )?semis$|^saleable semis$", ["Saleable Semis"]),
    (r"^(total )?saleable steel( production)?$", ["Saleable Steel"]),
]

_PLANT_ALIASES: Dict[str, List[Tuple[str, List[str]]]] = {
    "BSP": [
        (r"\bsp ii$", ["SP-2"]),
        (r"\bsp iii$", ["SP-3"]),
        (r"\bbf 4 7$", ["BF#1-7"]),
        (r"^bf 8$", ["BF#8"]),
        (r"^total$", ["Total Crude Steel", "SMS-2", "SMS-3"]),
        (r"crude steel sms ii$|^sms ii$", ["SMS-2"]),
        (r"^sms iii$", ["SMS-3"]),
        (r"cast blooms$", ["SMS-2 BLOOM"]),
        (r"^cast slabs$", ["SMS-2 SLAB"]),
        (r"billets ?105", ["SMS-3 Billet105"]),
        (r"billets ?150", ["SMS-3 Billet150"]),
        (r"^blooms$", ["SMS-3 BLOOM(CV1&2)"]),
        (r"\brsm rails$", ["RSM_RAIL"]),
        (r"\burm rails$", ["URM_RAIL"]),
        (r"^prime rsm$", ["RSMPRIME"]),
        (r"^urm$", ["URMPRIME"]),
        (r"^merchant products?$", ["MM"]),
        (r"^wire rods?$", ["WIRERODS"]),
        (r"^brm$", ["BARS&RODMILL"]),
        (r"^plates$", ["PLATEMILL"]),
        (r"^billets$", ["SEMIS BilletS"]),
        (r"^ccs blooms$", ["SEMIS BLOOM"]),
        (r"^slabs$", ["SEMIS SLABS"]),
    ],
    "DSP": [
        (r"^hm to asp$", ["Hot Metal to ASP"]),
        (r"^hm to pcm$", ["Hot Metal to PCM"]),
        (r"^bottom pouring$", ["Bottom Pouring Ingot"]),
        (r"^concast steel$", ["SMS Total Caster"]),
        (r"^bloom m c 3$", ["Bloom Caster"]),
        (r"^brc round$", ["Round Production"]),
        (r"^merchant mill$", ["MM"]),
        (r"^msm$", ["MSM"]),
        (r"^wheel (and )?axle plant$", ["WAP"]),
    ],
    "RSP": [
        (r"^oven pushing", ["COB#1-5"]),
        (r"^pcm$", ["Pig Iron"]),
        (r"^battery 6$", ["COB#6"]),
        (r"^sp i$", ["SP-1"]),
        (r"^sp 2$|^sp ii$", ["SP-2"]),
        (r"^sp 3$|^sp iii$", ["SP-3"]),
        (r"^bf ?1$", ["BF#1"]),
        (r"^bf ?4$", ["BF#4"]),
        (r"^bf ?5$", ["BF#5"]),
        (r"^crude steel sms i$", ["SMS-1 CCM-1"]),
        (r"hsm 2 rolling coils$|^coils$", ["HSM-2 Total HR Coil"]),
        (r"^hrc s hsm 2$", ["HSM-2 HR Coil (Sale)"]),
        (r"^hrp ssl$", ["HSM-2 HR Plate"]),
        (r"^npm plates$", ["NPM Plate"]),
        (r"^pm plates$", ["OPM Plate"]),
        (r"^plates$", ["NPM Plate", "OPM Plate"]),
        (r"^e r ?w pipes$|^erw pipes$", ["ERW Pipes"]),
        (r"^s w pipes$|^sw pipes$", ["SW Pipes"]),
        (r"^ssm coil$|^crno", ["CRNO Coils"]),
    ],
    "BSL": [
        (r"^oven pushings?", ["Oven Pushing (nos/day)"]),
        (r"cast slab ?sms new$", ["SMS-1 CCM-1"]),
        (r"cast slab ?sms ii$", ["SMS-2 CCM-1&2"]),
        (r"^hr coil$", ["HSM Total HR Coil", "HSM HR Coil (Sale)"]),
        (r"^cr saleable$", ["CR Saleable"]),
        (r"^crm i (and )?ii$", ["CR(1&2) Total Saleable"]),
        (r"^crm iii$", ["CR III Total Saleable"]),
        (r"^slab$", ["Saleable Semis"]),
    ],
    "ISP": [
        (r"^cob ?10", ["COB#10"]),
        (r"^cob ?11", ["COB#11"]),
        (r"^all cob$", ["Oven Pushing (nos/day)"]),
        (r"^caster ?1 ?2$", ["SMS CCM-1&2"]),
        (r"^caster ?3$", ["SMS CCM-3"]),
        (r"^wr ?mill$", ["WRMILL"]),
        (r"^bar ?mill$", ["BARMILL"]),
        (r"^us ?mill$", ["USMILL"]),
        (r"^150 billets$", ["Saleable 150 Billets"]),
        (r"^200 blooms$", ["200 Blooms"]),
    ],
}

# Items the file gives only as parts: item -> label patterns summed.
_COMPOSITES: Dict[str, List[Tuple[str, List[str]]]] = {
    "DSP": [
        ("Billet Caster", [r"^billet m c 1$", r"^billet m c 2$"]),
        ("BRC", [r"^brc bloom$", r"^brc round$"]),
    ],
}
# Items equal to another item in the plant's reporting: item <- source item.
_COPIES: Dict[str, List[Tuple[str, str]]] = {
    "RSP": [("Finished Steel", "Saleable Steel")],
}

_NUM_RE = re.compile(r"^-?\d[\d,]*(\.\d+)?$")
_STOP_MARKERS = ("ROLLING PLAN", "From:", "Regards")


def _num(tok) -> Optional[float]:
    if isinstance(tok, (int, float)) and not isinstance(tok, bool):
        return float(tok)
    s = str(tok).strip()
    return float(s.replace(",", "")) if _NUM_RE.match(s) else None


def _norm(label: str) -> str:
    """Lower-case English part of a label: after the last ' / ' when Hindi
    precedes it, without a leading serial number, units in brackets or
    punctuation ('4 Hot Metal BF:4-7' -> 'hot metal bf 4 7')."""
    s = str(label or "")
    if " / " in s:
        s = s.rsplit(" / ", 1)[1]
    s = re.sub(r"\((nos|pushings)[^)]*\)", " ", s, flags=re.I)
    s = s.replace("&", " and ").replace("²", "")
    s = re.sub(r"[^A-Za-z0-9]+", " ", s).strip().lower()
    s = re.sub(r"^(\d{1,2}|[ivx]+)\s+(?=[a-z])", "", s)      # serial number / roman list mark
    for prefix in ("sinter ", "hot metal ", "crude steel ", "finished ", "sms ii ", "sms iii "):
        # BSP prefixes a section name to the section's first line ('3 SINTER SP - II')
        if s.startswith(prefix) and re.search(r"\b(sp|bf|cast|billets|blooms|urm|rsm)\b", s[len(prefix):]):
            s = s[len(prefix):]
            break
    return s


def read_lines(data: bytes, filename: str) -> Tuple[List[dict], str]:
    """-> ([{label, app, op}], file text for plant / month detection).
    Raises ValueError for a file with no readable text (a scan or a photo)."""
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")):
        return _read_xlsx(data)
    if name.endswith(".pdf"):
        return _read_pdf(data)
    raise ValueError("Upload an Excel (.xlsx) or PDF plan file. A photo or scan has no text to read; "
                     "enter that plan on the Operating Plan (OP) tab instead.")


def _read_pdf(data: bytes):
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        text = "\n".join(pg.extract_text() or "" for pg in pdf.pages)
    if len(re.findall(r"[A-Za-z]", text)) < 40:
        raise ValueError("This PDF has no readable text (it looks scanned). Enter the plan on the "
                         "Operating Plan (OP) tab instead.")
    lines = []
    for raw in text.splitlines():
        if any(m in raw for m in _STOP_MARKERS) and lines:
            break                                      # rolling-plan pages, e-mail trail
        toks = raw.split()
        for i in range(1, len(toks) - 1):
            a, b = _num(toks[i]), _num(toks[i + 1])
            label = " ".join(toks[:i])
            if a is not None and b is not None and re.search(r"[A-Za-z]", label):
                lines.append({"label": label, "app": a, "op": b})
                break
    return lines, text


def _read_xlsx(data: bytes):
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    text_parts = []
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        text_parts += [" ".join(str(v) for v in r if v is not None) for r in rows[:6]]
        head = _xlsx_header(rows)
        if head is None:
            continue
        hi, lc, ac, oc = head
        lines = []
        for r in rows[hi + 1:]:
            cell = lambda c: r[c] if c < len(r) else None
            a, b = _num(cell(ac)) if cell(ac) is not None else None, _num(cell(oc)) if cell(oc) is not None else None
            if a is None or b is None:
                continue
            lines.append({"label": str(cell(lc) or "").strip(), "app": a, "op": b})
        return lines, "\n".join(text_parts + [ws.title])
    raise ValueError("No sheet has an 'Item | APP | Plan' header row.")


def _xlsx_header(rows):
    """(row index, label col, APP col, OP col) of the 'Item | APP | Plan' row."""
    for i, r in enumerate(rows[:15]):
        cells = [str(v).strip().lower() if v is not None else "" for v in r]
        lc = next((c for c, v in enumerate(cells) if re.match(r"^(i ?t ?e ?m ?s?|particulars|department)$", v)), None)
        ac = next((c for c, v in enumerate(cells) if re.match(r"^(app|abp)\b", v)), None)
        oc = next((c for c, v in enumerate(cells)
                   if c != ac and re.search(r"operating plan|proposed plan|monthly plan|^plan$|^rmt$|^op$", v)), None)
        if lc is not None and ac is not None and oc is not None:
            return i, lc, ac, oc
    return None


def detect(text: str, filename: str) -> dict:
    """Best guess of plant and month ('YYYY-MM') from the file name and text."""
    hay = f"{filename}\n{text[:4000]}"
    # the file name first; then a 'SAIL/DSP' style header; then the plant the
    # text names most (an e-mailed plan carries every plant's address)
    plant = next((p for p in PLANTS if re.search(rf"\b{p}\b", filename)), None)
    if plant is None:
        m = re.search(r"SAIL\s*/\s*([A-Z]{3,4})\b", text[:2000])
        plant = m.group(1) if m and m.group(1) in PLANTS else None
    if plant is None:
        counts = {p: len(re.findall(rf"\b{p}\b", text)) for p in PLANTS}
        counts["ISP"] += len(re.findall(r"IISCO", text, re.I))
        best = max(counts, key=counts.get)
        plant = best if counts[best] else None
    month = None
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s'\-_.]*((?:20)?\d{2})\b", hay, re.I)
    if m:
        y = int(m.group(2))
        month = f"{2000 + y if y < 100 else y}-{MONTHS[m.group(1).lower()]:02d}"
    return {"plant": plant, "month": month}


def _app_close(a: Optional[float], b: Optional[float]) -> bool:
    """File APP vs database APP: equal after the file's rounding (to the
    nearest unit, or 1 %)."""
    if a is None or b is None:
        return False
    return abs(a - b) <= max(0.55, abs(b) * 0.01)


def map_lines(plant: str, lines: List[dict], db_items: Dict[str, Optional[float]]) -> List[dict]:
    """Proposed item for each line. db_items = {item_name: APP or None} for
    the plant and month. Each returned row: label, app, op (as in the file),
    scale (1 or 0.001), item (or None), op_value (in the item's units),
    db_app, status in {'matched', 'check', 'app-only', 'duplicate',
    'unmatched'} and selected (bool)."""
    aliases = _PLANT_ALIASES.get(plant, [])
    rows = []
    for ln in lines:
        key = _norm(ln["label"])
        cands = next((c for p, c in aliases if re.search(p, key)), None)
        if cands is None:
            cands = next((c for p, c in _COMMON_ALIASES if re.search(p, key)), [])
        cands = [c for c in cands if c in db_items]
        rows.append(_resolve(ln, key, cands, db_items))
    rows += _composites(plant, rows, db_items)
    rows += _copies(plant, rows, db_items)
    _drop_duplicates(rows)
    return rows


def _resolve(ln, key, cands, db_items):
    row = {"label": ln["label"], "key": key, "app": ln["app"], "op": ln["op"], "scale": 1.0,
           "item": None, "db_app": None, "status": "unmatched", "selected": False}

    def hit(item, scale):
        return _app_close(ln["app"] * scale, db_items.get(item))

    for scale in (1.0, 0.001):
        matched = [c for c in cands if hit(c, scale)]
        if len(matched) == 1:
            return _set(row, matched[0], scale, db_items, "matched")
    if len(cands) == 1:
        # named by its label but the APP differs: proposed, ticked only when
        # the APP is near (rounding) or unknown - a far-off APP usually means
        # the wrong plant or month
        scale = 0.001 if ln["app"] >= 1000 and (db_items.get(cands[0]) or 0) < 1000 else 1.0
        _set(row, cands[0], scale, db_items, "check")
        db_app = db_items.get(cands[0])
        row["selected"] = db_app is None or abs(ln["app"] * scale - db_app) <= max(1.0, abs(db_app) * 0.15)
        return row
    if not cands and not key:
        # an unlabelled total line (BSL prints Finished Steel without a label)
        for scale in (1.0, 0.001):
            matched = [i for i, v in db_items.items() if _app_close(ln["app"] * scale, v)]
            if len(matched) == 1:
                return _set(row, matched[0], scale, db_items, "app-only")
    return row


def _set(row, item, scale, db_items, status):
    row.update(item=item, scale=scale, db_app=db_items.get(item), status=status, selected=True,
               op_value=round(row["op"] * scale, 3))
    return row


def _composites(plant, rows, db_items):
    out = []
    for item, patterns in _COMPOSITES.get(plant, []):
        parts = [next((r for r in rows if re.search(p, r["key"])), None) for p in patterns]
        if item not in db_items or any(p is None for p in parts):
            continue
        app = sum(p["app"] for p in parts)
        op = sum(p["op"] for p in parts)
        label = " + ".join(p["label"].rsplit(" / ", 1)[-1] for p in parts)
        row = {"label": label, "key": "", "app": app, "op": op, "scale": 1.0, "item": None,
               "db_app": None, "status": "unmatched", "selected": False, "composite": True}
        out.append(_set(row, item, 1.0, db_items, "matched" if _app_close(app, db_items[item]) else "check"))
    return out


def _copies(plant, rows, db_items):
    out = []
    for item, source in _COPIES.get(plant, []):
        src = next((r for r in rows if r["item"] == source and r["selected"]), None)
        if src is None or item not in db_items:
            continue
        row = dict(src, label=f"{src['label']} (= {source})", key="", composite=True)
        out.append(_set(row, item, src["scale"], db_items,
                        "matched" if _app_close(src["app"] * src["scale"], db_items[item]) else "check"))
    return out


_RANK = {"matched": 0, "check": 1, "app-only": 2}


def _drop_duplicates(rows):
    """One line per item: the best-matched (then first) line keeps it."""
    best = {}
    for i, r in enumerate(rows):
        if r["selected"]:
            j = best.get(r["item"])
            if j is None or _RANK[r["status"]] < _RANK[rows[j]["status"]]:
                best[r["item"]] = i
    for i, r in enumerate(rows):
        if r["selected"] and best[r["item"]] != i:
            r.update(selected=False, status="duplicate")

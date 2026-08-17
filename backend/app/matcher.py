"""Receipt <-> bank-transaction matching engine (confidence-scored for human review)."""
from difflib import SequenceMatcher
from datetime import date, datetime
import re, unicodedata

AMOUNT_TOL = 0.02          # exact/tiny-diff tolerance (rounding, fees)
AMOUNT_WINDOW = 1.00       # max abs diff that still gets any amount credit
DATE_WINDOW_DAYS = 7
MERCHANT_STOPWORDS = {"le","la","les","de","du","des","the","sa","supermarche",
                      "market","restaurant","cafe","com","fr","m","mr","paris"}


def norm(s):
    """Lowercase, strip accents, drop punctuation, tokenize. Keeps CJK as whole tokens."""
    if not s:
        return []
    s = unicodedata.normalize("NFKD", str(s))
    # strip latin diacritics
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff ]", " ", s.lower())
    toks = []
    for t in s.split():
        if not t:
            continue
        if re.fullmatch(r"[a-z0-9]+", t) and (t in MERCHANT_STOPWORDS or len(t) <= 1):
            continue
        toks.append(t)
    return toks


def merchant_sim(a, b):
    ta, tb = norm(a), norm(b)
    if not ta or not tb:
        return 0.0
    sa, sb = set(ta), set(tb)
    inter = len(sa & sb); union = len(sa | sb)
    jaccard = inter / union if union else 0.0
    order = SequenceMatcher(None, ta, tb).ratio()
    return 0.6 * jaccard + 0.4 * order


def parse_date(dstr, ref_year=2026):
    dstr = (dstr or "").strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})$", dstr)
    if m:
        return date(ref_year, int(m[2]), int(m[1]))
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(dstr, fmt).date()
        except ValueError:
            continue
    return None


def score(receipt, txn):
    amt_diff = abs(float(receipt["amount"]) - float(txn["debit"]))
    if amt_diff > AMOUNT_WINDOW:
        return 0.0, {"amount": 0, "date": 0, "merchant": 0}
    a_s = 1.0 if amt_diff <= AMOUNT_TOL else max(0.0, 1.0 - (amt_diff - AMOUNT_TOL) / (AMOUNT_WINDOW - AMOUNT_TOL))

    r_d = parse_date(receipt.get("date")); t_d = parse_date(txn.get("date"))
    if r_d and t_d:
        days = abs((r_d - t_d).days)
        d_s = 1.0 / (1 + days) if days <= DATE_WINDOW_DAYS else 0.0
    else:
        d_s = 0.5

    m_s = merchant_sim(receipt.get("merchant", ""), txn.get("description", ""))
    conf = 0.55 * a_s + 0.30 * m_s + 0.15 * d_s
    return conf, {"amount": round(a_s, 3), "date": round(d_s, 3), "merchant": round(m_s, 3)}


def bucket(conf):
    if conf >= 0.80: return "auto"
    if conf >= 0.55: return "review"
    return "no_match"


def match_all(receipts, txns):
    """Returns (matches, unmatched_txns). matches: list of dicts per receipt."""
    used = set(); results = []
    for r in receipts:
        cands = []
        for i, t in enumerate(txns):
            if t.get("debit") is None or i in used:
                continue
            conf, brk = score(r, t)
            cands.append((conf, i, t, brk))
        cands.sort(key=lambda x: -x[0])
        conf, i, t, brk = (cands[0] if cands else (0.0, None, None, None))
        # below review threshold => no candidate to show (avoid misleading ties)
        if conf < 0.55:
            t, brk = None, None
        b = bucket(conf)
        results.append({
            "receipt": r, "txn": t, "confidence": round(conf, 3),
            "breakdown": brk, "bucket": b,
            "merchant_sim": round(merchant_sim(r.get("merchant", ""), (t or {}).get("description", "")), 3),
        })
        if conf >= 0.55 and t is not None:
            used.add(i)
    unmatched_txns = [t for i, t in enumerate(txns) if i not in used and t.get("debit") is not None]
    return results, unmatched_txns

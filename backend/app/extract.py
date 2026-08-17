"""Extraction services:
  - extract_receipt(bytes)  -> Qwen2.5-VL-7B (local ollama) structured receipt
  - parse_bank_pdf(bytes)   -> pdfplumber (electronic bank statement)
  - parse_bank_image(bytes) -> PaddleOCR PP-StructureV3 (scanned/photo statement)
"""
import base64, json, io, re, os, urllib.request
from . import config

RECEIPT_SYSTEM = (
    "You are an OCR engine for purchase receipts. Extract fields as JSON. "
    "Use English keys. keys: merchant(string), date(YYYY-MM-DD), time(HH:MM), "
    "total_amount(number), currency(ISO code), card_last4(string or empty), "
    "items(array of {name, price}). Keep the original merchant name language. "
    "Do not invent amounts; if a field is absent set it to null."
)

BANK_IMAGE_SYSTEM = (
    "You are an OCR engine for bank statement images. Output a JSON object "
    "{\"transactions\": [...]}. Each transaction: {date, description, debit, credit}. "
    "Preserve original text exactly."
)


# ---------------- receipts: vision AI (ollama local or OpenAI-compatible) ----------------
def _vision_chat(user_prompt, image_bytes, system_prompt=RECEIPT_SYSTEM):
    """Call the configured vision model with an image. Returns raw response text."""
    v = config.vision()
    b64 = base64.b64encode(image_bytes).decode()
    if v["provider"] == "ollama":
        payload = {
            "model": v["model"], "stream": False, "format": "json",
            "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": user_prompt, "images": [b64]}],
        }
        data = _post(v["base_url"] + "/api/chat", payload,
                     headers={"Content-Type": "application/json"})
        return data["message"]["content"]
    else:
        # OpenAI-compatible vision endpoint
        payload = {
            "model": v["model"], "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]},
            ],
        }
        headers = {"Content-Type": "application/json"}
        if v["api_key"]:
            headers["Authorization"] = f"Bearer {v['api_key']}"
        data = _post(v["base_url"] + "/chat/completions", payload, headers=headers)
        return data["choices"][0]["message"]["content"]


def extract_receipt(image_bytes):
    content = _vision_chat("Extract the receipt.", image_bytes)
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    rec = json.loads(content)
    # normalize total_amount -> amount, and force positive (receipts are charges;
    # some receipts write the total as a negative debit).
    if "amount" not in rec or rec.get("amount") is None:
        rec["amount"] = rec.get("total_amount")
    try:
        rec["amount"] = abs(float(rec["amount"]))
    except (TypeError, ValueError):
        rec["amount"] = None
    return rec


# ---------------- bank: PDF (electronic) ----------------
def parse_bank_pdf(pdf_bytes):
    import pdfplumber
    text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"
    # fall back to table extraction if layout-based text is empty
    txns = _parse_bank_text(text)
    if not txns:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            tables = []
            for page in pdf.pages:
                tables += page.extract_tables()
        txns = _parse_bank_tables(tables)
    return txns


def _parse_bank_text(text):
    """Naive line-based parse: DATE DESC DEBIT CREDIT. Best-effort; real banks vary."""
    txns = []
    amt = r"([0-9]{1,3}(?:[.,][0-9]{2}))"
    for ln in text.splitlines():
        m = re.match(r"^\s*(\d{2}/\d{2})\s+(.*?)\s*$", ln)
        if not m:
            continue
        date_s, rest = m.group(1), m.group(2)
        # find amounts at end
        debits = re.findall(r"([0-9][0-9.,]{1,8})\s*$", rest)
        # crude: strip trailing amount if present
        tail = re.search(r"(.*?)(?:\s+([0-9][0-9.,]{1,8}))?\s*$", rest)
        desc = tail.group(1).strip()
        txns.append({"date": date_s, "description": desc,
                     "debit": _to_float(tail.group(2)), "credit": None})
    return txns


def _parse_bank_tables(tables):
    txns = []
    for table in tables:
        for row in table:
            cells = [c.strip() if c else "" for c in row]
            if not cells or not re.match(r"^\d{2}/\d{2}$", cells[0]):
                continue
            txns.append({"date": cells[0], "description": cells[1] if len(cells) > 1 else "",
                         "debit": _to_float(cells[2] if len(cells) > 2 else None),
                         "credit": _to_float(cells[3] if len(cells) > 3 else None)})
    return txns


# ---------------- bank: image/scan (PaddleOCR PP-StructureV3) ----------------
_paddlex_ocr = None

def parse_bank_image(image_bytes):
    global _paddlex_ocr
    try:
        if _paddlex_ocr is None:
            from paddleocr import PPStructureV3
            _paddlex_ocr = PPStructureV3(lang="en")
        tmp = "/tmp/_bank_stmt.png"
        open(tmp, "wb").write(image_bytes)
        res = _paddlex_ocr.predict(tmp)[0]
        html = res["table_res_list"][0].get("pred_html", "")
        return _parse_html_rows(html)
    except Exception as e:
        # fallback: plain OCR text
        return {"error": str(e), "hint": "install paddleocr + paddlex[ocr]"}


def _parse_html_rows(html):
    rows = re.findall(r"<tr>(.*?)</tr>", html, re.S)
    txns = []
    for row in rows:
        cells = re.findall(r"<td>(.*?)</td>", row, re.S)
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        line = " ".join(cells)
        m = re.match(r"(\d{2}/\d{2})\s+(.*?)\s+([0-9][0-9.,]{1,8})\s*$", line)
        if m and not any(w in line.upper() for w in ("SOLDE", "TOTAL", "DATE")):
            txns.append({"date": m.group(1), "description": m.group(2),
                         "debit": _to_float(m.group(3)), "credit": None})
    return txns


# ---------------- helpers ----------------
def _post(url, payload, headers=None, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers=headers or {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _to_float(v):
    if v is None or v == "":
        return None
    s = str(v).replace(",", ".").replace(" ", "")
    try:
        return round(float(s), 2)
    except Exception:
        return None

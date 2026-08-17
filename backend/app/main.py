"""Bill-Matcher FastAPI backend. Serves API + static frontend."""
import os, json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import store, extract, classify
from .matcher import match_all

app = FastAPI(title="Bill Matcher")
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND = os.path.join(BASE, "frontend")

store.init()


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))


# ---------------- upload ----------------
@app.post("/api/receipt")
async def upload_receipt(file: UploadFile = File(...)):
    data = await file.read()
    try:
        rec = extract.extract_receipt(data)
        rec["filename"] = file.filename
        rid = store.add_receipt(rec)
        return {"id": rid, "receipt": rec}
    except Exception as e:
        raise HTTPException(500, f"收据提取失败: {e}")


@app.post("/api/bank")
async def upload_bank(file: UploadFile = File(...)):
    data = await file.read()
    name = (file.filename or "").lower()
    try:
        if name.endswith(".pdf"):
            txns = extract.parse_bank_pdf(data)
        else:
            txns = extract.parse_bank_image(data)
            if isinstance(txns, dict) and "error" in txns:
                raise HTTPException(500, txns["error"])
        ids = store.add_transactions(txns)
        return {"ids": ids, "count": len(txns), "transactions": txns}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"账单解析失败: {e}")


# ---------------- list / match / confirm / classify ----------------
@app.get("/api/receipts")
def get_receipts():
    return store.all_receipts()


@app.get("/api/transactions")
def get_transactions():
    return store.all_transactions()


@app.post("/api/match")
def run_match():
    receipts = store.all_receipts()
    txns = store.all_transactions()
    matches, unmatched = match_all(receipts, txns)
    for m in matches:
        store.upsert_match(
            m["receipt"]["id"],
            m["txn"]["id"] if m["txn"] else None,
            m["confidence"], m["breakdown"],
            m["bucket"] if m["bucket"] != "no_match" else "unmatched")
    # mark previously-confirmed as auto so confirmations persist through re-match
    for m in matches:
        if m["bucket"] == "auto":
            store.set_status(m["receipt"]["id"], m["txn"]["id"], "auto")
    return {"matches": matches, "unmatched_txns": unmatched}


@app.post("/api/confirm")
async def confirm(payload: dict):
    rid = payload["receipt_id"]
    txn_id = payload.get("txn_id")
    status = payload.get("status", "confirmed")
    store.set_status(rid, txn_id, status)
    return {"ok": True}


@app.post("/api/classify")
def run_classify():
    matches = store.all_matches()
    confirmed = [m for m in matches if m["status"] in ("auto", "confirmed") and m["txn_id"]]
    expenses = [{"id": m["receipt_id"],
                 "merchant": m["r_merchant"],
                 "description": m["t_description"],
                 "amount": m["r_amount"],
                 "date": m["r_date"]} for m in confirmed]
    if not expenses:
        return {"error": "还没有已确认的配对。请先在复核界面确认。"}
    cats = classify.classify(expenses)
    if isinstance(cats, dict) and "error" in cats:
        return cats
    # persist category onto matches via breakdown
    for m in confirmed:
        brk = json.loads(m["breakdown"] or "{}")
        brk["category"] = cats.get(str(m["receipt_id"]))
        store.upsert_match(m["receipt_id"], m["txn_id"], m["confidence"], brk,
                           m["status"] if m["status"] in ("auto", "confirmed") else "auto")
    return {"categories": cats}


@app.get("/api/matches")
def get_matches():
    return store.all_matches()


@app.get("/api/summary")
def summary():
    matches = store.all_matches()
    confirmed = [m for m in matches if m["status"] in ("auto", "confirmed") and m["txn_id"]]
    total = sum(m["r_amount"] or 0 for m in confirmed)
    by_cat = {}
    for m in confirmed:
        cat = json.loads(m["breakdown"] or "{}").get("category", "未分类")
        by_cat[cat] = by_cat.get(cat, 0) + (m["r_amount"] or 0)
    return {"total_confirmed": len(confirmed), "total_amount": round(total, 2),
            "by_category": by_cat,
            "unmatched_receipts": sum(1 for m in matches if m["status"] == "unmatched")}


@app.post("/api/reset")
def reset():
    store.clear_receipts(); store.clear_transactions(); store.reset_matches()
    return {"ok": True}


# serve frontend static (after routes so / isn't shadowed)
if os.path.isdir(FRONTEND):
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

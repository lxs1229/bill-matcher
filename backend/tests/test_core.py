"""Core logic tests (matcher + config). No heavy ML / network deps needed."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import matcher, config

SAMPLE_RECEIPTS = [
    {"id": 1, "merchant": "CARREFOUR MARKET", "amount": 22.83, "date": "2026-08-12"},
    {"id": 2, "merchant": "WONG KOK SUPERMARCHE", "amount": 17.50, "date": "2026-08-12"},
    {"id": 3, "merchant": "BOULANGERIE PAUL 12E", "amount": 6.40, "date": "15/08"},
]
SAMPLE_TXNS = [
    {"date": "03/08", "description": "RETRAIT DAB 20 BOULEVARD", "debit": 50.00, "credit": None},
    {"date": "05/08", "description": "CARREFOUR MARKET PARIS", "debit": 22.83, "credit": None},
    {"date": "12/08", "description": "WONG KOK SUPERMARCHE", "debit": 17.50, "credit": None},
    {"date": "15/08", "description": "BOULANGERIE PAUL 12E", "debit": 6.40, "credit": None},
    {"date": "20/08", "description": "APPLE.COM/BILL", "debit": 9.99, "credit": None},
]


# ---------- merchant similarity ----------
def test_merchant_sim_same_merchant():
    assert matcher.merchant_sim("CARREFOUR MARKET", "CARREFOUR MARKET PARIS") > 0.5


def test_merchant_sim_unrelated():
    assert matcher.merchant_sim("CARREFOUR MARKET", "RESTAURANT LE MONG KOK") < 0.3


# ---------- date parsing ----------
def test_parse_date_bank_style():
    d = matcher.parse_date("15/08")
    assert d is not None and d.day == 15 and d.month == 8


def test_parse_date_iso():
    d = matcher.parse_date("2026-08-12")
    assert d is not None and d.year == 2026


# ---------- scoring ----------
def test_score_exact_match_high():
    conf, brk = matcher.score(SAMPLE_RECEIPTS[0], SAMPLE_TXNS[1])
    assert conf >= 0.80


def test_score_wrong_amount_zero():
    conf, _ = matcher.score(SAMPLE_RECEIPTS[0], SAMPLE_TXNS[0])  # 22.83 vs 50.00
    assert conf < 0.55


# ---------- match_all ----------
def test_match_all_finds_correct_pairs():
    matches, unmatched = matcher.match_all(SAMPLE_RECEIPTS, SAMPLE_TXNS)
    by_id = {m["receipt"]["id"]: m for m in matches}
    assert by_id[1]["txn"]["description"] == "CARREFOUR MARKET PARIS"
    assert by_id[2]["txn"]["description"] == "WONG KOK SUPERMARCHE"
    assert by_id[3]["txn"]["description"] == "BOULANGERIE PAUL 12E"
    # APPLE has no receipt -> should remain unmatched
    assert any(t["description"] == "APPLE.COM/BILL" for t in unmatched)


# ---------- config defaults (no hermes/hermes on CI) ----------
def test_config_defaults():
    v = config.vision()
    assert v["provider"] in ("ollama", "openai_compatible")
    assert v["model"]
    c = config.classify()
    assert c["base_url"] and c["model"]
    assert len(config.categories()) >= 3

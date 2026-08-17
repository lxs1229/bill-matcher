"""Configuration loader.

All AI endpoints (vision extraction + classification) are set in the user-editable
`config.yaml` at the project root. This module loads it and exposes typed config
objects, with safe fallbacks so a missing/invalid file never crashes the app.

API-key fallback order (when api_key is empty in config.yaml):
  1. environment variable  (DEEPSEEK_API_KEY / VISION_API_KEY)
  2. Hermes config ~/.hermes/config.yaml  (for DeepSeek provider, if present)
"""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")

DEFAULT_CATEGORIES = ["餐饮", "超市购物", "交通", "居住/水电", "娱乐/订阅",
                      "数码/购物", "医疗", "旅行", "转账", "其他"]

_HERMES_CONFIG = os.path.expanduser("~/.hermes/config.yaml")


def _load_yaml():
    import yaml
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    return data


def _hermes_deepseek_key():
    if not os.path.exists(_HERMES_CONFIG):
        return None
    try:
        import yaml
        with open(_HERMES_CONFIG, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        for prov in cfg.get("custom_providers", []) or []:
            if "deepseek" in (prov.get("base_url") or "").lower() and prov.get("api_key"):
                return prov["api_key"]
    except Exception:
        return None
    return None


def _cfg():
    try:
        return _load_yaml()
    except Exception:
        return {}


def _get(d, keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            d = d[k]
        else:
            return default
    return d


def vision():
    c = _cfg().get("vision", {}) or {}
    provider = str(c.get("provider", "ollama")).lower()
    key = c.get("api_key") or os.environ.get("VISION_API_KEY") or ""
    return {
        "provider": provider,
        "base_url": (c.get("base_url") or "http://localhost:11434").rstrip("/"),
        "model": c.get("model") or "qwen2.5vl:7b",
        "api_key": key,
    }


def classify():
    c = _cfg().get("classify", {}) or {}
    provider = str(c.get("provider", "deepseek")).lower()
    base = (c.get("base_url") or "https://api.deepseek.com").rstrip("/")
    model = c.get("model") or "deepseek-v4-flash"
    key = c.get("api_key") or os.environ.get("DEEPSEEK_API_KEY") or ""
    if not key and "deepseek" in base:
        key = _hermes_deepseek_key() or ""
    return {"provider": provider, "base_url": base, "model": model, "api_key": key}


def categories():
    cats = _cfg().get("categories") or DEFAULT_CATEGORIES
    return [c for c in cats if c] if cats else DEFAULT_CATEGORIES


def deepseek_api_key():
    return classify()["api_key"] or None


def deepseek_ready():
    return bool(deepseek_api_key())

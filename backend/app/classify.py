"""DeepSeek (or any OpenAI-compatible) classification of confirmed expenses."""
import json, urllib.request
from . import config


def classify(expenses):
    """expenses: list of {id, merchant, description, amount, date}. Returns {id: category}."""
    cl = config.classify()
    if not cl["api_key"]:
        return {"error": "分类 AI 未配置 API key：请检查 config.yaml 的 classify.api_key，"
                         "或设置环境变量 DEEPSEEK_API_KEY"}
    cats = config.categories()
    system = (
        "You are an expense categorizer. Classify each transaction into ONE of: "
        + ", ".join(cats) +
        ". Respond with a JSON object {\"categories\": {\"<id>\": \"<category>\"}} "
        "using the same keys as input. Only use the listed categories."
    )
    inp = {str(e["id"]): {"merchant": e.get("merchant"), "description": e.get("description"),
                          "amount": e.get("amount"), "date": e.get("date")} for e in expenses}
    body = {
        "model": cl["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(inp, ensure_ascii=False)},
        ],
        "temperature": 0, "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        cl["base_url"] + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {cl['api_key']}"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    content = data["choices"][0]["message"]["content"].strip()
    content = content.strip("`").lstrip("json")
    parsed = json.loads(content)
    return parsed.get("categories", parsed)

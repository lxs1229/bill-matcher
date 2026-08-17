# Bill Matcher · 账单配对工具

![CI](https://github.com/lxs1229/bill-matcher/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-green)

把**消费收据**和**银行卡流水**自动配对，给每笔消费打上分类标签，供人工复核。全程本地可选、免费、隐私（银行数据不出机器）。

> 面向使用者的完整架构说明见 **[ARCHITECTURE.md](ARCHITECTURE.md)**。

---

## ✨ 它能做什么

- **上传收据**（照片 / 电子PDF / 邮件截图）→ 自动提取商户、金额、日期、卡号
- **上传银行账单**（电子PDF / 照片 / 扫描件）→ 自动解析出交易列表
- **智能配对**：每张收据 ↔ 对应银行交易，按「金额 + 商户名 + 日期」三因子打分
- **人工复核界面**：高置信自动配对，中置信待你确认，低置信标不匹配
- **分类**：DeepSeek 把已确认支出归入类别（餐饮 / 超市购物 / …）
- **月度汇总**：总支出、按类别统计

## 🚀 快速开始

### 前置要求
- macOS / Linux / Windows（需 Python 3.10+）
- Python 3.10+
- 一个**视觉识别 API**（收据识别用，OpenAI 兼容接口即可；如 Qwen-VL / 通义 / GLM 等）
- 一个**分类 API**（如 DeepSeek）
- （可选）本地 [Ollama](https://ollama.com/download)，可免费用本地视觉模型，数据不出机器

### 安装
```bash
./setup.sh     # 一键：建 venv + 装依赖（ollama 可选，不装也能用云端 API）
```

### 启动
```bash
./run.sh       # 然后浏览器打开 http://localhost:8000
```

### 配置 AI（必做）
编辑项目根目录的 **`config.yaml`**，填入你的视觉 + 分类 API：
```yaml
vision:    # 收据视觉识别
  provider: openai_compatible   # 云端API；若用本地ollama则填 ollama
  base_url: https://api.xxx.com/v1   # 你的服务商地址
  model: qwen-vl-max            # 你的视觉模型
  api_key: sk-xxxx              # 你的 key

classify:  # 分类 AI
  provider: deepseek            # deepseek 或 openai_compatible
  base_url: https://api.deepseek.com
  model: deepseek-v4-flash
  api_key: ""                   # 留空自动读环境变量 / ~/.hermes/config.yaml
```
改完保存 → 重启 `./run.sh` 生效。

---

## 🧩 工作流程

```
上传收据 ──► 视觉AI(Qwen2.5-VL) ──► 结构化收据[商户/金额/日期]
上传账单 ──► PDF文本解析 / PaddleOCR表格 ──► 交易列表
                          │
                          ▼
              配对引擎（金额+商户+日期 三因子打分）
                          │
              人工复核界面（确认 / 拒绝）
                          │
              DeepSeek 分类 ──► 月度汇总
```

## 📁 目录结构

```
bill-matcher/
├── config.yaml          # ★ AI 供应商配置（改这里）
├── setup.sh             # 一键安装
├── run.sh               # 启动
├── ARCHITECTURE.md      # 架构设计说明
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── .venv/           # (安装后生成) Python 环境
│   └── app/
│       ├── main.py      # FastAPI 路由
│       ├── extract.py   # 收据(视觉) + 账单(PDF/PaddleOCR) 提取
│       ├── matcher.py   # 配对引擎
│       ├── classify.py  # 分类
│       ├── store.py     # SQLite 存储
│       └── config.py    # 读取 config.yaml
├── frontend/
│   └── index.html       # 单页界面
└── samples/             # 测试用的模拟收据+账单
```

## ❓ 常见问题

**Q: 上传收据报 "Connection refused" / 提取失败**
→ 你用的是本地 ollama 但服务没启动。打开 Ollama 应用或运行 `ollama serve`；或者直接在 config.yaml 改用云端视觉 API（`provider: openai_compatible` + 填 API）。

**Q: 视觉识别报 "api_key" 相关错误**
→ 云端 API 必须填 `vision.api_key`；确认 `vision.base_url` / `model` 和你服务商的文档一致。

**Q: 银行账单解析报 "paddlepaddle not installed"**
→ 依赖没装全，重新跑 `./setup.sh`，或手动 `pip install paddlepaddle paddleocr "paddlex[ocr]"`。

**Q: 分类报 "API key 未配置"**
→ 在 `config.yaml` 的 `classify.api_key` 填入，或设置环境变量 `DEEPSEEK_API_KEY`。

**Q: 我的银行账单能识别吗？**
→ 电子 PDF 用文本解析（100% 准确）；照片/扫描用 PaddleOCR 表格识别，**表格网格线清晰时准确率极高**。

## ⚠️ 已知局限
- 中文商户名 ↔ 英文账单名（如「巴黎旺角茶餐厅」↔「RESTAURANT LE MONG KOK」）模糊匹配偏弱，可能需要人工确认。
- 不同银行账单排版差异大，PDF 文本解析对非标准排版可能需要微调。

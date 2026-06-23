# AI Module Blueprint — Airbnb Analytics Platform

> Tài liệu hướng dẫn xây dựng lại module AI/LLM cho dự án Airbnb Analytics Platform.
> Áp dụng kiến trúc đã chạy ổn định từ dự án TNBIKE, điều chỉnh cho context Airbnb
> (MotherDuck/DuckDB, dbt Gold layer, Streamlit frontend).

---

## 1. Tổng quan kiến trúc

### Nguyên tắc cốt lõi

```
LLM KHÔNG được:                    LLM CHỈ được:
  ✗ Đọc raw data                     ✓ Nhận summary JSON từ Gold layer
  ✗ Tự tính metric                   ✓ Diễn giải metric đã tính sẵn
  ✗ Bịa số liệu                     ✓ So sánh và đề xuất dựa trên data thật
  ✗ Cam kết ROI/lợi nhuận            ✓ Cảnh báo rủi ro và giới hạn dữ liệu
```

### Luồng dữ liệu end-to-end

```
┌─────────────────────────────────────────────────────────────┐
│                    DỮ LIỆU CÓ SẴN                          │
│                                                             │
│  Raw Airbnb Data → MotherDuck → dbt Bronze → Silver → Gold │
│                                                             │
│  Gold models đã có:                                         │
│    • gold_ai_qa_investment_recommendations  (scores + tiers)       │
│    • gold_ai_listing_market_summary  (neighbourhood agg)    │
│    • fact_listing_current_snapshot    (listing-level)        │
│    • dim_host, dim_listing, dim_location, dim_date          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  TẦNG 1: CONTEXT BUILDER  (llm/context_builder.py)          │
│                                                             │
│  Query Gold layer → DataFrame → JSON compact ≤ 8,000 chars │
│  Mỗi use case có 1 hàm riêng:                              │
│    build_investment_context()                               │
│    build_market_summary_context()                           │
│    build_room_type_context()                                │
│    build_comparison_context(neighbourhoods)                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  TẦNG 2: ANSWER GENERATOR  (llm/answer_generator.py)        │
│                                                             │
│  Chọn prompt theo use case → Gọi GroqKeyPoolClient          │
│  → Parse JSON response → Nếu lỗi → Trả fallback           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  TẦNG 3: LLM CLIENT  (llm/llm_client.py)                   │
│                                                             │
│  Key 1 → Groq API (llama-3.3-70b-versatile)                │
│    lỗi 429 → cooldown key 1 → Key 2                        │
│      lỗi tiếp → fallback model (llama-3.1-8b-instant)      │
│        lỗi toàn bộ → raise, answer_generator trả fallback  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  TẦNG 4: STREAMLIT UI  (app/components/ai_chat.py)          │
│                                                             │
│  Quick Prompt Buttons → trigger use case cụ thể             │
│  Nhận structured JSON → render thành cards/bảng             │
│  Nhận fallback → render bảng Gold data thô                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Cấu trúc thư mục

### Hiện tại (trước khi làm)

```
llm/
├── groq_insights.py          ← 1 file làm tất cả: prompt + API call + parse
└── outputs/
    └── generated_insights.md

app/components/
└── ai_chat.py                ← UI trộn lẫn data loading + rendering
```

### Mục tiêu (sau khi làm)

```
llm/
├── __init__.py
├── llm_client.py             ← [MỚI] GroqKeyPoolClient: key rotation, cooldown, fallback
├── context_builder.py        ← [MỚI] Gold data → JSON compact (≤ 8,000 chars)
├── prompt_templates.py       ← [MỚI] System prompts cho từng use case
├── answer_generator.py       ← [MỚI] Orchestrator: context + prompt + LLM + fallback
├── groq_insights.py          ← [SỬA] Refactor: delegate sang llm_client
└── outputs/

app/components/
└── ai_chat.py                ← [SỬA] Render structured JSON thành cards

configs/
└── settings.py               ← [SỬA] Mở rộng LLMSettings
```

### Vai trò từng file

| File | Trách nhiệm | Import từ | Tham chiếu TNBIKE |
|------|-------------|-----------|-------------------|
| `llm/llm_client.py` | Gọi Groq API an toàn: xoay key, cooldown, thử fallback model | `configs.settings` | `ai/llm_client.py` GroqKeyPoolClient |
| `llm/context_builder.py` | Query Gold layer, nén DataFrame → JSON string gọn | `utils.motherduck`, `utils.sql` | `ai/interpreters/bi_context_builder.py` |
| `llm/prompt_templates.py` | Chứa tất cả system prompt, output schema | *(không import gì)* | `ai/interpreters/bi_llm_interpreter.py` L17-48 |
| `llm/answer_generator.py` | Kết nối context + prompt + LLM, xử lý lỗi + fallback | `llm_client`, `context_builder`, `prompt_templates` | `ai/interpreters/bi_llm_interpreter.py` L76-116 |
| `llm/groq_insights.py` | Giữ tương thích ngược, delegate sang `llm_client` | `llm_client` | *(giữ nguyên interface cũ)* |
| `app/components/ai_chat.py` | UI: buttons, render cards, hiển thị context preview | `llm.answer_generator` | *(không có tương đương — TNBIKE dùng FastAPI)* |

---

## 3. Chi tiết từng file

### 3.1 `llm/llm_client.py` — Resilient Groq Client

**Mục đích**: Thay thế `urllib` call thủ công bằng client có khả năng tự phục hồi.

**Class chính**: `GroqKeyPoolClient`

```python
# Pseudocode — cấu trúc class

class GroqKeyPoolClient:
    keys: list[str]              # ["gsk_abc...", "gsk_xyz..."]
    model: str                   # "llama-3.3-70b-versatile"
    fallback_models: list[str]   # ["llama-3.1-8b-instant"]
    max_tokens: int              # 1200
    temperature: float           # 0.2
    cooldown_seconds: int        # 60
    _cooldowns: dict[str, float] # key → thời điểm hết cooldown

    def chat_text(prompt, system) -> str:
        """Gọi Groq, trả raw text. Tự xoay key + fallback model khi lỗi."""
        for model in [self.model, *self.fallback_models]:
            for _ in range(len(self.keys)):
                key = self._next_key()
                try:
                    return self._call_groq(key, model, prompt, system)
                except RateLimitError:
                    self._cooldown_key(key)
                    continue
        raise RuntimeError("All keys exhausted")

    def chat_json(prompt, system) -> dict:
        """Gọi chat_text, parse JSON, strip markdown fences."""
        text = self.chat_text(prompt, system)
        return json.loads(strip_json_fences(text))
```

**Cách đọc keys**:

```python
# .env
GROQ_API_KEY=gsk_primary_key_here
GROQ_API_KEYS=gsk_key1,gsk_key2,gsk_key3    # optional, nhiều key

# Ưu tiên: GROQ_API_KEYS (nếu có) → GROQ_API_KEY (fallback)
```

**Cơ chế cooldown** (từ TNBIKE):

```
Thời điểm T=0: Key 1 gọi → lỗi 429
  → Key 1 bị cooldown đến T=60s
  → Key 2 gọi → thành công → trả kết quả

Thời điểm T=70: Key 1 hết cooldown → có thể dùng lại
```

**Cơ chế fallback model**:

```
llama-3.3-70b-versatile → lỗi tất cả key
  → llama-3.1-8b-instant → thử lại tất cả key
    → vẫn lỗi → raise RuntimeError
```

---

### 3.2 `llm/context_builder.py` — Gold Data Compression

**Mục đích**: Query Gold layer, nén DataFrame thành JSON string gọn gàng để gửi lên LLM.

**Nguyên tắc nén** (từ TNBIKE `bi_context_builder.py`):

```
1. Chỉ lấy top N rows (không gửi toàn bộ)
2. Round số: giá → 0 decimal, tỷ lệ → 2 decimal
3. Loại bỏ cột không cần (internal keys, surrogate keys)
4. Hard limit: nếu JSON > 8,000 chars → cắt tiếp (giảm N, bỏ cột phụ)
5. Luôn kèm market baseline để LLM có cơ sở so sánh
```

**Hàm cho từng use case**:

```python
MAX_CONTEXT_CHARS = 8000

def build_investment_context() -> str:
    """
    Query: gold_ai_qa_investment_recommendations ORDER BY opportunity_score DESC LIMIT 8
    Output: JSON string với top 8 candidates + market baseline
    Gửi kèm: scoring rules (opportunity_score, risk_score logic)
    """

def build_market_summary_context() -> str:
    """
    Query: gold_ai_listing_market_summary GROUP BY neighbourhood
    Output: JSON string với aggregate metrics toàn thị trường
    Gửi kèm: market-wide medians (price, occupancy, revenue)
    """

def build_room_type_context(neighbourhood: str | None = None) -> str:
    """
    Query: gold_ai_listing_market_summary GROUP BY room_type
           (filter neighbourhood nếu có)
    Output: JSON string so sánh room types
    """

def build_comparison_context(neighbourhoods: list[str]) -> str:
    """
    Query: gold_ai_qa_investment_recommendations WHERE neighbourhood IN (...)
    Output: JSON string với metrics song song của 2+ neighbourhood
    """
```

**Ví dụ output** (gửi lên LLM):

```json
{
  "market_baseline": {
    "market_median_price": 1500,
    "market_median_occupancy_rate": 0.42,
    "market_median_estimated_revenue": 85000
  },
  "top_candidates": [
    {
      "neighbourhood": "Dusit",
      "recommended_room_type": "Entire home/apt",
      "listing_count": 89,
      "room_type_listing_count": 45,
      "room_type_median_price": 2100,
      "room_type_median_occupancy_rate": 0.72,
      "room_type_median_estimated_revenue": 182000,
      "opportunity_score": 78.5,
      "risk_score": 15.0,
      "action_tier": "Strong Invest",
      "risk_flags": "No major risk flags"
    }
  ],
  "scoring_rules": "Opportunity Score = 40% revenue + 30% occupancy + 20% competition + 10% room type confidence. Risk flags: listing_count < 30 = Data Trap, > 300 = Saturation."
}
```

---

### 3.3 `llm/prompt_templates.py` — System Prompts

**Mục đích**: Tập trung tất cả prompts, tách khỏi logic code.

**Cấu trúc mỗi prompt** (4 phần cố định):

```
1. ROLE        — Bạn là ai, expertise gì
2. DATA        — {data_context} placeholder cho JSON từ context_builder
3. OUTPUT      — JSON schema bắt buộc (mẫu key + kiểu dữ liệu)
4. GUARDRAILS  — Ràng buộc: không bịa, không cam kết ROI, luôn nêu risk
```

#### Prompt 1: Investment Recommendations

```python
INVESTMENT_SYSTEM_PROMPT = """
You are a data-driven Airbnb market-entry advisor analyzing Bangkok short-term rental data.

ROLE:
- Recommend the best neighbourhoods for opening a new Airbnb listing.
- Base recommendations only on the aggregate Gold-layer metrics provided below.
- Explain why each opportunity exists and what risks should be validated.

AGGREGATE CONTEXT:
{data_context}

REQUIRED OUTPUT (JSON):
{{
  "executive_summary": "2-3 sentence overview of the market situation",
  "top_recommendations": [
    {{
      "rank": 1,
      "neighbourhood": "...",
      "recommended_room_type": "...",
      "action_tier": "Strong Invest | Investigate Further | Stable but Low Priority | Avoid",
      "opportunity_level": "High | Medium | Low",
      "risk_level": "Low | Medium | High",
      "confidence_level": "High | Medium | Low",
      "investment_thesis": "One paragraph: why this opportunity exists",
      "opportunity_drivers": ["driver 1 with number", "driver 2 with number"],
      "key_risks": ["risk 1", "risk 2"],
      "suggested_next_steps": ["validation step 1", "validation step 2"]
    }}
  ],
  "opportunity_matrix": {{
    "strong_invest": ["Neighbourhood — Room Type: short reason"],
    "investigate_further": ["..."],
    "stable_but_low_priority": ["..."],
    "avoid": ["..."]
  }},
  "data_notes": ["Limitation 1", "Limitation 2"]
}}

GUARDRAILS:
Quality standards for reasoning:
- Every recommendation must answer: WHY this opportunity exists, what DRIVES the signal, and what could INVALIDATE the thesis.
- Compare each candidate against market baselines provided. A metric is only meaningful relative to the market median.
- Detect contradictions: high price but low occupancy, high revenue but tiny sample size, strong score but many risk flags. Call these out explicitly.
- Distinguish between what the DATA shows vs what is NOT in the dataset. If critical information (cost, regulation, seasonality) is missing, state that the recommendation requires external validation.
- If evidence is insufficient for a confident recommendation, say so. Label it as "hypothesis" and specify what data would confirm or reject it.
- A weak recommendation restates numbers without explaining causation. Reject your own output if it does this.

Hard constraints:
- Use only numbers from the provided context. Do not invent.
- Do not guarantee ROI or profitability.
- Return pure JSON only. No markdown. No additional explanation.
"""
```

#### Prompt 2: Market Summary

```python
MARKET_SUMMARY_SYSTEM_PROMPT = """
You are an Airbnb market analyst summarizing Bangkok short-term rental performance.

AGGREGATE CONTEXT:
{data_context}

REQUIRED OUTPUT (JSON):
{{
  "market_overview": "3-4 sentence summary of overall market health",
  "key_metrics": {{
    "total_active_listings": 0,
    "median_price_thb": 0,
    "median_occupancy_rate": "0%",
    "median_estimated_revenue_thb": 0
  }},
  "top_performing_areas": ["area 1: reason", "area 2: reason"],
  "underperforming_areas": ["area 1: reason"],
  "room_type_insights": ["insight 1", "insight 2"],
  "market_risks": ["risk 1", "risk 2"],
  "data_notes": ["limitation 1"]
}}

GUARDRAILS:
Quality standards for reasoning:
- Identify underlying market drivers, not just stating the highest/lowest numbers.
- Highlight contradictions or anomalies in the data (e.g., areas with high listing counts but low occupancy).
- Identify macro risks or missing data points that a business operator should know.

Hard constraints:
- Use only the metrics provided. Do not invent numbers.
- Return pure JSON only.
"""
```

#### Prompt 3: Neighbourhood Comparison

```python
COMPARISON_SYSTEM_PROMPT = """
You are an Airbnb market analyst comparing specific neighbourhoods.

COMPARISON CONTEXT:
{data_context}

REQUIRED OUTPUT (JSON):
{{
  "comparison_summary": "Which area is stronger overall and why",
  "candidates": [
    {{
      "neighbourhood": "...",
      "strengths": ["strength 1 with data", "strength 2"],
      "weaknesses": ["weakness 1 with data"],
      "best_room_type": "...",
      "verdict": "Recommended | Proceed with caution | Not recommended"
    }}
  ],
  "recommendation": "Final recommendation with reasoning",
  "data_notes": ["limitation 1"]
}}

GUARDRAILS:
Quality standards for reasoning:
- Do not just list metrics side-by-side. Explain what the difference *means* for an investor.
- Address trade-offs explicitly (e.g., Candidate A has higher revenue but Candidate B has lower risk/competition).
- State clearly what would make one candidate a better choice than the other (e.g., "If budget allows, A is better. For lower risk, B is better").

Hard constraints:
- Compare using the same metrics for each candidate.
- Use only the metrics provided. Do not invent numbers.
- Return pure JSON only.
"""
```

#### Prompt 4: Room Type Analysis

```python
ROOM_TYPE_SYSTEM_PROMPT = """
You are an Airbnb room type strategist.

ROOM TYPE CONTEXT:
{data_context}

REQUIRED OUTPUT (JSON):
{{
  "analysis_summary": "Which room type performs best and why",
  "room_types": [
    {{
      "room_type": "...",
      "median_price": 0,
      "median_occupancy_rate": "0%",
      "median_estimated_revenue": 0,
      "listing_count": 0,
      "verdict": "Strong performer | Average | Weak performer",
      "reasoning": "Why this verdict"
    }}
  ],
  "recommendation": "Best room type to invest in and why",
  "data_notes": ["limitation 1"]
}}

GUARDRAILS:
Quality standards for reasoning:
- Explain why a certain room type performs better. Is it due to target audience (families vs solo travelers), supply constraints, or pricing power?
- Note any data quality issues, like a room type having very few listings, making its high metrics unreliable.

Hard constraints:
- Use only the metrics provided. Do not invent numbers.
- Return pure JSON only.
"""
```

---

### 3.4 `llm/answer_generator.py` — Orchestrator + Fallback

**Mục đích**: Kết nối tất cả modules lại, xử lý lỗi, trả fallback khi LLM unavailable.

```python
# Pseudocode — luồng chính

USE_CASE_CONFIG = {
    "investment": {
        "context_fn": context_builder.build_investment_context,
        "prompt_template": prompt_templates.INVESTMENT_SYSTEM_PROMPT,
        "fallback_fn": _investment_fallback,
    },
    "market_summary": {
        "context_fn": context_builder.build_market_summary_context,
        "prompt_template": prompt_templates.MARKET_SUMMARY_SYSTEM_PROMPT,
        "fallback_fn": _market_summary_fallback,
    },
    "comparison": {
        "context_fn": context_builder.build_comparison_context,
        "prompt_template": prompt_templates.COMPARISON_SYSTEM_PROMPT,
        "fallback_fn": _comparison_fallback,
    },
    "room_type": {
        "context_fn": context_builder.build_room_type_context,
        "prompt_template": prompt_templates.ROOM_TYPE_SYSTEM_PROMPT,
        "fallback_fn": _room_type_fallback,
    },
}


def generate_answer(use_case: str, **kwargs) -> dict:
    """
    Entry point duy nhất cho mọi LLM call.

    Args:
        use_case: "investment" | "market_summary" | "comparison" | "room_type"
        **kwargs: entities cho context_fn (vd: neighbourhoods=["Dusit", "Bang Phlat"])

    Returns:
        dict — structured JSON từ LLM hoặc fallback dict
    """
    config = USE_CASE_CONFIG[use_case]

    # Bước 1: Build context từ Gold layer
    context = config["context_fn"](**kwargs)

    # Bước 2: Format prompt
    prompt = config["prompt_template"].format(data_context=context)

    # Bước 3: Gọi LLM
    client = GroqKeyPoolClient()
    try:
        result = client.chat_json(prompt=prompt)
        result["_meta"] = {
            "status": "SUCCESS",
            "provider": "groq",
            "model": client.model,
            "context_chars": len(context),
        }
        return result
    except json.JSONDecodeError:
        # LLM trả text không phải JSON → fallback
        return config["fallback_fn"]("LLM returned invalid JSON", context)
    except Exception as exc:
        # LLM hoàn toàn không trả lời → fallback
        return config["fallback_fn"](str(exc), context)


def _investment_fallback(reason: str, raw_context: str) -> dict:
    """
    Trả dữ liệu Gold thô khi LLM unavailable.
    User vẫn thấy data, chỉ thiếu phần diễn giải AI.
    """
    return {
        "_meta": {"status": "LLM_UNAVAILABLE", "reason": reason},
        "executive_summary": (
            "AI analysis is temporarily unavailable. "
            "Showing raw Gold-layer opportunity data below."
        ),
        "top_recommendations": [],  # Streamlit sẽ render bảng Gold thô thay thế
        "raw_context": raw_context,
        "data_notes": [
            "AI interpretation unavailable. Data shown is direct from Gold layer.",
            reason,
        ],
    }
```

**Tại sao cần fallback** (bài học từ TNBIKE):

```
Không có fallback:
  Groq lỗi → st.error("Groq API returned HTTP 429") → user thấy lỗi đỏ → mất điểm demo

Có fallback:
  Groq lỗi → hiển thị bảng Gold data thô + thông báo "AI temporarily unavailable"
  → user vẫn thấy data → demo không bị gián đoạn
```

---

### 3.5 `configs/settings.py` — Mở rộng LLMSettings

**Thêm các trường mới**:

```python
@dataclass(frozen=True)
class LLMSettings:
    groq_api_key: str           # giữ tương thích ngược (1 key)
    groq_api_keys: str          # MỚI: nhiều key, phân tách dấu phẩy
    model: str                  # "llama-3.3-70b-versatile"
    fallback_models: str        # MỚI: "llama-3.1-8b-instant"
    max_tokens: int             # MỚI: default 1200
    temperature: float          # MỚI: default 0.2
    cooldown_seconds: int       # MỚI: default 60

LLM = LLMSettings(
    groq_api_key=getenv("GROQ_API_KEY", ""),
    groq_api_keys=getenv("GROQ_API_KEYS", ""),
    model=getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
    fallback_models=getenv("LLM_FALLBACK_MODELS", "llama-3.1-8b-instant"),
    max_tokens=_get_int("LLM_MAX_TOKENS", 1200),
    temperature=float(getenv("LLM_TEMPERATURE", "0.2")),
    cooldown_seconds=_get_int("LLM_KEY_COOLDOWN_SECONDS", 60),
)
```

**Cập nhật `.env`**:

```env
# LLM Configuration
GROQ_API_KEY=gsk_primary_key
GROQ_API_KEYS=gsk_key1,gsk_key2,gsk_key3
LLM_MODEL=llama-3.3-70b-versatile
LLM_FALLBACK_MODELS=llama-3.1-8b-instant
LLM_MAX_TOKENS=1200
LLM_TEMPERATURE=0.2
```

---

### 3.6 `app/components/ai_chat.py` — UI Streamlit

**Layout tổng thể**:

```
┌──────────────────────────────────────────────────────────────┐
│  🤖 AI Investment Advisor                                    │
│  Data-driven recommendations from Gold-layer analytics       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─ Quick Actions ──────────────────────────────────────┐   │
│  │ [🏆 Top 3 Investments]  [📊 Market Overview]          │   │
│  │ [🏠 Best Room Type]     [🔍 Compare Areas]            │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ▸ Preview data sent to Groq (expander)                     │
│                                                              │
│  ┌─ Results ────────────────────────────────────────────┐   │
│  │                                                       │   │
│  │  Executive Summary                                    │   │
│  │  "Bangkok Airbnb market shows strong demand in..."    │   │
│  │                                                       │   │
│  │  ┌── #1 Dusit — Entire home/apt ──────────────────┐  │   │
│  │  │ 🏆 Strong Invest                                │  │   │
│  │  │ 🚀 Opportunity: High  🛡️ Risk: Low  ✅ High     │  │   │
│  │  │                                                 │  │   │
│  │  │ Investment Thesis:                              │  │   │
│  │  │ Strong revenue at 182K THB with 72% occupancy   │  │   │
│  │  │                                                 │  │   │
│  │  │ Why:                                            │  │   │
│  │  │ • Median occupancy 72% (market: 42%)            │  │   │
│  │  │ • Revenue 182K THB (market: 85K THB)            │  │   │
│  │  │                                                 │  │   │
│  │  │ Risks:                                          │  │   │
│  │  │ • Sample size only 45 listings                  │  │   │
│  │  │ • Operating costs not included                  │  │   │
│  │  │                                                 │  │   │
│  │  │ Next Steps:                                     │  │   │
│  │  │ • Visit area, check local short-term rental law │  │   │
│  │  └─────────────────────────────────────────────────┘  │   │
│  │                                                       │   │
│  │  ┌── #2 Chom Thong — Private Room ────────────────┐  │   │
│  │  │ 🔍 Investigate Further                          │  │   │
│  │  │ ...                                             │  │   │
│  │  └─────────────────────────────────────────────────┘  │   │
│  │                                                       │   │
│  │  ┌── Opportunity Matrix ──────────────────────────┐  │   │
│  │  │ Strong Invest:      Dusit, Chom Thong           │  │   │
│  │  │ Investigate Further: Bang Phlat, Khlong Toei    │  │   │
│  │  │ Avoid:              Watthana (saturated)        │  │   │
│  │  └─────────────────────────────────────────────────┘  │   │
│  │                                                       │   │
│  │  ⚠ Data Notes                                        │   │
│  │  • Based on aggregated Gold-layer data only           │   │
│  │  • Not a guarantee of ROI or profitability            │   │
│  │                                                       │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

**Render logic** (pseudocode):

```python
def render_ai_chat_page():
    st.subheader("🤖 AI Investment Advisor")
    st.caption("Data-driven recommendations from Gold-layer analytics")

    # ── Quick Action Buttons ──
    col1, col2, col3, col4 = st.columns(4)
    if col1.button("🏆 Top 3 Investments", use_container_width=True):
        _handle_use_case("investment")
    if col2.button("📊 Market Overview", use_container_width=True):
        _handle_use_case("market_summary")
    if col3.button("🏠 Best Room Type", use_container_width=True):
        _handle_use_case("room_type")
    if col4.button("🔍 Compare Areas", use_container_width=True):
        _handle_comparison()

    # ── Context Preview ──
    with st.expander("Preview data sent to Groq", expanded=False):
        if "last_context" in st.session_state:
            st.code(st.session_state.last_context, language="json")

    # ── Results ──
    if "last_result" in st.session_state:
        result = st.session_state.last_result
        meta = result.get("_meta", {})

        if meta.get("status") == "LLM_UNAVAILABLE":
            st.warning(f"AI temporarily unavailable: {meta.get('reason')}")
            st.info("Showing raw Gold-layer data instead:")
            # render bảng Gold data thô
        else:
            _render_structured_result(result)


def _handle_use_case(use_case: str):
    with st.spinner("Loading Gold-layer data and calling Groq..."):
        result = answer_generator.generate_answer(use_case)
        st.session_state.last_result = result
        st.rerun()


def _render_structured_result(result: dict):
    # Executive Summary
    if summary := result.get("executive_summary"):
        st.markdown(f"**{summary}**")

    # Recommendation Cards
    for rec in result.get("top_recommendations", []):
        _render_recommendation_card(rec)

    # Opportunity Matrix
    if matrix := result.get("opportunity_matrix"):
        _render_opportunity_matrix(matrix)

    # Data Notes
    if notes := result.get("data_notes"):
        with st.expander("⚠ Data & Decision Notes"):
            for note in notes:
                st.caption(f"• {note}")


def _render_recommendation_card(rec: dict):
    """Render 1 recommendation thành card dùng st.container."""
    tier = rec.get("action_tier", "Unknown")
    tier_colors = {
        "Strong Invest": "🟢",
        "Investigate Further": "🟡",
        "Stable but Low Priority": "🔵",
        "Avoid": "🔴",
    }
    icon = tier_colors.get(tier, "⚪")

    with st.container(border=True):
        st.markdown(f"### #{rec.get('rank')} {rec.get('neighbourhood')} — {rec.get('recommended_room_type')}")

        cols = st.columns(4)
        cols[0].metric("Action", f"{icon} {tier}")
        cols[1].metric("Opportunity", rec.get("opportunity_level"))
        cols[2].metric("Risk", rec.get("risk_level"))
        cols[3].metric("Confidence", rec.get("confidence_level"))

        st.markdown(f"**Investment Thesis:** {rec.get('investment_thesis')}")

        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("**✓ Why this opportunity:**")
            for d in rec.get("opportunity_drivers", []):
                st.markdown(f"- {d}")
        with col_right:
            st.markdown("**⚠ Key risks:**")
            for r in rec.get("key_risks", []):
                st.markdown(f"- {r}")

        st.markdown("**→ Next steps:**")
        for s in rec.get("suggested_next_steps", []):
            st.markdown(f"- {s}")
```

---

## 4. Cách demo cho thầy

### Kịch bản demo 1: Investment Recommendations (đáp ứng yêu cầu đề)

```
1. Mở Streamlit dashboard → vào trang AI Q&A
2. Bấm nút "🏆 Top 3 Investments"
3. Spinner: "Loading Gold-layer data and calling Groq..."
4. Kết quả hiện ra: 3 cards với Action Tier, Risk, Drivers, Next Steps
5. Mở expander "Preview data sent to Groq" → cho thầy thấy JSON gọn từ Gold layer
```

**Thầy hỏi: "Sao không gửi raw data lên LLM?"**
> "Em chỉ gửi summary đã aggregate từ Gold layer — khoảng 8,000 ký tự. Raw data có hàng nghìn listings, gửi lên vừa tốn chi phí API vừa vượt context window của LLM. Gold layer đã tính sẵn opportunity_score và risk_score bằng dbt, LLM chỉ diễn giải kết quả."

**Thầy hỏi: "Nếu API lỗi thì sao?"**
> "Hệ thống có fallback — nếu Groq API không trả lời được, trang vẫn hiển thị dữ liệu thô từ Gold layer kèm thông báo 'AI temporarily unavailable'. User vẫn thấy data, không bị crash."

### Kịch bản demo 2: Market Overview

```
1. Bấm "📊 Market Overview"
2. Kết quả: tổng quan thị trường Bangkok, top areas, underperforming areas
3. Giải thích: "Mỗi nút bấm gọi một hàm riêng, query Gold layer khác nhau, dùng prompt khác nhau"
```

---

## 5. Thứ tự triển khai

```
Bước 1: Backend core (2-3 giờ)
  1.1  configs/settings.py        ← mở rộng LLMSettings (15 phút)
  1.2  llm/llm_client.py          ← GroqKeyPoolClient (45 phút)
  1.3  llm/context_builder.py     ← 4 hàm build context (30 phút)
  1.4  llm/prompt_templates.py    ← 4 system prompts (30 phút)
  1.5  llm/answer_generator.py    ← generate_answer + fallbacks (30 phút)

  → Test: chạy python -c "from llm.answer_generator import generate_answer; ..."

Bước 2: UI (1-2 giờ)
  2.1  app/components/ai_chat.py  ← Quick Actions + render cards (1 giờ)

  → Test: mở Streamlit, bấm nút, thấy cards

Bước 3: Polish (30 phút)
  3.1  Refactor groq_insights.py  ← delegate sang llm_client
  3.2  Cập nhật .env.example
  3.3  Cập nhật docs/llm_interpretation.md
```

---

## 6. Checklist tự kiểm tra

```
[ ] llm/llm_client.py tạo xong, import không lỗi
[ ] llm/context_builder.py query Gold layer thành công, output ≤ 8,000 chars
[ ] llm/prompt_templates.py có đủ 4 prompts
[ ] llm/answer_generator.py gọi Groq thành công, trả structured JSON
[ ] llm/answer_generator.py trả fallback khi xóa GROQ_API_KEY
[ ] app/components/ai_chat.py render cards đẹp khi nhận JSON
[ ] app/components/ai_chat.py hiện bảng Gold khi nhận fallback
[ ] Expander "Preview data sent to Groq" hiển thị đúng context
[ ] groq_insights.py vẫn hoạt động (tương thích ngược)
[ ] .env có GROQ_API_KEY và LLM_MODEL
[ ] Không có secret nào bị commit
```

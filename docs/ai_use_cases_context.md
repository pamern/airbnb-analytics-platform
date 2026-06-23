# AI Use Cases Context — Airbnb Analytics Platform

Tài liệu này định nghĩa chi tiết 4 Use Cases (UC) của AI Module trong dự án. Các UC được thiết kế theo chuẩn "AI Cố vấn" (Consultant), sử dụng phương pháp **Push Context** từ dbt Gold layer vào LLM Prompt, hoàn toàn không cho LLM tự viết SQL query trực tiếp vào Database.

---

## 🌟 UC1: Đề xuất Cơ hội Đầu tư (Investment Recommendations)

**Mục đích:** Giúp các nhà đầu tư/Host mới xác định nhanh chóng các khu vực "vàng" đáng xuống tiền nhất, kèm theo đánh giá rủi ro rõ ràng.
- **Persona (Người dùng):** Nhà đầu tư mới, người muốn tối ưu hóa nguồn vốn mở Airbnb.
- **Nguồn dữ liệu (Gold Layer):** `gold.gold_ai_qa_investment_recommendations`
- **Logic query (Context Builder):**
  - Lấy Top 8 khu vực tốt nhất (Sort theo `action_tier`, `opportunity_score` giảm dần, `risk_score` tăng dần).
  - Lấy theo kèm dòng thông tin Baseline trung bình của toàn thị trường.
- **Nhiệm vụ của LLM:**
  - Không liệt kê số liệu khô khan, mà phải trả lời được câu hỏi **TẠI SAO** (Ví dụ: "Doanh thu kỳ vọng cao do cầu vượt cung ở loại phòng Entire Home").
  - Phải chỉ ra **RỦI RO** (dựa vào `risk_flags`), không hứa hẹn lợi nhuận.
- **UI Element:** Nút bấm `🏆 Top 3 Cơ hội Đầu tư`

---

## 🌟 UC2: Khám sức khỏe & Tổng quan Thị trường (Market Health & Overview)

**Mục đích:** Đưa ra cái nhìn vĩ mô về toàn bộ thị trường Airbnb Bangkok hiện tại.
- **Persona (Người dùng):** Property Manager, Host đang hoạt động muốn biết biến động vĩ mô.
- **Nguồn dữ liệu (Gold Layer):** `gold.gold_ai_listing_market_summary` (tổng hợp theo toàn thị trường).
- **Logic query (Context Builder):**
  - `SELECT * FROM gold_ai_listing_market_summary` và gom nhóm lấy trung vị (median) của giá, tỷ lệ lấp đầy, doanh thu.
  - Lấy Top 5 khu vực mạnh nhất và Top 3 khu vực yếu nhất.
- **Nhiệm vụ của LLM:**
  - Viết 1 bản Executive Summary phân tích "sức khỏe" chung của thị trường.
  - Tìm ra các "anomalies" (điểm bất thường) trong dữ liệu, ví dụ: "Khu vực X có giá cao nhất nhưng tỷ lệ lấp đầy rất thấp -> Giá đang không phù hợp với thực tế".
- **UI Element:** Nút bấm `📊 Tổng quan Sức khỏe Thị trường`

---

## 🌟 UC3: Chiến lược Loại phòng & Định giá (Room Type & Pricing Strategy)

**Mục đích:** Tư vấn chiến lược cấu hình tài sản (Entire Home vs Private/Shared Room).
- **Persona (Người dùng):** Host mới đang xây nhà/thuê nhà, phân vân nên ngăn phòng hay cho thuê nguyên căn.
- **Nguồn dữ liệu (Gold Layer):** `gold.gold_ai_listing_market_summary` (Group by `room_type`).
- **Logic query (Context Builder):**
  - Lấy metrics so sánh giữa các `room_type` trên toàn bộ thị trường.
- **Nhiệm vụ của LLM:**
  - So sánh trực diện (Trade-off): "Entire home có giá cao nhưng cần nhiều vốn và dễ trống lịch, trong khi Private Room có dòng tiền ổn định hơn với tỷ lệ lấp đầy cao hơn".
  - Đưa ra lời khuyên cụ thể dựa trên số liệu doanh thu trung vị (median revenue).
- **UI Element:** Nút bấm `🏠 Phân tích Loại phòng & Chiến lược`

---

## 🌟 UC4: So sánh Đối đầu 2 Khu vực (Head-to-Head Comparison)

**Mục đích:** Tư vấn lựa chọn cuối cùng khi nhà đầu tư đang phân vân giữa 2-3 sự lựa chọn cụ thể.
- **Persona (Người dùng):** Nhà đầu tư đã có mục tiêu hẹp (Ví dụ: "Tôi đang định thuê nhà ở Khlong Toei hoặc Bang Phlat").
- **Nguồn dữ liệu (Gold Layer):** `gold.gold_ai_qa_investment_recommendations`
- **Logic query (Context Builder):**
  - Nhận input là mảng các `neighbourhoods` do user chọn từ giao diện.
  - `SELECT * FROM gold_ai_qa_investment_recommendations WHERE neighbourhood IN (...)`
- **Nhiệm vụ của LLM:**
  - Đặt các chỉ số của các khu vực lên bàn cân một cách khách quan.
  - LLM đưa ra kết luận: "Nếu bạn ưu tiên an toàn, hãy chọn A. Nếu bạn muốn lãi cao và chấp nhận rủi ro cạnh tranh, hãy chọn B".
- **UI Element:** Dropdown (Multiselect) chọn khu vực + Nút `⚔️ So sánh Đầu tư`

---

## 💡 Tổng kết Data Flow cho cả 4 UC
Mỗi Use Case sẽ tuân thủ nghiêm ngặt 4 bước:
1. **User Action:** Bấm nút / Chọn Dropdown trên Streamlit UI.
2. **Context Builder:** Chạy SQL query tương ứng vào bảng Gold, gom 1 DataFrame. Nén DataFrame đó thành 1 đoạn Text/JSON (Max ~8000 ký tự).
3. **Answer Generator:** Dùng System Prompt của UC đó (chứa các tiêu chuẩn Consultant Guardrails) + đoạn Data Context. Gọi Groq API qua `llm_client.py` (Có cơ chế Retry/Fallback).
4. **UI Render:** Nhận JSON phản hồi từ LLM, bóc tách và hiển thị lên các Streamlit Cards đẹp mắt.

"""
UI Component for AI Q&A rendering the Advisor LLM results in English.
Optimized to load options from cached dataframe to prevent rendering delays.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from llm.answer_generator import generate_answer


def _get_neighbourhoods() -> list[str]:
    """Return the top neighbourhoods in Bangkok directly to ensure instant page load without database blocking."""
    return [
        "Watthana",
        "Khlong Toei",
        "Ratchathewi",
        "Huai Khwang",
        "Sathon",
        "Bang Rak",
        "Phra Nakhon",
        "Pathum Wan",
        "Bang Na",
        "Chatuchak",
        "Bang Kapi",
        "Dusit",
        "Chom Thong",
        "Don Mueang",
        "Phaya Thai"
    ]


def render_ai_chat_page() -> None:
    # State management for AI use cases
    valid_use_cases = {"market_signals", "entry_strategy", "avoid_warnings"}
    if "active_use_case" not in st.session_state or st.session_state.active_use_case not in valid_use_cases:
        st.session_state.active_use_case = None

    st.markdown("## AI Market Advisor")
    st.write(
        "Use Bangkok Airbnb market data to discover market signals, entry strategies, and risks."
    )
    st.divider()

    st.markdown("### Quick Analysis")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Market Signals", use_container_width=True):
            st.session_state.active_use_case = "market_signals"
            st.rerun()
        st.caption("What should I pay attention to in the Bangkok Airbnb market?")

    with col2:
        if st.button("Entry Strategy", use_container_width=True):
            st.session_state.active_use_case = "entry_strategy"
            st.rerun()
        st.caption("Which direction should I take if I want to start?")

    with col3:
        if st.button("Risk Warnings", use_container_width=True):
            st.session_state.active_use_case = "avoid_warnings"
            st.rerun()
        st.caption("Which areas or segments should I avoid?")

    st.divider()

    # ── Handle Execution & Results Rendering ──
    if st.session_state.active_use_case:
        uc = st.session_state.active_use_case
        kwargs = {}

        with st.spinner("Analyzing market data & generating AI report..."):
            try:
                result = generate_answer(uc, **kwargs)
            except Exception as e:
                st.error(f"**AI Analysis Failed:** {type(e).__name__}: {e}")
                st.info("Please check your `.env` configuration (GROQ_API_KEY, MOTHERDUCK_TOKEN) and try again.")
                import traceback
                with st.expander("Full Error Details", expanded=False):
                    st.code(traceback.format_exc(), language="text")
                return

        # Show status meta or error
        meta = result.get("_meta", {})
        if meta.get("status") == "LLM_UNAVAILABLE":
            st.error(f"AI Service Temporarily Unavailable: {meta.get('reason')}")
            st.info("Direct Gold-layer fallback metrics:")
            st.write(result.get("data_notes", []))
            return

        # Render Results according to the UC
        if uc == "market_signals":
            _render_market_signals(result)
        elif uc == "entry_strategy":
            _render_entry_strategy(result)
        elif uc == "avoid_warnings":
            _render_avoid_warnings(result)

        # Data & Decision Notes
        if notes := result.get("data_notes"):
            with st.expander("⚠ Data & Validation Notes", expanded=False):
                for note in notes:
                    st.caption(f"• {note}")

        # Developer / Debug Tools at the bottom
        st.write("")
        with st.expander("Developer Tools (Response JSON)", expanded=False):
            st.json(result)


def _render_market_signals(result: dict) -> None:
    st.markdown("### Market Snapshot & Signals")

    if overview := result.get("market_overview"):
        if isinstance(overview, dict):
            if summary := overview.get("summary"):
                st.info(summary)
            if takeaway := overview.get("key_takeaway"):
                st.success(f"Key takeaway: {takeaway}")
        else:
            st.info(overview)

    snapshot = result.get("market_snapshot", {})
    if snapshot:
        cols = st.columns(4)
        cols[0].metric("Total Active Listings", f"{snapshot.get('total_active_listings', 0):,}")

        price = snapshot.get("median_nightly_price_thb", snapshot.get("median_price_thb", 0))
        cols[1].metric("Median Nightly Price", f"{price:,} THB" if isinstance(price, (int, float)) else str(price))

        cols[2].metric("Median Occupancy", snapshot.get("median_occupancy_rate", "0%"))

        rev = snapshot.get("median_estimated_revenue_thb", 0)
        cols[3].metric("Median Estimated Revenue", f"{rev:,} THB" if isinstance(rev, (int, float)) else str(rev))

        if note := snapshot.get("revenue_period_note"):
            st.caption(note)

    col_sig, col_watch = st.columns(2)
    with col_sig:
        st.markdown("#### Notable Market Signals")
        for signal in result.get("notable_market_signals", []):
            _render_signal_card(
                signal,
                title_key="signal_title",
                body_keys=[
                    ("Related", "related_entities"),
                    ("Evidence", "evidence_metrics"),
                    ("Interpretation", "interpretation"),
                    ("Personal Relevance", "personal_relevance"),
                    ("What To Watch Next", "what_to_watch_next"),
                ],
            )

    with col_watch:
        st.markdown("#### Watchlist Signals")
        for signal in result.get("watchlist_signals", []):
            _render_signal_card(
                signal,
                title_key="watchlist_title",
                body_keys=[
                    ("Related", "related_entities"),
                    ("Evidence", "evidence_metrics"),
                    ("Why It Matters", "why_it_matters"),
                    ("Not A Final Decision", "not_a_final_decision"),
                ],
            )

    st.markdown("---")
    col_tr, col_an = st.columns(2)
    with col_tr:
        st.markdown("#### Segment Trends")
        for trend in result.get("segment_trends", []):
            _render_signal_card(
                trend,
                title_key="segment_name",
                body_keys=[
                    ("Evidence", "evidence_metrics"),
                    ("Trend Interpretation", "trend_interpretation"),
                    ("Personal Relevance", "personal_relevance"),
                ],
            )

    with col_an:
        st.markdown("#### Pricing Anomalies")
        for anomaly in result.get("pricing_anomalies", []):
            _render_signal_card(
                anomaly,
                title_key="anomaly_title",
                body_keys=[
                    ("Related Area", "related_area"),
                    ("Evidence", "evidence_metrics"),
                    ("Interpretation", "interpretation"),
                    ("What To Verify Next", "what_to_verify_next"),
                ],
            )


def _render_signal_card(item, title_key: str, body_keys: list[tuple[str, str]]) -> None:
    if not isinstance(item, dict):
        st.markdown(f"- {item}")
        return

    title = item.get(title_key) or item.get("title") or "Market signal"
    with st.container(border=True):
        st.markdown(f"**{title}**")
        for label, key in body_keys:
            value = item.get(key)
            if not value:
                continue
            if isinstance(value, list):
                clean_values = [str(v) for v in value if v not in (None, "")]
                if clean_values:
                    st.markdown(f"**{label}:**")
                    for entry in clean_values:
                        st.markdown(f"- {entry}")
            else:
                st.markdown(f"**{label}:** {value}")


def _format_key_drivers(raw_drivers) -> list[str]:
    if isinstance(raw_drivers, dict):
        return [
            f"{key.replace('_', ' ').title()}: {value}"
            for key, value in raw_drivers.items()
            if value not in (None, "")
        ]

    if not isinstance(raw_drivers, list):
        return [str(raw_drivers)] if raw_drivers else []

    drivers: list[str] = []
    index = 0
    while index < len(raw_drivers):
        item = raw_drivers[index]
        if isinstance(item, dict):
            drivers.extend(_format_key_drivers(item))
            index += 1
            continue

        text = str(item).strip()
        if index + 2 < len(raw_drivers) and str(raw_drivers[index + 1]).strip() == ":":
            value = str(raw_drivers[index + 2]).strip()
            drivers.append(f"{text.replace('_', ' ').title()}: {value}")
            index += 3
            continue

        if text and text != ":":
            drivers.append(text)
        index += 1

    return drivers


def _render_entry_strategy_legacy(result: dict) -> None:
    st.markdown("### 🏆 Recommended Market Entry Strategies")
    
    if summary := result.get("executive_summary"):
        st.info(summary)

    # Render recommendations as containers
    for rec in result.get("top_recommendations", []):
        tier = rec.get("action_tier", "Unknown")
        tier_colors = {
            "Strong Invest": "🟢",
            "Investigate Further": "🟡",
            "Stable but Low Priority": "🔵",
            "Avoid": "🔴"
        }
        icon = tier_colors.get(tier, "⚪")

        with st.container(border=True):
            st.markdown(f"#### Rank #{rec.get('rank', 'N/A')} {rec.get('neighbourhood')} — {rec.get('recommended_room_type')}")
            
            # Metrics
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.markdown(f"**Action Tier:** {icon} {tier}")
            col_m2.markdown(f"**Opportunity Level:** `{rec.get('opportunity_level', 'N/A')}`")
            col_m3.markdown(f"**Risk Level:** `{rec.get('risk_level', 'N/A')}`")

            col_sub1, col_sub2 = st.columns(2)
            col_sub1.markdown(f"**Dominant Segment:** `{rec.get('dominant_segment', 'N/A')}`")
            col_sub2.markdown(f"**Estimated Starting Price:** `{rec.get('estimated_starting_price', 'N/A')}`")

            st.write("")
            st.markdown(f"**Thesis:** {rec.get('entry_thesis', '')}")
            
            st.markdown("**Key Drivers:**")
            for driver in _format_key_drivers(rec.get("key_drivers", [])):
                st.markdown(f"- {driver}")

            st.markdown(f"**Suggested Configuration:** {rec.get('suggested_setup', '')}")

    if advice := result.get("strategic_advice"):
        st.markdown("---")
        st.markdown("#### 💡 Strategic Advice")
        st.markdown(advice)


def _render_entry_strategy(result: dict) -> None:
    st.markdown("### Recommended Market Entry Strategies")

    if summary := result.get("executive_summary"):
        if isinstance(summary, dict):
            if text := summary.get("summary"):
                st.info(text)
            col_logic, col_posture = st.columns(2)
            col_logic.markdown(f"**Recommended Entry Logic:** {summary.get('recommended_entry_logic', 'N/A')}")
            col_posture.markdown(f"**Decision Posture:** `{summary.get('decision_posture', 'N/A')}`")
        else:
            st.info(summary)

    baseline = result.get("market_baseline_used", {})
    if baseline:
        st.markdown("#### Market Baseline Used")
        cols = st.columns(3)
        price = baseline.get("market_median_nightly_price_thb", 0)
        cols[0].metric("Median Nightly Price", f"{price:,} THB" if isinstance(price, (int, float)) else str(price))
        cols[1].metric("Median Occupancy", baseline.get("market_median_occupancy_rate", "0%"))
        rev = baseline.get("market_median_estimated_revenue_thb", 0)
        cols[2].metric("Median Estimated Revenue", f"{rev:,} THB" if isinstance(rev, (int, float)) else str(rev))
        if interpretation := baseline.get("baseline_interpretation"):
            st.caption(interpretation)

    for rec in result.get("top_recommendations", []):
        tier = rec.get("action_tier", "Unknown")
        tier_labels = {
            "Strong Invest": "[Strong]",
            "Investigate Further": "[Investigate]",
            "Stable but Low Priority": "[Stable]",
            "Avoid": "[Avoid]",
        }
        tier_label = tier_labels.get(tier, "[Review]")

        with st.container(border=True):
            title = rec.get("recommendation_title") or f"{rec.get('neighbourhood')} - {rec.get('recommended_room_type')}"
            st.markdown(f"#### Rank #{rec.get('rank', 'N/A')} {title}")

            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.markdown(f"**Action Tier:** {tier_label} {tier}")
            col_m2.markdown(f"**Decision:** `{rec.get('decision_label', 'N/A')}`")
            col_m3.markdown(f"**Opportunity:** `{rec.get('opportunity_level', 'N/A')}`")
            col_m4.markdown(f"**Risk:** `{rec.get('risk_level', 'N/A')}`")

            col_sub1, col_sub2, col_sub3 = st.columns(3)
            col_sub1.markdown(f"**Dominant Segment:** `{rec.get('dominant_segment', 'N/A')}`")
            col_sub2.markdown(f"**Confidence:** `{rec.get('confidence_level', 'N/A')}`")
            col_sub3.markdown(f"**Room Type:** `{rec.get('recommended_room_type', 'N/A')}`")

            st.write("")
            if ranked_reason := rec.get("why_ranked_here"):
                st.markdown(f"**Why Ranked Here:** {ranked_reason}")
            if thesis := rec.get("entry_thesis"):
                st.markdown(f"**Thesis:** {thesis}")

            evidence = rec.get("evidence", {})
            if evidence:
                st.markdown("**Evidence:**")
                for label, value in evidence.items():
                    if value:
                        st.markdown(f"- **{label.replace('_', ' ').title()}:** {value}")

            if tradeoffs := rec.get("tradeoffs"):
                st.markdown("**Trade-offs:**")
                for item in tradeoffs:
                    st.markdown(f"- {item}")

            if benchmark := rec.get("market_price_benchmark"):
                st.markdown(f"**Market Price Benchmark:** {benchmark}")
            if positioning := rec.get("suggested_positioning"):
                st.markdown(f"**Suggested Positioning:** {positioning}")
            if playbook := rec.get("entry_playbook"):
                st.markdown("**Entry Playbook:**")
                for item in playbook:
                    st.markdown(f"- {item}")
            if conditions := rec.get("conditions_to_reconsider"):
                st.markdown("**Conditions To Reconsider:**")
                for item in conditions:
                    st.markdown(f"- {item}")

            if rec.get("key_drivers"):
                st.markdown("**Key Drivers:**")
                for driver in _format_key_drivers(rec.get("key_drivers", [])):
                    st.markdown(f"- {driver}")
            if rec.get("suggested_setup"):
                st.markdown(f"**Suggested Configuration:** {rec.get('suggested_setup')}")

    if insights := result.get("cross_candidate_insights"):
        st.markdown("---")
        st.markdown("#### Cross-candidate Insights")
        for insight in insights:
            _render_signal_card(
                insight,
                title_key="insight_title",
                body_keys=[
                    ("Evidence", "evidence"),
                    ("Strategic Meaning", "strategic_meaning"),
                ],
            )

    if guidance := result.get("final_entry_guidance"):
        st.markdown("---")
        st.markdown("#### Final Entry Guidance")
        if isinstance(guidance, dict):
            for label, key in [
                ("Best Fit For Risk-averse User", "best_fit_for_risk_averse_user"),
                ("Best Fit For Revenue-oriented User", "best_fit_for_revenue_oriented_user"),
                ("What Not To Overinterpret", "what_not_to_overinterpret"),
            ]:
                if value := guidance.get(key):
                    st.markdown(f"**{label}:** {value}")
        else:
            st.markdown(guidance)

    if advice := result.get("strategic_advice"):
        st.markdown("---")
        st.markdown("#### Strategic Advice")
        st.markdown(advice)


def _render_avoid_warnings(result: dict) -> None:
    st.markdown("### ⚠️ Avoid List & Risk Warning System")
    
    if overview := result.get("risk_overview"):
        st.warning(overview)

    for area in result.get("high_risk_areas", []):
        with st.container(border=True):
            st.markdown(f"#### 🔴 Avoid: {area.get('neighbourhood')} — {area.get('room_type')}")
            
            col_left, col_right = st.columns(2)
            col_left.markdown(f"**Risk Score:** `{area.get('risk_score', 0)} / 100`")
            col_right.markdown(f"**Risk Level:** `{area.get('risk_level', 'High')}`")

            st.write("")
            st.markdown(f"**Why to Avoid:** {area.get('why_to_avoid', '')}")
            
            st.markdown("**Risk Flags Detected:**")
            for flag in area.get("risk_flags", []):
                st.markdown(f"- `{flag}`")

            if mitigation := area.get("mitigation_if_already_invested"):
                st.markdown(f"**Mitigation Strategy:** *{mitigation}*")

    # Saturated segments & Macro warnings
    st.markdown("---")
    col_sat, col_mac = st.columns(2)
    with col_sat:
        st.markdown("#### 📦 Saturated Listing Segments")
        for seg in result.get("saturated_segments", []):
            st.markdown(f"- {seg}")
            
    with col_mac:
        st.markdown("#### 🏢 Macro Regulatory & Market Warnings")
        for warning in result.get("macro_warnings", []):
            st.markdown(f"- {warning}")


def _render_idea_validator(result: dict) -> None:
    st.markdown("### 🔍 Airbnb Concept Validation Report")
    
    eval_data = result.get("concept_evaluation", {})
    if eval_data:
        verdict = eval_data.get("verdict", "high_risk").lower()
        score = eval_data.get("score_pct", 0)

        verdict_styles = {
            "highly_feasible": ("Highly Feasible 🟢", st.success),
            "moderately_feasible": ("Moderately Feasible 🟡", st.warning),
            "high_risk": ("High Risk 🟠", st.warning),
            "unrealistic": ("Unrealistic 🔴", st.error)
        }
        
        label, func = verdict_styles.get(verdict, ("Unknown Risk", st.info))
        
        # Display large status box
        func(f"**Concept Verdict:** {label} ({score}% Feasibility Score)\n\n"
             f"**Price Assessment:** {eval_data.get('price_check', '')}")

    if report := result.get("feasibility_report"):
        st.markdown("#### 📖 Feasibility Analysis")
        st.write(report)

    # Market Benchmarks
    bench = result.get("market_benchmarks", {})
    if bench:
        st.markdown("#### 📊 Target Neighborhood Room-Type Benchmarks")
        cols = st.columns(3)
        
        m_price = bench.get("median_nightly_price_thb", 0)
        cols[0].metric("Median Price", f"{m_price:,} THB" if isinstance(m_price, (int, float)) else str(m_price))
        
        cols[1].metric("Median Occupancy", bench.get("median_occupancy_rate", "0%"))
        
        rev = bench.get("median_estimated_revenue_thb", 0)
        cols[2].metric("Est. Annual Revenue", f"{rev:,} THB" if isinstance(rev, (int, float)) else str(rev))
        
        st.caption(f"Dominant Segment: `{bench.get('dominant_segment', 'N/A')}`")

    # Strengths and Challenges
    st.markdown("---")
    col_str, col_cha = st.columns(2)
    with col_str:
        st.markdown("#### 👍 Strengths of Your Concept")
        for strength in result.get("strengths_of_idea", []):
            st.markdown(f"- {strength}")
            
    with col_cha:
        st.markdown("#### 👎 Risks & Challenges")
        for challenge in result.get("risks_and_challenges", []):
            st.markdown(f"- {challenge}")

    if recs := result.get("actionable_recommendations"):
        st.markdown("---")
        st.markdown("#### 🚀 Actionable Recommendations")
        for rec in recs:
            st.markdown(f"- {rec}")

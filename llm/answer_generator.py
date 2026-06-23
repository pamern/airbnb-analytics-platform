"""
Orchestrates context gathering, prompt building, LLM calling, and fallback logic for the 4 new Use Cases.
"""

import logging
import traceback

from llm import prompt_templates
from llm.context_builder import (
    build_market_signals_context,
    build_entry_strategy_context,
    build_avoid_warnings_context,
    build_idea_validation_context,
)
from llm.llm_client import GroqKeyPoolClient

logger = logging.getLogger(__name__)


# Fallback Handlers for 4 UCs when LLM is unavailable
def _market_signals_fallback(reason: str, raw_context: str) -> dict:
    return {
        "_meta": {"status": "LLM_UNAVAILABLE", "reason": reason},
        "market_overview": {
            "summary": "AI market analysis is temporarily unavailable. Please refer to raw dashboard charts.",
            "key_takeaway": "The LLM service is unavailable, so no generated market signal interpretation is available.",
        },
        "market_snapshot": {
            "total_active_listings": 0,
            "median_nightly_price_thb": 0,
            "median_occupancy_rate": "0%",
            "median_estimated_revenue_thb": 0,
            "revenue_period_note": "Fallback response; revenue period could not be interpreted.",
        },
        "notable_market_signals": [],
        "watchlist_signals": [],
        "segment_trends": [],
        "pricing_anomalies": [],
        "data_notes": [reason, raw_context[:500] + "..."]
    }


def _entry_strategy_fallback(reason: str, raw_context: str) -> dict:
    return {
        "_meta": {"status": "LLM_UNAVAILABLE", "reason": reason},
        "executive_summary": {
            "summary": "AI entry recommendations are temporarily unavailable. Raw dataset fallback active.",
            "recommended_entry_logic": "No generated entry logic is available while the LLM service is unavailable.",
            "decision_posture": "Cautious entry",
        },
        "market_baseline_used": {
            "market_median_nightly_price_thb": 0,
            "market_median_occupancy_rate": "0%",
            "market_median_estimated_revenue_thb": 0,
            "baseline_interpretation": "Fallback response; market baseline could not be interpreted.",
        },
        "top_recommendations": [],
        "cross_candidate_insights": [],
        "final_entry_guidance": {
            "best_fit_for_risk_averse_user": "No guidance available due to API disconnect.",
            "best_fit_for_revenue_oriented_user": "No guidance available due to API disconnect.",
            "what_not_to_overinterpret": "Do not infer ROI, profit, legal feasibility, or operating cost from this fallback response.",
        },
        "data_notes": [reason, raw_context[:500] + "..."]
    }


def _avoid_warnings_fallback(reason: str, raw_context: str) -> dict:
    return {
        "_meta": {"status": "LLM_UNAVAILABLE", "reason": reason},
        "risk_overview": "AI risk warning system is temporarily offline.",
        "high_risk_areas": [],
        "saturated_segments": [],
        "macro_warnings": [],
        "data_notes": [reason, raw_context[:500] + "..."]
    }


def _idea_validator_fallback(reason: str, raw_context: str) -> dict:
    return {
        "_meta": {"status": "LLM_UNAVAILABLE", "reason": reason},
        "concept_evaluation": {
            "user_neighbourhood": "N/A",
            "user_room_type": "N/A",
            "user_target_price_thb": 0,
            "verdict": "high_risk",
            "score_pct": 0,
            "price_check": "Validation failed due to database or API error."
        },
        "feasibility_report": "Unable to validate concept because the AI advisor is currently offline.",
        "market_benchmarks": {},
        "strengths_of_idea": [],
        "risks_and_challenges": ["AI system offline"],
        "actionable_recommendations": ["Try again later"],
        "data_notes": [reason, raw_context[:500] + "..."]
    }


USE_CASE_CONFIG = {
    "market_signals": {
        "context_fn": build_market_signals_context,
        "prompt": prompt_templates.MARKET_SIGNALS_PROMPT,
        "fallback": _market_signals_fallback,
    },
    "entry_strategy": {
        "context_fn": build_entry_strategy_context,
        "prompt": prompt_templates.ENTRY_STRATEGY_PROMPT,
        "fallback": _entry_strategy_fallback,
    },
    "avoid_warnings": {
        "context_fn": build_avoid_warnings_context,
        "prompt": prompt_templates.AVOID_WARNINGS_PROMPT,
        "fallback": _avoid_warnings_fallback,
    },
    "idea_validator": {
        "context_fn": build_idea_validation_context,
        "prompt": prompt_templates.IDEA_VALIDATOR_PROMPT,
        "fallback": _idea_validator_fallback,
    },
}


def generate_answer(use_case: str, **kwargs) -> dict:
    """
    Entry point for all LLM calls.
    Args:
        use_case: "market_signals", "entry_strategy", "avoid_warnings", "idea_validator"
        **kwargs: arguments for the context function (e.g. neighbourhood, room_type, target_price)
    """
    logger.info(f"[AI] generate_answer called with use_case={use_case!r}, kwargs={list(kwargs.keys())}")

    if use_case not in USE_CASE_CONFIG:
        available = list(USE_CASE_CONFIG.keys())
        raise ValueError(
            f"Unknown use case: {use_case!r}. Available: {available}"
        )

    config = USE_CASE_CONFIG[use_case]
    context = ""

    # 1. Build Context
    try:
        context = config["context_fn"](**kwargs)
        logger.info(f"[AI] Context built for {use_case}, length={len(context)}")
    except Exception as e:
        logger.error(f"Failed to build context for {use_case}: {e}\n{traceback.format_exc()}")
        return config["fallback"](f"Context builder failed: {e}", "")

    # 2. Format Prompt
    try:
        prompt_template = config["prompt"]
        prompt = prompt_template.format(data_context=context)
        logger.info(f"[AI] Prompt formatted for {use_case}, length={len(prompt)}")
    except Exception as e:
        logger.error(f"Failed to format prompt for {use_case}: {e}\n{traceback.format_exc()}")
        return config["fallback"](f"Prompt formatting failed: {e}", context)

    # 3. Call LLM
    try:
        client = GroqKeyPoolClient()
        result = client.chat_json(prompt)
        if not isinstance(result, dict):
            logger.error(f"[AI] LLM returned non-dict: {type(result)}")
            return config["fallback"](f"LLM returned {type(result)} instead of dict", context)

        result["_meta"] = {
            "status": "SUCCESS",
            "provider": "groq",
            "model": client.model,
            "context_chars": len(context),
        }
        return result
    except Exception as e:
        logger.error(f"LLM generation failed for {use_case}: {e}\n{traceback.format_exc()}")
        return config["fallback"](str(e), context)

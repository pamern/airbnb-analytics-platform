"""
Queries the Gold layer to build compact JSON contexts for the 4 new AI Use Cases.
"""

import json
import pandas as pd
from typing import Optional
from functools import lru_cache

from utils.motherduck import connect_motherduck
from utils.sql import query_dataframe


def _get_connection():
    return connect_motherduck(read_only=True)


def _loads_json_cell(value, default=None):
    if default is None:
        default = {}
    if value is None or pd.isna(value):
        return default
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


@lru_cache(maxsize=1)
def build_market_signals_context() -> str:
    """UC1: Bangkok market signals, top/bottom area signals, and segment trends."""
    conn = _get_connection()
    try:
        sql = """
        with neighbourhood_stats as (
            select distinct
                neighbourhood,
                listing_count,
                median_price,
                median_occupancy_rate,
                median_estimated_revenue,
                neighbourhood_overpriced_listings_count
            from gold.gold_ai_qa_investment_recommendations
        ),

        overall as (
            select
                sum(listing_count) as total_listings,
                median(median_price) as market_median_price,
                median(median_occupancy_rate) as market_median_occupancy_rate,
                median(median_estimated_revenue) as market_median_revenue
            from neighbourhood_stats
        ),

        ranked_areas as (
            select
                neighbourhood,
                listing_count,
                median_price,
                median_occupancy_rate,
                median_estimated_revenue,
                row_number() over (order by median_estimated_revenue desc) as top_rank,
                row_number() over (order by median_estimated_revenue asc) as bottom_rank
            from neighbourhood_stats
            where listing_count >= 15
        ),

        segments as (
            select
                coalesce(room_type_dominant_segment, neighbourhood_dominant_segment, 'UNKNOWN') as segment,
                count(*) as candidate_count,
                sum(room_type_listing_count) as covered_listing_count
            from gold.gold_ai_qa_investment_recommendations
            group by 1
            order by count(*) desc
            limit 8
        ),

        anomalies as (
            select
                neighbourhood,
                neighbourhood_overpriced_listings_count as overpriced_listings_count
            from neighbourhood_stats
            where neighbourhood_overpriced_listings_count > 0
            order by neighbourhood_overpriced_listings_count desc
            limit 5
        )

        select
            (select to_json(o) from overall as o) as overall_market_snapshot,
            (
                select array_to_json(array_agg(to_json(a)))
                from (
                    select neighbourhood, listing_count, median_price, median_occupancy_rate, median_estimated_revenue
                    from ranked_areas
                    where top_rank <= 5
                    order by top_rank
                ) as a
            ) as top_5_performing_areas,
            (
                select array_to_json(array_agg(to_json(a)))
                from (
                    select neighbourhood, listing_count, median_price, median_occupancy_rate, median_estimated_revenue
                    from ranked_areas
                    where bottom_rank <= 3
                    order by bottom_rank
                ) as a
            ) as bottom_3_performing_areas,
            (select array_to_json(array_agg(to_json(s))) from segments as s) as segment_listing_distribution,
            (select array_to_json(array_agg(to_json(a))) from anomalies as a) as areas_with_highest_overpriced_listings
        """

        df = query_dataframe(conn, sql)
        if df.empty:
            return json.dumps({
                "overall_market_snapshot": {},
                "top_5_performing_areas": [],
                "bottom_3_performing_areas": [],
                "segment_listing_distribution": [],
                "areas_with_highest_overpriced_listings": []
            }, indent=2)

        overall_metrics = {}
        overall_raw = _loads_json_cell(df.at[0, "overall_market_snapshot"])
        if overall_raw:
            overall_metrics = {
                "total_listings": int(overall_raw.get("total_listings") or 0),
                "market_median_price_thb": float(overall_raw.get("market_median_price") or 0.0),
                "market_median_occupancy_rate": f"{float(overall_raw.get('market_median_occupancy_rate') or 0.0) * 100:.1f}%",
                "market_median_estimated_revenue_thb": float(overall_raw.get("market_median_revenue") or 0.0)
            }

        return json.dumps(
            {
                "overall_market_snapshot": overall_metrics,
                "top_5_performing_areas": _loads_json_cell(df.at[0, "top_5_performing_areas"], default=[]),
                "bottom_3_performing_areas": _loads_json_cell(df.at[0, "bottom_3_performing_areas"], default=[]),
                "segment_listing_distribution": _loads_json_cell(df.at[0, "segment_listing_distribution"], default=[]),
                "areas_with_highest_overpriced_listings": _loads_json_cell(
                    df.at[0,
                          "areas_with_highest_overpriced_listings"],
                    default=[],
                )
            },
            indent=2
        )
    finally:
        conn.close()


@lru_cache(maxsize=1)
def build_entry_strategy_context() -> str:
    """UC2: Top candidates with strong entry feasibility and baseline comparison details."""
    conn = _get_connection()
    try:
        sql = """
        select
            opp.neighbourhood,
            opp.recommended_room_type,
            opp.listing_count,
            opp.room_type_listing_count,
            opp.room_type_median_price,
            opp.room_type_median_occupancy_rate,
            opp.room_type_median_estimated_revenue,
            opp.market_median_price,
            opp.market_median_occupancy_rate,
            opp.market_median_estimated_revenue,
            opp.opportunity_score,
            opp.risk_score,
            opp.opportunity_level,
            opp.risk_level,
            opp.action_tier,
            opp.confidence_level,
            opp.room_type_dominant_segment as dominant_segment,
            coalesce(opp.risk_flags, 'No major risk flags') as risk_flags
        from gold.gold_ai_qa_investment_recommendations opp
        where opp.action_tier in ('Strong Invest', 'Investigate Further')
        order by
            case opp.action_tier
                when 'Strong Invest' then 1
                when 'Investigate Further' then 2
                else 3
            end,
            opp.opportunity_score desc
        limit 6
        """
        df = query_dataframe(conn, sql)
        if df.empty:
            return "No strong entry strategy options available at this time."

        candidates = []
        for _, row in df.iterrows():
            rt_rev = float(row["room_type_median_estimated_revenue"]) if pd.notna(row["room_type_median_estimated_revenue"]) else 0.0
            mkt_rev = float(row["market_median_estimated_revenue"]) if pd.notna(row["market_median_estimated_revenue"]) else 0.0
            rt_occ = float(row["room_type_median_occupancy_rate"]) if pd.notna(row["room_type_median_occupancy_rate"]) else 0.0
            mkt_occ = float(row["market_median_occupancy_rate"]) if pd.notna(row["market_median_occupancy_rate"]) else 0.0

            candidates.append({
                "neighbourhood": row["neighbourhood"],
                "recommended_room_type": row["recommended_room_type"],
                "room_type_listing_count": int(row["room_type_listing_count"]) if pd.notna(row["room_type_listing_count"]) else 0,
                "median_nightly_price_thb": float(row["room_type_median_price"]) if pd.notna(row["room_type_median_price"]) else 0.0,
                "median_occupancy_rate": f"{rt_occ * 100:.1f}%",
                "median_estimated_revenue_thb": rt_rev,
                "dominant_segment": row["dominant_segment"],
                "action_tier": row["action_tier"],
                "opportunity_level": row["opportunity_level"],
                "risk_level": row["risk_level"],
                "confidence_level": row["confidence_level"],
                "revenue_vs_market_pct": f"{((rt_rev / mkt_rev) - 1.0) * 100:+.1f}%" if mkt_rev > 0 else "+0.0%",
                "occupancy_vs_market_pct": f"{((rt_occ / mkt_occ) - 1.0) * 100:+.1f}%" if mkt_occ > 0 else "+0.0%"
            })

        first = df.iloc[0]
        return json.dumps({
            "market_baselines": {
                "market_median_price_thb": float(first["market_median_price"]) if pd.notna(first["market_median_price"]) else 0.0,
                "market_median_occupancy_rate": f"{float(first['market_median_occupancy_rate']) * 100:.1f}%" if pd.notna(first["market_median_occupancy_rate"]) else "0%",
                "market_median_estimated_revenue_thb": float(first["market_median_estimated_revenue"]) if pd.notna(first["market_median_estimated_revenue"]) else 0.0
            },
            "top_entry_candidates": candidates
        }, indent=2)
    finally:
        conn.close()


@lru_cache(maxsize=1)
def build_avoid_warnings_context() -> str:
    """UC3: Saturated and high-risk candidates with warning details and risk flags."""
    conn = _get_connection()
    try:
        sql = """
        select
            opp.neighbourhood,
            opp.recommended_room_type,
            opp.listing_count,
            opp.room_type_listing_count,
            opp.room_type_median_price,
            opp.room_type_median_occupancy_rate,
            opp.room_type_median_estimated_revenue,
            opp.market_median_price,
            opp.market_median_occupancy_rate,
            opp.market_median_estimated_revenue,
            opp.opportunity_score,
            opp.risk_score,
            opp.opportunity_level,
            opp.risk_level,
            opp.action_tier,
            opp.confidence_level,
            opp.room_type_dominant_segment as dominant_segment,
            coalesce(opp.risk_flags, 'No major risk flags') as risk_flags
        from gold.gold_ai_qa_investment_recommendations opp
        where opp.risk_score >= 15 or opp.action_tier = 'Avoid'
        order by opp.risk_score desc
        limit 8
        """
        df = query_dataframe(conn, sql)
        if df.empty:
            return "No high-risk segments identified in the current market snapshot."

        candidates = []
        for _, row in df.iterrows():
            rt_occ = float(row["room_type_median_occupancy_rate"]) if pd.notna(row["room_type_median_occupancy_rate"]) else 0.0
            mkt_occ = float(row["market_median_occupancy_rate"]) if pd.notna(row["market_median_occupancy_rate"]) else 0.0
            rt_rev = float(row["room_type_median_estimated_revenue"]) if pd.notna(row["room_type_median_estimated_revenue"]) else 0.0
            mkt_rev = float(row["market_median_estimated_revenue"]) if pd.notna(row["market_median_estimated_revenue"]) else 0.0

            candidates.append({
                "neighbourhood": row["neighbourhood"],
                "room_type": row["recommended_room_type"],
                "listing_count": int(row["room_type_listing_count"]) if pd.notna(row["room_type_listing_count"]) else 0,
                "median_nightly_price_thb": float(row["room_type_median_price"]) if pd.notna(row["room_type_median_price"]) else 0.0,
                "median_occupancy_rate": f"{rt_occ * 100:.1f}%",
                "median_estimated_revenue_thb": rt_rev,
                "dominant_segment": row["dominant_segment"],
                "risk_score": float(row["risk_score"]),
                "risk_level": row["risk_level"],
                "action_tier": row["action_tier"],
                "risk_flags": [flag.strip() for flag in row["risk_flags"].split(";")] if row["risk_flags"] else [],
                "occupancy_vs_market_pct": f"{((rt_occ / mkt_occ) - 1.0) * 100:+.1f}%" if mkt_occ > 0 else "+0.0%",
                "revenue_vs_market_pct": f"{((rt_rev / mkt_rev) - 1.0) * 100:+.1f}%" if mkt_rev > 0 else "+0.0%"
            })

        return json.dumps({
            "high_risk_and_saturated_candidates": candidates
        }, indent=2)
    finally:
        conn.close()


@lru_cache(maxsize=128)
def build_idea_validation_context(neighbourhood: str, room_type: str, target_price: float) -> str:
    """UC4: Specific neighbourhood & room type benchmarks to validate user target price."""
    conn = _get_connection()
    try:
        sql = """
        select
            opp.neighbourhood,
            opp.recommended_room_type,
            opp.room_type_listing_count,
            opp.room_type_median_price,
            opp.room_type_median_occupancy_rate,
            opp.room_type_median_estimated_revenue,
            opp.market_median_price,
            opp.market_median_occupancy_rate,
            opp.market_median_estimated_revenue,
            opp.opportunity_score,
            opp.risk_score,
            opp.opportunity_level,
            opp.risk_level,
            opp.action_tier,
            opp.confidence_level,
            opp.room_type_dominant_segment as dominant_segment,
            coalesce(opp.risk_flags, 'No major risk flags') as risk_flags
        from gold.gold_ai_qa_investment_recommendations opp
        where opp.neighbourhood = ? and opp.recommended_room_type = ?
        limit 1
        """
        df = query_dataframe(conn, sql, [neighbourhood, room_type])
        if df.empty:
            # Return general area statistics if the specific combination is not in the opportunity table
            sql_fallback = """
            select
                neighbourhood,
                recommended_room_type,
                room_type_listing_count,
                room_type_median_price,
                room_type_median_occupancy_rate,
                room_type_median_estimated_revenue,
                room_type_dominant_segment as dominant_segment
            from gold.gold_ai_qa_investment_recommendations
            where neighbourhood = ?
            limit 3
            """
            df_fb = query_dataframe(conn, sql_fallback, [neighbourhood])
            if df_fb.empty:
                return json.dumps({
                    "user_concept": {"neighbourhood": neighbourhood, "room_type": room_type, "target_price_thb": target_price},
                    "message": f"No historical listing data available for the neighbourhood '{neighbourhood}'."
                })
            
            return json.dumps({
                "user_concept": {"neighbourhood": neighbourhood, "room_type": room_type, "target_price_thb": target_price},
                "error": "exact_combination_not_found",
                "similar_room_types_in_neighbourhood": df_fb.to_dict(orient="records")
            }, indent=2)

        row = df.iloc[0]
        rt_occ = float(row["room_type_median_occupancy_rate"]) if pd.notna(row["room_type_median_occupancy_rate"]) else 0.0
        mkt_occ = float(row["market_median_occupancy_rate"]) if pd.notna(row["market_median_occupancy_rate"]) else 0.0

        return json.dumps({
            "user_concept": {
                "neighbourhood": neighbourhood,
                "room_type": room_type,
                "target_price_thb": target_price
            },
            "market_benchmarks": {
                "neighbourhood": row["neighbourhood"],
                "room_type": row["recommended_room_type"],
                "listing_count": int(row["room_type_listing_count"]) if pd.notna(row["room_type_listing_count"]) else 0,
                "median_nightly_price_thb": float(row["room_type_median_price"]) if pd.notna(row["room_type_median_price"]) else 0.0,
                "median_occupancy_rate": f"{rt_occ * 100:.1f}%",
                "median_estimated_revenue_thb": float(row["room_type_median_estimated_revenue"]) if pd.notna(row["room_type_median_estimated_revenue"]) else 0.0,
                "dominant_segment": row["dominant_segment"],
                "market_median_price_thb": float(row["market_median_price"]) if pd.notna(row["market_median_price"]) else 0.0,
                "market_median_occupancy_rate": f"{mkt_occ * 100:.1f}%",
                "risk_flags": [flag.strip() for flag in row["risk_flags"].split(";")] if row["risk_flags"] else []
            }
        }, indent=2)
    finally:
        conn.close()

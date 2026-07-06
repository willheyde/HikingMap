#!/usr/bin/env python3
"""
difficulty_delta_report.py

Aggregates hike_completions.difficulty_felt against the DifficultyLevel each
trail was predicted at (hikes.difficulty, as it was when the hike was
searched — see trip_stops.trail_data.hike_id) and flags the trails with the
largest predicted-vs-actual deltas.

This is groundwork for the elevation/tag data quality issues already
identified in QA — it does NOT feed back into the live recommendation
engine. Read the output, decide which hikes' difficulty/elevation data
actually needs correcting, and do that by hand (or in a follow-up task).

USAGE
-----
    python reports/difficulty_delta_report.py
    python reports/difficulty_delta_report.py --min-reviews 2 --top 10
    python reports/difficulty_delta_report.py --out my_report.md

Only reviews where went=true and difficulty_felt is set are considered —
matches the questionnaire's own gating (difficulty_felt is only collected
when the user says they actually went).
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

# Running `python reports/difficulty_delta_report.py` puts reports/ (not
# pythonBackend/) at the front of sys.path, so DBConnection wouldn't resolve
# without this — lets the script run directly rather than requiring
# `python -m reports.difficulty_delta_report`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DBConnection import get_connection

DIFFICULTY_ORDINAL: dict[str, int] = {
    "EASY": 1,
    "MODERATE": 2,
    "DIFFICULT": 3,
    "EXPERT": 4,
}
ORDINAL_LABEL = {v: k.title() for k, v in DIFFICULTY_ORDINAL.items()}

QUERY = """
    SELECT
        h.id          AS hike_id,
        h.name        AS hike_name,
        h.difficulty  AS predicted_difficulty,
        hc.difficulty_felt,
        hc.rating
    FROM hike_completions hc
    JOIN trip_stops ts ON ts.trip_id = hc.trip_id
    JOIN hikes h        ON h.id::text = ts.trail_data ->> 'hike_id'
    WHERE hc.went = true
      AND hc.difficulty_felt IS NOT NULL
"""


def fetch_rows() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(QUERY)
            return [dict(r) for r in cur.fetchall()]


def build_report(rows: list[dict], min_reviews: int) -> list[dict]:
    """
    Groups by hike (not by hike+predicted-difficulty — a hike's predicted
    difficulty is a fixed DB value at report-run time, not something that
    varies per review) and computes the average felt-vs-predicted delta.

    delta > 0 -> trail felt harder than predicted, on average.
    delta < 0 -> trail felt easier than predicted, on average.
    """
    by_hike: dict[tuple, list[str]] = defaultdict(list)
    for row in rows:
        key = (row["hike_id"], row["hike_name"], row["predicted_difficulty"])
        by_hike[key].append(row["difficulty_felt"])

    report = []
    for (hike_id, name, predicted), felt_list in by_hike.items():
        predicted_ord = DIFFICULTY_ORDINAL.get((predicted or "").upper())
        felt_ords = [DIFFICULTY_ORDINAL[f.upper()] for f in felt_list if f and f.upper() in DIFFICULTY_ORDINAL]
        if predicted_ord is None or len(felt_ords) < min_reviews:
            continue

        avg_felt = sum(felt_ords) / len(felt_ords)
        report.append({
            "hike_id":           str(hike_id),
            "name":              name,
            "predicted":         predicted,
            "predicted_ordinal": predicted_ord,
            "n_reviews":         len(felt_ords),
            "avg_felt_ordinal":  round(avg_felt, 2),
            "delta":             round(avg_felt - predicted_ord, 2),
        })

    report.sort(key=lambda r: abs(r["delta"]), reverse=True)
    return report


def _ordinal_to_label(ordinal: float) -> str:
    rounded = round(ordinal)
    return ORDINAL_LABEL.get(rounded, str(ordinal))


def render_markdown(report: list[dict], top: int, total_reviews: int) -> str:
    lines = [
        f"# Difficulty delta report — {datetime.now(timezone.utc).isoformat()}",
        "",
        f"{total_reviews} rated review(s) across {len(report)} hike(s) with enough data.",
        "",
        "Positive delta = felt harder than predicted. Negative = felt easier.",
        "",
        "| Hike | Predicted | Avg. felt | Delta | # Reviews |",
        "|---|---|---|---|---|",
    ]
    for r in report[:top]:
        lines.append(
            f"| {r['name']} | {r['predicted'].title()} | "
            f"{_ordinal_to_label(r['avg_felt_ordinal'])} ({r['avg_felt_ordinal']}) | "
            f"{'+' if r['delta'] >= 0 else ''}{r['delta']} | {r['n_reviews']} |"
        )
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-reviews", type=int, default=1,
                    help="Skip hikes with fewer than this many rated reviews (default: 1).")
    ap.add_argument("--top", type=int, default=20,
                    help="How many hikes to show, sorted by |delta| descending (default: 20).")
    ap.add_argument("--out", default="reports/difficulty_delta_report.md",
                    help="Where to write the markdown report.")
    args = ap.parse_args()

    rows = fetch_rows()
    if not rows:
        print("No rated reviews found yet — nothing to report.")
        return

    report = build_report(rows, min_reviews=args.min_reviews)
    if not report:
        print(f"No hikes with >= {args.min_reviews} rated review(s) — nothing to report.")
        return

    markdown = render_markdown(report, top=args.top, total_reviews=len(rows))
    print(markdown)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"\nReport saved to {args.out}")


if __name__ == "__main__":
    main()

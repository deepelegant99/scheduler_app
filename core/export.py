
from __future__ import annotations
import pandas as pd

def build_output_rows(assignments: list) -> pd.DataFrame:
    rows = []
    for s, best in assignments:
        excluded = [d for d in s["no_school_list"] if s["q_start"] <= d <= s["q_end"] and d.weekday()=={"Mon":0,"Tue":1,"Wed":2,"Thu":3,"Fri":4}[best["weekday"]]]
        start_date = best["sessions"][0]
        end_date = best["sessions"][-1]
        rows.append({
            "school_name": s["name"],
            "school_url": s["url"],
            "bell_schedule_page_url": s["bell_url"],
            "school_calendar_page_url": s["cal_url"],
            "recommended_day_of_week": best["weekday"],
            "recommended_start_time_local": best["start_time"],
            "recommended_end_time_local": best["end_time"],
            "recommended_start_date": start_date.isoformat(),
            "recommended_end_date": end_date.isoformat(),
            "recommended_total_sessions": best["count"],
            "excluded_dates": ";".join([d.isoformat() for d in excluded]),
            "early_release_day": s["early_release"],
            "typical_release_time_mon": s["dismissal_map"].get("Mon",""),
            "typical_release_time_tue": s["dismissal_map"].get("Tue",""),
            "typical_release_time_wed": s["dismissal_map"].get("Wed",""),
            "typical_release_time_thu": s["dismissal_map"].get("Thu",""),
            "typical_release_time_fri": s["dismissal_map"].get("Fri",""),
            "term_window_start": s["q_start"].isoformat(),
            "term_window_end": s["q_end"].isoformat(),
            "no_school_dates": ";".join([d.isoformat() for d in s["no_school_list"]]),
            "explanation": f"Balanced assignment; {best['count']} sessions within term window.",
        })
    return pd.DataFrame(rows)

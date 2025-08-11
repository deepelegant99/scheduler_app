
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, time as dtime
import time

from core.crawl import get, extract_anchors, shortlist, pick_links_llm, fetch_page_text
from core.parse_bell import parse_bell_text
from core.parse_calendar import parse_calendar_text
from core.schedule import weekly_sessions_between, clamp_times
from core.balance import assign_balanced
from core.utils import clean_text

st.set_page_config(page_title="Facilitron-ready Scheduler", layout="wide")
st.title("Facilitron-ready Scheduler (Low-impact Crawl)")

with st.sidebar:
    st.header("Global Preferences")
    earliest = st.time_input("Earliest start (local)", value=dtime(15,0))
    latest = st.time_input("Latest end (local)", value=dtime(17,30))
    duration = st.number_input("Session duration (minutes)", min_value=45, max_value=120, value=60, step=5)
    buffer_min = st.number_input("Buffer after dismissal (minutes)", min_value=0, max_value=60, value=15, step=5)
    target_sessions = st.number_input("Preferred number of sessions", min_value=6, max_value=16, value=10)
    min_sessions = st.number_input("Minimum acceptable sessions", min_value=6, max_value=16, value=8)

    st.markdown("---")
    st.header("Quarter Window (fallback)")
    quarter_start = st.date_input("Quarter start", value=date(date.today().year, 9, 9))
    quarter_end = st.date_input("Quarter end", value=date(date.today().year, 12, 13))
    st.caption("Used if calendar parsing is unclear.")

    st.markdown("---")
    st.header("Even Spread (neutral)")
    cap_mon = st.number_input("Soft cap Mon", 0, 50, 3)
    cap_tue = st.number_input("Soft cap Tue", 0, 50, 3)
    cap_wed = st.number_input("Soft cap Wed", 0, 50, 3)
    cap_thu = st.number_input("Soft cap Thu", 0, 50, 3)
    cap_fri = st.number_input("Soft cap Fri", 0, 50, 3)
    alpha = st.number_input("Penalty α", 0.0, 10.0, 1.5, 0.1)
    soft_caps = {"Mon":cap_mon, "Tue":cap_tue, "Wed":cap_wed, "Thu":cap_thu, "Fri":cap_fri}

    st.markdown("---")
    st.header("Low-impact Crawl")
    enable_llm_picker = st.checkbox("Use OpenAI to pick links (low-impact)", value=False)
    max_anchors = st.number_input("Max anchors to send to AI", 10, 60, 30, 5)
    delay_between_schools = st.number_input("Delay between schools (seconds)", 0, 10, 2)

st.subheader("1) Upload Notion CSV (must include: school_name, school_url)")
csv_file = st.file_uploader("Upload CSV", type=["csv"])

if csv_file:
    df = pd.read_csv(csv_file)
    if "school_name" not in df.columns or "school_url" not in df.columns:
        st.error("CSV must contain 'school_name' and 'school_url' columns.")
    else:
        st.success(f"Loaded {len(df)} schools.")
        st.write(df.head())

        if st.button("2) Process"):
            schools = []
            for i, row in df.iterrows():
                name = str(row["school_name"])
                url = str(row["school_url"])
                st.write(f"### {name}")
                st.write(url)

                # 1) GET homepage (1 request)
                r = get(url)
                if not r:
                    st.warning(f"[{name}] Could not load homepage.")
                    continue
                anchors = extract_anchors(r.text, url)
                cand = shortlist(anchors, url, per_cat=15)[:int(max_anchors)]

                # 2) LLM or heuristic pick (0 requests)
                if enable_llm_picker:
                    choice = pick_links_llm(cand, url)
                else:
                    choice = {"notes":"heuristic", **{k:v for k,v in pick_links_llm(cand, url).items()}}

                bell_url = choice.get("bell_schedule_url","") or ""
                cal_url  = choice.get("calendar_url","") or ""

                # 3) Fetch chosen pages (2 requests)
                bell_text = fetch_page_text(bell_url) if bell_url and bell_url!="NOT_FOUND" else ""
                cal_text  = fetch_page_text(cal_url)  if cal_url and cal_url!="NOT_FOUND"  else ""

                # Parse bell & calendar
                dismissal_map, early_release = parse_bell_text(bell_text)
                default_dismissal = "15:05"
                for wd in ["Mon","Tue","Thu","Fri"]:
                    dismissal_map.setdefault(wd, default_dismissal)
                dismissal_map.setdefault("Wed", "13:30" if early_release=="Wed" else default_dismissal)

                no_school_list = parse_calendar_text(cal_text)
                avoid_dates = set(no_school_list)

                # Build candidates per weekday
                candidates = []
                for wd in ["Mon","Tue","Wed","Thu","Fri"]:
                    if early_release == wd:
                        continue
                    # start = dismissal + buffer
                    try:
                        hh,mm = map(int, dismissal_map.get(wd,"15:00").split(":"))
                        start_time = (datetime.combine(date.today(), datetime.strptime(f"{hh}:{mm}", "%H:%M").time()) + timedelta(minutes=int(buffer_min))).time()
                    except Exception:
                        start_time = (datetime.combine(date.today(), datetime.strptime("15:00","%H:%M").time()) + timedelta(minutes=int(buffer_min))).time()

                    start_time, end_time = clamp_times(start_time, earliest, latest, int(duration))
                    if not start_time:
                        continue

                    sessions = weekly_sessions_between(quarter_start, quarter_end, wd, avoid_dates, int(target_sessions), int(min_sessions))
                    if not sessions:
                        continue

                    candidates.append({
                        "weekday": wd,
                        "start_time": start_time.strftime("%H:%M"),
                        "end_time": end_time.strftime("%H:%M"),
                        "sessions": sessions,
                        "count": len(sessions)
                    })

                if not candidates:
                    st.warning(f"[{name}] No viable slot found.")
                    continue

                schools.append({
                    "name": name,
                    "url": url,
                    "bell_url": bell_url,
                    "cal_url": cal_url,
                    "dismissal_map": dismissal_map,
                    "early_release": early_release or "",
                    "q_start": quarter_start, "q_end": quarter_end,
                    "no_school_list": no_school_list,
                    "candidates": candidates
                })

                time.sleep(int(delay_between_schools))

            if not schools:
                st.info("No results produced. Try adjusting settings or quarter window.")
            else:
                assignments = assign_balanced(schools, soft_caps, float(alpha))

                # Build output
                from core.export import build_output_rows
                out_df = build_output_rows(assignments)
                st.subheader("Facilitron-ready results (balanced)")
                st.dataframe(out_df, use_container_width=True)
                csv_bytes = out_df.to_csv(index=False).encode("utf-8")
                st.download_button("Download results CSV", data=csv_bytes, file_name="facilitron_ready_schedule.csv", mime="text/csv")

                with st.expander("Debug details"):
                    for s, best in assignments:
                        st.markdown(f"**{s['name']}** → {best['weekday']} {best['start_time']}-{best['end_time']} ({best['count']} sessions)")
                        st.write("Bell URL:", s["bell_url"] or "(not found)")
                        st.write("Calendar URL:", s["cal_url"] or "(not found)")
                        st.write("Dismissal map:", s["dismissal_map"])
                        st.write("Early release:", s["early_release"] or "n/a")
                        st.write("No-school (parsed):", [d.isoformat() for d in s["no_school_list"]])

else:
    st.info("Upload your Notion-exported CSV to begin (must have columns: school_name, school_url).")

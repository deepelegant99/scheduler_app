
from __future__ import annotations
from datetime import date, datetime, timedelta, time as dtime
from dateutil.rrule import rrule, WEEKLY

WD = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
WD_IDX = {d:i for i,d in enumerate(WD)}

def weekly_sessions_between(q_start: date, q_end: date, weekday: str, avoid_dates: set, target_sessions: int, min_sessions: int):
    start = q_start
    while start.weekday() != WD_IDX[weekday]:
        start += timedelta(days=1)
    sessions = []
    for dt in rrule(WEEKLY, dtstart=start, until=q_end):
        d = dt.date()
        if d in avoid_dates:
            continue
        sessions.append(d)
        if len(sessions) >= target_sessions:
            break
    return sessions if len(sessions) >= min_sessions else []

def clamp_times(start_time: dtime, earliest: dtime, latest: dtime, duration_min: int):
    if start_time < earliest:
        start_time = earliest
    end_time = (datetime.combine(date.today(), start_time) + timedelta(minutes=duration_min)).time()
    if end_time > latest:
        return None, None
    return start_time, end_time

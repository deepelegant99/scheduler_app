
from __future__ import annotations
from typing import Dict, List, Tuple

WD = ["Mon","Tue","Wed","Thu","Fri"]

def assign_balanced(schools: List[dict], soft_caps: Dict[str,int], alpha: float) -> List[Tuple[dict, dict]]:
    load = {d:0 for d in WD}
    out = []
    for s in sorted(schools, key=lambda x: len(x["candidates"])):
        best = None; best_score = -1e9; best_tie = ""
        for c in s["candidates"]:
            d = c["weekday"]
            cap = soft_caps.get(d, 0)
            over = max(0, load[d] - cap)
            score = c["count"] - float(alpha) * over
            tie = c["start_time"]
            if (score > best_score) or (score == best_score and tie > best_tie):
                best, best_score, best_tie = c, score, tie
        out.append((s, best))
        load[best["weekday"]] += 1
    return out

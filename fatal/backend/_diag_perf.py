import sys, time
sys.path.insert(0, '.')
import db
from matcher import match

t0 = time.time()
profiles = db.fetch_profiles()
t1 = time.time()
print(f"fetch_profiles: {len(profiles)} profiles in {t1-t0:.2f}s")

target = profiles[0]
t2 = time.time()
results = []
for p in profiles:
    if p.user_uid == target.user_uid:
        continue
    if target.matching_phase != p.matching_phase:
        continue
    r = match(target, p)
    if not r.hard_block:
        results.append(r)
t3 = time.time()
print(f"matching: {len(results)} candidates in {t3-t2:.2f}s")

above_70 = [r for r in results if r.score >= 70.0]
above_60 = [r for r in results if r.score >= 60.0]
above_50 = [r for r in results if r.score >= 50.0]
print(f"Scores: >=70: {len(above_70)}, >=60: {len(above_60)}, >=50: {len(above_50)}")
if results:
    scores = sorted([r.score for r in results], reverse=True)
    print(f"Top 10 scores: {[round(s,1) for s in scores[:10]]}")
    print(f"Bottom 10 scores: {[round(s,1) for s in scores[-10:]]}")

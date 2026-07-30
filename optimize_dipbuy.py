#!/usr/bin/env python3
"""Dip-Buy 深度优化 — 基于历史回撤×恢复时间×恢复概率
用法: python3 optimize_dipbuy.py
"""
import json, math, statistics, urllib.request, time, re
from pathlib import Path
from datetime import datetime

HOLDINGS = Path(__file__).parent / "holdings.json"

def fetch(code):
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    req = urllib.request.Request(url, headers={"Referer": "https://fund.eastmoney.com/", "User-Agent": "Mozilla/5.0"})
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                text = r.read().decode("utf-8")
            m = re.search(r'Data_netWorthTrend\s*=\s*(\[.+?\]);', text, re.DOTALL)
            if not m: return []
            raw = json.loads(m.group(1))
            out = []
            for p in raw:
                ts = p.get("x") or p.get("timestamp")
                if not ts or ts == 0: continue
                out.append({"date": datetime.fromtimestamp(ts/1000).strftime("%Y-%m-%d"),
                            "nav": float(p.get("y",0))})
            return out
        except: time.sleep(1)
    return []

def analyze(code):
    s = fetch(code)
    if not s or len(s) < 100: return None
    s.reverse()
    navs = [x["nav"] for x in s]
    n = len(navs); years = n/250
    
    dr = [(navs[i]-navs[i-1])/navs[i-1] for i in range(1,n)]
    vol = statistics.stdev(dr)*math.sqrt(250) if len(dr)>20 else 0
    
    peak = navs[0]; events = []
    active = False; ds = 0; dt = 0; dm = 0
    for i, nav in enumerate(navs):
        if nav > peak: peak = nav
        dd = (peak-nav)/peak
        if dd > 0.01 and not active:
            active = True; ds = i; dm = dd; dt = i
        elif dd > dm and active:
            dm = dd; dt = i
        elif dd < 0.005 and active:
            events.append({"dd": dm, "trough": dt, "rec": i-dt, "ok": True})
            active = False
    if active: events.append({"dd": dm, "trough": dt, "rec": n-1-dt, "ok": False})
    
    TH = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20]
    out = []
    for th in TH:
        m = [e for e in events if e["dd"] >= th]
        if not m or len(m) < 2:
            out.append({"th": th, "cnt": len(m), "freq": 0, "med": 999, "r1m": 0, "r3m": 0})
            continue
        r = [e["rec"] for e in m if e["ok"]]
        out.append({
            "th": th, "cnt": len(m),
            "freq": round(len(m)/max(years,0.5), 1),
            "med": round(statistics.median(r) if r else 999, 0),
            "r1m": round(sum(1 for e in m if e["rec"]<=22)/len(m), 2),
            "r3m": round(sum(1 for e in m if e["rec"]<=66)/len(m), 2),
        })
    return {"vol": vol, "n": n, "ev": len(events), "th": out}

def rec(t):
    if t["cnt"] < 2: return "—"
    if t["freq"] > 30: return "—"
    if t["med"] <= 30 and t["r3m"] >= 0.5: return "✅ 1x加仓"
    if t["med"] <= 60 and t["r3m"] >= 0.3: return "✅ 0.5x加仓"
    if t["med"] <= 20 and t["r1m"] >= 0.3: return "⚠️ 快恢复(小补)"
    return "❌"

# ── 主流程 ──
cfg = json.loads(open(HOLDINGS, encoding="utf-8").read())
funds = [(f["name"], f["code"], f.get("dca_daily",0) or 0) for f in cfg["funds"] if (f.get("dca_daily",0) or 0) > 0]

print("Dip-Buy 深度优化")
print("=" * 90)

for name, code, dca in funds:
    if not code: continue
    print(f"\n  拉取 {name}...", end=" ")
    r = analyze(code)
    if not r: print("失败"); continue
    print(f"{r['n']}天 {r['vol']*100:.0f}%vol")
    
    print(f"  {'回撤≥':>6} {'次数':>4} {'频率/年':>8} {'中位恢复':>8} {'1月恢复':>8} {'3月恢复':>8}  建议")
    for t in r["th"]:
        if t["cnt"] < 2: continue
        print(f"  {t['th']*100:>5.0f}% {t['cnt']:>4} {t['freq']:>7.1f} {t['med']:>7.0f}天 {t['r1m']:>7.0%} {t['r3m']:>7.0%}   {rec(t)}")
    
    # 找最优
    best = None
    for t in r["th"]:
        if t["cnt"] >= 2 and t["freq"] <= 24 and t["freq"] >= 0.5 and t["med"] <= 45:
            if not best or t["r3m"] > r["th"][best]["r3m"]:
                best = r["th"].index(t)
    if best is not None:
        bt = r["th"][best]
        print(f"  ⭐ 最优: -{bt['th']*100:.0f}%触发, 频率{bt['freq']:.1f}次/年, 中位{bt['med']:.0f}天恢复, {bt['r3m']*100:.0f}%概率3月内恢复")

print("\n✅ 完成")
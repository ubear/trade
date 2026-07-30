#!/usr/bin/env python3
"""投资组合仪表盘 — 数据采集层
输出 dashboard_data.json, 供前端消费
用法: python3 portfolio_dashboard.py
"""
import json, re, time, urllib.request, datetime, os
from pathlib import Path

BARK_KEY = os.environ.get("BARK_KEY", "")
BARK_URL = f"https://api.day.app/{BARK_KEY}/" if BARK_KEY else None
HOLDINGS = Path(__file__).parent / "holdings.json"
OUTPUT   = Path(__file__).parent / "dashboard_data.json"

def fetch_nav_series(code: str, retries: int = 2):
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    req = urllib.request.Request(url, headers={"Referer": "https://fund.eastmoney.com/", "User-Agent": "Mozilla/5.0"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=12) as r:
                text = r.read().decode("utf-8")
            m = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', text, re.DOTALL)
            if not m: raise ValueError("no data")
            raw = json.loads(m.group(1))
            out = []
            for item in raw:
                ts = item.get("x")
                if isinstance(ts, (int, float)) and ts > 1e10:
                    dt = datetime.datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                else:
                    dt = str(ts)
                nav = item.get("y", 0)
                if nav > 0:
                    out.append({"date": dt, "nav": nav, "return": item.get("equityReturn", 0)})
            return out
        except Exception:
            if attempt < retries: time.sleep(1.5)
            else: raise

def compute():
    cfg = json.loads(HOLDINGS.read_text(encoding="utf-8"))
    funds_output = []
    total_value = 0.0
    total_cost = 0.0
    dca_total = sum(f.get("dca_daily", 0) for f in cfg["funds"])

    for f in cfg["funds"]:
        code = f.get("code", "")
        if not code: continue
        name = f["name"]
        dca = f.get("dca_daily", 0)
        tp_list = f.get("tp") or []
        tp_mode = f.get("tp_mode", "graduated")
        bucket = f.get("bucket", "")

        try:
            series = fetch_nav_series(code)
        except Exception as e:
            funds_output.append({"name": name, "code": code, "error": str(e)})
            continue
        if not series:
            funds_output.append({"name": name, "code": code, "error": "no data"})
            continue

        latest_nav = series[0]["nav"]
        latest_date = series[0]["date"]
        prev_nav = series[1]["nav"] if len(series) > 1 else latest_nav
        day_change = (latest_nav - prev_nav) / prev_nav if prev_nav else 0
        week_idx = min(5, len(series) - 1)
        week_prev = series[week_idx]["nav"]
        week_change = (latest_nav - week_prev) / week_prev if week_prev else 0

        # -- 估值 --
        shares = f.get("shares")
        avg_cost = f.get("avg_cost")
        fb_val = f.get("fallback_value")
        fb_pnl = f.get("fallback_pnl")
        pnl_pct = None
        if shares and avg_cost and avg_cost > 0:
            cost = shares * avg_cost
            value = shares * latest_nav
            pnl_pct = (latest_nav - avg_cost) / avg_cost
        elif fb_val and fb_pnl is not None:
            value = float(fb_val)
            cost = value / (1 + float(fb_pnl)) if float(fb_pnl) != -1 else 0
            pnl_pct = float(fb_pnl)
        else:
            value = 0.0; cost = 0.0
        total_value += value; total_cost += cost

        # -- 止盈距离 --
        tp_next = None; tp_distance = None
        tp_stage = f.get("tp_stage", 0)
        if tp_list and tp_mode == "graduated" and tp_stage < len(tp_list):
            tp_next = tp_list[tp_stage]
            if pnl_pct is not None: tp_distance = max(0, tp_next - pnl_pct)
        elif tp_list and tp_mode == "full":
            tp_next = tp_list[0]
            if pnl_pct is not None: tp_distance = max(0, tp_next - pnl_pct)

        # -- 波动率 --
        navs = [s["nav"] for s in series[:min(250, len(series))]]
        vol = 0.0
        if len(navs) >= 20:
            dr = [(navs[i] - navs[i+1]) / navs[i+1] for i in range(len(navs) - 1)]
            vol = (sum(r*r for r in dr) / len(dr)) ** 0.5 * (250 ** 0.5)

        funds_output.append({
            "name": name, "code": code, "bucket": bucket,
            "nav": round(latest_nav, 4), "nav_date": latest_date,
            "day_change": round(day_change, 6), "week_change": round(week_change, 6),
            "volatility": round(vol, 4),
            "value": round(value, 0), "cost": round(cost, 0),
            "pnl_pct": round(pnl_pct, 6) if pnl_pct is not None else None,
            "dca_daily": dca,
            "tp": tp_list, "tp_mode": tp_mode,
            "tp_next": tp_next,
            "tp_distance": round(tp_distance, 6) if tp_distance is not None else None,
            "tp_triggered": tp_stage,
        })

    total_pnl = (total_value - total_cost) / total_cost if total_cost > 0 else 0
    result = {
        "updated": datetime.date.today().isoformat(),
        "total_value": round(total_value, 0),
        "total_cost": round(total_cost, 0),
        "total_pnl_pct": round(total_pnl, 6),
        "dca_daily_total": dca_total,
        "funds": funds_output,
        "alerts": [],
    }
    for fd in funds_output:
        td = fd.get("tp_distance")
        if td is not None and td <= 0.05:
            result["alerts"].append({
                "type": "tp_close", "fund": fd["name"],
                "message": f"{fd['name']} 距止盈{td*100:.1f}% 当前{(fd.get('pnl_pct') or 0)*100:+.1f}% 下档+{fd['tp_next']*100:.0f}%"
            })
    return result

if __name__ == "__main__":
    data = compute()
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    active = [f for f in data["funds"] if f.get("dca_daily", 0) > 0]
    print(f"✓ dashboard_data.json ({len(data['funds'])}只, {len(active)}只定投, {len(data['alerts'])}条告警)")
    print(f"  市值 ¥{data['total_value']:,.0f}  收益 {data['total_pnl_pct']*100:+.2f}%")

    # Bark推送
    if BARK_URL:
        import urllib.parse as ulp
        pnl_str = f"{data['total_pnl_pct']*100:+.2f}%"
        summary = f"市值¥{data['total_value']:,.0f} 收益{pnl_str}"
        if data["alerts"]:
            alert_msgs = "\n".join(a["message"] for a in data["alerts"])
            body = f"{summary}\n\n⚠️ 止盈告警:\n{alert_msgs}"
            title = "📊 每日汇总·有告警"
        else:
            body = summary
            title = "📊 每日汇总"
        try:
            params = "sound=bell&isArchive=1"
            if data["alerts"]:
                params += "&level=critical&volume=5"
            url = f"{BARK_URL}{ulp.quote(title, safe='')}/{ulp.quote(body, safe='')}?{params}"
            urllib.request.urlopen(urllib.request.Request(url), timeout=5)
            print(f"  → Bark推送成功 ({'critical' if data['alerts'] else 'normal'})")
        except Exception as e:
            print(f"  → Bark推送失败: {e}")

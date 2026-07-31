#!/usr/bin/env python3
"""投资组合仪表盘 — 数据采集层
输出 dashboard_data.json, 供前端消费
用法: python3 portfolio_dashboard.py
"""
import json, re, time, urllib.request, datetime, os
from pathlib import Path

BARK_KEY = os.environ.get("BARK_KEY", "")
BARK_URL = f"https://api.day.app/{BARK_KEY}/" if BARK_KEY else None
FEISHU_URL = os.environ.get("FEISHU_URL", "")
TZ = os.environ.get("TZ", "Asia/Shanghai")
HOLDINGS = Path(__file__).parent / "holdings.json"
OUTPUT   = Path(__file__).parent / "data.json"

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
            "name": name, "code": code, "bucket": bucket, "cat": f.get("cat", ""),
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

    # 推送 (Bark + PushDeer)
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
    
    def try_push(label, url_func):
        try:
            url_func()
            print(f"  → {label}推送成功")
        except Exception as e:
            print(f"  → {label}推送失败: {e}")
    
    if BARK_URL:
        params = "sound=bell&isArchive=1"
        if data["alerts"]: params += "&level=critical&volume=5"
        try_push("Bark", lambda: urllib.request.urlopen(urllib.request.Request(
            f"{BARK_URL}{ulp.quote(title, safe='')}/{ulp.quote(body, safe='')}?{params}"), timeout=5))
    if FEISHU_URL:
        now = datetime.datetime.now()
        date_str = now.strftime("%m-%d 周%w").replace("周0","周日").replace("周1","周一").replace("周2","周二").replace("周3","周三").replace("周4","周四").replace("周5","周五").replace("周6","周六")
        short = {
            "中证A500联接A": "中证A500", "A股红利低波ETF联接A": "红利低波",
            "摩根标普港股通低波红利ETF联接A": "港股红利", "恒生科技联接A": "恒生科技",
            "创新药精选50ETF联接A": "创新药", "科创创业50联接A": "科创50",
            "建信纳斯达克100A": "建信纳指", "博时标普500ETF联接A": "博时标普",
            "华夏纳斯达克100联接A": "华夏纳指", "广发全球医疗A": "广发医疗",
            "易方达蓝筹精选(张坤)": "易方达蓝筹", "中欧红利优享A": "中欧红利",
            "博时恒生医疗联接A": "恒生医疗", "易方达全球成长精选A": "全球成长",
            "富国天惠精选成长A": "富国天惠", "南方纳斯达克100指数A": "南方纳指",
            "天弘科创创业50ETF联接A(存量)": "天弘科创(存)", "华泰红利低波ETF联接A(存量)": "华泰红利(存)",
        }
        def fmt_daily(pct):
            if pct > 0: return f"<font color='red'>+{pct:.2f}%</font>"
            if pct < 0: return f"<font color='green'>{pct:.2f}%</font>"
            return f"{pct:.2f}%"
        def fmt_total(pnl):
            if pnl is None: return "持平"
            if pnl > 0: return f"<font color='red'>+{pnl*100:.2f}%</font>"
            if pnl < 0: return f"<font color='green'>{pnl*100:.2f}%</font>"
            return "持平"
        sections = {"defense": [], "attack": [], "watch": []}
        section_icons = {"defense": "🛡️ **防御仓**", "attack": "⚔️ **进攻仓**", "watch": "👀 **观察仓**"}
        for f in data["funds"]:
            nm = short.get(f["name"], f["name"])
            d = f.get("day_change") or 0
            pnl = f.get("pnl_pct")
            cat = f.get("cat", "watch")
            line = f"- **{nm:<8s}**　　日{fmt_daily(d)}　　累计{fmt_total(pnl)}"
            sections[cat].append(line)
        total_pnl = data['total_pnl_pct'] * 100
        tp_color = "red" if total_pnl > 0 else "green" if total_pnl < 0 else "grey"
        lines = [f"**总市值** ¥{data['total_value']:,.0f}　｜　**收益** <font color='{tp_color}'>{total_pnl:+.2f}%</font>", "", "---", ""]
        for cat in ["defense", "attack", "watch"]:
            if sections[cat]:
                lines.append(section_icons[cat])
                lines.extend(sections[cat])
                lines.append("")
        # 提醒板块
        if data["alerts"]:
            lines.append("---")
            lines.append("")
            lines.append("⚠️ **提醒**")
            lines.append("")
            for a in data["alerts"]:
                lines.append(f"- {a['message']}")
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": f"📊 投资日报 | {date_str} 特别提醒"}, "template": "blue"},
                "elements": [{"tag": "markdown", "content": "\n".join(lines)}]
            }
        }
        try_push("飞书", lambda: urllib.request.urlopen(urllib.request.Request(
            FEISHU_URL, data=json.dumps(card).encode(), headers={"Content-Type": "application/json"}), timeout=10))

#!/usr/bin/env python3
"""周度基金组合评估脚本
数据源: 天天基金 pingzhongdata (需Referer头)
用法: python3 weekly_review.py [--json]
每周运行一次, 输出: 净值/周涨跌/持仓收益率/距止盈阈值距离/行动建议
"""
import json, re, sys, time, urllib.request, datetime
from pathlib import Path

HOLDINGS = Path(__file__).parent / "holdings.json"

def fetch_nav_series(code: str, retries: int = 2):
    """返回 [(date_str, nav), ...] 全部历史"""
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    req = urllib.request.Request(url, headers={"Referer": "https://fund.eastmoney.com/", "User-Agent": "Mozilla/5.0"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                raw = r.read().decode("utf-8", "ignore")
            i = raw.find("Data_netWorthTrend")
            if i < 0:
                raise ValueError("no Data_netWorthTrend")
            i = raw.find("[", i)
            arr, _ = json.JSONDecoder().raw_decode(raw[i:])
            out = []
            for p in arr:
                d = datetime.datetime.fromtimestamp(p["x"] / 1000).strftime("%Y-%m-%d")
                out.append((d, p["y"]))
            return out
        except Exception as e:
            if attempt == retries:
                raise
            time.sleep(1.5)

def pct(x):
    return f"{x*100:+.2f}%"

def main():
    as_json = "--json" in sys.argv
    cfg = json.loads(HOLDINGS.read_text(encoding="utf-8"))
    rows, actions, total_val, total_cost = [], [], 0.0, 0.0

    for f in cfg["funds"]:
        code = f.get("code") or ""
        if not code:
            rows.append({"name": f["name"], "status": "code未填,跳过"})
            continue
        try:
            series = fetch_nav_series(code)
        except Exception as e:
            rows.append({"name": f["name"], "status": f"抓取失败: {e}"})
            continue

        nav_d, nav = series[-1]
        # 周涨跌: 对比5个交易日前
        wk_idx = max(0, len(series) - 6)
        wk_d, wk_nav = series[wk_idx]
        wk_chg = nav / wk_nav - 1

        # 持仓收益率
        shares = f.get("shares")
        avg_cost = f.get("avg_cost")
        est = ""
        if shares and avg_cost:
            cost = shares * avg_cost
            value = shares * nav
        elif f.get("fallback_value"):
            # 用最近已知市值+收益率, 按最新净值反推份额(估算)
            fb_v, fb_p = f["fallback_value"], f.get("fallback_pnl", 0.0)
            cost = fb_v / (1 + fb_p)
            shares_est = fb_v / nav  # 近似: 假设配置时价值≈当前净值口径
            value = shares_est * nav
            est = "(估)"
        else:
            cost = value = 0.0

        pnl = (value / cost - 1) if cost > 0 else None
        if cost > 0:
            total_val += value; total_cost += cost

        # 止盈检查
        tp, stage = f.get("tp"), f.get("tp_stage", 0)
        tp_mode = f.get("tp_mode", "graduated")
        action = ""
        if tp == "breakeven":
            if pnl is not None and pnl >= 0:
                action = "🔴 已回本 → 按纪律全部清仓"
                actions.append(f"{f['name']}: 回本清仓")
            elif pnl is not None:
                action = f"距回本还差{pct(-pnl)}"
        elif isinstance(tp, list) and pnl is not None and stage < len(tp):
            th = tp[stage]
            if tp_mode == "full":
                if pnl >= th:
                    action = f"🔴 触发止盈线{pct(th)} → **全部卖出**"
                    actions.append(f"{f['name']}: 全部卖出(止盈{pct(th)})")
                else:
                    action = f"止盈线{pct(th)}全卖, 还差{pct(th - pnl)}"
            else:
                label = ["第一批(卖1/3)", "第二批(卖1/3)", "第三批(清仓)"][stage]
                if pnl >= th:
                    action = f"🔴 触发止盈{label} (阈值{pct(th)}) → 卖出当前持仓1/3"
                    actions.append(f"{f['name']}: 止盈{label}")
                else:
                    action = f"下一档{label} 阈值{pct(th)}, 还差{pct(th - pnl)}"

        rows.append({
            "name": f["name"], "code": code, "nav": nav, "nav_date": nav_d,
            "week": wk_chg, "pnl": pnl, "est": est, "action": action,
            "dca": f.get("dca_daily", 0), "bucket": f.get("bucket", "")
        })

    # 输出
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    print(f"===== 周度基金评估 ({datetime.date.today()}) =====")
    print(f"{'基金':<22}{'净值日':<12}{'周涨跌':>8}{'持仓收益':>10}  行动")
    print("-" * 100)
    for r in rows:
        if "status" in r:
            print(f"{r['name']:<22}{r['status']}")
            continue
        pnl_s = f"{pct(r['pnl'])}{r['est']}" if r["pnl"] is not None else "—"
        nm = r["name"][:20]
        print(f"{nm:<22}{r['nav_date']:<12}{pct(r['week']):>8}{pnl_s:>12}  {r['action']}")
    print("-" * 100)
    if total_cost > 0:
        print(f"存量合计: 市值≈¥{total_val:,.0f}  成本≈¥{total_cost:,.0f}  收益率{pct(total_val/total_cost-1)}")
    if actions:
        print("\n⚠️  本周需执行:")
        for a in actions:
            print(f"  · {a}")
    else:
        print("\n✅ 本周无需操作, 继续定投")
    dca_sum = sum(f.get("dca_daily", 0) for f in cfg["funds"])
    print(f"日定投合计: ¥{dca_sum} (应为¥920)")

if __name__ == "__main__":
    main()

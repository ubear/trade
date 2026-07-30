#!/usr/bin/env python3
"""策略优化引擎 — 基于历史数据校准止盈/补仓/再平衡参数
用法: python3 optimize_strategy.py
依赖: 同 portfolio_dashboard.py (无额外依赖)
"""
import json, math, statistics, urllib.request, time
from pathlib import Path

HOLDINGS = Path(__file__).parent / "holdings.json"
OUTPUT = Path(__file__).parent / "optimize_results.json"

def fetch_nav_series(code, retries=2):
    """拉取基金净值历史 (eastmoney)"""
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    req = urllib.request.Request(url, headers={
        "Referer": "https://fund.eastmoney.com/",
        "User-Agent": "Mozilla/5.0"
    })
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8")
            # 解析 Data_netWorthTrend
            import re
            m = re.search(r'Data_netWorthTrend\s*=\s*(\[.+?\]);', text, re.DOTALL)
            if not m:
                return []
            raw = json.loads(m.group(1))
            series = []
            for p in raw:
                ts = p.get("x") or p.get("timestamp")
                if not ts or ts == 0: continue
                nav = p.get("y")
                if nav is None: continue
                from datetime import datetime
                date = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                series.append({"date": date, "nav": float(nav)})
            return series
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                raise
    return []

def analyze_fund(code, name):
    """对单只基金做完整分析"""
    print(f"  拉取 {name} ({code})...")
    try:
        series = fetch_nav_series(code)
    except Exception as e:
        print(f"    ❌ 失败: {e}")
        return None
    
    if len(series) < 100:
        print(f"    ⚠️ 数据不足 ({len(series)}天)")
        return None
    
    series.reverse()  # 最早在前
    navs = [s["nav"] for s in series]
    n = len(navs)
    
    # ── 日收益率 ──
    dr = [(navs[i] - navs[i-1]) / navs[i-1] for i in range(1, n)]
    
    # ── 年化波动率 ──
    vol = statistics.stdev(dr) * math.sqrt(250) if len(dr) > 20 else 0
    
    # ── 最大回撤 ──
    peak = navs[0]; max_dd = 0; max_dd_end = 0
    dd_series = []
    for i, nav in enumerate(navs):
        if nav > peak: peak = nav
        dd = (peak - nav) / peak
        dd_series.append(dd)
        if dd > max_dd:
            max_dd = dd; max_dd_end = i
    
    # ── 回撤恢复时间 ──
    recovery_days = []
    in_dd = False; dd_start = 0
    for i, dd in enumerate(dd_series):
        if dd > 0.01 and not in_dd:
            in_dd = True; dd_start = i
        elif dd < 0.005 and in_dd:
            recovery_days.append(i - dd_start)
            in_dd = False
    avg_recovery = statistics.mean(recovery_days) if recovery_days else 0
    
    # ── 滚动2年最大涨幅 (用于止盈阈值) ──
    window = min(500, n)
    rolling_peaks = []
    for i in range(0, n - window, 5):
        max_nav = max(navs[i:i+window])
        gain = max_nav / navs[i] - 1
        if gain > 0: rolling_peaks.append(gain)
    
    rolling_peaks.sort()
    def q(arr, p):
        idx = min(int(len(arr) * p), len(arr) - 1)
        return arr[idx] if arr else 0
    
    tp_p25 = q(rolling_peaks, 0.25)  # P25 → 第一档
    tp_p50 = q(rolling_peaks, 0.50)  # P50 → 第二档
    tp_p75 = q(rolling_peaks, 0.75)  # P75 → 第三档
    
    # ── 回撤分布 (用于补仓阈值) ──
    # 取所有回撤事件的最大回撤值
    dd_events = []
    in_dd = False; dd_max = 0
    for dd in dd_series:
        if dd > 0.01:
            if not in_dd: in_dd = True; dd_max = dd
            elif dd > dd_max: dd_max = dd
        elif in_dd:
            dd_events.append(dd_max)
            in_dd = False
    if in_dd: dd_events.append(dd_max)
    
    dd_events.sort()
    dip_p50 = q(dd_events, 0.50)  # 中位回撤
    dip_p25 = q(dd_events, 0.25)  # 轻度回撤
    dip_p10 = q(dd_events, 0.10)  # 深度回撤
    
    # ── 建议 ──
    # 止盈: P25/P50/P75, 下限5%
    tp1 = max(round(tp_p25 * 100 / 5) * 5, 10)
    tp2 = max(round(tp_p50 * 100 / 5) * 5, tp1 + 5)
    tp3 = max(round(tp_p75 * 100 / 5) * 5, tp2 + 10)
    
    # 补仓: 按回撤分三档
    dip1 = max(round(dip_p25 * 100, 1), 1.0)  # 轻跌→替代
    dip2 = max(round(dip_p50 * 100, 1), dip1 + 0.5)  # 中跌→加倍
    dip3 = max(round(dip_p10 * 100, 1), dip2 + 1.0)  # 深跌→三倍
    
    return {
        "name": name, "code": code,
        "days": n, "vol": round(vol, 4),
        "max_dd": round(max_dd, 4),
        "avg_recovery_days": round(avg_recovery, 0),
        "tp_p25": round(tp_p25, 4), "tp_p50": round(tp_p50, 4), "tp_p75": round(tp_p75, 4),
        "tp_recommend": [tp1, tp2, tp3],
        "dip_p10": round(dip_p10, 4), "dip_p25": round(dip_p25, 4), "dip_p50": round(dip_p50, 4),
        "dip_recommend": [dip1, dip2, dip3],
        "rolling_peaks_count": len(rolling_peaks),
        "dd_events_count": len(dd_events),
    }

def cfg_fund_tp(cfg, name):
    for f in cfg["funds"]:
        if f["name"] == name:
            tp = f.get("tp")
            if not tp: return "(永不止盈)"
            return "+" + "/+".join(f"{int(t*100)}%" for t in tp)
    return "—"

# ===== 主流程 =====
print("策略优化引擎启动")
print("=" * 80)

cfg = json.loads(open(HOLDINGS, encoding="utf-8").read())
funds = [f for f in cfg["funds"] if f.get("dca_daily", 0) > 0]

results = {}
for f in funds:
    code = f.get("code", "")
    if not code: continue
    name = f["name"]
    r = analyze_fund(code, name)
    if r:
        results[name] = r

# ===== 输出 =====
print("\n" + "=" * 80)
print("一、止盈阈值优化 (基于历史2年滚动最大涨幅)")
print("-" * 80)
print(f"{'基金':<22} {'历史':>6} {'vol':>6} {'maxDD':>6} {'P25':>6} {'P50':>6} {'P75':>6} │ {'建议':>18} │ {'当前阈值':>18}")
print("-" * 80)
for name, r in results.items():
    cur = cfg_fund_tp(cfg, name)
    print(f"{name:<22} {r['days']:>5}d {r['vol']*100:>5.1f}% {r['max_dd']*100:>5.1f}% "
          f"{r['tp_p25']*100:>5.0f}% {r['tp_p50']*100:>5.0f}% {r['tp_p75']*100:>5.0f}% │ "
          f"+{r['tp_recommend'][0]}/+{r['tp_recommend'][1]}/+{r['tp_recommend'][2]}% │ "
          f"{cur}")

print("\n二、补仓梯度优化 (基于历史回撤分布)")
print("-" * 80)
print(f"{'基金':<22} {'中位回撤':>8} {'轻回撤':>8} {'重回撤':>8} │ {'建议梯度':>20} │ {'恢复天数':>8}")
print("-" * 80)
for name, r in results.items():
    print(f"{name:<22} {r['dip_p50']*100:>7.1f}% {r['dip_p25']*100:>7.1f}% {r['dip_p10']*100:>7.1f}% │ "
          f"-{r['dip_recommend'][0]}%/-{r['dip_recommend'][1]}%/-{r['dip_recommend'][2]}% "
          f"({1}x/{2}x/{3}x) │ {r['avg_recovery_days']:>6.0f}d")

# ── 再平衡权重计算 ──
print("\n三、风险平价权重 (目标配置)")
print("-" * 80)
# 仅DCA基金
dca_data = {name: r for name, r in results.items()}
# 风险平价: w_i ∝ 1/σ_i
inv_vol = {name: 1.0 / max(r['vol'], 0.01) for name, r in dca_data.items()}
total_inv = sum(inv_vol.values())
rp_weights = {name: inv_vol[name] / total_inv for name in inv_vol}

print(f"{'基金':<22} {'波动率':>7} {'风险平价权重':>10} {'当前定投权重':>10} {'差异':>8}")
print("-" * 80)
total_dca = sum(f["dca_daily"] for f in funds if f.get("code"))
for f in funds:
    name = f["name"]
    if name not in dca_data: continue
    cur_w = f["dca_daily"] / total_dca
    rp_w = rp_weights.get(name, 0)
    diff = (rp_w - cur_w) * 100
    print(f"{name:<22} {dca_data[name]['vol']*100:>6.1f}% {rp_w:>9.1%} {cur_w:>9.1%} {diff:>+7.1f}pp")

# ── 止盈再投资建议 ──
print("\n四、止盈再投资优先序")
print("-" * 80)
# 按波动率从低到高排序(=防御优先)
sorted_defense = sorted(dca_data.items(), key=lambda x: x[1]['vol'])
print("止盈后资金: 50%现金 + 50%按以下优先级加仓(波动率最低优先)")
for i, (name, r) in enumerate(sorted_defense[:5]):
    print(f"  P{i+1}: {name} (vol {r['vol']*100:.1f}%)")
# 保存结果
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n✅ 结果已保存到 {OUTPUT}")

#!/usr/bin/env python3
"""指数全量历史回测 — 止盈阈值校准
运行: pip3 install akshare && python3 index_tp_backtest.py
如果网络好, 5分钟跑完
"""
import akshare as ak
import datetime

# 底层指数代码（东方财富格式）
INDICES = {
    '沪深300(A500代理)': '000300',
    '红利低波H30269':    'H30269',
    'CS创新药931152':    '931152',
    '科创创业50 931643':  '931643',
}
# 恒科不在A股指数范围, 用基金数据

def pct(arr, p):
    a = sorted(arr); return a[min(int(len(a)*p), len(a)-1)] if a else 0

print("=" * 95)
print(f"{'指数':<18} {'范围':<22} {'点':>5} {'P25 2yr':>7} {'P50 2yr':>7} {'P75 2yr':>7} │ 建议 +P1/+P2/+P3")
print("-" * 95)

for name, code in INDICES.items():
    try:
        df = ak.index_zh_a_hist(symbol=code, period='daily', start_date='20100101', end_date='20260730')
        if df is None or len(df) < 500: continue
        closes = df['收盘'].values
        n = len(closes)
        du_2yr = []
        for i in range(0, n, 5):  # sample every 5 days
            end_i = min(i + 500, n)
            max_c = max(closes[i:end_i])
            g = max_c / closes[i] - 1
            if g > 0: du_2yr.append(g)
        
        dur = f"{df.iloc[0]['日期']}~{df.iloc[-1]['日期']}"
        p25, p50, p75 = [pct(du_2yr, q) for q in [0.25, 0.5, 0.75]]
        p1 = max(round(p25*100/5)*5, 5)
        p2 = max(round(p50*100/5)*5, 10)
        p3 = max(round(p75*100/5)*5, 15)
        print(f"{name:<18} {dur} {len(df):>5}  {p25*100:>+5.0f}%  {p50*100:>+5.0f}%  {p75*100:>+5.0f}%  │ +{p1}/+{p2}/+{p3}%")
    except Exception as e:
        print(f"{name:<18} 失败({e})")

print("\n跑完把输出贴给我, 我帮你校准最终阈值。")

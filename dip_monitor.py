#!/usr/bin/env python3
"""
大跌监控 + Bark推送
每天14:50运行, 检查指数/基金是否触发补仓阈值
用法: python3 dip_monitor.py [--dry-run]
      配置: 设置环境变量 BARK_KEY (Bark App -> 右上角+ -> 复制Key)
"""
import json, urllib.request, os, sys, datetime, time

# ======= 配置 ==========
BARK_KEY = os.environ.get("BARK_KEY", "")
BARK_URL = f"https://api.day.app/{BARK_KEY}/" if BARK_KEY else None

# 基金→指数映射 + 大跌阈值
FUNDS = {
    # (定投金额, 指数secid, 阈值%, 模式, 数据时效)
    # 模式: replace=替代周五(A股/HK), extra=额外加仓, none=不提醒
    # 时效: live=盘中实时可操作, overnight=基于前夜收盘(T-1)
    "恒科":       (100, "124.HSTECH",   -2.0, "replace", "live"),
    "创新药":     (100, None,           -2.0, "replace", "live"),
    "张坤":       (10,  None,           -1.0, "replace", "live"),
    "红利低波":   (100, "2.H30269",     -2.0, "extra",   "live"),
    # QDII全部日限额触顶, 无额外加仓空间
}

# ======= 指数实时行情 ==========
def fetch_index_realtime(secid):
    """获取指数实时涨跌幅"""
    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f170,f58"
    headers = {"Referer": "https://quote.eastmoney.com/"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode('utf-8'))
        d = data.get("data", {})
        if d:
            price = d.get("f43", 0) / 100 if d.get("f43") else 0
            pct = d.get("f170", 0) / 100 if d.get("f170") else 0
            name = d.get("f58", "")
            return {"price": price, "pct": pct, "name": name}
    except Exception as e:
        pass
    return None

# ======= 基金最新净值 ==========
def fetch_fund_latest(code):
    """获取基金最新净值及日涨跌幅"""
    url = f"https://fundgz.1234567.com.cn/js/{code}.js?rt={int(time.time()*1000)}"
    headers = {"Referer": "https://fund.eastmoney.com/"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as r:
            text = r.read().decode('utf-8')
        # jsonpgz({"fundcode":"013127","name":"...","jzrq":"...","dwjz":"...","gsz":"...","gszzl":"...",...});
        text = text[text.index("{"):text.rindex("}")+1]
        data = json.loads(text)
        est_nav = float(data.get("gsz", 0))       # 估算净值
        prev_nav = float(data.get("dwjz", 0))     # 上一日净值
        if prev_nav > 0:
            pct = (est_nav - prev_nav) / prev_nav * 100 if est_nav > 0 else 0
            return {"name": data.get("name",""), "est_nav": est_nav, "prev_nav": prev_nav, "pct": pct}
    except Exception as e:
        pass
    return None

# ======= 基金代码映射 ==========
FUND_CODES = {
    "恒科": "013127", "创新药": "014564", "张坤": "005827",
    "南方纳指": "016452", "广发医疗": "000369", "建信纳指": "539001", "红利低波": "020602",
}

# ======= 主逻辑 ==========
def main():
    dry = "--dry-run" in sys.argv
    alerts = []
    
    now = datetime.datetime.now()
    ts = now.strftime("%m-%d %H:%M")
    
    for fname, (amt, idx_secid, threshold, mode, freshness) in FUNDS.items():
        if mode == "none":
            continue
        
        pct = None
        source = ""
        code = FUND_CODES.get(fname)
        
        # 优先用指数实时数据 (A股/HK盘中)
        if idx_secid and now.hour < 15:
            idx = fetch_index_realtime(idx_secid)
            if idx:
                pct = idx["pct"]
                source = "盘中实时"
        
        # fallback: 基金估值
        if pct is None and code:
            fund = fetch_fund_latest(code)
            if fund and fund["pct"] != 0:
                pct = fund["pct"]
                source = "盘中实时" if freshness == "live" else "前夜收盘"
        
        if pct is None:
            continue
        
        if pct <= threshold:
            if mode == "replace":
                mode_label = "⚡替代周五"
            else:
                mode_label = "💰额外加仓"
            freshness_label = "" if freshness == "live" else "【QDII·前夜美股】"
            msg = f"{freshness_label}{fname} {pct:+.1f}% (阈值{threshold:+.0f}%) → {mode_label} ({source})"
            alerts.append(msg)
            continue
        
    
    if not alerts:
        print(f"[{ts}] 无触发")
        return
    
    print(f"[{ts}] 触发 {len(alerts)} 只:")
    for a in alerts:
        print(f"  {a}")
    
    # Bark推送
    if BARK_URL and not dry:
        title = f"📉 定投监控 {ts}"
        body = "\n".join(alerts)
        try:
            url = f"{BARK_URL}{urllib.parse.quote(title, safe='')}/{urllib.parse.quote(body, safe='')}?sound=bell&isArchive=1"
            urllib.request.urlopen(urllib.request.Request(url), timeout=5)
            print("  → Bark已推送")
        except Exception as e:
            print(f"  → Bark推送失败: {e}")
    elif dry:
        print("  [dry-run] 跳过推送")

if __name__ == "__main__":
    import urllib.parse
    main()

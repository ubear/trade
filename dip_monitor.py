#!/usr/bin/env python3
"""大跌监控 + Bark/PushDeer双推送
每天14:50运行, 检查指数/基金是否触发补仓阈值
用法: python3 dip_monitor.py [--dry-run]
配置: BARK_KEY + PUSHDEER_KEY 环境变量
"""
import json, urllib.request, os, sys, datetime, time, urllib.parse as ulp

BARK_KEY = os.environ.get("BARK_KEY", "")
BARK_URL = f"https://api.day.app/{BARK_KEY}/" if BARK_KEY else None
SERVERCHAN_KEY = os.environ.get("SERVERCHAN_KEY", "")
SERVERCHAN_URL = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send" if SERVERCHAN_KEY else None
# 基金→指数映射 + 大跌阈值
FUNDS = {
    "恒科":       (100, "124.HSTECH",   -5.0, "replace", "live"),
    "创新药":     (100, None,           -4.0, "replace", "live"),
    "红利低波":   (100, "2.H30269",     -4.0, "extra",   "live"),
    # 港股红利: 数据仅200天暂不自动推送, 手动检查
    # A500/科创创业50: 不补(频率低/恢复快)
    # QDII: 限额触顶
    # 张坤: 出清目标不补
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
    "恒科": "013127", "创新药": "014564", "红利低波": "020602",
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
        
    # Bark推送
    if BARK_URL and not dry:
        try:
            url = f"{BARK_URL}{ulp.quote(title, safe='')}/{ulp.quote(body, safe='')}?sound=bell&isArchive=1"
            urllib.request.urlopen(urllib.request.Request(url), timeout=5)
            print("  → Bark已推送")
        except Exception as e:
            print(f"  → Bark失败: {e}")
    # Server酱推送
    if SERVERCHAN_URL and not dry:
        try:
            data = ulp.urlencode({"title": title, "desp": body}).encode()
            urllib.request.urlopen(urllib.request.Request(SERVERCHAN_URL, data=data), timeout=5)
            print("  → Server酱已推送")
        except Exception as e:
            print(f"  → Server酱失败: {e}")
    elif dry:
        print("  [dry-run] 跳过推送")

if __name__ == "__main__":
    import urllib.parse
    main()

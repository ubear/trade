#!/usr/bin/env python3
"""合并仪表盘：将 dashboard_data.json 嵌入 dashboard.html → dashboard_dist.html"""
import json
from pathlib import Path

BASE = Path(__file__).parent
html = BASE / "dashboard.html"
data = BASE / "dashboard_data.json"
dist = BASE / "dashboard_dist.html"

# 读取模板和数据
template = html.read_text(encoding="utf-8")
jdata = json.loads(data.read_text(encoding="utf-8"))
json_str = json.dumps(jdata, ensure_ascii=False)

# 替换 fetch 调用为内联数据
# 找到: const resp = await fetch('...');
# 替换为: const data = <JSON>;
old = """const resp = await fetch('/trade/dashboard_data.json?t=' + Date.now());
    const data = await resp.json();"""
new = f"const data = {json_str};"

replaced = template.replace(old, new)

# 同时更新 catch 中的错误信息
replaced = replaced.replace(
    "数据加载失败 — 运行 python3 portfolio_dashboard.py 生成数据",
    "数据加载失败"
)

dist.write_text(replaced, encoding="utf-8")
print(f"✓ {dist} ({len(replaced)} bytes, data embedded)")

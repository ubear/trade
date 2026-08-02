#!/usr/bin/env python3
"""将 data.json 嵌入模板 → dist 产物
- dashboard.html → dashboard_dist.html (workflow cp 为 dashboard/portfolio/v3)
- app.html → app_dist.html
- index.html → index_dist.html
git 中保留模板(含 __DATA_PLACEHOLDER__), 部署前构建覆盖"""
import json
from pathlib import Path

BASE = Path(__file__).parent
jdata = json.dumps(json.loads((BASE / "data.json").read_text(encoding="utf-8")), ensure_ascii=False)

TARGETS = {
    "dashboard.html": "dashboard_dist.html",
    "app.html": "app_dist.html",
    "index.html": "index_dist.html",
}

for tpl_name, out_name in TARGETS.items():
    tpl = (BASE / tpl_name).read_text(encoding="utf-8")
    out = tpl.replace("__DATA_PLACEHOLDER__", jdata)
    assert "__DATA_PLACEHOLDER__" not in out, f"{tpl_name} 仍有占位符"
    (BASE / out_name).write_text(out, encoding="utf-8")
    print(f"✓ {out_name} ({len(out)} bytes, embedded)")

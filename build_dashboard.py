#!/usr/bin/env python3
"""将 data.json 嵌入 dashboard.html → dashboard_dist.html"""
import json
from pathlib import Path

BASE = Path(__file__).parent
template = (BASE / "dashboard.html").read_text(encoding="utf-8")
jdata = json.loads((BASE / "data.json").read_text(encoding="utf-8"))

out = template.replace("__DATA_PLACEHOLDER__", json.dumps(jdata, ensure_ascii=False))

(BASE / "dashboard_dist.html").write_text(out, encoding="utf-8")
print(f"✓ dashboard_dist.html ({len(out)} bytes, embedded)")

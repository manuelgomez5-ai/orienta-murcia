import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
keys = ["status", "ranking", "vacancies", "adjudications", "exclusions", "annulled", "documents"]
payload = {}
for key in keys:
    path = DATA / f"{key}.json"
    payload[key] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"rows": []}
(DATA / "bundle.js").write_text("window.ORIENTA_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8")

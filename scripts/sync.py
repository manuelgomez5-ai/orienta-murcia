from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from parsers import (
    contains_orientation,
    extract_pdf_text,
    fold,
    parse_adjudications,
    parse_exclusions,
    parse_ranking,
    parse_vacancies,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SPECIALTY = "0590018"
TIMEOUT = 50
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "OrientaMurcia/2.0 (+public educational data monitor; contact repository owner)",
    "Accept-Language": "es-ES,es;q=0.9",
})

SOURCE_PAGES = [
    "https://www.carm.es/web/pagina?IDCONTENIDO=4254&IDTIPO=100&RASTRO=c%24m22725%2C22759",
    "https://www.carm.es/web/pagina?IDCONTENIDO=24219&IDTIPO=100&RASTRO=c77%24m22725%2C22759%2C4491%2C72314%2C4500%2C4497",
    "https://www.carm.es/web/pagina?IDCONTENIDO=4052&IDTIPO=100&RASTRO=c798%24m3911%2C4036",
    "https://www.carm.es/web/pagina?IDCONTENIDO=4921&IDTIPO=100&RASTRO=c798%24m3911%2C4036",
    "https://www.carm.es/web/pagina?IDCONTENIDO=74695&IDTIPO=100&RASTRO=c798%24m3977%2C74131",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def get(url: str) -> requests.Response:
    last_error = None
    for attempt in range(4):
        try:
            response = SESSION.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"No se pudo descargar {url}: {last_error}")


def load_json(name: str, default: dict) -> dict:
    path = DATA / name
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(name: str, payload: dict) -> None:
    (DATA / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def absolute(base: str, href: str) -> str:
    return urljoin(base, href.replace("&amp;", "&"))


def title_is_relevant(title: str) -> bool:
    f = fold(title)
    if "INFANTIL Y PRIMARIA" in f and "SECUNDARIA" not in f:
        return False
    return any(term in f for term in [
        "SECUNDARIA", "ORIENTACION", "ADJUDIC", "VACANT", "EXCLUID", "INTERIN"
    ])


def classify(title: str) -> str:
    """Classify an official publication by its purpose, not isolated words.

    Results titles frequently contain the word "vacantes" (for example,
    "Resultados provisionales del acto ... de vacantes"). They must be
    treated as adjudications before the generic vacancy rule is evaluated.
    """
    f = fold(title)
    if "ANULAD" in f:
        return "Vacantes anuladas"
    if "EXCLUID" in f:
        return "Exclusiones"
    if (("RELACION DEFINITIVA" in f or "RELACION PROVISIONAL" in f) and "INTERINO" in f) or "LISTAS DE INTERINOS" in f:
        return "Ranking"
    if ("RESULTADO" in f or "ADJUDICATARIO" in f) and ("ADJUDIC" in f or "PLAZA" in f):
        return "Adjudicación"
    if "VACANT" in f or "SUSTITUC" in f:
        return "Vacantes"
    if "CONVOCA" in f or "ACTO DE ADJUDICACION" in f:
        return "Convocatoria"
    return "Documento"


def extract_date(title: str) -> str:
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", title)
    if not match:
        return ""
    d, m, y = match.groups()
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def discover_detail(detail_url: str, inherited_title: str) -> list[dict]:
    response = get(detail_url)
    soup = BeautifulSoup(response.text, "html.parser")
    heading = soup.find(["h2", "h3"])
    detail_title = " ".join(heading.get_text(" ", strip=True).split()) if heading else inherited_title
    documents = []
    for anchor in soup.find_all("a", href=True):
        href = absolute(detail_url, anchor["href"])
        if "/web/descarga?" not in href and "integra.servlets.Blob" not in href:
            continue
        label = " ".join(anchor.get_text(" ", strip=True).split())
        combined = detail_title if label.lower() in {"descargar archivo", "archivo"} else f"{detail_title} · {label}"
        documents.append({
            "date": extract_date(detail_title),
            "type": classify(combined),
            "title": combined,
            "url": href,
            "detail_url": detail_url,
            "official": True,
        })
    return documents


def discover_documents() -> list[dict]:
    found: dict[str, dict] = {}
    for page_url in SOURCE_PAGES:
        response = get(page_url)
        soup = BeautifulSoup(response.text, "html.parser")
        candidates = []
        for anchor in soup.find_all("a", href=True):
            title = " ".join(anchor.get_text(" ", strip=True).split())
            if not title or not title_is_relevant(title):
                continue
            href = absolute(page_url, anchor["href"])
            candidates.append((title, href))
        # The newest entries are at the top. A cap avoids crawling the 1,500-entry archive.
        for title, href in candidates[:35]:
            try:
                if "/web/descarga?" in href or "integra.servlets.Blob" in href:
                    found[href] = {
                        "date": extract_date(title), "type": classify(title), "title": title,
                        "url": href, "detail_url": page_url, "official": True,
                    }
                elif "IDTIPO=60" in href or "IDCONTENIDO=" in href:
                    for doc in discover_detail(href, title):
                        found[doc["url"]] = doc
            except Exception as exc:
                print(f"Aviso: no se pudo inspeccionar {href}: {exc}")
    return list(found.values())


def download_pdf(url: str, destination: Path) -> str:
    response = get(url)
    content = response.content
    destination.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def merge_rows(existing: list[dict], incoming: list[dict], keys: tuple[str, ...]) -> list[dict]:
    merged = {tuple(str(row.get(k, "")) for k in keys): row for row in existing}
    for row in incoming:
        merged[tuple(str(row.get(k, "")) for k in keys)] = row
    return list(merged.values())


def build_bundle() -> None:
    payload = {
        "status": load_json("status.json", {}),
        "ranking": load_json("ranking.json", {"rows": []}),
        "vacancies": load_json("vacancies.json", {"rows": []}),
        "adjudications": load_json("adjudications.json", {"rows": []}),
        "exclusions": load_json("exclusions.json", {"rows": []}),
        "annulled": load_json("annulled.json", {"rows": []}),
        "documents": load_json("documents.json", {"rows": []}),
    }
    (DATA / "bundle.js").write_text(
        "window.ORIENTA_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )


def main() -> None:
    DATA.mkdir(exist_ok=True)
    status = load_json("status.json", {"errors": []})
    errors: list[str] = []

    documents_payload = load_json("documents.json", {"rows": []})
    documents_by_url = {row["url"]: row for row in documents_payload.get("rows", []) if row.get("url")}
    adjudications = load_json("adjudications.json", {"rows": []}).get("rows", [])
    exclusions = load_json("exclusions.json", {"rows": []}).get("rows", [])
    annulled = load_json("annulled.json", {"rows": []}).get("rows", [])
    vacancies_payload = load_json("vacancies.json", {"rows": []})
    ranking_payload = load_json("ranking.json", {"rows": []})

    try:
        discovered = discover_documents()
    except Exception as exc:
        discovered = []
        errors.append(f"Descubrimiento: {exc}")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        for doc in discovered:
            old = documents_by_url.get(doc["url"])
            if old and old.get("processed"):
                continue
            try:
                pdf_path = temp / (hashlib.md5(doc["url"].encode()).hexdigest() + ".pdf")
                checksum = download_pdf(doc["url"], pdf_path)
                text = extract_pdf_text(pdf_path)
                if not contains_orientation(text):
                    doc.update({"processed": True, "orientation_rows": 0, "checksum": checksum})
                    documents_by_url[doc["url"]] = doc
                    continue

                date = doc.get("date", "")
                doc_type = doc.get("type", "Documento")
                row_count = 0
                if doc_type == "Ranking":
                    parsed_ranking = parse_ranking(text, doc["url"], date)
                    row_count = parsed_ranking.get("official_total", 0)
                    if row_count and (not ranking_payload.get("source_date") or date >= ranking_payload.get("source_date", "")):
                        ranking_payload = parsed_ranking
                elif doc_type == "Vacantes":
                    rows = parse_vacancies(text, doc["url"], date)
                    row_count = sum(r.get("quantity", 1) for r in rows)
                    if rows and (not vacancies_payload.get("document_date") or date >= vacancies_payload.get("document_date", "")):
                        vacancies_payload = {
                            "updated_at": now_iso(),
                            "document_date": date,
                            "source_url": doc["url"],
                            "rows": rows,
                        }
                elif doc_type == "Vacantes anuladas":
                    rows = parse_vacancies(text, doc["url"], date)
                    for row in rows:
                        row["status"] = "Anulada"
                    row_count = sum(r.get("quantity", 1) for r in rows)
                    annulled = merge_rows(annulled, rows, ("centre_code", "jornada", "hours", "document_date"))
                elif doc_type == "Exclusiones":
                    rows = parse_exclusions(text, doc["url"], date)
                    exclusion_status = "Definitiva" if "DEFINIT" in fold(doc.get("title", "")) else "Provisional"
                    for row in rows:
                        row.update({
                            "course": "",
                            "status": exclusion_status,
                            "affects_interim_ranking": exclusion_status == "Definitiva",
                        })
                    row_count = len(rows)
                    exclusions = merge_rows(exclusions, rows, ("list_number", "document_date"))
                elif doc_type == "Adjudicación":
                    status_label = "Provisional" if "PROVISION" in fold(doc.get("title", "")) else "Definitiva"
                    rows = parse_adjudications(text, doc["url"], date, status_label)
                    for row in rows:
                        row.update({"course": "", "scope": "Interinos / Secundaria", "affects_interim_ranking": status_label == "Definitiva"})
                    row_count = len(rows)
                    adjudications = merge_rows(adjudications, rows, ("list_number", "document_date", "status", "centre"))

                doc.update({
                    "processed": True,
                    "orientation_rows": row_count,
                    "checksum": checksum,
                    "processed_at": now_iso(),
                })
                documents_by_url[doc["url"]] = doc
            except Exception as exc:
                message = f"{doc.get('title', doc.get('url'))}: {exc}"
                print("Error:", message)
                errors.append(message)

    docs = sorted(documents_by_url.values(), key=lambda r: (r.get("date", ""), r.get("title", "")), reverse=True)[:100]
    save_json("documents.json", {"rows": docs})
    save_json("vacancies.json", vacancies_payload)
    save_json("ranking.json", ranking_payload)
    save_json("adjudications.json", {"rows": adjudications})
    save_json("exclusions.json", {"rows": exclusions})
    save_json("annulled.json", {"rows": annulled})

    status.update({
        "last_check": now_iso(),
        "last_success": now_iso() if not errors else status.get("last_success", ""),
        "mode": "automatic",
        "message": "Sincronización completada." if not errors else "Sincronización completada con avisos.",
        "specialty": SPECIALTY,
        "errors": errors[-20:],
    })
    save_json("status.json", status)
    build_bundle()
    print(status["message"])


if __name__ == "__main__":
    main()

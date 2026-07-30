from __future__ import annotations

import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SPECIALTY_CODE = "0590018"
SPECIALTY_NAME = "ORIENTACION EDUCATIVA"


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in value if not unicodedata.combining(ch)).upper()


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract layout-preserving text. Poppler is preferred; pypdf is fallback."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout.decode("utf-8", errors="replace")
    except (FileNotFoundError, subprocess.CalledProcessError):
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        return "\n\f\n".join(page.extract_text() or "" for page in reader.pages)


def contains_orientation(text: str) -> bool:
    folded = fold(text)
    return SPECIALTY_CODE in folded or "590018 ORIENTACION" in folded or SPECIALTY_NAME in folded


def _slice(line: str, start: int, end: int | None = None) -> str:
    if len(line) <= start:
        return ""
    return line[start:end]


def _find_section(lines: list[str], index: int) -> str:
    for line in reversed(lines[max(0, index - 90):index + 1]):
        f = fold(line)
        if "VACANTES DE PLANTILLA" in f:
            return "Plantilla"
        if "VACANTES DE SUSTITUCION" in f or "SUSTITUCIONES" in f:
            return "Sustitución"
    return "Vacante"


def parse_vacancies(text: str, source_url: str = "", document_date: str = "") -> list[dict]:
    """Parse 0590018 rows from CARM's fixed-width vacancy PDFs.

    The PDFs place the function on the line immediately before the centre row, and
    wrap locality/function/jornada across subsequent lines. The parser keeps the
    official vacancy quantity (`Dis`) instead of assuming one row equals one place.
    """
    lines = text.split("\n")
    records: list[dict] = []

    specialty_indexes = [
        i for i, line in enumerate(lines)
        if SPECIALTY_CODE in fold(line) and "ORIENTACION" in fold(line)
    ]

    for pos, i in enumerate(specialty_indexes):
        next_i = specialty_indexes[pos + 1] if pos + 1 < len(specialty_indexes) else min(len(lines), i + 12)
        search_end = min(next_i, i + 7)
        code_index = None
        for j in range(max(0, i - 1), search_end):
            if re.match(r"^\s*\d{8}\s", lines[j]):
                code_index = j
                break
        if code_index is None:
            continue

        code_line = lines[code_index]
        block_end = min(next_i, code_index + 8)
        block = lines[i:block_end]

        code_match = re.match(r"^\s*(\d{8})\s+", code_line)
        if not code_match:
            continue
        centre_code = code_match.group(1)
        centre = normalize_space(_slice(code_line, 11, 61))

        locality_parts: list[str] = []
        for line in lines[code_index:block_end]:
            part = normalize_space(_slice(line, 61, 80))
            if part and not any(token in fold(part) for token in ["FUNCION", "JORNADA", "PAGINA"]):
                locality_parts.append(part)
        locality = normalize_space(" ".join(dict.fromkeys(locality_parts)))

        function_text = normalize_space(" ".join(_slice(line, 80, 100) for line in block))
        journey_text = normalize_space(" ".join(_slice(line, 100, 113) for line in block))
        profile_text = normalize_space(" ".join(_slice(line, 120, 131) for line in block))
        observations = normalize_space(" ".join(_slice(line, 142, None) for line in block))

        if "COMPLETA" in fold(journey_text):
            jornada = "Completa"
            hours = None
        else:
            hour_match = re.search(r"PARCIAL\s*(\d{1,2})", fold(journey_text))
            jornada = "Parcial"
            hours = int(hour_match.group(1)) if hour_match else None

        quantity_text = normalize_space(_slice(code_line, 131, 135))
        quantity_match = re.search(r"\d+", quantity_text)
        quantity = int(quantity_match.group()) if quantity_match else 1

        cupo = normalize_space(_slice(code_line, 113, 120))
        itinerary = normalize_space(_slice(code_line, 135, 139))
        mobile = normalize_space(_slice(code_line, 139, 142))

        record = {
            "centre_code": centre_code,
            "centre": centre,
            "locality": locality,
            "function_code": SPECIALTY_CODE,
            "function": "Orientación Educativa",
            "jornada": jornada,
            "hours": hours,
            "cupo": cupo,
            "profile": profile_text,
            "quantity": quantity,
            "section": _find_section(lines, i),
            "itinerant": itinerary,
            "mobile": mobile,
            "observations": observations,
            "document_date": document_date,
            "source_url": source_url,
        }
        records.append(record)

    # Keep genuine repeated centre rows (complete + partial), remove extraction duplicates.
    unique: dict[tuple, dict] = {}
    for row in records:
        key = (
            row["centre_code"], row["jornada"], row["hours"], row["quantity"],
            row["profile"], row["section"], row["observations"]
        )
        unique[key] = row
    return list(unique.values())


def _mask_name(name: str) -> str:
    parts = [p for p in normalize_space(name).split(" ") if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][0] + "."
    return " ".join(p[0] + "." for p in parts)


def parse_exclusions(text: str, source_url: str = "", document_date: str = "") -> list[dict]:
    lines = text.split("\n")
    inside = False
    rows: list[dict] = []
    for line in lines:
        f = fold(line)
        if re.search(r"FUNCION:\s*0?590018\b", f):
            inside = True
            continue
        if inside and "FUNCION:" in f and not re.search(r"FUNCION:\s*0?590018\b", f):
            break
        if not inside:
            continue
        match = re.search(r"\b(\d{8})\s+(\*+\d{4}\*+)\s+(.+?)\s*$", line)
        if not match:
            continue
        number, masked_id, full_name = match.groups()
        full_name = normalize_space(full_name)
        rows.append({
            "list_number": number,
            "masked_id": masked_id,
            "name": _mask_name(full_name),
            "reason": "No participación",
            "document_date": document_date,
            "source_url": source_url,
        })
    return rows


def parse_adjudications(text: str, source_url: str = "", document_date: str = "", status: str = "Definitiva") -> list[dict]:
    """Parse orientation award rows from both weekly and July CARM layouts."""
    lines = text.split("\n")
    rows: list[dict] = []
    inside = False
    current_header: dict[str, tuple[int, int]] | None = None

    for idx, line in enumerate(lines):
        f = fold(line)
        if re.search(r"FUNCION:\s*0?590018\b", f):
            inside = True
            current_header = None
            continue
        if inside and "FUNCION:" in f and not re.search(r"FUNCION:\s*0?590018\b", f):
            inside = False
            current_header = None
            continue
        if not inside:
            continue

        if ("Nº LISTA" in line.upper() or "NO LISTA" in f or "N.LISTA" in f) and "DNI" in f:
            # Two modern layouts are supported. Use the visible header positions.
            positions = {}
            labels = ["Nº Lista", "DNI", "Apellido1", "Apellido2", "Nombre", "Centro", "Municipio", "Función", "Jornada", "Perfil", "V/S", "Obs."]
            found = []
            for label in labels:
                p = line.find(label)
                if p >= 0:
                    found.append((p, label))
            found.sort()
            for n, (start, label) in enumerate(found):
                end = found[n + 1][0] if n + 1 < len(found) else max(len(line), start + 20)
                positions[label] = (start, end)
            current_header = positions
            continue

        if not re.search(r"\*+\d{4}\*+", line) or not re.search(r"\b\d{8}\b", line):
            continue

        list_match = re.search(r"\b(\d{8})\b", line)
        id_match = re.search(r"(\*+\d{4}\*+)", line)
        if not list_match or not id_match:
            continue

        list_number = list_match.group(1)
        masked_id = id_match.group(1)
        priority_match = re.match(r"^\s*(\d{1,2})\s+" + re.escape(list_number), line)
        priority = priority_match.group(1) if priority_match else ""

        if current_header and all(key in current_header for key in ["Apellido1", "Apellido2", "Nombre"]):
            def col(label: str) -> str:
                start, end = current_header[label]
                return normalize_space(_slice(line, start, end))
            surname1, surname2, given = col("Apellido1"), col("Apellido2"), col("Nombre")
            full_name = normalize_space(" ".join([surname1, surname2, given]))
            municipality = col("Municipio") if "Municipio" in current_header else ""
            function = col("Función") if "Función" in current_header else SPECIALTY_CODE
            jornada = col("Jornada") if "Jornada" in current_header else ""
            profile = col("Perfil") if "Perfil" in current_header else ""
            vacancy_type = col("V/S") if "V/S" in current_header else ""
        else:
            # Fallback for reordered extraction: name is the text between DNI and centre/function codes.
            tail = line[id_match.end():]
            cut = re.search(r"\b(?:3\d{7}|0590[A-Z0-9]{3}|0590018)\b", tail)
            full_name = normalize_space(tail[:cut.start()] if cut else tail)
            municipality = ""
            function = SPECIALTY_CODE
            jornada = "Completa" if "COMPLETA" in f else ("Parcial" if "PARCIAL" in f else "")
            profile = "SIN PERFIL" if "SIN PERFIL" in f else ""
            vacancy_type = "VS" if re.search(r"\bVS\b", f) else ("VP" if re.search(r"\bVP\b", f) else "")

        # Centre often sits on one or more lines immediately above/below the person row.
        centre_parts: list[str] = []
        for j in range(max(0, idx - 2), min(len(lines), idx + 4)):
            candidate = lines[j]
            match = re.search(r"\b(3\d{7}|307\d{5})\s+(.+)", candidate)
            if match:
                centre_parts.append(normalize_space(match.group(0)))
        centre = normalize_space(" ".join(dict.fromkeys(centre_parts)))

        rows.append({
            "priority": priority,
            "list_number": list_number,
            "masked_id": masked_id,
            "name": _mask_name(full_name),
            "centre": centre,
            "municipality": municipality,
            "function_code": function or SPECIALTY_CODE,
            "jornada": jornada,
            "profile": profile,
            "vacancy_type": vacancy_type,
            "status": status,
            "document_date": document_date,
            "source_url": source_url,
        })

    unique: dict[tuple, dict] = {}
    for row in rows:
        unique[(row["list_number"], row["masked_id"], row["centre"], row["document_date"])] = row
    return list(unique.values())


def parse_ranking(text: str, source_url: str = "", document_date: str = "") -> dict:
    """Extract the complete Block 1 + Block 2 ranking for specialty 018.

    CARM repeats the specialty heading on every page. Some PDFs also contain
    later exclusion annexes with the same specialty, so every candidate section
    is parsed and the largest valid Block 1/2 section is selected.
    """
    lines = text.split("\n")
    specialty_indexes = [
        i for i, line in enumerate(lines)
        if "ESPECIALIDAD: 018 ORIENTACION EDUCATIVA" in fold(line)
    ]
    candidates: list[list[dict]] = []

    for start in specialty_indexes:
        end = len(lines)
        for i in range(start + 1, len(lines)):
            f = fold(lines[i])
            if "ESPECIALIDAD:" in f and "ESPECIALIDAD: 018 ORIENTACION EDUCATIVA" not in f:
                end = i
                break
        block = None
        block_counts = {1: 0, 2: 0}
        rows: list[dict] = []
        for line in lines[start:end]:
            f = fold(line)
            if "LISTA:" in f and "BLOQUE 1" in f:
                block = 1
            elif "LISTA:" in f and "BLOQUE 2" in f:
                block = 2
            match = re.search(
                r"\b(\d{8})\s+(\*+\d{4}\*+)\s+(.+?)\s+(-?\d+[.,]\d{4})\s*$",
                line,
            )
            if not match or block not in (1, 2):
                continue
            number, masked_id, name, points = match.groups()
            block_counts[block] += 1
            rows.append({
                "block": block,
                "block_rank": block_counts[block],
                "list_number": number,
                "masked_id": masked_id,
                "name": normalize_space(name),
                "points": float(points.replace(",", ".")),
            })
        if rows:
            candidates.append(rows)

    if not candidates:
        return {
            "status": "empty", "course": "", "source_label": "",
            "source_url": source_url, "source_date": document_date,
            "official_total": 0, "block_1_total": 0, "block_2_total": 0,
            "notice": "No se pudo extraer el ranking.", "rows": [],
        }

    rows = max(candidates, key=len)
    block1 = sum(1 for row in rows if row["block"] == 1)
    for row in rows:
        row["global"] = row["block_rank"] if row["block"] == 1 else block1 + row["block_rank"]
    rows.sort(key=lambda row: row["global"])
    block2 = sum(1 for row in rows if row["block"] == 2)
    folded_text = fold(text)
    course_match = re.search(r"CURSO\s+(\d{4}/\d{4})", folded_text)
    is_definitive = "RELACION DEFINITIVA DEL PERSONAL INTERINO" in folded_text
    return {
        "status": "complete" if is_definitive else "provisional",
        "course": course_match.group(1) if course_match else "",
        "source_label": ("Relación definitiva" if is_definitive else "Relación provisional") + " del personal interino de Secundaria y otros cuerpos",
        "source_url": source_url,
        "source_date": document_date,
        "official_total": len(rows),
        "block_1_total": block1,
        "block_2_total": block2,
        "notice": ("Lista definitiva" if is_definitive else "Lista provisional") + " completa cargada desde la publicación oficial de la CARM.",
        "rows": rows,
    }

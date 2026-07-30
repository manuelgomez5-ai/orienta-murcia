from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from parsers import extract_pdf_text, parse_vacancies, parse_adjudications, parse_exclusions

ROOT = Path(__file__).resolve().parents[2]

def test_current_vacancies():
    pdf = ROOT / "latest_vacantes_secundaria_2026-07-29.pdf"
    if not pdf.exists():
        return
    rows = parse_vacancies(extract_pdf_text(pdf))
    assert rows
    assert all(r["function_code"] == "0590018" for r in rows)
    assert sum(r["quantity"] for r in rows) >= len(rows)


def test_adjudications():
    pdf = ROOT / "sample_adjudicacion_orientacion.pdf"
    if not pdf.exists():
        return
    rows = parse_adjudications(extract_pdf_text(pdf))
    assert len(rows) >= 10


def test_exclusions():
    pdf = ROOT / "sample_exclusiones_orientacion.pdf"
    if not pdf.exists():
        return
    rows = parse_exclusions(extract_pdf_text(pdf))
    assert len(rows) == 4


def test_definitive_ranking():
    from parsers import parse_ranking
    pdf = ROOT / "definitive_interinos_2026_2027.pdf"
    if not pdf.exists():
        return
    ranking = parse_ranking(extract_pdf_text(pdf))
    assert ranking["official_total"] == 457
    assert ranking["block_1_total"] == 196
    assert ranking["block_2_total"] == 261
    manuel = next(row for row in ranking["rows"] if row["list_number"] == "25002960")
    assert manuel["global"] == 282
    assert manuel["block_rank"] == 86

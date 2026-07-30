from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sync import classify


def test_results_of_vacancies_are_adjudications():
    title = "30/07/2026. Resultados provisionales del acto de adjudicación telemático de vacantes para Secundaria"
    assert classify(title) == "Adjudicación"


def test_plain_vacancy_list_is_vacancies():
    title = "Lista de vacantes de Secundaria para el acto de adjudicación"
    assert classify(title) == "Vacantes"

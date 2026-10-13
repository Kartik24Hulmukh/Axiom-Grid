"""Regression checks for dependency skips, not model/platform assurance."""
import runpy
from pathlib import Path

import openpyxl
import pytest

from kairo.excel import engine


@pytest.fixture(scope="module")
def excel_acceptance():
    namespace = runpy.run_path(str(Path(__file__).with_name("test_acceptance_gauntlet.py")))
    return namespace["TestExcelDomain"]().test_excel_formula_values


@pytest.mark.parametrize("error", [
    AssertionError("oracle mismatch"),
    RuntimeError("converter did not produce output"),
    AttributeError("invalid test contract"),
])
def test_excel_acceptance_does_not_skip_real_failures(
    tmp_path, monkeypatch, excel_acceptance, error
):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(engine, "xlsx_recompute", fail)
    with pytest.raises(type(error), match=str(error)):
        excel_acceptance(tmp_path)


def test_excel_acceptance_preserves_unavailable_skip(tmp_path, monkeypatch, excel_acceptance):
    def unavailable(*args, **kwargs):
        raise engine.LibreOfficeUnavailableError("not installed")

    monkeypatch.setattr(engine, "xlsx_recompute", unavailable)
    with pytest.raises(pytest.skip.Exception, match="LibreOffice not available"):
        excel_acceptance(tmp_path)


def test_real_excel_oracle_rejects_wrong_expected_value(tmp_path):
    """One tiny real subprocess conversion; no model, load or network."""
    path = tmp_path / "negative-formula.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet["A1"], sheet["A2"], sheet["A3"] = 100, 200, "=A1+A2"
    workbook.save(path)
    workbook.close()
    try:
        with pytest.raises(AssertionError, match="expected 301, got 300"):
            engine.xlsx_recompute(str(path), {"Sheet!A3": 301})
    except engine.LibreOfficeUnavailableError:
        pytest.skip("LibreOffice not available — honest degradation")
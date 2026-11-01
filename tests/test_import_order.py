"""F-021: on the Windows dev machine, importing `elasticsearch` BEFORE `torch` makes torch fail with
WinError 1114 (c10.dll). Each check runs in a FRESH interpreter, because the test process has
already imported torch (see tests/conftest.py) and would hide the problem.
"""
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parent.parent


def _run_fresh(code: str) -> subprocess.CompletedProcess:
    # -I (isolated) so nothing from the cwd or env can change what is imported; the repo root is
    # added explicitly because -I drops it from sys.path.
    prelude = f"import sys; sys.path.insert(0, {str(ROOT)!r}); "
    return subprocess.run([sys.executable, "-I", "-c", prelude + code],
                          capture_output=True, text=True, timeout=300)


def test_api_module_imports_in_a_fresh_interpreter():
    result = _run_fresh("import voltagent.api.main")
    assert result.returncode == 0, result.stderr[-800:]


@pytest.mark.parametrize("script", ["scripts/ingest.py", "scripts/evaluate_retrieval.py"])
def test_cli_scripts_import_in_a_fresh_interpreter(script):
    code = ("import importlib.util as u; "
            f"s = u.spec_from_file_location('cli', {str(ROOT / script)!r}); "
            "m = u.module_from_spec(s); sys.modules['cli'] = m; s.loader.exec_module(m)")  # @dataclass needs sys.modules
    result = _run_fresh(code)
    assert result.returncode == 0, result.stderr[-800:]


@pytest.mark.xfail(
    strict=False,
    reason="F-021 environment fault: elasticsearch-before-torch crashes on the affected Windows setup. "
    "Non-strict so the test also passes on machines without the fault.",
)
def test_hazard_elasticsearch_before_torch():
    result = _run_fresh("import elasticsearch; import torch")
    assert result.returncode == 0, result.stderr[-300:]

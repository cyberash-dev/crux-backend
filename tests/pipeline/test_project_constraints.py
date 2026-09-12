# @covers pipeline:CST-001
# @covers pipeline:NFR-001
# @covers pipeline:DLT-002
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_requires_python_is_pinned_to_3_12() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())

    assert pyproject["project"]["requires-python"] == ">=3.12"


def test_nfr_probe_protocol_carries_the_spec_thresholds() -> None:
    protocol = (PROJECT_ROOT / "docs" / "nfr-001-probe.md").read_text()

    assert "wall_clock_minutes <= 60" in protocol
    assert "external_api_cost_usd <= 5" in protocol
    assert "## Run notes" in protocol

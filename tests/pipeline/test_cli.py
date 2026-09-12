# @covers pipeline:CON-001
# @covers pipeline:POL-001
# @covers pipeline:DLT-001
from pathlib import Path

from typer.testing import CliRunner

from konspekt.features.factcheck.domain.claims import ExtractedClaim
from konspekt.features.factcheck.ports.outbound.search_credential_error import (
    SearchCredentialError,
)
from konspekt.pipeline.cli import create_app
from tests.pipeline.pipeline_fakes import FakePorts

SENTINEL_ELEVENLABS = "sentinel-elevenlabs-key-3f9a"
SENTINEL_ANTHROPIC = "sentinel-anthropic-key-7c2d"
SENTINEL_EXA = "sentinel-exa-key-5b1e"


def keys_env() -> dict[str, str]:
    return {
        "ELEVENLABS_API_KEY": SENTINEL_ELEVENLABS,
        "ANTHROPIC_API_KEY": SENTINEL_ANTHROPIC,
        "EXA_API_KEY": SENTINEL_EXA,
    }


class RejectedSearchClaimExtraction:
    def extract_claims(
        self, core_text_with_timestamps: str, language: str
    ) -> list[ExtractedClaim]:
        raise SearchCredentialError("Exa rejected EXA_API_KEY (HTTP 401)")


def a_video(tmp_path: Path) -> Path:
    video = tmp_path / "lecture.mp4"
    video.write_bytes(b"video-bytes")
    return video


def test_happy_path_exits_zero_and_writes_pdf(tmp_path: Path) -> None:
    fakes = FakePorts()
    app = create_app(ports_factory=lambda config, budget: fakes.as_ports())
    out_dir = tmp_path / "out"

    result = CliRunner().invoke(
        app,
        ["build", str(a_video(tmp_path)), "--out", str(out_dir)],
        env=keys_env(),
    )

    assert result.exit_code == 0, result.output
    assert (out_dir / "lecture" / "konspekt.pdf").exists()
    assert "total spend:" in result.output


def test_missing_video_exits_2_without_running_stages(tmp_path: Path) -> None:
    fakes = FakePorts()
    app = create_app(ports_factory=lambda config, budget: fakes.as_ports())

    result = CliRunner().invoke(
        app,
        ["build", str(tmp_path / "absent.mp4"), "--out", str(tmp_path / "out")],
        env=keys_env(),
    )

    assert result.exit_code == 2
    assert fakes.media_tools.calls == 0


def test_unknown_flag_exits_2(tmp_path: Path) -> None:
    app = create_app(ports_factory=lambda config, budget: FakePorts().as_ports())

    result = CliRunner().invoke(
        app,
        ["build", str(a_video(tmp_path)), "--frobnicate"],
        env=keys_env(),
    )

    assert result.exit_code == 2


def test_missing_elevenlabs_key_exits_2_with_default_transcriber(tmp_path: Path) -> None:
    fakes = FakePorts()
    app = create_app(ports_factory=lambda config, budget: fakes.as_ports())
    env_without_key = {"ELEVENLABS_API_KEY": "", "ANTHROPIC_API_KEY": ""}

    result = CliRunner().invoke(
        app,
        ["build", str(a_video(tmp_path)), "--out", str(tmp_path / "out")],
        env=env_without_key,
    )

    assert result.exit_code == 2
    assert fakes.media_tools.calls == 0
    assert "ELEVENLABS_API_KEY" in result.output


def test_default_claude_cli_provider_needs_no_anthropic_key(tmp_path: Path) -> None:
    fakes = FakePorts()
    app = create_app(ports_factory=lambda config, budget: fakes.as_ports())
    env_without_anthropic = {**keys_env(), "ANTHROPIC_API_KEY": ""}

    result = CliRunner().invoke(
        app,
        ["build", str(a_video(tmp_path)), "--out", str(tmp_path / "out")],
        env=env_without_anthropic,
    )

    assert result.exit_code == 0, result.output


def test_api_provider_requires_anthropic_key(tmp_path: Path) -> None:
    fakes = FakePorts()
    app = create_app(ports_factory=lambda config, budget: fakes.as_ports())
    env_without_anthropic = {"ELEVENLABS_API_KEY": SENTINEL_ELEVENLABS, "ANTHROPIC_API_KEY": ""}

    result = CliRunner().invoke(
        app,
        ["build", str(a_video(tmp_path)), "--llm-provider", "api", "--out", str(tmp_path / "out")],
        env=env_without_anthropic,
    )

    assert result.exit_code == 2
    assert fakes.media_tools.calls == 0
    assert "ANTHROPIC_API_KEY" in result.output


def test_whisper_transcriber_needs_no_elevenlabs_key(tmp_path: Path) -> None:
    fakes = FakePorts()
    app = create_app(ports_factory=lambda config, budget: fakes.as_ports())
    env_without_keys = {**keys_env(), "ELEVENLABS_API_KEY": "", "ANTHROPIC_API_KEY": ""}

    result = CliRunner().invoke(
        app,
        ["build", str(a_video(tmp_path)), "--transcriber", "whisper", "--out", str(tmp_path / "out")],
        env=env_without_keys,
    )

    assert result.exit_code == 0, result.output


def test_missing_claude_binary_exits_2_for_default_provider(tmp_path: Path) -> None:
    fakes = FakePorts()
    app = create_app(
        ports_factory=lambda config, budget: fakes.as_ports(),
        claude_binary="/nonexistent/claude-binary",
    )

    result = CliRunner().invoke(
        app,
        ["build", str(a_video(tmp_path)), "--out", str(tmp_path / "out")],
        env=keys_env(),
    )

    assert result.exit_code == 2
    assert fakes.media_tools.calls == 0
    assert "claude" in result.output


def test_secrets_never_reach_output_files_or_logs(tmp_path: Path) -> None:
    app = create_app(ports_factory=lambda config, budget: FakePorts().as_ports())
    out_dir = tmp_path / "out"

    result = CliRunner().invoke(
        app,
        ["build", str(a_video(tmp_path)), "--out", str(out_dir)],
        env=keys_env(),
    )

    assert result.exit_code == 0, result.output
    assert SENTINEL_ELEVENLABS not in result.output
    assert SENTINEL_ANTHROPIC not in result.output
    assert SENTINEL_EXA not in result.output
    for produced in out_dir.rglob("*"):
        if produced.is_file():
            content = produced.read_bytes()
            assert SENTINEL_ELEVENLABS.encode() not in content
            assert SENTINEL_ANTHROPIC.encode() not in content
            assert SENTINEL_EXA.encode() not in content


# @covers pipeline:DLT-005
def test_missing_exa_key_exits_2_without_running_stages(tmp_path: Path) -> None:
    fakes = FakePorts()
    app = create_app(ports_factory=lambda config, budget: fakes.as_ports())
    env_without_exa = {**keys_env(), "EXA_API_KEY": ""}

    result = CliRunner().invoke(
        app,
        ["build", str(a_video(tmp_path)), "--out", str(tmp_path / "out")],
        env=env_without_exa,
    )

    assert result.exit_code == 2
    assert fakes.media_tools.calls == 0
    assert "EXA_API_KEY" in result.output


# @covers analysis:EXT-014
def test_search_credential_rejection_exits_2(tmp_path: Path) -> None:
    fakes = FakePorts(claim_extraction=RejectedSearchClaimExtraction())
    app = create_app(ports_factory=lambda config, budget: fakes.as_ports())

    result = CliRunner().invoke(
        app,
        ["build", str(a_video(tmp_path)), "--out", str(tmp_path / "out")],
        env=keys_env(),
    )

    assert result.exit_code == 2
    assert "EXA_API_KEY" in result.output


# @covers pipeline:DLT-004
def test_illustration_flags_default_to_six_candidates_and_no_generation(tmp_path: Path) -> None:
    captured_configs = []

    def capturing_factory(config, budget):
        captured_configs.append(config)
        return FakePorts().as_ports()

    app = create_app(ports_factory=capturing_factory)

    result = CliRunner().invoke(
        app, ["build", str(a_video(tmp_path)), "--out", str(tmp_path / "out")], env=keys_env()
    )

    assert result.exit_code == 0, result.output
    assert captured_configs[0].commons_candidates == 6
    assert captured_configs[0].generated_images is False


# @covers pipeline:DLT-004
def test_illustration_flags_are_passed_through(tmp_path: Path) -> None:
    captured_configs = []

    def capturing_factory(config, budget):
        captured_configs.append(config)
        return FakePorts().as_ports()

    app = create_app(ports_factory=capturing_factory)

    result = CliRunner().invoke(
        app,
        [
            "build", str(a_video(tmp_path)), "--out", str(tmp_path / "out"),
            "--commons-candidates", "9", "--generated-images",
        ],
        env=keys_env(),
    )

    assert result.exit_code == 0, result.output
    assert captured_configs[0].commons_candidates == 9
    assert captured_configs[0].generated_images is True

# @covers analysis:EXT-013
import stat
from pathlib import Path

from konspekt.features.notes.adapters.outbound.codex_image_generation import (
    CodexImageGeneration,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\nfakepixels"


def a_stub_codex(tmp_path: Path, body: str) -> str:
    script_path = tmp_path / "codex-stub"
    script_path.write_text("#!/bin/sh\n" + body)
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)
    return str(script_path)


def a_file_writing_codex(tmp_path: Path, args_log_path: Path) -> str:
    return a_stub_codex(
        tmp_path,
        f'printf "%s" "$*" > "{args_log_path}"\n'
        'cd "$6" || exit 1\n'
        'target=$(printf "%s" "$*" | sed -n "s/.*as \\([A-Za-z0-9_]*\\.png\\).*/\\1/p")\n'
        'printf "png" > "$target"\n'
        'echo "$target"\n',
    )


def test_generated_file_path_is_returned_when_file_exists(tmp_path: Path) -> None:
    dest_dir = tmp_path / "images"
    dest_dir.mkdir()
    generator = CodexImageGeneration(
        binary_name=a_file_writing_codex(tmp_path, tmp_path / "args.log")
    )

    stored_path = generator.generate("Radius and ulna, anterior view", str(dest_dir), "illustration_s1")

    assert stored_path == str(dest_dir / "illustration_s1.png")
    assert (dest_dir / "illustration_s1.png").exists()


def test_prompt_passed_to_codex_names_the_target_file_and_flags(tmp_path: Path) -> None:
    dest_dir = tmp_path / "images"
    dest_dir.mkdir()
    log_path = tmp_path / "args.log"
    generator = CodexImageGeneration(binary_name=a_file_writing_codex(tmp_path, log_path))

    generator.generate("Radius and ulna, anterior view", str(dest_dir), "illustration_s1")

    recorded_args = log_path.read_text()
    assert recorded_args.startswith(
        f"exec --skip-git-repo-check -s workspace-write -C {dest_dir} "
    )
    assert "Radius and ulna, anterior view" in recorded_args
    assert "illustration_s1.png" in recorded_args
    assert "ONE educational illustration" in recorded_args


def test_non_zero_exit_yields_none(tmp_path: Path) -> None:
    dest_dir = tmp_path / "images"
    dest_dir.mkdir()
    generator = CodexImageGeneration(binary_name=a_stub_codex(tmp_path, "exit 3\n"))

    stored_path = generator.generate("prompt", str(dest_dir), "illustration_s1")

    assert stored_path is None


def test_exit_zero_without_file_yields_none(tmp_path: Path) -> None:
    dest_dir = tmp_path / "images"
    dest_dir.mkdir()
    generator = CodexImageGeneration(binary_name=a_stub_codex(tmp_path, "exit 0\n"))

    stored_path = generator.generate("prompt", str(dest_dir), "illustration_s1")

    assert stored_path is None


def test_jpg_output_is_accepted(tmp_path: Path) -> None:
    dest_dir = tmp_path / "images"
    dest_dir.mkdir()
    jpg_path = dest_dir / "illustration_s1.jpg"
    generator = CodexImageGeneration(
        binary_name=a_stub_codex(tmp_path, f'printf "jpg" > "{jpg_path}"\n')
    )

    stored_path = generator.generate("prompt", str(dest_dir), "illustration_s1")

    assert stored_path == str(jpg_path)


def test_missing_binary_yields_none(tmp_path: Path) -> None:
    generator = CodexImageGeneration(binary_name=str(tmp_path / "no-such-codex"))

    stored_path = generator.generate("prompt", str(tmp_path), "illustration_s1")

    assert stored_path is None


def test_timeout_yields_none(tmp_path: Path) -> None:
    dest_dir = tmp_path / "images"
    dest_dir.mkdir()
    generator = CodexImageGeneration(
        binary_name=a_stub_codex(tmp_path, "sleep 5\n"), timeout_seconds=0.2
    )

    stored_path = generator.generate("prompt", str(dest_dir), "illustration_s1")

    assert stored_path is None

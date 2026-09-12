from pathlib import Path

import typst


class TypstCompileError(Exception):
    pass


class TypstCompiler:
    def compile(self, markup_path: Path, root_dir: Path, font_dirs: list[Path]) -> bytes:
        try:
            pdf_bytes = typst.compile(
                input=markup_path,
                root=root_dir,
                font_paths=font_dirs,
                ignore_system_fonts=True,
            )
        except (typst.TypstError, RuntimeError) as error:
            raise TypstCompileError(str(error)) from error
        if not isinstance(pdf_bytes, bytes):
            raise TypstCompileError(
                f"typst.compile returned {type(pdf_bytes).__name__} instead of bytes"
            )
        return pdf_bytes

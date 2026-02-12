"""Export files from a MinerU work directory into user-facing locations."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List


class ExportError(RuntimeError):
    pass


def unique_file_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    for n in range(2, 1000):
        candidate = path.with_name(f"{stem}_v{n}{suffix}")
        if not candidate.exists():
            return candidate

    raise ExportError(f"Too many name conflicts while exporting {path.name}")


def unique_dir_path(path: Path) -> Path:
    if not path.exists():
        return path

    name = path.name
    parent = path.parent
    for n in range(2, 1000):
        candidate = parent / f"{name}_v{n}"
        if not candidate.exists():
            return candidate

    raise ExportError(f"Too many name conflicts while exporting {path.name}")


def _copy_file(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def find_files_by_extension(*, workdir: Path, ext: str) -> List[Path]:
    workdir = workdir.resolve()
    ext = ext.lstrip(".")
    return sorted(workdir.glob(f"**/*.{ext}"))


def export_single_file(*, src: Path, dest_file: Path) -> Path:
    dest_file = unique_file_path(dest_file)
    return _copy_file(src, dest_file)


def export_tree(*, files: List[Path], workdir: Path, dest_root: Path) -> Path:
    """Copy files to dest_root, preserving their relative path under workdir."""
    workdir = workdir.resolve()
    dest_root.mkdir(parents=True, exist_ok=True)
    for src in files:
        rel = src.relative_to(workdir)
        _copy_file(src, dest_root / rel)
    return dest_root

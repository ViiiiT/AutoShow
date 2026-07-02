#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg"}
DEFAULT_DELETE_EXTENSIONS = {".lrc"}
IGNORABLE_NAMES = {".DS_Store", "Thumbs.db"}


@dataclass
class ImportStats:
    moved_audio: int = 0
    skipped_duplicates: int = 0
    renamed_conflicts: int = 0
    ignored_files: int = 0
    removed_dirs: int = 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge downloaded music into the AutoShow media/music library."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "download",
        help="Download/import folder. Default: ./download",
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=ROOT / "media" / "music",
        help="AutoShow music library folder. Default: ./media/music",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually move files. Without this flag the script only prints a dry run.",
    )
    parser.add_argument(
        "--purge-leftovers",
        action="store_true",
        help="After importing, delete any remaining non-audio files in the source folder.",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    library = args.library.resolve()
    if not source.exists():
        raise SystemExit(f"source folder does not exist: {source}")
    if not source.is_dir():
        raise SystemExit(f"source is not a folder: {source}")

    stats = merge_library(source, library, apply=args.apply, purge_leftovers=args.purge_leftovers)
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"\n{mode} summary")
    print(f"  moved audio:        {stats.moved_audio}")
    print(f"  skipped duplicates: {stats.skipped_duplicates}")
    print(f"  renamed conflicts:  {stats.renamed_conflicts}")
    print(f"  ignored files:      {stats.ignored_files}")
    print(f"  removed dirs:       {stats.removed_dirs}")
    if not args.apply:
        print("\nRun again with --apply to actually move files.")
    return 0


def merge_library(source: Path, library: Path, *, apply: bool, purge_leftovers: bool) -> ImportStats:
    stats = ImportStats()
    audio_files = sorted(
        path
        for path in source.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )
    if apply:
        library.mkdir(parents=True, exist_ok=True)
    for audio_path in audio_files:
        import_one_audio(audio_path, source, library, apply=apply, stats=stats)
    cleanup_source(source, apply=apply, purge_leftovers=purge_leftovers, stats=stats)
    return stats


def import_one_audio(
    audio_path: Path,
    source: Path,
    library: Path,
    *,
    apply: bool,
    stats: ImportStats,
) -> None:
    relative = audio_path.relative_to(source)
    if len(relative.parts) < 3:
        stats.ignored_files += 1
        print(f"IGNORE unexpected layout: {relative}")
        return

    artist = relative.parts[0]
    album = relative.parts[1]
    destination_dir = library_child(library, artist, apply=apply) / album
    destination_dir = library_child(destination_dir.parent, album, apply=apply)
    destination = destination_dir / audio_path.name
    final_audio_path, duplicate = resolve_destination(audio_path, destination)

    if duplicate:
        stats.skipped_duplicates += 1
        print(f"DUPLICATE remove source: {relative}")
        if apply:
            audio_path.unlink()
        return

    if final_audio_path != destination:
        stats.renamed_conflicts += 1
        print(f"CONFLICT rename: {relative} -> {final_audio_path.relative_to(library)}")
    else:
        print(f"MOVE: {relative} -> {final_audio_path.relative_to(library)}")

    stats.moved_audio += 1
    if apply:
        final_audio_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(audio_path), str(final_audio_path))


def library_child(parent: Path, name: str, *, apply: bool) -> Path:
    existing = matching_child_dir(parent, name)
    if existing:
        return existing
    child = parent / name
    if apply:
        child.mkdir(parents=True, exist_ok=True)
    return child


def matching_child_dir(parent: Path, name: str) -> Path | None:
    if not parent.exists():
        return None
    wanted = normalized_name(name)
    for child in parent.iterdir():
        if child.is_dir() and normalized_name(child.name) == wanted:
            return child
    return None


def normalized_name(value: str) -> str:
    return " ".join(value.casefold().split())


def resolve_destination(source: Path, destination: Path) -> tuple[Path, bool]:
    if not destination.exists():
        return destination, False
    if same_file_content(source, destination):
        return destination, True
    return unique_path(destination), False


def unique_path(path: Path) -> Path:
    for number in range(2, 10000):
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find a free filename for {path}")


def same_file_content(left: Path, right: Path) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False
    return file_hash(left) == file_hash(right)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cleanup_source(source: Path, *, apply: bool, purge_leftovers: bool, stats: ImportStats) -> None:
    for path in sorted(source.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_file():
            if path.name in IGNORABLE_NAMES or path.suffix.lower() in DEFAULT_DELETE_EXTENSIONS or purge_leftovers:
                stats.ignored_files += 1
                print(f"DELETE leftover: {path.relative_to(source)}")
                if apply:
                    path.unlink()
            continue
        if path.is_dir() and not any(path.iterdir()):
            stats.removed_dirs += 1
            print(f"REMOVE empty dir: {path.relative_to(source)}")
            if apply:
                path.rmdir()


if __name__ == "__main__":
    raise SystemExit(main())

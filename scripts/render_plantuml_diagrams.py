#!/usr/bin/env python3
"""Extract PlantUML code blocks from docs and emit standalone .puml files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Tuple
import subprocess


def iter_markdown_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.md")):
        # Skip generated folders (e.g., the diagrams output directory itself).
        if "diagrams" in path.parts:
            continue
        yield path


def extract_diagrams(markdown: Path) -> List[Tuple[int, str]]:
    diagrams: List[Tuple[int, str]] = []
    capturing = False
    buffer: List[str] = []
    start_line = 0
    with markdown.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not capturing and stripped.lower().startswith("```plantuml"):
                capturing = True
                buffer = []
                start_line = line_number + 1
                continue
            if capturing and stripped == "```":
                capturing = False
                diagrams.append((start_line, "".join(buffer)))
                buffer = []
                continue
            if capturing:
                buffer.append(raw)
    if capturing:
        raise ValueError(
            f"Unterminated ```plantuml block in {markdown} starting at line {start_line}"
        )
    return diagrams


def write_puml(
    output_dir: Path, markdown: Path, diagrams: List[Tuple[int, str]]
) -> List[tuple[Path, str]]:
    rel = markdown.relative_to(output_dir.parent)
    slug = rel.as_posix().replace("/", "_").replace(".", "_")
    written: List[tuple[Path, str]] = []
    for index, (line_number, body) in enumerate(diagrams, start=1):
        filename = f"{slug}_diagram_{index:02d}.puml"
        target = output_dir / filename
        header = f"' Extracted from {rel}:{line_number}\n"
        content = header + body
        target.write_text(content, encoding="utf-8")
        written.append((target, content))
    return written


def clean_directory(output_dir: Path) -> None:
    if not output_dir.exists():
        return
    for path in output_dir.iterdir():
        if path.name.startswith("."):
            continue
        if path.is_file():
            path.unlink()


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract PlantUML code blocks from markdown files under docs/."
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs",
        help="Root directory that contains markdown files (default: docs/).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Destination directory for .puml files (default: DOCS/diagrams).",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Also render SVG files using the PlantUML CLI.",
    )
    parser.add_argument(
        "--plantuml-jar",
        type=Path,
        default=Path("/usr/share/plantuml/plantuml.jar"),
        help="Path to plantuml.jar when --render is used.",
    )
    args = parser.parse_args(argv)

    docs_dir = args.docs_dir
    output_dir = args.output_dir or docs_dir / "diagrams"
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_directory(output_dir)

    markdown_files = list(iter_markdown_files(docs_dir))
    total_written: List[tuple[Path, str]] = []
    for md in markdown_files:
        diagrams = extract_diagrams(md)
        if not diagrams:
            continue
        total_written.extend(write_puml(output_dir, md, diagrams))

    if not total_written:
        print("No PlantUML diagrams found under", docs_dir, file=sys.stderr)
        return 0
    print(f"Generated {len(total_written)} PlantUML source files in {output_dir}")

    if args.render:
        jar = args.plantuml_jar
        if not jar.exists():
            raise FileNotFoundError(f"PlantUML jar not found at {jar}")
        for puml_path, content in total_written:
            svg_path = puml_path.with_suffix(".svg")
            cmd = [
                "java",
                "-Djava.awt.headless=true",
                "-jar",
                str(jar),
                "-tsvg",
                "-pipe",
            ]
            result = subprocess.run(
                cmd, input=content.encode("utf-8"), capture_output=True, check=True
            )
            svg_path.write_bytes(result.stdout)
        print(f"Rendered {len(total_written)} SVG files in {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

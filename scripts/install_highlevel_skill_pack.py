#!/usr/bin/env python3
"""
Install the shared HighLevel skill and apply generated HighLevel overlays to an existing skill library.

Example:
  python scripts/install_highlevel_skill_pack.py --skills-root ~/.claude/skills
  python scripts/install_highlevel_skill_pack.py --skills-root ./skills --dry-run
"""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILLS = REPO_ROOT / "skills"
MANIFEST = REPO_ROOT / "migration" / "skills-highlevel-manifest.csv"
OVERLAYS = REPO_ROOT / "migration" / "overlays"

MARKER_PREFIX = "<!-- HIGHLEVEL-INTEGRATION-START:"
MARKER_SUFFIX = "<!-- HIGHLEVEL-INTEGRATION-END:"


def load_manifest():
    rows = []
    with MANIFEST.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def find_skill_file(skill_dir: Path) -> Path | None:
    for name in ("SKILL.md", "skill.md"):
        candidate = skill_dir / name
        if candidate.exists():
            return candidate
    return None


def replace_or_append_overlay(text: str, overlay: str, skill_name: str) -> str:
    start = f"{MARKER_PREFIX} {skill_name} -->"
    end = f"{MARKER_SUFFIX} {skill_name} -->"
    if start in text and end in text:
        before = text.split(start, 1)[0].rstrip()
        after = text.split(end, 1)[1].lstrip()
        return f"{before}\n\n{overlay.rstrip()}\n\n{after}".rstrip() + "\n"
    return text.rstrip() + "\n\n" + overlay.rstrip() + "\n"


def copy_shared_skill(target_root: Path, dry_run: bool):
    src = SOURCE_SKILLS / "highlevel-api"
    dest = target_root / "highlevel-api"
    if dry_run:
        action = "Would update" if dest.exists() else "Would copy"
        print(f"{action} shared skill: {dest}")
        return
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    print(f"Installed shared skill: {dest}")


def apply_overlays(target_root: Path, dry_run: bool):
    manifest_rows = load_manifest()
    changed = [row for row in manifest_rows if row["update"] != "No"]

    applied = []
    skipped = []

    for row in changed:
        skill = row["skill"]
        skill_dir = target_root / skill
        skill_file = find_skill_file(skill_dir)
        overlay_path = OVERLAYS / f"{skill}.md"

        if not overlay_path.exists():
            skipped.append((skill, "overlay-missing"))
            continue

        if skill_file is None:
            skipped.append((skill, "skill-file-missing"))
            continue

        original = skill_file.read_text(encoding="utf-8")
        overlay = overlay_path.read_text(encoding="utf-8")
        updated = replace_or_append_overlay(original, overlay, skill)

        if dry_run:
            applied.append((skill, "would-update"))
            continue

        backup = skill_file.with_suffix(skill_file.suffix + ".bak")
        if not backup.exists():
            backup.write_text(original, encoding="utf-8")
        skill_file.write_text(updated, encoding="utf-8")
        applied.append((skill, "updated"))

    return applied, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-root", required=True, help="Path to the existing skill library root")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing files")
    args = parser.parse_args()

    target_root = Path(args.skills_root).expanduser().resolve()
    target_root.mkdir(parents=True, exist_ok=True)

    copy_shared_skill(target_root, args.dry_run)
    applied, skipped = apply_overlays(target_root, args.dry_run)

    print("")
    print("Overlay results")
    for skill, status in applied:
        print(f"  {skill}: {status}")
    if skipped:
        print("")
        print("Skipped")
        for skill, status in skipped:
            print(f"  {skill}: {status}")


if __name__ == "__main__":
    main()

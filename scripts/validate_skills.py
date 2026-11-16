#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SECRET_PATTERNS = [
    re.compile(r"(?i)authorization:\s*bearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9._~+/=-]{20,}")
]

@dataclass(frozen=True)
class Meta:
    name: str
    version: str
    description: str
    path: Path

def parse_frontmatter(path: Path) -> Meta:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: missing opening frontmatter")
    try:
        end = lines[1:].index("---") + 1
    except ValueError as exc:
        raise ValueError(f"{path}: missing closing frontmatter") from exc

    data = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{path}: invalid frontmatter line {line!r}")
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("'\"")

    missing = {"name", "version", "description"} - data.keys()
    if missing:
        raise ValueError(f"{path}: missing {sorted(missing)}")
    return Meta(data["name"], data["version"], data["description"], path)

def collect():
    metas = {}
    errors = []
    for directory in sorted((ROOT / "skills").iterdir()):
        if not directory.is_dir():
            continue
        entry = directory / "SKILL.md"
        if not entry.exists():
            errors.append(f"{directory}: missing SKILL.md")
            continue
        try:
            meta = parse_frontmatter(entry)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if meta.name != directory.name:
            errors.append(f"{entry}: name must match directory")
        if not NAME.fullmatch(meta.name):
            errors.append(f"{entry}: invalid skill name")
        if not SEMVER.fullmatch(meta.version):
            errors.append(f"{entry}: invalid semver")
        if not 20 <= len(meta.description) <= 600:
            errors.append(f"{entry}: description length must be 20..600")
        metas[meta.name] = meta
    return metas, errors

def validate_registry(metas):
    errors = []
    path = ROOT / "skill-registry.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not SEMVER.fullmatch(data.get("repository_version", "")):
        errors.append("registry: repository_version must be semver")
    seen = set()
    for item in data.get("skills", []):
        name = item.get("name")
        if name in seen:
            errors.append(f"registry: duplicate {name}")
        seen.add(name)
        if name not in metas:
            errors.append(f"registry: missing skill directory {name}")
            continue
        if item.get("version") != metas[name].version:
            errors.append(f"registry: version mismatch for {name}")
        if item.get("path") != f"skills/{name}/SKILL.md":
            errors.append(f"registry: invalid path for {name}")
        if item.get("contract") != f"contracts/{name}.json":
            errors.append(f"registry: invalid contract path for {name}")
        if item.get("status") not in {"active", "experimental", "deprecated"}:
            errors.append(f"registry: invalid status for {name}")
    for name in set(metas) - seen:
        errors.append(f"registry: unregistered skill {name}")
    return data, errors

def validate_contract(name):
    path = ROOT / "contracts" / f"{name}.json"
    if not path.exists():
        return [f"{path}: missing contract"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{path}: invalid JSON: {exc}"]
    errors = []
    required = {"skill", "contract_version", "inputs", "outputs", "hard_guards"}
    if missing := required - data.keys():
        errors.append(f"{path}: missing {sorted(missing)}")
        return errors
    if data["skill"] != name:
        errors.append(f"{path}: skill name mismatch")
    if not SEMVER.fullmatch(data["contract_version"]):
        errors.append(f"{path}: invalid contract version")
    for key in ("inputs", "outputs", "hard_guards"):
        if not isinstance(data[key], list) or not data[key]:
            errors.append(f"{path}: {key} must be non-empty list")
    for item in data.get("inputs", []):
        if not isinstance(item, dict) or not {"name","required","description"} <= item.keys():
            errors.append(f"{path}: malformed input")
    for item in data.get("outputs", []):
        if not isinstance(item, dict) or not {"name","description"} <= item.keys():
            errors.append(f"{path}: malformed output")
    return errors

def validate_privacy():
    errors = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        rel = path.relative_to(ROOT)
        if any(part.lower() in {"private","secrets","cookies","sessions"} for part in rel.parts):
            errors.append(f"{rel}: private path must not be tracked")
        if path.suffix.lower() in {".md",".json",".csv",".py",".yml",".yaml",".sh"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    errors.append(f"{rel}: suspicious secret-like value")
    return errors

def validate_repository():
    metas, errors = collect()
    _, registry_errors = validate_registry(metas)
    errors += registry_errors
    for name in sorted(metas):
        errors += validate_contract(name)
    errors += validate_privacy()
    return errors

def main():
    errors = validate_repository()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Validation failed: {len(errors)} error(s)", file=sys.stderr)
        return 1
    metas, _ = collect()
    print(f"Validation passed: {len(metas)} skills checked.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

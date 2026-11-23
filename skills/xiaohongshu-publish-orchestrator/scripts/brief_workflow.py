#!/usr/bin/env python3
"""Local package validation and atomic submission ledger; never operates a browser."""
import argparse
import datetime as dt
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zlib

TERMINAL = {"UNDER_REVIEW", "SUBMITTED_UNDER_REVIEW", "PUBLISHED", "REJECTED"}
UNCERTAIN = {"SUBMITTING", "UNKNOWN", "SUBMISSION_UNKNOWN", "准备提交"}
REQUIRED = ("account_matches", "dedupe_clear", "body_complete", "privacy_pass",
            "image_positions", "images_loaded", "markers_removed", "cover_first",
            "preview_complete", "public_visibility")


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def decision(state):
    values = {state.get("stage"), state.get("submission_result"), state.get("review_status")}
    if values & (TERMINAL | {"审核中", "已公开", "未通过"}):
        return "SYNC_ONLY"
    if values & UNCERTAIN:
        return "VERIFY_PLATFORM_FIRST"
    return "CONTINUE"


def png_dimensions(path):
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a PNG: {path.name}")
    off, compressed, dimensions, ended = 8, [], None, False
    while off + 12 <= len(raw):
        length = struct.unpack(">I", raw[off:off + 4])[0]
        kind = raw[off + 4:off + 8]
        data = raw[off + 8:off + 8 + length]
        end = off + 12 + length
        if end > len(raw):
            raise ValueError(f"Truncated PNG: {path.name}")
        crc = struct.unpack(">I", raw[end - 4:end])[0]
        if zlib.crc32(kind + data) & 0xffffffff != crc:
            raise ValueError(f"PNG checksum failed: {path.name}")
        if kind == b"IHDR":
            dimensions = struct.unpack(">II", data[:8])
        elif kind == b"IDAT":
            compressed.append(data)
        elif kind == b"IEND":
            ended = end == len(raw)
            break
        off = end
    if not dimensions or not all(dimensions) or not ended or not compressed:
        raise ValueError(f"Incomplete PNG: {path.name}")
    if not zlib.decompress(b"".join(compressed)):
        raise ValueError(f"Empty PNG pixel stream: {path.name}")
    return dimensions


def local_file(directory, name):
    file = (directory / name).resolve()
    if not file.is_relative_to(directory.resolve()) or not file.is_file():
        raise ValueError(f"Missing or external package file: {name}")
    return file


def validate_manifest(directory, date, manifest):
    if manifest.get("date") != date:
        raise ValueError("Manifest date differs from requested date")
    images = manifest.get("images", manifest.get("image_order", []))
    if not images:
        raise ValueError("Image manifest is empty")
    if manifest.get("images_expected", len(images)) != len(images):
        raise ValueError("Image count differs from manifest")
    seen, result = set(), []
    for number, item in enumerate(images, 1):
        if item.get("number") != number or not item.get("caption"):
            raise ValueError("Image sequence or caption is incomplete")
        file = local_file(directory, item["file"])
        if file in seen:
            raise ValueError("Repeated original image file")
        seen.add(file)
        sha = hashlib.sha256(file.read_bytes()).hexdigest()
        if sha != item.get("sha256"):
            raise ValueError(f"Image hash differs: {file.name}")
        width, height = png_dimensions(file)
        result.append(dict(item, width=width, height=height))
    return result


def inline(text):
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # URLs remain visible even when a platform strips hyperlink attributes.
    return re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1（\2）", text)


def table_cells(line):
    return [x.strip() for x in line.strip().strip("|").split("|")]


def render_markdown(markdown, images):
    lines, blocks, found, i = markdown.splitlines(), [], [], 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        image = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        if image:
            number = len(found) + 1
            if number > len(images) or image.group(2) != images[number - 1]["file"]:
                raise ValueError("Markdown images differ from manifest order")
            found.append(image.group(2))
            blocks.append(f"<p>〔插图{number}〕</p>")
            caption = images[number - 1]["caption"]
            # Some source Markdown already has a separate caption; do not duplicate it.
            following = next((x.strip() for x in lines[i + 1:] if x.strip()), "")
            if following != caption:
                blocks.append(f"<p>{inline(caption)}</p>")
        elif i + 1 < len(lines) and "|" in line and re.fullmatch(r"[| :\-]+", lines[i + 1].strip()):
            headers = table_cells(line)
            i += 2
            while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                cells = table_cells(lines[i])
                if len(cells) != len(headers):
                    raise ValueError("Table row has missing cells")
                blocks.append("<p>" + "；".join(f"{inline(h)}：{inline(c)}" for h, c in zip(headers, cells)) + "</p>")
                i += 1
            continue
        elif re.match(r"^#{1,6} ", line):
            level, title = line.split(" ", 1)
            blocks.append(f"<h{len(level)}>{inline(title)}</h{len(level)}>")
        elif line.startswith("```") or "" in line:
            raise ValueError("Resolve code fences or proprietary citations before import")
        else:
            blocks.append(f"<p>{inline(line)}</p>")
        i += 1
    if len(found) != len(images):
        raise ValueError("Markdown lacks original image positions")
    return "\n".join(blocks)


def check_evidence(directory, state, checks, date):
    if state.get("date") != date or checks.get("date") != date:
        raise ValueError("State/check date mismatch")
    stamp = dt.datetime.fromisoformat(checks["checked_at"])
    if stamp.tzinfo is None:
        raise ValueError("Platform check timestamp needs timezone")
    age = (dt.datetime.now(dt.timezone.utc) - stamp).total_seconds()
    if not 0 <= age <= 900:
        raise ValueError("Platform checks are stale")
    local_file(directory, checks["evidence_file"])


def begin_submit(directory, state, checks, date):
    action = decision(state)
    if action != "CONTINUE":
        return {"action": action, "stage": state.get("stage")}
    check_evidence(directory, state, checks, date)
    if any(checks.get(key) is not True for key in REQUIRED):
        raise ValueError("Not all required platform checks passed")
    if checks.get("images_expected", 0) <= 0 or checks.get("images_loaded_count") != checks["images_expected"] or checks["images_expected"] != state.get("images_expected"):
        raise ValueError("Platform image count mismatch")
    state.update(stage="SUBMITTING", submission_result="准备提交", submission_intent_at=now(), checks=checks)
    atomic_json(directory / "进度.json", state)
    return {"action": "SUBMIT_ONCE", "stage": "SUBMITTING"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "status", "prepare", "begin-submit", "resolve-unsubmitted", "result"])
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--date", required=True, help="Explicit date in the configured timezone")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--checks", type=Path)
    parser.add_argument("--result", choices=["UNDER_REVIEW", "PUBLISHED", "REJECTED", "UNKNOWN"])
    parser.add_argument("--evidence")
    args = parser.parse_args()
    dt.date.fromisoformat(args.date)
    directory = args.directory.resolve()
    if directory.name != args.date:
        raise ValueError("Directory must be isolated by the explicit date")
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".workflow.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = directory / "进度.json"
        state = read_json(path) if path.exists() else {"date": args.date, "stage": "STARTED", "attempts": []}
        if state.get("date") != args.date:
            raise ValueError("Ledger belongs to another date")
        output = {"action": decision(state), "stage": state["stage"]}
        if args.command == "start":
            state.setdefault("attempts", []).append({"at": now(), "action": output["action"]})
            atomic_json(path, state)
        elif args.command == "prepare":
            if output["action"] == "CONTINUE":
                if args.markdown is None:
                    raise ValueError("A complete sanitized Markdown file is required")
                manifest = read_json(args.manifest) if args.manifest else state
                images = validate_manifest(directory, args.date, manifest)
                markdown = args.markdown.read_text(encoding="utf-8")
                if args.date not in markdown.splitlines()[0]:
                    raise ValueError("Markdown lacks the explicit original date in its title")
                rendered = render_markdown(markdown, images)
                derived = []
                for item in images:
                    dest = directory / f"{item['number']:02d}-上传兼容.jpg"
                    subprocess.run(["sips", "-s", "format", "jpeg", str(directory / item["file"]), "--out", str(dest)], check=True, capture_output=True)
                    derived.append({"number": item["number"], "file": dest.name, "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()})
                (directory / "发布正文.html").write_text(rendered, encoding="utf-8")
                state.update(stage="MEDIA_VERIFIED", images_expected=len(images), image_order=images, upload_derivatives=derived)
                atomic_json(path, state)
                output = {"action": "CONTINUE", "stage": "MEDIA_VERIFIED", "images": len(images)}
        elif args.command == "begin-submit":
            output = begin_submit(directory, state, read_json(args.checks), args.date)
        elif args.command == "resolve-unsubmitted":
            if decision(state) != "VERIFY_PLATFORM_FIRST":
                raise ValueError("Only an unresolved submission may be cleared")
            checks = read_json(args.checks)
            check_evidence(directory, state, checks, args.date)
            if checks.get("submission_explicitly_absent") is not True or checks.get("same_draft_verified") is not True:
                raise ValueError("Explicit platform and same-draft evidence is required")
            state.setdefault("attempts", []).append({"at": now(), "action": "CONFIRMED_NOT_SUBMITTED", "evidence": checks})
            state.update(stage="DRAFT", submission_result="NOT_SUBMITTED")
            state.pop("review_status", None)
            atomic_json(path, state)
            output = {"action": "CONTINUE", "stage": "DRAFT"}
        elif args.command == "result":
            if not args.result or not args.evidence:
                raise ValueError("Result and evidence are required")
            local_file(directory, args.evidence)
            if state.get("stage") == "PUBLISHED" and args.result != "PUBLISHED":
                raise ValueError("Do not downgrade an explicitly published receipt")
            if decision(state) == "SYNC_ONLY" and args.result == "UNKNOWN":
                raise ValueError("Do not replace a confirmed receipt with uncertainty")
            state.update(stage=args.result, submission_result=args.result, review_status={"UNDER_REVIEW": "审核中", "PUBLISHED": "已公开", "REJECTED": "未通过", "UNKNOWN": "待核实"}[args.result], submission_evidence=args.evidence, result_checked_at=now())
            atomic_json(path, state)
            output = {"stage": args.result, "action": decision(state)}
        print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, struct.error, zlib.error, subprocess.CalledProcessError) as exc:
        print(json.dumps({"action": "STOP", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2)

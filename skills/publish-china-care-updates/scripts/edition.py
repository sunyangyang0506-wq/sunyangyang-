"""Validate one editorial packet and render its original captioned image and video."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont, ImageOps

LANES = {"service", "policy", "research", "drug", "device", "partnership"}
STAGES = {
    "service": {"listed_service", "operational_change"},
    "policy": {"announcement", "pilot", "implemented"},
    "research": {"project_feasibility", "preclinical", "human_feasibility", "phase_1",
                 "phase_2", "phase_3", "observational", "safety_update"},
    "drug": {"preclinical", "trial_authorized", "phase_1", "phase_2", "phase_3",
             "under_review", "conditional_approval", "marketing_approval", "safety_update"},
    "device": {"project_feasibility", "preclinical", "human_feasibility", "under_review",
               "marketing_approval", "safety_update"},
    "partnership": {"public_call", "announced_agreement"},
}
CHECKS = ("facts", "rights", "english", "privacy", "editorial")
LINK = re.compile(r"https://[^\s]+")
CLINICAL = {"research", "drug", "device"}
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")

def require(condition, message):
    if not condition:
        raise ValueError(message)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def today():
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()

def line(value):
    return isinstance(value, str) and bool(value.strip())

def weburl(value):
    u = urlsplit(value)
    return u.scheme == "https" and bool(u.hostname) and not u.username and not u.password

def post_length(text):
    # Conservative for English. Count each full URL as 23; do not shorten the real link.
    stripped = LINK.sub("", text)
    return sum(1 if ord(c) <= 0x10ff or 0x2000 <= ord(c) <= 0x200d or
               0x2010 <= ord(c) <= 0x201f or 0x2032 <= ord(c) <= 0x2037 else 2
               for c in stripped) + 23 * len(LINK.findall(text))

def validate(d):
    day = date.fromisoformat(d["day"])
    require(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", d["story_key"]), "Invalid story_key")
    require(type(d["revision"]) is int and d["revision"] >= 1, "Invalid revision")
    require(d["lane"] in LANES and d["stage"] in STAGES[d["lane"]], "Lane/stage mismatch")
    require(d["publication_type"] in {"news", "guide", "background", "correction"}, "Wrong edition type")
    require(line(d["scope"]) and line(d["access"]), "Add jurisdiction/scope and access status")
    require(d["rights"] in {"original_text_graphics", "licensed_mix"}, "Unknown rights mode")
    assets = d.get("assets", [])
    require(isinstance(assets, list) and (bool(assets) == (d["rights"] == "licensed_mix")),
            "List the assets for a licensed mix")
    asset_ids = set()
    for a in assets:
        require(line(a["id"]) and a["id"] not in asset_ids and a["type"] in {"photo", "clip"}, "Invalid asset")
        require(weburl(a["source_url"]) and weburl(a["license_url"]) and line(a["credit"]),
                "Add original asset and rights evidence")
        require(all(a.get(k) is True for k in ("commercial", "derivatives", "people_cleared")),
                "Asset permission incomplete")
        require(re.fullmatch(r"[a-f0-9]{64}", a["sha256"]) and line(a["file"]), "Missing asset identity")
        asset_ids.add(a["id"])
    require(all(d["review"].get(k) is True for k in CHECKS), "Editorial review incomplete")
    require(isinstance(d["unknowns"], list), "List remaining uncertainties")
    event = date.fromisoformat(d["event_date"]) if d["event_date"] else None
    sources = {}
    dates = []
    for s in d["sources"]:
        require(line(s["id"]) and s["id"] not in sources, "Duplicate or empty source")
        require(weburl(s["url"]) and line(s["origin"]) and line(s["publisher"]), "Incomplete source")
        require(date.fromisoformat(s["checked_on"]) == day, "Reopen each source for the edition day")
        if s["published_on"]:
            stamp = date.fromisoformat(s["published_on"])
            require(stamp <= day, "Future publication date")
            dates.append(stamp)
        sources[s["id"]] = s
    require(sources, "No sources")
    if d["publication_type"] == "news":
        require(any(0 <= (day - t).days <= 7 for t in dates + ([event] if event else [])),
                "No recent dated development; use an explicitly labeled guide or background")
    claims = set()
    for claim in d["claims"]:
        require(line(claim["id"]) and claim["id"] not in claims and line(claim["fact"]),
                "Missing or duplicate claim")
        require(bool(claim["evidence"]), "Claim needs primary support")
        require(all(e["source"] in sources and line(e["locator"]) for e in claim["evidence"]),
                "Evidence pointer is incomplete")
        require(any(sources[e["source"]]["kind"] in {"official", "primary_study", "registry"}
                    for e in claim["evidence"]), "Claim lacks primary evidence")
        claims.add(claim["id"])
    require(claims, "No checked claims")
    if d["lane"] in CLINICAL:
        clinical = d["clinical"]
        for k in ("subject", "population", "jurisdiction", "limitations"):
            require(line(clinical[k]), "Missing clinical " + k)
        if d["stage"] in {"marketing_approval", "conditional_approval"}:
            require(line(clinical["indication"]) and clinical["regulator_source"] in sources and
                    sources[clinical["regulator_source"]]["kind"] == "official", "Missing regulatory evidence")
        if d["stage"].startswith("phase_") or d["stage"] == "human_feasibility":
            require("endpoint" in clinical and "n" in clinical and "comparator" in clinical,
                    "Record endpoint, sample size and comparator; null if unreported")
    copy = d["public_copy"]
    require(all(line(copy[k]) and post_length(copy[k]) <= 280 for k in ("root", "video")), "Post too long or empty")
    require(any(s["url"] in LINK.findall(copy["root"]) for s in sources.values()), "Root must link its evidence")
    require(line(copy["alt"]) and len(copy["alt"]) <= 1000, "Add an English image description")
    require(3 <= len(d["slides"]) <= 5 and line(d["source_credit"]), "Use 3–5 slides with credit")
    for s in d["slides"]:
        require(all(line(s[k]) for k in ("label", "headline", "body")), "Slide text missing")
        require(isinstance(s["claim_ids"], list) and set(s["claim_ids"]) <= claims, "Unknown slide claim")
    require({s["visual"] for s in d["slides"] if s.get("visual")} == asset_ids,
            "Slides must use the listed media and only those media")
    require(set().union(*(set(s["claim_ids"]) for s in d["slides"])), "Slides need checked evidence")

def font(name, size):
    filename = name + ".ttf"
    local = FONT_DIR / filename
    return ImageFont.truetype(str(local) if local.exists() else filename, size)

def block(draw, value, family, size, minimum, width, height):
    for pts in range(size, minimum - 1, -2):
        face = font(family, pts)
        lines = []
        for word in value.split():
            candidate = (lines[-1] + " " + word) if lines else word
            if lines and draw.textlength(candidate, font=face) <= width:
                lines[-1] = candidate
            else:
                lines.append(word)
        leading = round(pts * 1.30)
        if len(lines)*leading <= height and max(draw.textlength(t, font=face) for t in lines) <= width:
            return face, lines, leading
    raise ValueError("Text does not fit. Shorten this field: " + value)

def panel(d, slide, index, visual=None, credit=None):
    image = Image.new("RGB", (1280, 720), "#FAF7EF")
    draw = ImageDraw.Draw(image)
    ink, jade, muted = "#102E31", "#126C60", "#334F50"
    def paint(text, x, y, family, size, minimum, width, height, color):
        face, lines, leading = block(draw, text, family, size, minimum, width, height)
        for offset, row in enumerate(lines):
            draw.text((x, y + offset*leading), row, fill=color, font=face, anchor="lt")
    draw.rectangle((0, 0, 21, 720), fill=jade)
    paint(slide["label"], 72, 51, "DejaVuSans-Bold", 26, 22, 1090, 38, jade)
    draw.line((72, 111, 1208, 111), fill="#A6B9AE", width=2)
    width = 608 if visual else 1136
    paint(slide["headline"], 72, 154, "DejaVuSerif", 68 if visual else 84, 42, width, 212, ink)
    paint(slide["body"], 76, 380, "DejaVuSans", 33 if visual else 39, 26, width-20, 198, muted)
    if visual:
        image.paste(ImageOps.fit(visual.convert("RGB"), (480, 342)), (724, 170))
        paint(credit, 724, 531, "DejaVuSans", 21, 15, 480, 52, muted)
    draw.line((72, 598, 1208, 598), fill="#A6B9AE", width=2)
    paint(d["source_credit"], 74, 633, "DejaVuSans", 24, 18, 796, 55, muted)
    date_label = f'{d["day"]}   |   {index+1}/{len(d["slides"])}'
    draw.text((1205, 634), date_label, anchor="rt", font=font("DejaVuSans", 22), fill=jade)
    return image

def input_asset(asset, directory):
    require(directory is not None, "Pass --media-dir for licensed assets")
    path = (directory / asset["file"]).resolve()
    require(path.is_relative_to(directory.resolve()) and path.is_file(), "Asset missing or outside media directory")
    require(sha(path) == asset["sha256"], "Asset digest mismatch")
    return path

def encode_segment(tmp, still, clip, seconds, index):
    target = tmp / f"part-{index}.mp4"
    ff = ["ffmpeg","-hide_banner","-loglevel","error","-y","-loop","1","-framerate","25","-i",str(still)]
    if clip:
        ff += ["-protocol_whitelist","file,pipe","-f","mov","-i",str(clip),"-filter_complex",
               "[1:v]scale=480:342:force_original_aspect_ratio=increase,crop=480:342,setsar=1[v];"
               "[0:v][v]overlay=724:170:repeatlast=1[out]","-map","[out]"]
    ff += ["-an","-t",str(seconds),"-r","25","-pix_fmt","yuv420p","-c:v","libx264","-threads","2",str(target)]
    subprocess.run(ff,check=True)
    return target

def render(packet, out, media_dir=None):
    d = json.loads(packet.read_text())
    validate(d)
    out.mkdir(parents=True, exist_ok=True)
    # Stage all outputs before replacing the previous manifest.
    with tempfile.TemporaryDirectory(dir=out) as tempdir:
        tmp = Path(tempdir)
        captions, shots = [], []
        assets = {a["id"]: a for a in d.get("assets", [])}
        has_clips = any(a["type"] == "clip" for a in assets.values())
        elapsed = 0
        for i, slide in enumerate(d["slides"]):
            filename = f"slide-{i}.png"
            visual, credit, clip = None, None, None
            if slide.get("visual"):
                a = assets[slide["visual"]]
                path = input_asset(a, media_dir)
                credit = a["credit"]
                if a["type"] == "clip":
                    clip = path
                    path = tmp / f"poster-{i}.png"
                    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-protocol_whitelist","file,pipe",
                                    "-f","mov","-i",str(clip),"-frames:v","1",str(path)],check=True)
                with Image.open(path) as im:
                    visual = ImageOps.exif_transpose(im).convert("RGB")
            panel(d, slide, i, visual, credit).save(tmp / filename)
            caption = slide["headline"] + "\n" + slide["body"]
            seconds = max(5, min(9, round(len(caption.split()) / 2.8)))
            if has_clips:
                segment = encode_segment(tmp, tmp/filename, clip, seconds, i)
                shots.append(f"file '{segment.name}'")
            else:
                shots.extend([f"file '{filename}'", f"duration {seconds}"])
            fmt = lambda t: f"00:{t//60:02}:{t%60:02},000"
            captions.append(f"{i+1}\n{fmt(elapsed)} --> {fmt(elapsed+seconds)}\n{caption}\n")
            elapsed += seconds
        require(elapsed <= 30, "Shorten slide copy or use fewer slides for a 30-second edition")
        if not has_clips:
            shots.append(f"file '{filename}'")
        (tmp/"frames.txt").write_text("\n".join(shots)+"\n")
        if has_clips:
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0",
                            "-i",str(tmp/"frames.txt"),"-c","copy","-movflags","+faststart",
                            str(tmp/"explainer.mp4")],check=True)
        else:
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0",
                        "-i",str(tmp/"frames.txt"),"-t",str(elapsed),"-vf","fps=25","-pix_fmt","yuv420p",
                        "-c:v","libx264","-threads","2","-movflags","+faststart",str(tmp/"explainer.mp4")], check=True)
        (tmp/"slide-0.png").rename(tmp/"card.png")
        (tmp/"captions.srt").write_text("\n".join(captions))
        names = ("card.png","explainer.mp4","captions.srt")
        manifest = {"edition_sha256":sha(packet), "media_sha256":{k:sha(tmp/k) for k in names},
                    "duration_seconds":elapsed}
        (tmp/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        for name in (*names,"manifest.json"):
            (tmp/name).replace(out/name)
    return manifest

if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("packet",type=Path)
    a.add_argument("--out",type=Path,required=True)
    a.add_argument("--media-dir",type=Path)
    args = a.parse_args()
    print(json.dumps(render(args.packet,args.out,args.media_dir),indent=2))

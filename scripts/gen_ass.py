"""
SRT → ASS converter with dual bilingual styles.

Reads a bilingual SRT (English + Korean lines per block) and generates an ASS
file with two styles:
  - Korean: major, top area (Noto Sans KR Medium 39pt, bold, opaque black box)
  - English: minor, bottom area (Noto Sans KR DemiLight 27pt, slightly transparent)

These settings were finalized through v1~v6 iterative testing.

Usage:
  python gen_ass.py --srt input.srt --ass output.ass
  python gen_ass.py --srt input.srt --ass output.ass --res 1920x1080
"""
import re
import argparse

# ── v6 Final Style Definitions ──────────────────────────────────
# Tested and approved settings. Change only if user explicitly requests.
DEFAULT_STYLES = {
    "korean": {
        "fontname": "Noto Sans KR Medium",
        "fontsize": 39,
        "bold": 1,
        "primary_colour": "&H00FFFFFF",  # white
        "back_colour": "&HC0000000",  # semi-transparent black box
        "border_style": 3,  # opaque box
        "outline": 4,  # box padding (BorderStyle=3 needs >0 to render)
        "shadow": 0,
        "spacing": 0.5,
        "margin_v": 90,
    },
    "english": {
        "fontname": "Noto Sans KR DemiLight",
        "fontsize": 27,
        "bold": 0,
        "primary_colour": "&H20FFFFFF",  # slightly transparent white
        "back_colour": "&HC0000000",
        "border_style": 3,
        "outline": 4,  # box padding (BorderStyle=3 needs >0 to render)
        "shadow": 0,
        "spacing": 0.3,
        "margin_v": 14,
    },
}


def build_ass_header(res_x, res_y, styles=None):
    s = styles or DEFAULT_STYLES
    kr = s["korean"]
    en = s["english"]

    return (
        f"[Script Info]\n"
        f"Title: Bilingual Subtitles\n"
        f"ScriptType: v4.00+\n"
        f"WrapStyle: 0\n"
        f"ScaledBorderAndShadow: yes\n"
        f"YCbCr Matrix: TV.709\n"
        f"PlayResX: {res_x}\n"
        f"PlayResY: {res_y}\n"
        f"\n"
        f"[V4+ Styles]\n"
        f"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        f"OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        f"ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        f"Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Korean,{kr['fontname']},{kr['fontsize']},"
        f"{kr['primary_colour']},&H000000FF,&H00000000,{kr['back_colour']},"
        f"{kr['bold']},0,0,0,100,100,{kr['spacing']},0,"
        f"{kr['border_style']},{kr['outline']},{kr['shadow']},2,30,30,"
        f"{kr['margin_v']},1\n"
        f"Style: English,{en['fontname']},{en['fontsize']},"
        f"{en['primary_colour']},&H000000FF,&H00000000,{en['back_colour']},"
        f"{en['bold']},0,0,0,100,100,{en['spacing']},0,"
        f"{en['border_style']},{en['outline']},{en['shadow']},2,30,30,"
        f"{en['margin_v']},1\n"
        f"\n"
        f"[Events]\n"
        f"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        f"Effect, Text\n"
    )


def srt_to_ass_time(srt_time):
    """SRT timestamp (HH:MM:SS,mmm) → ASS timestamp (H:MM:SS.cc)."""
    match = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", srt_time)
    if not match:
        return "0:00:00.00"
    h, m, s, ms = match.groups()
    cs = int(ms) // 10
    return f"{int(h)}:{m}:{s}.{cs:02d}"


def is_korean(text):
    """Check if text contains Korean characters."""
    return bool(re.search(r"[\uac00-\ud7af\u3130-\u318f]", text))


def convert(srt_path, ass_path, res_x=1280, res_y=720):
    with open(srt_path, "r", encoding="utf-8") as f:
        srt_content = f.read()

    blocks = re.split(r"\n\n+", srt_content.strip())
    events = []

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        try:
            int(lines[0])
        except ValueError:
            continue

        time_match = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
            lines[1],
        )
        if not time_match:
            continue

        start = srt_to_ass_time(time_match.group(1))
        end = srt_to_ass_time(time_match.group(2))

        en_lines = []
        kr_lines = []
        for line in lines[2:]:
            if is_korean(line):
                kr_lines.append(line)
            else:
                en_lines.append(line)

        if kr_lines:
            kr_text = "\\N".join(kr_lines)
            events.append(f"Dialogue: 0,{start},{end},Korean,,0,0,0,,{kr_text}")
        if en_lines:
            en_text = "\\N".join(en_lines)
            events.append(f"Dialogue: 0,{start},{end},English,,0,0,0,,{en_text}")

    header = build_ass_header(res_x, res_y)

    with open(ass_path, "w", encoding="utf-8-sig") as f:
        f.write(header)
        f.write("\n".join(events))
        f.write("\n")

    print(f"Written {len(events)} dialogue events → {ass_path}")
    for e in events[:6]:
        print(f"  {e}")
    if len(events) > 6:
        print(f"  ... ({len(events) - 6} more)")


def main():
    parser = argparse.ArgumentParser(description="SRT → ASS bilingual converter")
    parser.add_argument("--srt", required=True, help="Input SRT path")
    parser.add_argument("--ass", required=True, help="Output ASS path")
    parser.add_argument(
        "--res",
        default="1280x720",
        help="Play resolution WxH (default: 1280x720)",
    )
    args = parser.parse_args()

    res_x, res_y = map(int, args.res.split("x"))
    convert(args.srt, args.ass, res_x, res_y)


if __name__ == "__main__":
    main()

"""
VTT → sentence-level cues extractor.

YouTube auto-captions have word-level timing in <c> tags. This script:
1. Parses VTT word-level timestamps from <c> tags
2. Deduplicates rolling-window lines (takes LAST line only)
3. Splits at sentence boundaries (.!?)
4. Outputs JSON with start/end/text per sentence

Usage:
  python extract_by_sentence.py --vtt subs.en.vtt --start 0 --end 99999 --output sentence_cues.json
"""
import re
import json
import argparse


def parse_ts(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def extract_sentences(vtt_path, clip_start, clip_end):
    with open(vtt_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse cue blocks
    cue_pattern = (
        r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*"
        r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})[^\n]*\n(.*?)(?=\n\n|\Z)"
    )
    cue_matches = re.findall(cue_pattern, content, re.DOTALL)

    # Build word-level timeline
    words = []
    for m in cue_matches:
        cue_start = parse_ts(m[0], m[1], m[2], m[3])
        cue_end = parse_ts(m[4], m[5], m[6], m[7])

        if cue_start < clip_start - 2 or cue_start > clip_end + 2:
            continue
        if cue_end - cue_start < 0.05:
            continue

        text_block = m[8].strip()
        lines = text_block.split("\n")
        if not lines:
            continue

        # Rolling window: only process LAST line (new content)
        last_line = lines[-1].strip()
        if not last_line:
            continue

        # First word uses cue start time
        first_match = re.match(r"^([^<]+)", last_line)
        if first_match:
            first_word = first_match.group(1).strip()
            if first_word:
                words.append((cue_start, first_word))

        # Timestamped words: <HH:MM:SS.mmm><c> word</c>
        tagged = re.findall(
            r"<(\d{2}):(\d{2}):(\d{2})\.(\d{3})><c>(.*?)</c>", last_line
        )
        for t in tagged:
            ts = parse_ts(t[0], t[1], t[2], t[3])
            word = t[4].strip()
            if word:
                words.append((ts, word))

    # Deduplicate close duplicates
    deduped = []
    for ts, w in words:
        if deduped and w == deduped[-1][1] and abs(ts - deduped[-1][0]) < 0.5:
            continue
        deduped.append((ts, w))

    deduped.sort(key=lambda x: x[0])

    # Split into sentences at .!? boundaries
    sentences = []
    current_words = []
    current_start = None

    for ts, w in deduped:
        if current_start is None:
            current_start = ts
        current_words.append((ts, w))

        if re.search(r"[.!?]$", w) and len(current_words) >= 3:
            text = " ".join(ww for _, ww in current_words)
            end_ts = ts + 0.5
            sentences.append((current_start, end_ts, text))
            current_words = []
            current_start = None

    # Remaining words
    if current_words:
        text = " ".join(ww for _, ww in current_words)
        end_ts = current_words[-1][0] + 0.8
        sentences.append((current_start, end_ts, text))

    # Offset to clip start
    result = []
    for s, e, t in sentences:
        s_off = max(0, s - clip_start)
        e_off = min(e - clip_start, clip_end - clip_start)
        if s_off < clip_end - clip_start:
            result.append(
                {"start": round(s_off, 3), "end": round(e_off, 3), "text": t}
            )

    return result


def main():
    parser = argparse.ArgumentParser(description="VTT → sentence-level cues")
    parser.add_argument("--vtt", required=True, help="Path to .vtt file")
    parser.add_argument(
        "--start", type=float, default=0, help="Clip start in seconds"
    )
    parser.add_argument(
        "--end", type=float, default=99999, help="Clip end in seconds"
    )
    parser.add_argument(
        "--output", default="sentence_cues.json", help="Output JSON path"
    )
    args = parser.parse_args()

    result = extract_sentences(args.vtt, args.start, args.end)

    for i, r in enumerate(result):
        dur = r["end"] - r["start"]
        print(f"{i+1:2d}. [{r['start']:6.1f} - {r['end']:6.1f}] ({dur:4.1f}s) {r['text']}")

    print(f"\nTotal sentences: {len(result)}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Saved → {args.output}")


if __name__ == "__main__":
    main()

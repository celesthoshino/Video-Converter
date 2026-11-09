"""
Video Converter
---------------
Put videos in the "input" folder, run this script, and converted (and
optionally smaller) copies show up in the "output" folder, one subfolder
per format.

    python convert_videos.py                   # asks which formats you want
    python convert_videos.py mp4               # convert everything to mp4
    python convert_videos.py mp4 -r 720        # mp4, at most 720p
    python convert_videos.py mp4 --max-mb 25   # mp4, each file under 25 MB
    python convert_videos.py mp4 -q low        # smaller files, lower quality

See README.md for all the details.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

# The input/output folders live next to this script, so it works no matter
# which folder you run it from.
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

# format name -> (file extension, video codec, audio settings, extra container settings)
FORMATS = {
    "mp4":  (".mp4",  "libx264",    ["-c:a", "aac", "-b:a", "160k"],        ["-movflags", "+faststart"]),
    "mkv":  (".mkv",  "libx264",    ["-c:a", "aac", "-b:a", "160k"],        []),
    "mov":  (".mov",  "libx264",    ["-c:a", "aac", "-b:a", "160k"],        ["-movflags", "+faststart"]),
    "webm": (".webm", "libvpx-vp9", ["-c:a", "libopus", "-b:a", "128k"],    []),
    "avi":  (".avi",  "mpeg4",      ["-c:a", "libmp3lame", "-b:a", "192k"], []),
}

# Settings for each video codec. "faststart"-style speed settings live here too.
CODEC_ARGS = {
    "libx264":    ["-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p"],
    "libvpx-vp9": ["-c:v", "libvpx-vp9", "-deadline", "good", "-cpu-used", "4", "-row-mt", "1", "-pix_fmt", "yuv420p"],
    "mpeg4":      ["-c:v", "mpeg4", "-vtag", "xvid"],
}

# --quality level -> settings per codec. Lower numbers mean better quality and bigger files.
QUALITY_ARGS = {
    "high":   {"libx264": ["-crf", "20"], "libvpx-vp9": ["-crf", "28", "-b:v", "0"], "mpeg4": ["-q:v", "3"]},
    "medium": {"libx264": ["-crf", "23"], "libvpx-vp9": ["-crf", "33", "-b:v", "0"], "mpeg4": ["-q:v", "5"]},
    "low":    {"libx264": ["-crf", "28"], "libvpx-vp9": ["-crf", "38", "-b:v", "0"], "mpeg4": ["-q:v", "8"]},
}

INPUT_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".wmv", ".flv", ".mpg", ".mpeg",
                    ".3gp", ".ts", ".mts", ".m2ts", ".ogv"}


def find_ffmpeg() -> str:
    """Use ffmpeg from PATH if it's installed, otherwise the copy that comes with imageio-ffmpeg."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        sys.exit(
            "Error: ffmpeg was not found.\n"
            "Fix it by running:  pip install -r requirements.txt\n"
            "(or install ffmpeg yourself: https://ffmpeg.org/download.html)"
        )


def probe(ffmpeg: str, path: Path) -> dict:
    """Length in seconds, and whether the file has video and audio, read from ffmpeg's description of it."""
    result = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)],
                            capture_output=True, encoding="utf-8", errors="replace")
    info = result.stderr
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", info)
    video_lines = [line for line in info.splitlines()
                   if "Video:" in line and "attached pic" not in line]  # ignore cover art
    return {
        "duration": int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3]) if match else None,
        "has_video": bool(video_lines),
        "has_audio": "Audio:" in info,
    }


def scale_filter(max_height) -> str:
    """
    Resize so the shorter side is at most max_height (720 = 720p), for both
    landscape and portrait (phone) videos. Never makes videos bigger.
    Width and height are kept even, which most players need.
    """
    if not max_height:
        return "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    r = max_height
    return (f"scale=w='if(gte(iw,ih),-2,trunc(min(iw,{r})/2)*2)'"
            f":h='if(gte(iw,ih),trunc(min(ih,{r})/2)*2,-2)'")


def run_ffmpeg(cmd: list[str], duration, label: str):
    """Run ffmpeg, showing a percentage while it works. Raises RuntimeError with ffmpeg's message on failure."""
    cmd = cmd[:1] + ["-hide_banner", "-loglevel", "error", "-nostats", "-progress", "pipe:1"] + cmd[1:]
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errors,
                                   encoding="utf-8", errors="replace")
        try:
            for line in process.stdout:
                if line.startswith("out_time_us=") and duration:
                    done_us = line.split("=", 1)[1].strip()
                    if done_us.isdigit():
                        percent = min(100, int(done_us) / 1_000_000 / duration * 100)
                        print(f"\r    {label} {percent:3.0f}%", end="", flush=True)
            process.wait()
        except KeyboardInterrupt:
            process.kill()
            raise
        finally:
            print("\r" + " " * 40 + "\r", end="")  # clear the progress line
        if process.returncode != 0:
            errors.seek(0)
            lines = errors.read().decode("utf-8", errors="replace").strip().splitlines()
            raise RuntimeError(lines[-1] if lines else "ffmpeg failed")


def convert(ffmpeg: str, src: Path, fmt: str, out_path: Path, args, info: dict):
    """Convert one video to one format. Raises RuntimeError on failure."""
    _, codec, audio_args, container_args = FORMATS[fmt]
    base = [ffmpeg, "-y", "-i", str(src),
            "-sn", "-dn",  # no subtitles or data tracks: only the main video and audio are kept
            "-vf", scale_filter(args.resolution), *CODEC_ARGS[codec]]
    limit = args.max_mb * 1024 * 1024 if args.max_mb else None

    # Normal encode: constant quality. Used unless the file has to fit a size limit
    # and the original is already bigger than that limit.
    if not limit or src.stat().st_size <= limit:
        run_ffmpeg(base + QUALITY_ARGS[args.quality][codec] + audio_args + container_args + [str(out_path)],
                   info["duration"], "converting")
        if not limit or out_path.stat().st_size <= limit:
            return

    # Two-pass encode at the bitrate that fits the size limit. The first pass
    # studies the video, the second pass uses that to spend the bits where they matter.
    if not info["duration"]:
        raise RuntimeError("couldn't read the video's length, so --max-mb can't be used for it")
    total_kbps = limit * 8 / 1000 / info["duration"] * 0.95  # 5% kept free for the container
    audio_kbps = (64 if total_kbps < 600 else 128) if info["has_audio"] else 0
    video_kbps = int(total_kbps - audio_kbps)
    if video_kbps < 50:
        raise RuntimeError(f"{args.max_mb} MB is too small for a video this long "
                           f"({format_time(info['duration'])}). Try a bigger --max-mb or shorten it first")
    audio_codec = audio_args[:2]
    with tempfile.TemporaryDirectory() as temp:
        passlog = ["-b:v", f"{video_kbps}k", "-passlogfile", str(Path(temp, "pass"))]
        run_ffmpeg(base + passlog + ["-pass", "1", "-an", "-f", "null", os.devnull],
                   info["duration"], "pass 1 of 2")
        run_ffmpeg(base + passlog + ["-pass", "2", *audio_codec, "-b:a", f"{audio_kbps}k", *container_args, str(out_path)],
                   info["duration"], "pass 2 of 2")


def format_time(seconds: float) -> str:
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    return f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if hours else f"{rest // 60}:{rest % 60:02d}"


def mb(size: int) -> str:
    if size < 1024 * 1024:
        return f"{size / 1024:,.0f} KB"
    return f"{size / 1024 / 1024:,.1f} MB"


def clean_formats(words: list[str]) -> list[str]:
    """Lowercase, drop leading dots and commas, and remove duplicates (keeping order)."""
    formats = []
    for word in words:
        for part in word.replace(",", " ").split():
            fmt = part.lower().lstrip(".")
            if fmt not in formats:
                formats.append(fmt)
    return formats


def ask_formats() -> list[str]:
    """Keep asking until the user types valid formats."""
    print("\nAvailable formats: " + ", ".join(FORMATS))
    while True:
        answer = input("Which formats do you want? (e.g. 'mp4', or 'all'): ").strip().lower()
        if answer == "all":
            return list(FORMATS)
        formats = clean_formats([answer])
        unknown = [f for f in formats if f not in FORMATS]
        if formats and not unknown:
            return formats
        print(f"  Unknown format(s): {', '.join(unknown)}. Try again." if unknown else "  Please type a format.")


def parse_resolution(text: str) -> int:
    value = text.lower().removesuffix("p")
    if not value.isdigit() or int(value) < 100:
        raise argparse.ArgumentTypeError("use a number like 1080, 720 or 480")
    return int(value)


def find_input_files(input_dir: Path) -> list[Path]:
    """Return the videos in input_dir. Other files are listed as ignored."""
    videos = []
    for path in sorted(input_dir.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() in INPUT_EXTENSIONS:
            videos.append(path)
        else:
            print(f"  [ignored] {path.name} (not a supported video file)")
    return videos


def main():
    parser = argparse.ArgumentParser(
        description="Convert every video in the input folder into other formats, and optionally make them smaller.",
        epilog="Supported formats: " + ", ".join(FORMATS),
    )
    parser.add_argument("formats", nargs="*", help="formats to convert to, e.g. mp4 webm")
    parser.add_argument("--all", action="store_true", help="convert to every supported format")
    parser.add_argument("-q", "--quality", choices=QUALITY_ARGS, default="medium",
                        help="high = bigger files, low = smaller files (default: medium)")
    parser.add_argument("-r", "--resolution", type=parse_resolution, metavar="HEIGHT",
                        help="make videos at most this size, e.g. 1080, 720 or 480 (default: keep the size)")
    parser.add_argument("--max-mb", type=float, metavar="MB",
                        help="make each video at most this many MB, e.g. 25")
    parser.add_argument("-i", "--input", type=Path, default=INPUT_DIR,
                        help="folder to read videos from (default: the input folder)")
    parser.add_argument("-o", "--output", type=Path, default=OUTPUT_DIR,
                        help="folder to save videos to (default: the output folder)")
    args = parser.parse_args()

    if args.max_mb is not None and args.max_mb <= 0:
        sys.exit("Error: --max-mb must be more than 0.")
    formats = list(FORMATS) if args.all else clean_formats(args.formats)
    unknown = [f for f in formats if f not in FORMATS]
    if unknown:
        sys.exit(f"Error: unknown format(s): {', '.join(unknown)}\nSupported: {', '.join(FORMATS)}")

    ffmpeg = find_ffmpeg()
    args.input.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)

    print(f"Looking in: {args.input}")
    files = find_input_files(args.input)
    if not files:
        print("No videos found. Put the videos you want converted in that folder, then run this again.")
        return

    print(f"Found {len(files)} video(s):")
    for f in files:
        print(f"  - {f.name}")
    if not formats:
        formats = ask_formats()

    stem_counts = Counter(f.stem.lower() for f in files)
    duplicate_stems = {stem for stem, count in stem_counts.items() if count > 1}

    converted = failed = 0
    for i, src in enumerate(files, start=1):
        info = probe(ffmpeg, src)
        length = f", {format_time(info['duration'])} long" if info["duration"] else ""
        print(f"\n[{i}/{len(files)}] {src.name}  ({mb(src.stat().st_size)}{length})")
        if not info["has_video"]:
            print("  [fail] it has no video in it (is it damaged, or an audio file?)")
            failed += len(formats)
            continue

        for fmt in formats:
            stem = f"{src.stem}_{src.suffix.lstrip('.').lower()}" if src.stem.lower() in duplicate_stems else src.stem
            fmt_dir = args.output / fmt
            fmt_dir.mkdir(exist_ok=True)
            out_path = fmt_dir / (stem + FORMATS[fmt][0])
            started = time.monotonic()
            try:
                convert(ffmpeg, src, fmt, out_path, args, info)
            except RuntimeError as error:
                out_path.unlink(missing_ok=True)  # don't leave half-written files behind
                print(f"  [fail] {fmt:<5} {error}")
                failed += 1
                continue
            except KeyboardInterrupt:
                out_path.unlink(missing_ok=True)
                raise
            took = format_time(time.monotonic() - started)
            print(f"  [ok]   {fmt:<5} -> {fmt}/{out_path.name}  ({mb(out_path.stat().st_size)}, took {took})")
            converted += 1

    print(f"\nDone: {converted} converted, {failed} failed.")
    print(f"Converted videos are in: {args.output}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(1)

"""Generate synthetic golden test fixtures and nasty edge cases.

Per TRD §6.10:
- Uses FFmpeg's built-in sources (testsrc, sine) and Pillow/pillow-heif.
- No copyrighted files.
- Generates golden files (video, audio, images).
- Generates nasty inputs (zero-byte, truncated, wrong extension, unicode names,
  shell-breaking symbols, long paths, garbage payloads).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import pillow_heif
from PIL import Image

pillow_heif.register_heif_opener()


def find_ffmpeg() -> str:
    """Locate ffmpeg executable in vendor/ or system PATH."""
    project_root = Path(__file__).resolve().parent.parent
    vendor_ffmpeg = project_root / "vendor" / "ffmpeg.exe"
    if vendor_ffmpeg.is_file():
        return str(vendor_ffmpeg)

    # Fallback to PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    raise FileNotFoundError(
        "ffmpeg not found in vendor/ffmpeg.exe or system PATH. "
        "Run 'python scripts/fetch_tools.py' first."
    )


def generate_images(out_dir: Path) -> dict[str, Path]:
    """Generate synthetic image test fixtures using Pillow and pillow-heif."""
    created: dict[str, Path] = {}

    # 1. img.png: 100x100 RGBA with transparent section
    png_path = out_dir / "img.png"
    im_rgba = Image.new("RGBA", (100, 100), color=(255, 0, 0, 255))
    # Draw a green rectangle with 50% opacity
    for x in range(25, 75):
        for y in range(25, 75):
            im_rgba.putpixel((x, y), (0, 255, 0, 128))
    im_rgba.save(png_path, format="PNG")
    created["png"] = png_path

    # 2. img.jpg: 100x100 RGB
    jpg_path = out_dir / "img.jpg"
    im_rgb = Image.new("RGB", (100, 100), color=(0, 0, 255))
    im_rgb.save(jpg_path, format="JPEG", quality=90)
    created["jpg"] = jpg_path

    # 3. img.bmp: 100x100 RGB
    bmp_path = out_dir / "img.bmp"
    im_rgb.save(bmp_path, format="BMP")
    created["bmp"] = bmp_path

    # 4. img.webp: 100x100 RGBA
    webp_path = out_dir / "img.webp"
    im_rgba.save(webp_path, format="WEBP", quality=90)
    created["webp"] = webp_path

    # 5. img.tiff: 100x100 RGB
    tiff_path = out_dir / "img.tiff"
    im_rgb.save(tiff_path, format="TIFF")
    created["tiff"] = tiff_path

    # 6. img.gif: 100x100 palette image
    gif_path = out_dir / "img.gif"
    im_gif = im_rgb.convert("P", palette=Image.Palette.ADAPTIVE)
    im_gif.save(gif_path, format="GIF")
    created["gif"] = gif_path

    # 7. img.heic: 100x100 RGB HEIC image
    heic_path = out_dir / "img.heic"
    try:
        im_rgb.save(heic_path, format="HEIF")
    except Exception:
        # Fallback if HEIF encoder has missing plugins
        heic_path.write_bytes(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 200)
    created["heic"] = heic_path

    return created


def generate_audio_video(out_dir: Path, ffmpeg_bin: str) -> dict[str, Path]:
    """Generate synthetic video and audio fixtures using FFmpeg lavfi filters."""
    created: dict[str, Path] = {}

    # 1. video_av.mp4 (video + audio, 3 seconds)
    video_av_path = out_dir / "video_av.mp4"
    cmd_av = [
        ffmpeg_bin,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=3:size=320x240:rate=24",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=3",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "aac",
        "-shortest",
        str(video_av_path),
    ]
    subprocess.run(cmd_av, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    created["video_av"] = video_av_path

    # 2. video_silent.mp4 (video only, no audio stream, 3 seconds)
    video_silent_path = out_dir / "video_silent.mp4"
    cmd_silent = [
        ffmpeg_bin,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=3:size=320x240:rate=24",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-an",
        str(video_silent_path),
    ]
    subprocess.run(cmd_silent, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    created["video_silent"] = video_silent_path

    # 3. audio.wav (3 seconds 440Hz PCM)
    audio_wav_path = out_dir / "audio.wav"
    cmd_wav = [
        ffmpeg_bin,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=3",
        "-c:a",
        "pcm_s16le",
        str(audio_wav_path),
    ]
    subprocess.run(cmd_wav, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    created["audio_wav"] = audio_wav_path

    # 4. audio.mp3 (3 seconds 440Hz MP3)
    audio_mp3_path = out_dir / "audio.mp3"
    cmd_mp3 = [
        ffmpeg_bin,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=3",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(audio_mp3_path),
    ]
    subprocess.run(cmd_mp3, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    created["audio_mp3"] = audio_mp3_path

    return created


def generate_nasty_inputs(
    out_dir: Path,
    video_av_path: Path,
    png_path: Path,
) -> dict[str, Path]:
    """Generate hostile, edge-case files that test error-handling and robustness."""
    created: dict[str, Path] = {}

    # 1. zero_byte.mp4
    zero_byte = out_dir / "zero_byte.mp4"
    zero_byte.write_bytes(b"")
    created["zero_byte"] = zero_byte

    # 2. truncated.mp4 (first 30% of video_av.mp4)
    full_bytes = video_av_path.read_bytes()
    cutoff = max(1, int(len(full_bytes) * 0.30))
    truncated = out_dir / "truncated.mp4"
    truncated.write_bytes(full_bytes[:cutoff])
    created["truncated"] = truncated

    # 3. png_named_jpg.jpg (valid PNG content named as .jpg)
    png_as_jpg = out_dir / "png_named_jpg.jpg"
    shutil.copyfile(png_path, png_as_jpg)
    created["png_named_jpg"] = png_as_jpg

    # 4. mp4_named_png.png (valid MP4 content named as .png)
    mp4_as_png = out_dir / "mp4_named_png.png"
    shutil.copyfile(video_av_path, mp4_as_png)
    created["mp4_named_png"] = mp4_as_png

    # 5. Non-English Hindi Unicode filename: वीडियो नमूना.mp4
    unicode_file = out_dir / "वीडियो नमूना.mp4"
    shutil.copyfile(video_av_path, unicode_file)
    created["unicode_name"] = unicode_file

    # 6. Shell-breaking symbols: a & b (final) v2.mp4
    shell_file = out_dir / "a & b (final) v2.mp4"
    shutil.copyfile(video_av_path, shell_file)
    created["shell_symbols"] = shell_file

    # 7. Garbage / non-container file
    garbage = out_dir / "garbage.mp4"
    garbage.write_bytes(b"\xde\xad\xbe\xef" * 4096)
    created["garbage"] = garbage

    # 8. Long path (>260 characters)
    # Windows standard paths are capped at 260 chars unless extended prefix \\?\ is used
    nested_dir = out_dir / "long_path"
    for i in range(10):
        nested_dir = nested_dir / f"nested_folder_level_{i:02d}_with_very_long_directory_name"
    nested_dir.mkdir(parents=True, exist_ok=True)
    long_path_file = nested_dir / "video_long_path.mp4"
    shutil.copyfile(video_av_path, long_path_file)
    created["long_path"] = long_path_file

    return created


def generate_all_fixtures(target_dir: Path | None = None) -> dict[str, Path]:
    """Generate all test fixtures into the specified directory."""
    fixtures_dir = target_dir or (Path(__file__).resolve().parent / "fixtures")
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating fixtures in {fixtures_dir} ...")
    ffmpeg_bin = find_ffmpeg()

    all_files: dict[str, Path] = {}
    print("  Generating images (Pillow / pillow-heif) ...")
    all_files.update(generate_images(fixtures_dir))

    print("  Generating audio and video (FFmpeg) ...")
    av_files = generate_audio_video(fixtures_dir, ffmpeg_bin)
    all_files.update(av_files)

    print("  Generating hostile / nasty edge-case inputs ...")
    nasty_files = generate_nasty_inputs(fixtures_dir, av_files["video_av"], all_files["png"])
    all_files.update(nasty_files)

    print(f"Done! {len(all_files)} fixture files generated successfully.")
    return all_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Cuttle test fixtures.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "fixtures",
        help="Output directory for generated fixtures",
    )
    args = parser.parse_args()
    try:
        generate_all_fixtures(args.out)
        return 0
    except Exception as e:
        print(f"Error generating fixtures: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

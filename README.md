# Video Converter

Converts videos into other formats and can make them smaller: lower the resolution, lower the quality, or fit each
video under a size limit (handy for Discord, email or WhatsApp). Put your videos in the `input` folder, run the script,
and get the converted videos in the `output` folder.

## Folder layout

```
video_converter/
├── convert_videos.py   the script
├── requirements.txt    Python packages to install
├── README.md           this file
├── input/              put the videos you want converted here
└── output/             converted videos appear here, one subfolder per format
    ├── mp4/
    └── ...
```

## Setup (one time)

1. Install **Python 3.9 or newer** from https://www.python.org/downloads/
   (on Windows, tick "Add Python to PATH" during install).
2. Open a terminal in the `video_converter` folder and run:

   ```
   pip install -r requirements.txt
   ```

   This installs a copy of **ffmpeg**, the program that does the conversion. If ffmpeg is already installed on your
   computer, the script uses that one instead, and this step is optional.

## How to use

1. Copy the videos you want converted into the `input` folder.
2. Open a terminal in the `video_converter` folder and run:

   ```
   python convert_videos.py
   ```

3. It lists the videos it found and asks which formats you want. Type one or more, separated by spaces (for example
   `mp4 webm`), or type `all`.
4. The converted videos are saved in `output/<format>/`. For example, `input/clip.mov` converted to mp4 becomes
   `output/mp4/clip.mp4`.

While a video converts, the script shows how far along it is. Big videos can take a few minutes each.

| Command | What it does |
|---|---|
| `python convert_videos.py` | Asks which formats you want |
| `python convert_videos.py mp4` | Converts every video to mp4 |
| `python convert_videos.py mp4 webm` | Converts every video to mp4 and webm |
| `python convert_videos.py mp4 -r 720` | mp4, at most 720p |
| `python convert_videos.py mp4 --max-mb 25` | mp4, every video at most 25 MB |
| `python convert_videos.py mp4 -q low` | mp4, smaller files at lower quality |
| `python convert_videos.py mp4 -r 720 -q low --max-mb 10` | Options can be combined |
| `python convert_videos.py --help` | Shows all options |

## Options

| Option | Default | Meaning |
|---|---|---|
| `formats` | asks you | One or more formats to convert to |
| `--all` | off | Convert to every supported format |
| `-q`, `--quality` | `medium` | `high`: looks best, bigger files. `medium`: good balance. `low`: smallest files, softer picture |
| `-r`, `--resolution` | keep | Largest size, as the height for normal videos: `2160` (4K), `1440`, `1080`, `720`, `480`, `360`. Videos already smaller are left as they are |
| `--max-mb` | none | Make every video at most this many MB. Long videos get a lower quality to fit |
| `-i`, `--input` | `input` folder | Folder to read videos from |
| `-o`, `--output` | `output` folder | Folder to save converted videos to |

## Supported formats

| Format | Notes |
|---|---|
| `mp4` | Plays everywhere: phones, browsers, TVs, every app. The best choice if you're not sure |
| `mkv` | Same quality as mp4. Popular for movies on computers, but not every phone or app plays it |
| `mov` | Apple's format. Same quality as mp4 |
| `webm` | Made for websites. Smaller than mp4 at the same quality, but converts more slowly |
| `avi` | Old format, only for old software or devices that need it. Bigger files |

**Videos it accepts:** `.mp4 .mkv .mov .webm .avi .m4v .wmv .flv .mpg .mpeg .3gp .ts .mts .m2ts .ogv`.
Other files are listed as "ignored" and left alone.

## Making videos smaller

There are three ways, and you can combine them:

- **`-r` (resolution)** helps the most. A 4K or 1080p video at 720p is several times smaller and still looks fine on
  a phone.
- **`-q low`** keeps the size but compresses harder.
- **`--max-mb`** guarantees the file size. If the video is already under the limit, it's converted normally. If it's
  bigger, the script works out how much quality fits in that size and converts it in two passes, which takes about
  twice as long. Very long videos with a small limit will look blocky; adding `-r 720` or `-r 480` helps a lot.

Common size limits: Discord 10 MB (free accounts), email attachments 20-25 MB, WhatsApp 100 MB.

## Good to know

- **Original videos are never changed or deleted.** The script only reads from `input`.
- **Converting to the same format still makes a new copy.** For example, mp4 to mp4 is how you shrink an mp4 with
  `-r`, `-q` or `--max-mb`.
- **Running it again overwrites earlier results** with the same name in `output`.
- **Phone videos stay the right way up**, and `-r 720` makes portrait videos 720 pixels wide instead of 720 tall,
  so they aren't squashed.
- **Videos are never made bigger** in resolution.
- **Only the main video and audio are kept.** Extra audio tracks (like other languages) and subtitles are dropped.
- **Videos with the same name but different extensions**, like `clip.mov` and `clip.avi`, keep their old extension in
  the new name so neither overwrites the other: `clip_mov.mp4` and `clip_avi.mp4`.
- **Subfolders inside `input` are not scanned.** Put the videos directly in `input`.

## Troubleshooting

**`Error: ffmpeg was not found`**

Run `pip install -r requirements.txt` from inside the `video_converter` folder.

**`it has no video in it`**

The file is damaged, or it's actually an audio file with a video extension.

**`MB is too small for a video this long`**

The size limit can't fit that much video. Use a bigger `--max-mb`, add `-r 480`, or cut the video shorter first.

**It's very slow**

Converting video is hard work for a computer, and `webm` is the slowest format. Lowering the resolution with `-r`
makes it faster.

**`'python' is not recognized`**

Python isn't on your PATH. On Windows, try `py convert_videos.py` instead, or reinstall Python with "Add Python to PATH" ticked.

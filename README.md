# AutoShow

AutoShow builds unattended radio-style music programs from a local music
library and station imaging assets. It is a local GUI app backed by Python and
ffmpeg; it renders finished audio files rather than doing live streaming.

## Run

Start the GUI from the project root:

```bash
python3 -m autoshow
```

The app opens automatically at:

```text
http://127.0.0.1:2025
```

To start without opening a browser:

```bash
python3 -m autoshow --no-open
```

## Folders

```text
download/       temporary music import folder
media/music/    long-term music library
media/assets/   station imaging assets
output/         rendered shows
```

The media and output folders are ignored by git so large audio files stay local.

## Import Music

The importer expects downloads shaped like:

```text
download/Artist/Album/Track.m4a
```

Preview an import:

```bash
python3 scripts/merge_music_library.py
```

Actually move audio into `media/music/Artist/Album/`:

```bash
python3 scripts/merge_music_library.py --apply
```

The importer skips exact duplicate audio, renames same-name conflicts, deletes
leftover `.lrc` lyric files, and removes empty download folders.

## Render Notes

The render backend uses ffmpeg. It supports loudness normalization, head/tail
silence trimming, fades, bedding, crossfades, sample rate, bit depth, channel
count, and export format selection.

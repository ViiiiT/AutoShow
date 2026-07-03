# AutoShow：无人值守音乐广播节目生成工具

AutoShow is a local tool for assembling unattended radio-style music programs.

## 项目介绍 / Project Overview

AutoShow 用来把音乐、台呼、Jingle、报时、节目包装等素材按节目单规则组合，最终渲染成一个完整的音频文件。它不是实时直播系统，而是面向“先编排、后导出”的广播节目制作工具。

AutoShow assembles songs and radio imaging assets into a finished audio file. It is not a live streaming system; it is designed for planning, editing, and rendering a completed show.

本项目完全是 Vibe Coding 的产物。代码、交互和渲染流程都在快速迭代中形成，建议在正式使用、公开部署或处理重要素材前自行审查代码、依赖和输出结果。

This project was built entirely through Vibe Coding. Please review the code, dependencies, and rendered output before production use or before processing important/private assets.

## 1. 文件结构 / File Structure

```text
autoshow/                 主程序与本地 GUI 服务
  __main__.py             python3 -m autoshow 的入口
  gui.py                  GUI、API、节目单逻辑和 ffmpeg 渲染后端

scripts/
  merge_music_library.py  音乐资源库合并脚本

download/                 临时下载/导入目录
media/
  music/                  长期音乐库
  assets/                 电台包装素材库
    BackNow/
    General/
    Intro/
    Jingle/
    RightBack/
    TimeCheck/

output/                   渲染输出目录
```

`media/`、`download/` 和 `output/` 中的真实音频文件默认不进入 Git；仓库只保留目录结构。这样可以避免把音乐、台呼素材和节目成品推到 GitHub。

Real audio files in `media/`, `download/`, and `output/` are ignored by Git. The repository keeps only the expected folder structure, so music, imaging assets, and rendered shows stay local.

## 2. 打开用法 / Running AutoShow

先确认本机可以使用 Python 3 和 ffmpeg。

Make sure Python 3 and ffmpeg are available on your machine.

在项目根目录运行：

Run from the project root:

```bash
python3 -m autoshow
```

启动后会自动打开浏览器，默认地址是：

The browser should open automatically at:

```text
http://127.0.0.1:2025
```

如果只想启动服务，不自动打开浏览器：

To start the server without opening a browser:

```bash
python3 -m autoshow --no-open
```

停止服务：

Stop the server:

```text
Ctrl + C
```

## 3. 资源库整合脚本 / Music Library Importer

脚本用于把临时下载目录 `download/` 中的音乐合并进长期媒体库 `media/music/`。

The importer moves downloaded audio from `download/` into the long-term library under `media/music/`.

它期待下载目录结构为：

Expected source layout:

```text
download/Artist/Album/Track.m4a
```

导入后的结构为：

Destination layout:

```text
media/music/Artist/Album/Track.m4a
```

先预览，不实际移动：

Preview without moving files:

```bash
python3 scripts/merge_music_library.py
```

确认无误后执行搬迁：

Move files after checking the preview:

```bash
python3 scripts/merge_music_library.py --apply
```

脚本行为：

Importer behavior:

- 只导入音频文件：`.mp3`、`.m4a`、`.wav`、`.flac`、`.aac`、`.ogg`
- `.lrc` 歌词文件不会进入媒体库，执行 `--apply` 时会从 `download/` 中清理
- 相同内容的重复音频会跳过，并删除 `download/` 里的重复副本
- 同名但内容不同的音频会自动改名，例如 `Track (2).m4a`
- 歌手/专辑目录已存在时会复用；大小写或多余空格略有差异时也会尽量合并到已有目录
- 搬迁完成后会清理空的下载子目录

- Imports audio files only: `.mp3`, `.m4a`, `.wav`, `.flac`, `.aac`, `.ogg`
- `.lrc` lyric files are not imported and are removed from `download/` when using `--apply`
- Exact duplicate audio is skipped and removed from the download folder
- Same-name but different-content files are renamed, for example `Track (2).m4a`
- Existing artist/album folders are reused, with case/spacing tolerant matching
- Empty download folders are removed after import

如果还想删除 `download/` 中其它非音频杂物：

To delete other non-audio leftovers from `download/`:

```bash
python3 scripts/merge_music_library.py --apply --purge-leftovers
```

## 4. 其它信息 / Other Notes

渲染功能目前包括：响度标准化、头尾无声片段裁切、淡入淡出、垫入垫出、交叉叠化、采样率/位深/声道设置，以及 MP3/WAV/FLAC/AAC/OGG 导出。

Rendering currently supports loudness normalization, head/tail silence trimming, fades, bedding, crossfades, sample rate, bit depth, channel count, and MP3/WAV/FLAC/AAC/OGG export.

如果超长节目渲染时报 `Too many open files`，可以先在启动 AutoShow 前临时提高当前终端的文件打开上限：

If a very large render fails with `Too many open files`, temporarily increase the file descriptor limit before starting AutoShow:

```bash
ulimit -n 2048
python3 -m autoshow
```

许可证见 `LICENSE`。请注意，代码许可证不覆盖你本地的音乐、台呼、Jingle 或其它音频素材。

See `LICENSE` for code licensing. The code license does not cover your local music, station imaging, jingles, or other audio assets.

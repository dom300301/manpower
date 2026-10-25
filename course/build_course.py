#!/usr/bin/env python3
"""數位課程影片製作程式（每章一支 1920×1080 MP4）。

流程：
  1. slides  ：input/slides/*.pptx → PDF → PNG（每頁一張）
  2. tts     ：scripts/chNN.txt 講稿 → 微軟語音 (edge-tts, zh-TW) → 每頁一段 mp3 + 字幕時間
  3. render  ：簡報 + Q 版講師（依音量同步口型）+ 字幕 → output/chNN.mp4

用法：
  python3 build_course.py slides                 # 轉所有簡報
  python3 build_course.py tts 01                 # 第 1 章配音
  python3 build_course.py render 01              # 第 1 章合成
  python3 build_course.py all 01                 # 第 1 章一次做完
  python3 build_course.py all                    # 全部章節

講稿格式（scripts/ch01.txt）：
  # 章節標題
  ## 1            ← 對應第 1 頁
  本頁旁白文字…
  ## 2
  …
"""
import asyncio, json, math, os, re, shutil, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from avatar import draw_avatar

ROOT = Path(__file__).parent
IN_SLIDES = ROOT / "input" / "slides"
SCRIPTS = ROOT / "scripts"
WORK = ROOT / "work"
OUT = ROOT / "output"
CONF = json.loads((ROOT / "course.json").read_text(encoding="utf-8")) if (ROOT / "course.json").exists() else {}

W, H, FPS = 1920, 1080, 24
VOICE = CONF.get("voice", "zh-TW-HsiaoChenNeural")
RATE = CONF.get("rate", "-5%")
COURSE_TITLE = CONF.get("title", "數位課程")
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
FONT_NAME = "WenQuanYi Zen Hei"

# 版面
SLIDE_BOX = (40, 110, 1500, 931)       # x0,y0,x1,y1  (1460×821 = 16:9)
AVATAR_BOX = (1540, 520, 1880, 900)    # 講師卡片
SUB_Y = 955                            # 字幕列頂端


def run(cmd, **kw):
    r = subprocess.run(cmd, text=True, capture_output=True, **kw)
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit(f"指令失敗: {' '.join(map(str, cmd))}")
    return r


def chapter_ids():
    return sorted(p.stem[2:] for p in SCRIPTS.glob("ch*.txt"))


# ---------------------------------------------------------------- 1. slides
def build_slides():
    """input/slides/NN_*.pptx → work/slides/NN/page-001.png …"""
    files = sorted(IN_SLIDES.glob("*.ppt*")) + sorted(IN_SLIDES.glob("*.pdf"))
    if not files:
        raise SystemExit(f"找不到簡報，請放到 {IN_SLIDES}")
    for f in files:
        m = re.match(r"(\d+)", f.stem)
        if not m:
            print(f"略過（檔名開頭需為章節數字）: {f.name}")
            continue
        cid = m.group(1).zfill(2)
        dst = WORK / "slides" / cid
        if dst.exists() and any(dst.glob("page-*.png")):
            print(f"[slides] 第 {cid} 章已存在，略過")
            continue
        dst.mkdir(parents=True, exist_ok=True)
        pdf = f if f.suffix.lower() == ".pdf" else dst / (f.stem + ".pdf")
        if f.suffix.lower() != ".pdf":
            run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(dst), str(f)])
        run(["pdftoppm", "-r", "110", "-png", str(pdf), str(dst / "page")])
        # pdftoppm 輸出 page-1.png / page-01.png 視頁數而定，統一改為 page-001.png
        for p in dst.glob("page-*.png"):
            n = int(p.stem.split("-")[1])
            p.rename(dst / f"page-{n:03d}.png")
        print(f"[slides] 第 {cid} 章：{len(list(dst.glob('page-*.png')))} 頁")


# ---------------------------------------------------------------- 2. tts
def parse_script(cid):
    txt = (SCRIPTS / f"ch{cid}.txt").read_text(encoding="utf-8")
    title = ""
    pages = {}
    cur = None
    for line in txt.splitlines():
        if line.startswith("## "):
            cur = int(line[3:].strip())
            pages[cur] = ""
        elif line.startswith("# "):
            title = line[2:].strip()
        elif cur is not None and line.strip():
            pages[cur] += line.strip()
    return title, pages


def split_sentences(text):
    parts = re.split(r"(?<=[。！？；])", text)
    return [p for p in parts if p.strip()]


async def _tts_one(text, mp3, sub_json):
    import edge_tts
    com = edge_tts.Communicate(text, VOICE, rate=RATE)
    words = []
    with open(mp3, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append((chunk["offset"] / 1e7, chunk["duration"] / 1e7, chunk["text"]))
    Path(sub_json).write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")


def build_tts(cid, fake=False):
    title, pages = parse_script(cid)
    d = WORK / "audio" / cid
    d.mkdir(parents=True, exist_ok=True)
    for n, text in pages.items():
        mp3, sj = d / f"p{n:03d}.mp3", d / f"p{n:03d}.json"
        if mp3.exists() and sj.exists():
            continue
        if fake:  # PoC 用：無網路時以靜音＋合成雜訊模擬語音長度（每字 0.28 秒）
            dur = max(1.5, len(text) * 0.28)
            run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=220:duration={dur}",
                 "-af", "volume=0.3,tremolo=f=4:d=0.9", str(mp3)])
            words, t = [], 0.0
            for s in split_sentences(text):
                sd = len(s) * 0.28
                words.append((t, sd, s)); t += sd
            sj.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
        else:
            asyncio.run(_tts_one(text, mp3, sj))
        print(f"[tts] 第 {cid} 章 第 {n} 頁 完成（{len(text)} 字）")


# ---------------------------------------------------------------- 3. render
def audio_duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(r.stdout.strip())


def audio_rms_per_frame(path, fps=FPS):
    """回傳每個影格的音量（0~1），用於口型。"""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                       capture_output=True)
    pcm = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768
    spf = 16000 // fps
    n = math.ceil(len(pcm) / spf)
    pcm = np.pad(pcm, (0, n * spf - len(pcm)))
    rms = np.sqrt((pcm.reshape(n, spf) ** 2).mean(axis=1))
    if rms.max() > 0:
        rms = rms / np.percentile(rms, 97).clip(min=1e-6)
    return rms.clip(0, 1)


def make_backdrop(cid, title, total_pages):
    """靜態底圖：背景、標題列、講師卡片底、字幕底。"""
    img = Image.new("RGB", (W, H), (236, 240, 246))
    d = ImageDraw.Draw(img)
    # 標題列
    d.rectangle([0, 0, W, 90], fill=(44, 62, 100))
    f_big = ImageFont.truetype(FONT, 38)
    f_mid = ImageFont.truetype(FONT, 30)
    d.text((40, 24), COURSE_TITLE, font=f_big, fill=(255, 255, 255))
    ct = f"第 {int(cid)} 章　{title}"
    tw = d.textlength(ct, font=f_mid)
    d.text((W - 40 - tw, 30), ct, font=f_mid, fill=(220, 228, 245))
    # 簡報框陰影
    x0, y0, x1, y1 = SLIDE_BOX
    d.rounded_rectangle([x0 + 6, y0 + 8, x1 + 6, y1 + 8], radius=14, fill=(200, 206, 216))
    d.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=(255, 255, 255))
    # 講師卡片
    ax0, ay0, ax1, ay1 = AVATAR_BOX
    d.rounded_rectangle([ax0, ay0, ax1, ay1], radius=24, fill=(255, 255, 255), outline=(190, 200, 220), width=3)
    f_small = ImageFont.truetype(FONT, 26)
    d.rounded_rectangle([ax0, ay1 - 48, ax1, ay1], radius=24, fill=(44, 62, 100))
    d.rectangle([ax0, ay1 - 48, ax1, ay1 - 24], fill=(44, 62, 100))
    lbl = CONF.get("lecturer", "課程講師")
    lw = d.textlength(lbl, font=f_small)
    d.text(((ax0 + ax1) / 2 - lw / 2, ay1 - 42), lbl, font=f_small, fill=(255, 255, 255))
    # 字幕底
    d.rectangle([0, SUB_Y - 10, W, H], fill=(30, 36, 50))
    return img


def fit_slide(png):
    x0, y0, x1, y1 = SLIDE_BOX
    bw, bh = x1 - x0 - 24, y1 - y0 - 24
    im = Image.open(png).convert("RGB")
    s = min(bw / im.width, bh / im.height)
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    return im, (x0 + 12 + (bw - im.width) // 2, y0 + 12 + (bh - im.height) // 2)


def fmt_ass_time(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def words_to_subs(words, max_chars=24):
    """把 TTS 字界事件合併成字幕句（約 24 字一行，遇句號換句）。"""
    subs, buf, start = [], "", None
    for off, dur, text in words:
        if start is None:
            start = off
        buf += text
        end = off + dur
        if re.search(r"[。！？；]$", buf) or len(buf) >= max_chars:
            subs.append((start, end, buf)); buf, start = "", None
    if buf:
        subs.append((start, end, buf))
    # 讓每句字幕延續到下一句開始，避免閃爍
    out = []
    for i, (s, e, t) in enumerate(subs):
        e2 = subs[i + 1][0] if i + 1 < len(subs) else e + 0.6
        out.append((s, max(e, e2 - 0.05), t))
    return out


def build_render(cid):
    title, pages = parse_script(cid)
    sdir, adir = WORK / "slides" / cid, WORK / "audio" / cid
    rdir = WORK / "render" / cid
    if rdir.exists():
        shutil.rmtree(rdir)
    rdir.mkdir(parents=True)
    OUT.mkdir(exist_ok=True)

    backdrop = make_backdrop(cid, title, len(pages))
    # 預先畫好講師各種狀態（3 口型 × 2 眼 × 5 傾角）
    ax0, ay0, ax1, ay1 = AVATAR_BOX
    asz = ax1 - ax0 - 20
    tilts = [-3, -1.5, 0, 1.5, 3]
    cache = {(m, e, ti): draw_avatar(asz, mouth=m, eyes=e, tilt=t)
             for m in range(3) for e in ("open", "closed") for ti, t in enumerate(tilts)}

    concat_lines, ass_events, t_global = [], [], 0.0
    page_videos = []
    for n in sorted(pages):
        png = sdir / f"page-{n:03d}.png"
        mp3, sj = adir / f"p{n:03d}.mp3", adir / f"p{n:03d}.json"
        if not png.exists():
            raise SystemExit(f"缺少簡報頁 {png}")
        if not mp3.exists():
            raise SystemExit(f"缺少配音 {mp3}，請先執行 tts")
        dur = audio_duration(mp3) + 0.8  # 每頁尾端留 0.8 秒
        rms = audio_rms_per_frame(mp3)
        nframes = int(round(dur * FPS))

        base = backdrop.copy()
        im, pos = fit_slide(png)
        base.paste(im, pos)
        # 頁碼
        d = ImageDraw.Draw(base)
        f_pg = ImageFont.truetype(FONT, 24)
        d.text((AVATAR_BOX[0] + 4, SLIDE_BOX[1] + 4), f"第 {n} 頁 / 共 {len(pages)} 頁", font=f_pg, fill=(90, 100, 120))

        # 逐格輸出到 ffmpeg（只替換講師區域，速度快）
        pv = rdir / f"p{n:03d}.mp4"
        ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                               "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(mp3),
                               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                               "-af", "apad", "-c:a", "aac", "-b:a", "128k", "-t", f"{dur:.3f}", str(pv)],
                              stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        rng = np.random.default_rng(n)
        next_blink = rng.uniform(2, 5) * FPS
        blink_left = 0
        mouth_prev = 0
        for i in range(nframes):
            v = rms[i] if i < len(rms) else 0.0
            m = 2 if v > 0.55 else (1 if v > 0.18 else 0)
            if m == mouth_prev and v > 0.18 and i % 3 == 0:  # 持續發聲時口型小變化
                m = 1 if m == 2 else 2
            mouth_prev = m
            if blink_left > 0:
                blink_left -= 1; e = "closed"
            elif i >= next_blink:
                blink_left = 3; next_blink = i + rng.uniform(2.5, 5.5) * FPS; e = "closed"
            else:
                e = "open"
            ti = int(round(2 + 2 * math.sin(i / FPS * 0.9)))  # 緩慢左右律動
            fr = base.copy()
            fr.paste(cache[(m, e, ti)], (ax0 + 10, ay0 + 6), cache[(m, e, ti)])
            ff.stdin.write(fr.tobytes())
        ff.stdin.close(); err = ff.stderr.read().decode(errors="replace"); ff.wait()
        if ff.returncode:
            raise SystemExit("ffmpeg 影格輸出失敗:\n" + err[-2000:])
        page_videos.append(pv)

        # 字幕（全章時間軸）
        words = json.loads(sj.read_text(encoding="utf-8"))
        for s, e, text in words_to_subs(words):
            ass_events.append(f"Dialogue: 0,{fmt_ass_time(t_global + s)},{fmt_ass_time(t_global + e)},Default,,0,0,0,,{text}")
        t_global += dur
        print(f"[render] 第 {cid} 章 第 {n} 頁：{dur:.1f} 秒")

    # 串接各頁 + 燒字幕
    lst = rdir / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in page_videos), encoding="utf-8")
    ass = rdir / "subs.ass"
    ass.write_text(
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{FONT_NAME},44,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,1.5,0,2,60,60,40,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        + "\n".join(ass_events) + "\n", encoding="utf-8")
    joined = rdir / "joined.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
    final = OUT / f"ch{cid}.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(joined), "-vf", f"subtitles={ass.as_posix()}:fontsdir=/usr/share/fonts",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(final)])
    print(f"[done] {final}  長度 {t_global/60:.1f} 分鐘")


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__); raise SystemExit(1)
    stage = args[0]
    fake = "--fake-audio" in args
    ids = [a.zfill(2) for a in args[1:] if a.isdigit()] or chapter_ids()
    if stage == "slides":
        build_slides()
    elif stage == "tts":
        for c in ids: build_tts(c, fake=fake)
    elif stage == "render":
        for c in ids: build_render(c)
    elif stage == "all":
        build_slides()
        for c in ids:
            build_tts(c, fake=fake); build_render(c)
    else:
        print(__doc__)

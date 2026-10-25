"""Q 版 OL 講師繪製模組（純向量，Pillow 繪製）。

提供 draw_avatar(size, mouth, eyes, tilt) 回傳 RGBA 影像：
  mouth: 0=閉口 1=半開 2=張口
  eyes:  'open' | 'closed'
  tilt:  頭部左右傾斜角度（度），用於點頭／律動
"""
from PIL import Image, ImageDraw

# 色票（可依需求調整）
SKIN = (255, 224, 196)
SKIN_SHADE = (240, 196, 168)
HAIR = (72, 48, 40)
HAIR_LIGHT = (104, 72, 60)
BLAZER = (52, 72, 110)       # 深藍西裝外套
BLAZER_DARK = (40, 56, 88)
BLOUSE = (250, 250, 252)
SCARF = (196, 84, 96)         # 領巾
EYE = (60, 44, 40)
EYE_WHITE = (255, 255, 255)
BLUSH = (255, 170, 170, 110)
MOUTH = (200, 90, 100)
LINE = (70, 50, 45)


def _ellipse(d, cx, cy, rx, ry, fill, outline=None, width=0):
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill, outline=outline, width=width)


def draw_avatar(size=600, mouth=0, eyes="open", tilt=0.0):
    S = size / 600.0  # 以 600px 為基準縮放
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    cx = 300 * S
    # ---- 身體（西裝外套 + 襯衫 + 領巾）----
    body_top = 380 * S
    d.rounded_rectangle([cx - 150 * S, body_top, cx + 150 * S, 620 * S], radius=70 * S, fill=BLAZER)
    # 襯衫 V 領
    d.polygon([(cx - 55 * S, body_top), (cx + 55 * S, body_top), (cx, body_top + 110 * S)], fill=BLOUSE)
    # 外套翻領
    d.polygon([(cx - 75 * S, body_top - 5 * S), (cx - 40 * S, body_top - 5 * S), (cx - 10 * S, body_top + 120 * S), (cx - 50 * S, body_top + 125 * S)], fill=BLAZER_DARK)
    d.polygon([(cx + 75 * S, body_top - 5 * S), (cx + 40 * S, body_top - 5 * S), (cx + 10 * S, body_top + 120 * S), (cx + 50 * S, body_top + 125 * S)], fill=BLAZER_DARK)
    # 領巾
    d.polygon([(cx - 30 * S, body_top + 5 * S), (cx + 30 * S, body_top + 5 * S), (cx, body_top + 60 * S)], fill=SCARF)
    # 頸部
    d.rectangle([cx - 28 * S, 330 * S, cx + 28 * S, body_top + 10 * S], fill=SKIN_SHADE)

    # ---- 頭部（可傾斜）----
    head = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hd = ImageDraw.Draw(head)
    hx, hy = cx, 230 * S
    # 後髮（鮑伯頭）
    _ellipse(hd, hx, hy - 10 * S, 150 * S, 150 * S, HAIR)
    hd.rounded_rectangle([hx - 150 * S, hy - 10 * S, hx + 150 * S, hy + 175 * S], radius=60 * S, fill=HAIR)
    # 臉
    _ellipse(hd, hx, hy, 128 * S, 135 * S, SKIN)
    # 耳朵
    _ellipse(hd, hx - 128 * S, hy + 10 * S, 18 * S, 24 * S, SKIN)
    _ellipse(hd, hx + 128 * S, hy + 10 * S, 18 * S, 24 * S, SKIN)
    # 前髮（斜瀏海）
    hd.pieslice([hx - 150 * S, hy - 160 * S, hx + 150 * S, hy + 80 * S], 190, 350, fill=HAIR)
    hd.polygon([(hx - 150 * S, hy - 30 * S), (hx - 110 * S, hy - 110 * S), (hx - 70 * S, hy - 20 * S), (hx - 110 * S, hy + 20 * S)], fill=HAIR)
    hd.polygon([(hx - 60 * S, hy - 125 * S), (hx + 20 * S, hy - 135 * S), (hx + 90 * S, hy - 60 * S), (hx + 40 * S, hy - 30 * S), (hx - 20 * S, hy - 60 * S)], fill=HAIR)
    hd.polygon([(hx + 80 * S, hy - 110 * S), (hx + 150 * S, hy - 30 * S), (hx + 150 * S, hy + 20 * S), (hx + 110 * S, hy - 10 * S)], fill=HAIR)
    # 髮光
    hd.arc([hx - 100 * S, hy - 150 * S, hx + 60 * S, hy - 40 * S], 200, 300, fill=HAIR_LIGHT, width=int(8 * S))
    # 腮紅
    _ellipse(hd, hx - 70 * S, hy + 45 * S, 26 * S, 14 * S, BLUSH)
    _ellipse(hd, hx + 70 * S, hy + 45 * S, 26 * S, 14 * S, BLUSH)
    # 眼睛
    for ex in (hx - 52 * S, hx + 52 * S):
        if eyes == "open":
            _ellipse(hd, ex, hy + 10 * S, 22 * S, 28 * S, EYE_WHITE, outline=LINE, width=int(3 * S))
            _ellipse(hd, ex, hy + 14 * S, 14 * S, 20 * S, EYE)
            _ellipse(hd, ex - 5 * S, hy + 4 * S, 5 * S, 6 * S, EYE_WHITE)
        else:
            hd.arc([ex - 22 * S, hy, ex + 22 * S, hy + 36 * S], 20, 160, fill=LINE, width=int(4 * S))
        # 眉毛
        hd.arc([ex - 24 * S, hy - 40 * S, ex + 24 * S, hy - 12 * S], 200, 340, fill=LINE, width=int(4 * S))
    # 鼻子
    hd.arc([hx - 6 * S, hy + 40 * S, hx + 8 * S, hy + 56 * S], 300, 90, fill=LINE, width=int(3 * S))
    # 嘴巴（三種口型）
    my = hy + 78 * S
    if mouth == 0:
        hd.arc([hx - 22 * S, my - 12 * S, hx + 22 * S, my + 10 * S], 20, 160, fill=MOUTH, width=int(4 * S))
    elif mouth == 1:
        _ellipse(hd, hx, my, 18 * S, 9 * S, MOUTH, outline=LINE, width=int(2 * S))
    else:
        _ellipse(hd, hx, my + 2 * S, 22 * S, 16 * S, MOUTH, outline=LINE, width=int(2 * S))
        _ellipse(hd, hx, my - 4 * S, 14 * S, 5 * S, EYE_WHITE)  # 牙齒
    # 耳環
    _ellipse(hd, hx - 128 * S, hy + 36 * S, 5 * S, 5 * S, (230, 190, 90))
    _ellipse(hd, hx + 128 * S, hy + 36 * S, 5 * S, 5 * S, (230, 190, 90))

    if tilt:
        head = head.rotate(tilt, resample=Image.BICUBIC, center=(hx, 360 * S))
    img.alpha_composite(head)
    return img


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "avatar_preview.png"
    sheet = Image.new("RGBA", (600 * 3, 600 * 2), (255, 255, 255, 255))
    for i, (m, e) in enumerate([(0, "open"), (1, "open"), (2, "open"), (0, "closed"), (1, "open"), (2, "open")]):
        a = draw_avatar(600, mouth=m, eyes=e, tilt=(-4 if i >= 3 else 0))
        sheet.alpha_composite(a, ((i % 3) * 600, (i // 3) * 600))
    sheet.convert("RGB").save(out)
    print("saved", out)

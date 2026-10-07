#!/usr/bin/env python3
"""
質詢擬答離線查詢系統 — 建檔腳本

用法：
    python3 build.py                      # 讀 input/*.docx，輸出 output/index.html
    python3 build.py --input 資料夾 --output 檔案.html
    python3 build.py --report             # 只列出切題結果（題目清單），不產生網頁，供人工核對

    python3 build.py --mobile             # 另外輸出手機用「密碼加密版」（會詢問密碼）

切題規則：
    * 以「分節符號」或「分頁符號」為頁界。
    * 每頁第一個非空、且整段粗體的段落 = 題目；它之前若有「標題」樣式段落，當作前置標籤（例如題號、會期）。
    * 檔案開頭、第一題之前若只有少量文字（封面），其第一段視為「科別／來源」標籤。
    * 第一段為「目錄」或「目次」的頁面（含跨頁的目錄）略過，不當成題目。
    * Word 自動編號（例如「2-2.」「一、」「（一）」）會還原成文字，可用題號搜尋。
    * 內文保留粗體、底線、表格與圖片（圖片以 base64 內嵌，離線可看）。
    * 舊版 .doc 會先自動轉成 .docx（需本機有 LibreOffice 或 Microsoft Word），轉檔結果放在 input/.converted/。

資料完全在本機處理，不會連網。
"""
import argparse
import base64
import datetime as dt
import html
import json
import os
import math
import platform
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

try:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph
except ImportError:
    sys.exit("缺少 python-docx，請先執行：python3 -m pip install python-docx")

HERE = Path(__file__).resolve().parent
COVER_MAX_CHARS = 120          # 第一頁內文少於此字數視為封面
MIN_IMAGE_BYTES = 500          # 小於此大小的圖形物件視為裝飾（文字方塊、線條），略過
MAX_NUMBER_SENTENCES = 10
SECTION_MAX_CHARS = 40         # 主題分頁標題頁的字數上限
SECTION_RE = re.compile(r"^(?:[壹貳參肆伍陸柒捌玖拾]+[、.．]|第[一二三四五六七八九十百0-9０-９]+[章篇部節類]|專區)")

NUM_RE = re.compile(r"[0-9０-９]|[一二三四五六七八九十百千萬億零〇]+(?:人|名|員|個|％|%|億|萬|年|元|席|案|類|成)")
SENT_SPLIT_RE = re.compile(r"(?<=[。；！？!?；])|\n")


# ---------------------------------------------------------------- helpers
def esc(s: str) -> str:
    return html.escape(s, quote=False)


def run_is_bold(run, para) -> bool:
    b = run.bold
    if b is None:
        try:
            if run.style is not None and run.style.font.bold:
                return True
        except Exception:
            pass
        st = para.style
        while st is not None:
            if st.font.bold is not None:
                return bool(st.font.bold)
            st = st.base_style
        return False
    return bool(b)


def para_all_bold(para) -> bool:
    runs = [r for r in para.runs if r.text.strip()]
    if not runs:
        return False
    return all(run_is_bold(r, para) for r in runs)


def para_is_heading_style(para) -> bool:
    name = (para.style.name if para.style is not None else "") or ""
    return name.lower().startswith(("heading", "title", "標題"))


def para_breaks_page(p_el, para) -> tuple[bool, bool]:
    """回傳 (此段之前換頁, 此段之後換頁)。"""
    before = bool(para.paragraph_format.page_break_before)
    after = False
    if p_el.find(qn("w:pPr") + "/" + qn("w:sectPr")) is not None:
        after = True
    for br in p_el.iter(qn("w:br")):
        if br.get(qn("w:type")) == "page":
            # 分頁符號若在段落開頭，視為「之前」換頁；否則「之後」
            r = br.getparent()
            prev_text = "".join(
                t.text or "" for t in r.itersiblings(preceding=True) for t in t.iter(qn("w:t"))
            )
            if prev_text.strip():
                after = True
            else:
                before = True
    return before, after


# ---------------------------------------------------------------- Word 自動編號
_CN_DIGITS = "零一二三四五六七八九"


def cn_number(n: int) -> str:
    """1→一、10→十、21→二十一、105→一百零五（一般公文編號用到百位已足夠）。"""
    if n <= 0:
        return str(n)
    if n >= 1000:
        return str(n)
    h, rest = divmod(n, 100)
    t, u = divmod(rest, 10)
    s = ""
    if h:
        s += _CN_DIGITS[h] + "百"
    if t:
        s += ("" if (t == 1 and not h) else _CN_DIGITS[t]) + "十"
    elif h and u:
        s += "零"
    if u:
        s += _CN_DIGITS[u]
    return s


def roman(n: int) -> str:
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
            (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, r in vals:
        while n >= v:
            out += r
            n -= v
    return out


def format_num(n: int, fmt: str) -> str:
    if fmt in ("decimal", "decimalZero"):
        return f"{n:02d}" if fmt == "decimalZero" else str(n)
    if fmt == "decimalFullWidth":
        return str(n).translate(str.maketrans("0123456789", "０１２３４５６７８９"))
    if fmt in ("chineseCountingThousand", "taiwaneseCountingThousand", "chineseCounting",
               "taiwaneseCounting", "ideographDigital", "chineseLegalSimplified"):
        return cn_number(n)
    if fmt in ("ideographTraditional",):
        return "甲乙丙丁戊己庚辛壬癸"[(n - 1) % 10]
    if fmt in ("ideographZodiac",):
        return "子丑寅卯辰巳午未申酉戌亥"[(n - 1) % 12]
    if fmt == "upperLetter":
        return chr(64 + (n - 1) % 26 + 1)
    if fmt == "lowerLetter":
        return chr(96 + (n - 1) % 26 + 1)
    if fmt == "upperRoman":
        return roman(n)
    if fmt == "lowerRoman":
        return roman(n).lower()
    if fmt in ("bullet", "none"):
        return ""
    return str(n)


class Numbering:
    """依 Word 的 numbering.xml 計算每個段落的自動編號文字（python-docx 本身不提供）。"""

    def __init__(self, doc):
        self.levels = {}      # numId -> {ilvl: (fmt, lvlText, start)}
        self.counters = {}    # numId -> {ilvl: 目前數值}
        try:
            root = doc.part.numbering_part.element
        except Exception:
            return
        abstract = {}
        for a in root.findall(qn("w:abstractNum")):
            lv = {}
            for l in a.findall(qn("w:lvl")):
                lv[int(l.get(qn("w:ilvl")))] = self._lvl(l, ("decimal", "%1.", 1))
            abstract[a.get(qn("w:abstractNumId"))] = lv
        for n in root.findall(qn("w:num")):
            aid = n.find(qn("w:abstractNumId"))
            lv = dict(abstract.get(aid.get(qn("w:val")) if aid is not None else None, {}))
            for o in n.findall(qn("w:lvlOverride")):
                i = int(o.get(qn("w:ilvl")))
                so = o.find(qn("w:startOverride"))
                ol = o.find(qn("w:lvl"))
                if ol is not None:
                    lv[i] = self._lvl(ol, lv.get(i, ("decimal", "%1.", 1)))
                if so is not None and i in lv:
                    lv[i] = (lv[i][0], lv[i][1], int(so.get(qn("w:val"))))
            self.levels[n.get(qn("w:numId"))] = lv

    @staticmethod
    def _lvl(l, default):
        def val(tag, d):
            e = l.find(qn(tag))
            return e.get(qn("w:val")) if e is not None and e.get(qn("w:val")) is not None else d
        fmt, text, start = default
        return (val("w:numFmt", fmt), val("w:lvlText", text), int(val("w:start", start)))

    @staticmethod
    def _num_pr(para):
        """段落本身或其樣式（含繼承）上的編號設定。"""
        el = para._p.find(qn("w:pPr") + "/" + qn("w:numPr"))
        st = para.style
        while el is None and st is not None:
            ppr = st.element.find(qn("w:pPr"))
            el = ppr.find(qn("w:numPr")) if ppr is not None else None
            st = st.base_style
        if el is None:
            return None, None
        nid = el.find(qn("w:numId"))
        ilvl = el.find(qn("w:ilvl"))
        return (nid.get(qn("w:val")) if nid is not None else None,
                int(ilvl.get(qn("w:val"))) if ilvl is not None else 0)

    def label(self, para) -> str:
        try:
            nid, ilvl = self._num_pr(para)
        except Exception:
            return ""
        if not nid or nid == "0" or nid not in self.levels:
            return ""
        lv = self.levels[nid]
        if ilvl not in lv:
            return ""
        cnt = self.counters.setdefault(nid, {})
        cnt[ilvl] = cnt.get(ilvl, lv[ilvl][2] - 1) + 1
        for deeper in [k for k in cnt if k > ilvl]:   # 上層前進時，下層重新起算
            del cnt[deeper]
        fmt, text, _ = lv[ilvl]
        if fmt in ("bullet", "none"):
            return ""

        def sub(m):
            k = int(m.group(1)) - 1
            if k not in lv:
                return ""
            n = cnt.get(k, lv[k][2])     # 未出現過的上層，以其起始值顯示
            return format_num(n, lv[k][0])
        return re.sub(r"%(\d)", sub, text)


class ImageStore:
    def __init__(self):
        self.count = 0
        self.skipped = 0

    def extract(self, el, part) -> list[str]:
        """回傳段落內所有圖片的 <img> HTML。"""
        out = []
        for blip in el.iter(qn("a:blip")):
            rid = blip.get(qn("r:embed"))
            if not rid or rid not in part.rels:
                continue
            rel = part.rels[rid]
            try:
                blob = rel.target_part.blob
                ctype = rel.target_part.content_type
            except Exception:
                continue
            if len(blob) < MIN_IMAGE_BYTES or not ctype.startswith("image/"):
                self.skipped += 1
                continue
            if ctype in ("image/x-emf", "image/x-wmf", "image/emf", "image/wmf"):
                # 瀏覽器無法顯示 EMF/WMF，留下提示
                out.append('<div class="img-missing">［此處有 EMF/WMF 向量圖，瀏覽器無法顯示，請見原 Word 檔］</div>')
                self.skipped += 1
                continue
            self.count += 1
            b64 = base64.b64encode(blob).decode("ascii")
            out.append(f'<img src="data:{ctype};base64,{b64}" alt="圖{self.count}">')
        return out


# ---------------------------------------------------------------- rendering
def render_runs(para) -> str:
    parts = []
    for r in para.runs:
        t = r.text
        if not t:
            continue
        s = esc(t).replace("\n", "<br>")
        if run_is_bold(r, para):
            s = f"<b>{s}</b>"
        if r.underline:
            s = f"<u>{s}</u>"
        parts.append(s)
    return "".join(parts)


def render_paragraph(para, p_el, part, images: ImageStore, num: "Numbering | None" = None) -> tuple[str, str]:
    """回傳 (html, plain_text)。有自動編號時，編號文字放在段首。"""
    imgs = images.extract(p_el, part)
    text = para.text
    h = ""
    if text.strip():
        lab = num.label(para) if num is not None else ""
        body = render_runs(para)
        if lab:
            text = lab + text
            body = (f"<b>{esc(lab)}</b>" if para_all_bold(para) else esc(lab)) + body
        h = f"<p>{body}</p>"
    if imgs:
        h += '<figure>' + "".join(imgs) + "</figure>"
    return h, text


def render_table(tbl: Table, part, images: ImageStore, num: "Numbering | None" = None) -> tuple[str, str]:
    rows_html = []
    texts = []
    for row in tbl.rows:
        seen = set()
        cells_html = []
        for cell in row.cells:
            key = id(cell._tc)
            if key in seen:
                continue  # 水平合併儲存格重複出現
            seen.add(key)
            inner_html = []
            inner_text = []
            for child in cell._tc.iterchildren():
                tag = child.tag.split("}")[1]
                if tag == "p":
                    p = Paragraph(child, cell)
                    h, t = render_paragraph(p, child, part, images, num)
                    inner_html.append(h)
                    inner_text.append(t)
                elif tag == "tbl":
                    h, t = render_table(Table(child, cell), part, images, num)
                    inner_html.append(h)
                    inner_text.append(t)
            span = child_span(cell._tc)
            attr = f' colspan="{span}"' if span > 1 else ""
            cells_html.append(f"<td{attr}>{''.join(inner_html)}</td>")
            texts.append(" ".join(x for x in inner_text if x.strip()))
        rows_html.append("<tr>" + "".join(cells_html) + "</tr>")
    return "<table>" + "".join(rows_html) + "</table>", "\n".join(texts)


def child_span(tc) -> int:
    gs = tc.find(qn("w:tcPr") + "/" + qn("w:gridSpan"))
    try:
        return int(gs.get(qn("w:val"))) if gs is not None else 1
    except Exception:
        return 1


# ---------------------------------------------------------------- parsing
def parse_docx(path: Path, images: ImageStore) -> dict:
    doc = Document(str(path))
    part = doc.part
    body = doc.element.body
    num = Numbering(doc)

    pages = [[]]  # 每頁是一串 block：dict(kind, html, text, bold, heading)
    for child in body.iterchildren():
        tag = child.tag.split("}")[1]
        if tag == "p":
            para = Paragraph(child, doc)
            before, after = para_breaks_page(child, para)
            if before and pages[-1]:
                pages.append([])
            h, t = render_paragraph(para, child, part, images, num)
            if h:
                pages[-1].append(dict(kind="p", html=h, text=t, bold=para_all_bold(para),
                                      heading=para_is_heading_style(para)))
            if after:
                pages.append([])
        elif tag == "tbl":
            h, t = render_table(Table(child, doc), part, images, num)
            pages[-1].append(dict(kind="tbl", html=h, text=t, bold=False, heading=False))
    pages = [p for p in pages if p]

    def first_text(page):
        b = next((b for b in page if b["text"].strip()), None)
        return re.sub(r"[\s\u3000]", "", b["text"]) if b else ""

    def is_toc(page):
        t = first_text(page)
        return len(t) <= 20 and t.endswith(("目錄", "目次", "目錄表"))

    # 本檔若以 Word「標題」樣式標示題目（至少 2 題），則只認標題樣式段落為題目；
    # 其他頁面開頭的粗體段落（答復要點）視為上一題的跨頁內容，避免一題被切成多題
    heading_titles = 0
    for page in pages:
        b = next((b for b in page if b["kind"] == "p" and (b["bold"] or b["heading"])), None)
        if b and b["heading"] and not SECTION_RE.match(b["text"]) and not is_toc(page):
            heading_titles += 1
    heading_mode = heading_titles >= 2

    cover = ""
    section = ""
    items = []
    in_toc = False
    for idx, page in enumerate(pages):
        # 目錄頁：第一段以「目錄／目次」結尾者略過（如「組編人力處目錄」）；其後沒有題目的頁面視為目錄續頁
        if is_toc(page):
            in_toc = True
            continue
        if in_toc and not any(b["kind"] == "p" and (b["bold"] or b["heading"]) for b in page):
            continue
        in_toc = False

        page_chars = sum(len(b["text"].strip()) for b in page)
        has_rich = any(b["kind"] == "tbl" or "<img" in b["html"] for b in page)
        # 主題分頁標題（如「壹、與組織編制有關」）：整頁只有短短一行，記為後續題目的分類標籤
        lines = [b for b in page if b["text"].strip()]
        if (not has_rich and page_chars <= SECTION_MAX_CHARS and SECTION_RE.match(first_text(page))
                and not any(b["kind"] == "p" and (b["bold"] or b["heading"]) for b in lines[1:])):
            section = next(b for b in page if b["text"].strip())["text"].strip()
            continue

        # 找題目
        if heading_mode:
            title_i = next((i for i, b in enumerate(page) if b["kind"] == "p" and b["heading"]), None)
        else:
            title_i = next((i for i, b in enumerate(page) if b["kind"] == "p" and b["bold"]), None)
        # 同一頁先有分類標題、後有題目：分類標題記為標籤，題目取下一個
        if title_i is not None and SECTION_RE.match(page[title_i]["text"].strip()):
            key = "heading" if heading_mode else "bold"
            nxt = next((i for i in range(title_i + 1, len(page)) if page[i]["kind"] == "p" and page[i][key]), None)
            if nxt is not None:
                section = page[title_i]["text"].strip()
                page = page[:title_i] + page[title_i + 1:]
                title_i = nxt - 1
        pre = [b for b in page[:title_i] if b["kind"] == "p"] if title_i is not None else []
        body_blocks = page[title_i + 1:] if title_i is not None else page
        body_chars = sum(len(b["text"].strip()) for b in body_blocks)

        # 封面：只看第一頁；題目樣式的段落（標題樣式、或以問號結尾）不會被當成封面
        looks_like_q = title_i is not None and (heading_mode or page[title_i]["text"].strip().endswith(("？", "?")))
        if idx == 0 and not items and body_chars < COVER_MAX_CHARS and not has_rich and not looks_like_q:
            # 封面：第一段記為封面文字（僅供參考，來源以檔名顯示）
            cover = first_text(page)
            continue

        if title_i is None:
            # 沒有題目的頁面：併入前一題（跨頁內容）
            if items:
                items[-1]["html"] += "".join(b["html"] for b in page)
                items[-1]["text"] += "\n" + "\n".join(b["text"] for b in page)
                items[-1]["para_text"] += "\n" + "\n".join(b["text"] for b in page if b["kind"] == "p")
                items[-1]["pages"] += 1
                continue
            title = f"（未偵測到題目）第 {idx + 1} 頁"
        else:
            title = page[title_i]["text"].strip()

        pre_text = " ".join(b["text"].strip() for b in pre if b["text"].strip())
        items.append(dict(
            title=title,
            pre=" ".join(x for x in (section, pre_text) if x),
            html="".join(b["html"] for b in body_blocks),
            text="\n".join(b["text"] for b in body_blocks),
            # 數字速查只取段落文字，表格內容不拆句（表格會完整顯示在全文中）
            para_text="\n".join(b["text"] for b in body_blocks if b["kind"] == "p"),
            pages=1,
            hasTable=any(b["kind"] == "tbl" for b in body_blocks),
            hasImage=any("<img" in b["html"] for b in body_blocks),
        ))

    # 來源一律以檔名顯示（同一題的摘要版／詳細版等不同版本，靠檔名區分）
    return dict(file=path.name, dept=path.stem, items=items, cover=cover,
                mode="標題樣式" if heading_mode else "粗體段落")



def number_sentences(text: str) -> list[str]:
    out = []
    for s in SENT_SPLIT_RE.split(text):
        s = s.strip()
        cjk = len(re.findall(r"[一-鿿]", s))
        if 6 <= len(s) <= 160 and cjk >= 4 and NUM_RE.search(s) and s not in out:
            out.append(s)
        if len(out) >= MAX_NUMBER_SENTENCES:
            break
    return out


def load_synonyms(path: Path) -> dict:
    """synonyms.txt 格式：每行一個主題，「主題名：詞1、詞2、詞3」。# 開頭為註解。"""
    topics = {}
    if not path.exists():
        return topics
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "：" in line:
            name, terms = line.split("：", 1)
        elif ":" in line:
            name, terms = line.split(":", 1)
        else:
            continue
        words = [w.strip() for w in re.split(r"[、,，;；\s]+", terms) if w.strip()]
        name = name.strip()
        if name and name not in words:
            words.insert(0, name)
        topics[name] = words
    return topics


# ---------------------------------------------------------------- .doc 轉檔
def find_soffice():
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    mac = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    return str(mac) if mac.exists() else None


def convert_doc(src: Path, out_dir: Path) -> Path | None:
    """把舊版 .doc 轉成 .docx（結果快取在 out_dir，原檔較新時才重轉）。失敗回傳 None。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / (src.stem + ".docx")
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return dst
    soffice = find_soffice()
    if soffice:
        r = subprocess.run([soffice, "--headless", "--convert-to", "docx", "--outdir", str(out_dir), str(src)],
                           capture_output=True, text=True, timeout=180)
        if dst.exists():
            return dst
        print(f"  ！LibreOffice 轉檔失敗：{src.name}  {r.stderr.strip()[:200]}")
    if platform.system() == "Darwin" and Path("/Applications/Microsoft Word.app").exists():
        # 用 Mac 上的 Word 另存新檔（第一次執行時，系統可能詢問是否允許控制 Word，請按「好」）
        script = (
            'tell application "Microsoft Word"\n'
            f'  open (POSIX file "{src.resolve()}")\n'
            f'  save as active document file name "{dst.resolve()}" file format format document\n'
            '  close active document saving no\n'
            'end tell'
        )
        subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=180)
        if dst.exists():
            return dst
        print(f"  ！Word 轉檔失敗：{src.name}")
    return None


def collect_inputs(input_dir: Path) -> list[Path]:
    docx = [p for p in input_dir.glob("*.docx") if not p.name.startswith("~$")]
    docs = [p for p in input_dir.glob("*.doc") if not p.name.startswith("~$")]
    have = {p.stem for p in docx}
    failed = []
    for d in docs:
        if d.stem in have:
            print(f"  （略過 {d.name}：同名 .docx 已存在）")
            continue
        c = convert_doc(d, input_dir / ".converted")
        if c:
            print(f"  {d.name} → 已轉為 .docx（{c.relative_to(input_dir)}）")
            docx.append(c)
        else:
            failed.append(d.name)
    if failed:
        print("\n【以下 .doc 無法自動轉檔，本次未納入】" + "、".join(failed))
        print("  → 請用 Word 開啟後「另存新檔」選 .docx，放回 input/ 再執行一次。\n")
    return sorted(docx, key=lambda p: p.name)


# ---------------------------------------------------------------- 輕量「相關題目」（不需模型）
def bigrams(s: str) -> list[str]:
    s = re.sub(r"[^0-9A-Za-z一-鿿]+", " ", s)
    out = []
    for seg in s.split():
        out += [seg[i:i + 2] for i in range(len(seg) - 1)] if len(seg) > 1 else [seg]
    return out


def light_related(items, top_k=6, min_sim=0.12) -> list[list[dict]]:
    """以「中文兩字詞 TF-IDF 相似度」找相關題目；題目文字加權 3 倍。純 Python，數百題約數秒。"""
    vecs = []
    df = Counter()
    for it in items:
        tf = Counter(bigrams(it["title"]) * 3 + bigrams(it["text"]))
        vecs.append(tf)
        df.update(tf.keys())
    n = len(items)
    idf = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}
    norm_vecs = []
    for tf in vecs:
        v = {t: (1 + math.log(c)) * idf[t] for t, c in tf.items() if idf[t] > 0}
        z = math.sqrt(sum(x * x for x in v.values())) or 1
        norm_vecs.append({t: x / z for t, x in v.items()})
    out = []
    for i, a in enumerate(norm_vecs):
        sims = []
        for j, b in enumerate(norm_vecs):
            if i == j:
                continue
            small, big = (a, b) if len(a) < len(b) else (b, a)
            sim = sum(x * big.get(t, 0) for t, x in small.items())
            if sim >= min_sim:
                sims.append((sim, j))
        sims.sort(reverse=True)
        out.append([dict(id=items[j]["id"], score=round(s, 3)) for s, j in sims[:top_k]])
    return out


# ---------------------------------------------------------------- 手機密碼加密版
def encrypt_html(html_text: str, password: str, out: Path):
    """整份網頁 gzip 壓縮後以 AES-256-GCM 加密（金鑰由密碼經 PBKDF2-SHA256 60 萬次導出）。
    手機瀏覽器輸入密碼後在本機解密顯示；伺服器上只有密文。"""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
    except ImportError:
        sys.exit("缺少 cryptography 套件，請先執行：python3 -m pip install cryptography")
    import gzip
    iters = 600_000
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iters).derive(password.encode("utf-8"))
    ct = AESGCM(key).encrypt(iv, gzip.compress(html_text.encode("utf-8"), 9), None)
    b = lambda x: base64.b64encode(x).decode("ascii")
    shell = (HERE / "mobile_shell.html").read_text(encoding="utf-8")
    payload = json.dumps(dict(v=1, iter=iters, salt=b(salt), iv=b(iv), ct=b(ct)))
    out.write_text(shell.replace("/*__ENC__*/", payload), encoding="utf-8")
    print(f"已輸出手機加密版：{out}  ({out.stat().st_size / 1024 / 1024:.2f} MB)")


def ask_password() -> str:
    import getpass
    while True:
        p1 = getpass.getpass("請設定手機版密碼（至少 12 字元，輸入時不會顯示）：")
        if len(p1) < 12:
            print("  密碼太短，請至少 12 字元。")
            continue
        if getpass.getpass("請再輸入一次：") != p1:
            print("  兩次輸入不一致，請重新設定。")
            continue
        return p1


# ---------------------------------------------------------------- main
def build(input_dir: Path, output: Path, synonyms_path: Path, template_path: Path, report_only: bool,
          use_semantic: bool = True, semantic_search: bool = True, mobile_password: str | None = None):
    files = collect_inputs(input_dir)
    if not files:
        sys.exit(f"在 {input_dir} 找不到可讀取的 Word 檔（.docx／.doc）")

    images = ImageStore()
    topics = load_synonyms(synonyms_path)
    docs, items = [], []
    for f in files:
        d = parse_docx(f, images)
        docs.append(dict(file=d["file"], dept=d["dept"], count=len(d["items"]), mode=d["mode"]))
        for order, it in enumerate(d["items"], 1):
            full = it["title"] + "\n" + it["text"]
            tags = [name for name, words in topics.items() if any(w in full for w in words)]
            items.append(dict(
                id=f"{len(items) + 1}",
                dept=d["dept"], file=d["file"], order=order,
                title=it["title"], pre=it["pre"],
                html=it["html"], text=it["text"],
                numbers=number_sentences(it["para_text"]),
                topics=tags, pages=it["pages"],
                hasTable=it["hasTable"], hasImage=it["hasImage"],
            ))

    print(f"讀取 {len(files)} 份檔案，切出 {len(items)} 題，內嵌圖片 {images.count} 張（略過裝飾物件 {images.skipped} 個）")
    for d in docs:
        warn = "  ⚠ 0 題：此檔沒有可辨識的題目" if d["count"] == 0 else ""
        print(f"  - {d['file']}  題數={d['count']}  （題目判定：{d['mode']}）{warn}")
    if report_only:
        print("\n題目清單（請核對切題是否正確）：")
        for it in items:
            flag = ""
            if it["title"].startswith("（未偵測到題目）"):
                flag = " ⚠未偵測到題目"
            elif len(it["text"].strip()) < 30:
                flag = " ⚠內容過短（可能是分隔頁）"
            elif len(it["title"]) > 120:
                flag = " ⚠題目過長（可能把內文當題目）"
            extra = []
            if it["hasTable"]: extra.append("表")
            if it["hasImage"]: extra.append("圖")
            if it["pages"] > 1: extra.append(f"{it['pages']}頁")
            sec = f"〔{it['pre'][:12]}〕" if it["pre"] else ""
            print(f"[{it['dept'][:16]}] {it['order']:3d}. {sec}{it['title'][:50]}{flag}  {' '.join(extra)}")
        return

    # 第二階段：語意相近題目（本機模型，離線計算；環境不具備時自動略過）
    has_semantic = False
    if use_semantic and not (HERE / "semantic.py").exists():
        use_semantic = False
    if use_semantic:
        import semantic
        ok, why = semantic.available()
        if ok:
            rel, n_new, n_chunks = semantic.related_items(items)
            for it, r in zip(items, rel):
                it["related"] = r
            has_semantic = True
            print(f"語意相近題目：共 {n_chunks} 段，其中 {n_new} 段新計算（其餘取自快取）")
        else:
            print(f"【略過語意計算】{why}")
    if not has_semantic:
        for it, r in zip(items, light_related(items)):
            it["related"] = r
        print("相關題目：以輕量文字相似度計算（不需模型）")

    data = dict(
        built=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        docs=docs, topics=topics, items=items, semantic=has_semantic,
    )
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    template = template_path.read_text(encoding="utf-8")
    if "/*__DATA__*/" not in template:
        sys.exit("template.html 缺少 /*__DATA__*/ 標記")
    if "<!--__SEM_ASSETS__-->" not in template:
        sys.exit("template.html 缺少 <!--__SEM_ASSETS__--> 標記")
    base = template.replace("/*__DATA__*/", payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(base.replace("<!--__SEM_ASSETS__-->", ""), encoding="utf-8")
    print(f"已輸出：{output}  ({output.stat().st_size / 1024 / 1024:.1f} MB)")
    if mobile_password:
        encrypt_html(base.replace("<!--__SEM_ASSETS__-->", ""), mobile_password,
                     output.with_name(output.stem + "-手機加密版.html"))

    # 語意版：把模型、執行引擎、各段向量一起內嵌，查詢框可用語意搜尋（檔案較大，建議筆電使用）
    if has_semantic and semantic_search:
        sem_out = output.with_name(output.stem + "-語意版.html")
        sem_out.write_text(base.replace("<!--__SEM_ASSETS__-->", semantic_assets(items)), encoding="utf-8")
        print(f"已輸出：{sem_out}  ({sem_out.stat().st_size / 1024 / 1024:.1f} MB)")


def write_empty(template_path: Path, output: Path):
    """只輸出程式外殼，不含任何題目、向量或來源資訊。"""
    data = dict(built=dt.datetime.now().strftime("%Y-%m-%d %H:%M"), docs=[], topics={}, items=[], semantic=False)
    template = template_path.read_text(encoding="utf-8")
    out = template.replace("/*__DATA__*/", json.dumps(data, ensure_ascii=False)).replace("<!--__SEM_ASSETS__-->", "")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(out, encoding="utf-8")
    print(f"已輸出空殼版：{output}  ({output.stat().st_size / 1024:.0f} KB)")


def semantic_assets(items) -> str:
    import semantic
    vendor = HERE / "vendor"
    ort_js = (vendor / "ort.wasm.bundle.min.mjs").read_text(encoding="utf-8")
    # 把 ES module 的 export 改成掛到 window，才能直接內嵌在單一 HTML 中
    m = re.search(r"export\s*\{([^}]*)\}\s*;?\s*(//# sourceMappingURL=\S+\s*)?$", ort_js)
    if not m:
        sys.exit("vendor/ort.wasm.bundle.min.mjs 格式與預期不符（找不到 export）")
    pairs = []
    for part in m.group(1).split(","):
        local, _, exported = part.strip().partition(" as ")
        pairs.append(f"{(exported or local).strip()}:{local.strip()}")
    ort_js = ort_js[:m.start()] + "window.__ort={" + ",".join(pairs) + "};"
    uni_js = (vendor / "unigram.js").read_text(encoding="utf-8")
    for name, src in (("ort", ort_js), ("unigram", uni_js)):
        if "</script" in src.lower():
            sys.exit(f"{name} 原始碼含有 </script，無法內嵌")
    pieces, scores_b64 = semantic.vocab_payload()
    pieces_b64 = base64.b64encode(pieces.encode("utf-8")).decode("ascii")
    b64 = lambda p: base64.b64encode(p.read_bytes()).decode("ascii")
    meta = json.dumps(semantic.browser_payload(items))
    return "\n".join([
        f'<script id="sem-meta" type="application/json">{meta}</script>',
        f'<script id="sem-pieces" type="application/octet-stream">{pieces_b64}</script>',
        f'<script id="sem-scores" type="application/octet-stream">{scores_b64}</script>',
        f'<script id="sem-wasm" type="application/octet-stream">{b64(vendor / "ort-wasm-simd-threaded.wasm")}</script>',
        f'<script id="sem-model" type="application/octet-stream">{b64(semantic.MODEL_DIR / "model_quantized.onnx")}</script>',
        f"<script>{uni_js}</script>",
        f'<script type="module">{ort_js}</script>',
    ])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=str(HERE / "input"), help="Word 檔資料夾")
    ap.add_argument("--output", default=str(HERE / "output" / "index.html"))
    ap.add_argument("--synonyms", default=str(HERE / "synonyms.txt"))
    ap.add_argument("--template", default=str(HERE / "template.html"))
    ap.add_argument("--report", action="store_true", help="只列出切題結果，不產生網頁")
    ap.add_argument("--no-semantic", action="store_true", help="不計算語意相近題目（較快）")
    ap.add_argument("--no-semantic-search", action="store_true", help="不另外輸出「語意版」大檔")
    ap.add_argument("--empty", action="store_true", help="輸出不含任何資料的空殼網頁（例如給其他單位套用）")
    ap.add_argument("--mobile", action="store_true", help="另外輸出手機用密碼加密版（執行時詢問密碼）")
    a = ap.parse_args()
    pw = None
    if a.mobile and not a.report:
        pw = os.environ.get("QA_PASSWORD") or ask_password()
    if a.empty:
        write_empty(Path(a.template), Path(a.output))
        sys.exit(0)
    build(Path(a.input), Path(a.output), Path(a.synonyms), Path(a.template), a.report,
          not a.no_semantic, not a.no_semantic_search, pw)

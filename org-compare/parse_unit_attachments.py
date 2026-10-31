#!/usr/bin/env python3
"""
解析各機關辦事細則「附表」（內部單位設置表 PDF），取得以附表列單位的（多為四級）機關之內部單位清單。

用法：
    python3 parse_unit_attachments.py --master 總表.xlsx --cache moj_cache --pdf-dir moj_cache/pdfs_units --out units_from_attachments.json [--offline]

作法：對總表「條文」中每個處務規程／辦事細則 pcode，若條文含「如附表」且開放資料有 PDF 附件，下載後：
  1. 先用表格模式：第一欄（機關名稱）向下填滿，合併續列，取「內部單位」欄；
  2. 表格讀不到時用文字模式：以機關名稱為分隔，擷取其後出現的單位名稱。
輸出 {機關全名: {"單位": [...], "依據": "附件檔名"}}。
"""
import argparse, json, os, re, subprocess, sys, time
import pandas as pd
import pdfplumber
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UNIT_TAIL = r'(?:組|科|室|課|股|中心|站|隊|所|分院|處|部|館|園|場|段|班|員|會|大隊|小組|中隊)'
UNIT_RE = re.compile(r'[一-龥（）()]{1,14}?' + UNIT_TAIL + r'$')
AGENCY_TAIL = re.compile(r'(分局|分署|監理所|工程分局|管理處|航空站|醫院|療養院|榮民服務處|之家|農場|分所|分院|分處|檢驗所|總臺|教養院|兒童之家|老人之家|中心)$')
ENUM_RE = re.compile(r'[一二三四五六七八九十]+、')

NOISE_RE = re.compile(r'^(?:各|合計|共|另|其中|必要時|得|[一二三四五六七八九十百]+(?:個|所|隊|站|股|組|分隊|小隊|中隊)|.*得於.*|.*合計.*)')
def clean_units(text):
    text = re.sub(r'\s', '', text or '')
    text = re.sub(r'（[^）]*）|\([^)]*\)', '', text)
    parts = re.split(r'[、，。；,;：:]|' + ENUM_RE.pattern, text)
    out = []
    for p in parts:
        p = p.strip()
        if not p or len(p) > 16 or NOISE_RE.match(p): continue
        p = re.sub(r'^(?:[一二三四五六七八九十]+個)', '', p)
        if UNIT_RE.match(p) and not re.search(r'及.*(隊|所|站)$', p) and p not in out:
            out.append(p)
    return out

HDR_RE = re.compile(r'名稱|單位|類型|等級|機關|醫院|設置')
def parse_tables(pdf):
    """回傳 [(機關名稱, 單位欄文字)]：機關名稱向下填滿、續列合併；分組表（類型／等級）中空白單位欄沿用同組前一列。"""
    rows, name_col, unit_col, grouped = [], 0, 1, False
    for page in pdf.pages:
        for t in page.extract_tables():
            if not t or len(t[0]) < 2: continue
            hdr = [re.sub(r'\s', '', c or '') for c in t[0]]
            data = t
            if sum(1 for h in hdr if HDR_RE.search(h)) >= 1 and all(len(h) <= 12 for h in hdr):
                data = t[1:]
                name_col = next((i for i, h in enumerate(hdr) if re.search(r'名稱|機關|醫院|分局|分署|所$', h)), 0)
                unit_col = next((i for i, h in enumerate(hdr) if i != name_col and re.search(r'內部|單位|組|科|室', h)), name_col + 1)
                grouped = any(re.search(r'類型|等級|種類', h) for h in hdr) and name_col > 0
            cur = None
            for r in data:
                cells = [re.sub(r'\s', '', c or '') for c in r]
                nm = cells[name_col] if name_col < len(cells) else ''
                grp_start = grouped and bool(cells[0]) and name_col != 0
                if nm and re.search(AGENCY_TAIL.pattern[:-1] + r'$', nm):
                    cur = nm; rows.append([cur, '', grp_start])
                elif nm and cur is None:
                    cur = nm; rows.append([cur, '', grp_start])
                if cur is None: continue
                txt = cells[unit_col] if unit_col < len(cells) else ''
                if not txt:
                    for i, c in enumerate(cells):
                        if i != name_col and c != nm and len(c) > 1 and re.search(UNIT_TAIL + r'(?:[。、，]|$)', c): txt = c; break
                rows[-1][1] += txt
    if grouped:  # 同一類型組內，空白單位欄沿用組首列；新組開始即重設
        last = ''
        for r in rows:
            if r[2]: last = r[1]
            elif not clean_units(r[1]) and last: r[1] = last
            elif clean_units(r[1]): last = r[1]
    return [(r[0], r[1]) for r in rows]

def parse_text(pdf):
    text = ''.join((p.extract_text() or '') + '\n' for p in pdf.pages)
    text = re.sub(r'[ \t　]', '', text)
    rows, cur = [], None
    for line in text.split('\n'):
        m = re.match(r'^([\u4e00-\u9fa5]{2,20}?' + AGENCY_TAIL.pattern[:-1] + r')', line)
        if m and not re.search(r'^(?:一|二|三|四|五|六|七|八|九|十)+、', line):
            cur = m.group(1); rows.append([cur, line[m.end():]]); continue
        if cur: rows[-1][1] += line
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--master', required=True); ap.add_argument('--cache', default='moj_cache')
    ap.add_argument('--pdf-dir', default='moj_cache/pdfs_units'); ap.add_argument('--out', default='units_from_attachments.json')
    ap.add_argument('--offline', action='store_true')
    a = ap.parse_args()
    from check_updates import load_open_data
    idx = load_open_data(a.cache, a.offline)
    art = pd.read_excel(a.master, '條文', dtype=str)
    art['pcode'] = art['連結'].str.extract(r'pcode=([A-Z]\d{7})')[0]
    proc = art[(art['法規類別'] != '組織法規')]
    need = proc[proc['條文內容'].str.contains('如附表', na=False)]
    by_pc = need.groupby('pcode')['機關'].apply(lambda s: sorted(set(s))).to_dict()
    os.makedirs(a.pdf_dir, exist_ok=True)
    result, stats = {}, []
    for pc, agencies in by_pc.items():
        L = idx.get(pc)
        if not L: continue
        atts = [x for x in L['LawAttachements'] if x['FileName'].upper().endswith('.PDF') and re.search(r'單位', x['FileName'])] or \
               [x for x in L['LawAttachements'] if x['FileName'].upper().endswith('.PDF')]
        if not atts: stats.append((pc, L['LawName'], len(agencies), 0, '無PDF附件')); continue
        att = atts[-1]; fid = att['FileURL'].split('FileId=')[1]
        p = os.path.join(a.pdf_dir, f'{pc}_{fid}.pdf')
        if not os.path.exists(p):
            subprocess.run(['curl', '-sS', '-L', '--max-time', '120', '-A', 'Mozilla/5.0', '-o', p, att['FileURL'] + '&lan=C']); time.sleep(0.5)
        if not (os.path.exists(p) and open(p, 'rb').read(4) == b'%PDF'):
            stats.append((pc, L['LawName'], len(agencies), 0, 'PDF下載失敗')); continue
        with pdfplumber.open(p) as pdf:
            if not any((pg.extract_text() or '').strip() for pg in pdf.pages):
                stats.append((pc, L['LawName'], len(agencies), 0, '掃描檔，需 OCR')); continue
            rows = parse_tables(pdf)
            mode = '表格'
            if sum(1 for n, u in rows if clean_units(u)) < max(1, len(agencies) // 3):
                rows2 = parse_text(pdf)
                if sum(1 for n, u in rows2 if clean_units(u)) > sum(1 for n, u in rows if clean_units(u)):
                    rows = rows2; mode = '文字'
        found = 0
        for ag in agencies:
            units = None
            cands = []
            for nm, utxt in rows:
                nm2 = re.sub(r'[\s　]', '', nm)
                if len(nm2) < 3 or nm2 in ('分署', '分局', '醫院', '名稱', '機關名稱'): continue
                if ag.endswith(nm2) or nm2 == ag: score = 2
                elif nm2 in ag and len(nm2) >= 4: score = 1
                elif ag in nm2: score = 1
                else: continue
                u = clean_units(utxt)
                if u: cands.append((score, len(nm2), u))
            if cands:
                cands.sort(key=lambda x: (-x[0], -x[1])); units = cands[0][2]
            if units:
                found += 1
                result[ag] = {'單位': units, '依據': f'{L["LawName"]}附表「{att["FileName"]}」'}
        stats.append((pc, L['LawName'], len(agencies), found, mode))
    json.dump(result, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for s in stats: print(s)
    print(f'共 {sum(s[2] for s in stats)} 個機關，解析到 {len(result)} 個 → {a.out}')

if __name__ == '__main__':
    main()

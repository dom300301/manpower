#!/usr/bin/env python3
"""
資料整備：把「組織法編制表_總表.xlsx」整理成查詢系統用的 JSON（不論最後採哪種系統形式都需要）。

用法：
    python3 build_dataset.py --master 總表.xlsx --out data/ [--fixes manual_fixes.json] [--attach-units units_from_attachments.json]

輸出：
    data/agencies.json   每機關一筆：基本資料 + 結構指標 + 品質旗標
    data/positions.json  編制表明細（每職稱一列，含數值化員額、職等上下限、是否主管、是否簡任、列品質）
    data/articles.json   組織法規與處務規程條文
    data/meta.json       資料版本（總表產生時間、整備時間、機關數）
    data/建檔檢核.md     建檔時語意檢查命中的列與機關（待審清單）

缺值語義（2026-11-07 起）：
    無任何員額數字可加總的機關，人數類指標一律 null（不是 0），並以「資料狀態」說明原因；
    明細有錯位或疑似控制列待審者，同樣不給總額（避免把剩餘加總當成正確總額）。
品質旗標：
    驗算結果（列舉）、品質註記（陣列）、可比較（布林，程式驗算，不看字串前綴）、來源核對狀態（與表內驗算分開記錄）。
"""
import argparse, json, os, re, datetime as dt
import pandas as pd

import unicodedata
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))   # python -I 下仍可匯入同目錄模組
from statutory_headcount import parse_agency as statutory_parse, summarize as statutory_summary, scan_contract_clauses
CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
def nfkc(s):
    """解析副本用：NFKC 正規化（相容字 六 U+F9D1→六、全形括號／數字→半形）。顯示與匯出一律用 raw。"""
    return unicodedata.normalize('NFKC', s) if isinstance(s, str) else s
def cn_int(t):
    """中文數字字串 → 整數。支援 十七、二十、一○三、一一八四、一Ｏ一、阿拉伯數字；不可解析回 None。"""
    if t is None: return None
    t = nfkc(str(t)).replace('O', '○').replace('o', '○').replace('〇', '○').replace('零', '○').strip()
    if not t: return None
    if t.isdigit(): return int(t)
    if re.search(r'[一二三四五六七八九十百千]', t) and '0' in t and not re.search(r'[1-9]', t): t = t.replace('0', '○')
    if not re.fullmatch(r'[○一二三四五六七八九十百千]+', t): return None
    if '十' not in t and '百' not in t and '千' not in t:
        return int(''.join(str({'○': 0, **CN}[c]) for c in t))
    total, num = 0, 0
    for c in t:
        if c in CN: num = CN[c]
        elif c == '十': total += (num or 1) * 10; num = 0
        elif c == '百': total += (num or 1) * 100; num = 0
        elif c == '千': total += (num or 1) * 1000; num = 0
    return total + num
NUM_TOK = r'[○〇零一二三四五六七八九十百千0-9Oo]+'
RANGE_SEP = r'[－—–\-～~至]'
def parse_headcount(raw):
    """員額原文 → 結構化（專任部分與括號部分各自上下限）。
    回傳 dict：專任_min, 專任_max, 專任_is_range, paren_raw, paren_min, paren_max, paren_is_range, 可解析(bool)
    例：'七'→(7,7)；'七-九'→(7,9,區間)；'三（六－八）'→專任(3,3)，括號(6,8,區間)；'（一）'→專任(0,0)，括號(1,1)；'(三~五)'→專任(0,0)，括號(3,5,區間)。"""
    out = {'專任_min': None, '專任_max': None, '專任_is_range': False, 'paren_raw': None, 'paren_min': None, 'paren_max': None, 'paren_is_range': False, '可解析': False}
    if raw is None or (isinstance(raw, float) and raw != raw): return out
    s = nfkc(str(raw)).replace('\u3127', '一').replace('\u039f', '○').replace('\u03bf', '○'); s = re.sub(r'\s', '', s)   # 解析副本：注音ㄧ→一、希臘 Ο→○（raw 不變）
    if not s: return out
    m = re.fullmatch(r'(' + NUM_TOK + r'(?:' + RANGE_SEP + NUM_TOK + r')?)?(?:[（(](' + NUM_TOK + r'(?:' + RANGE_SEP + NUM_TOK + r')?)[）)])?', s)
    if not m: return out
    def span(x):
        if x is None: return None, None, False
        parts = re.split(RANGE_SEP, x)
        lo = cn_int(parts[0]); hi = cn_int(parts[-1]) if len(parts) > 1 else lo
        if lo is None or hi is None: return None, None, False
        return lo, hi, len(parts) > 1
    fmin, fmax, frange = span(m.group(1)); pmin, pmax, prange = span(m.group(2))
    if m.group(1) is None and m.group(2) is None: return out
    if m.group(1) is None: fmin, fmax = 0, 0  # 純括號：專任 0（原表無專任）
    if (m.group(1) is not None and fmin is None) or (m.group(2) is not None and pmin is None): return out
    out.update({'專任_min': fmin, '專任_max': fmax, '專任_is_range': frange, 'paren_raw': m.group(2) and raw[raw.find('(') if '(' in raw else raw.find('（'):],
                'paren_min': pmin, 'paren_max': pmax, 'paren_is_range': prange, '可解析': True})
    return out

CONC_RE = re.compile(r'兼任|兼辦|兼理|兼充|派員兼|由.{1,14}兼')
UPPER_RE = re.compile(r'上限|不得高於|不得超過|最高')
COMMITTEE_TITLES = {'委員', '主任委員', '副主任委員'}
def paren_meaning(row_note, table_has_conc_evidence, title=None):
    """括號語意判定（只用本列備註；同表慣例僅記為候選證據，不自動放行）。
    回傳 (meaning, evidence)：meaning ∈ 兼任｜上限｜unknown。
    例外：委員會之「委員／主任委員／副主任委員」列，括號為兼任委員人數規模（審查指示 2026-11-07），不計入專任、保留人數供查照。"""
    note = str(row_note or '')
    m = CONC_RE.search(note)
    if m: return '兼任', f'本列備註「{m.group(0)}」'
    if title in COMMITTEE_TITLES: return '兼任', '委員會委員列之括號＝兼任委員人數規模（審查指示 2026-11-07），不計入專任'
    if UPPER_RE.search(note): return '上限', f'本列備註「{UPPER_RE.search(note).group(0)}」'
    if table_has_conc_evidence: return 'unknown', '本列無備註；同表其他列有兼任備註（候選證據，未放行）'
    return 'unknown', '本列無備註，同表亦無兼任證據'

def cn2n(t):
    if t == '十': return 10
    if t.startswith('十'): return 10 + CN[t[1]]
    if '十' in t:
        a, b = t.split('十'); return CN[a] * 10 + (CN[b] if b else 0)
    return CN.get(t)
def grade_range(s):
    m = re.findall(r'第([一二三四五六七八九十]+)職等', nfkc(str(s)))
    v = [cn2n(t) for t in m]
    return (min(v), max(v)) if v else (None, None)

HEAD_RE = re.compile(r'^(署長|局長|處長|所長|館長|院長|場長|校長|主任委員|部長|總處長|秘書長|主任|中心主任|總隊長|隊長|監獄長|典獄長|分署長|分局長|司長|主計長|人事長|委員長|理事主席|行長|總裁|局長兼|執行長|院長兼)$')
DEPUTY_RE = re.compile(r'^(副署長|副局長|副處長|副所長|副館長|副院長|副場長|副主任委員|政務次長|常務次長|副總處長|副秘書長|副總隊長|副隊長|副典獄長|副分署長|副分局長|副司長|副主計長|副人事長|副主任|副總裁|副校長)$')
MGR_RE = re.compile(r'(?:主任秘書|署長|局長|處長|所長|館長|院長|場長|校長|主任|秘書長|組長|科長|課長|股長|隊長|總隊長|分隊長|中隊長|大隊長|典獄長|分署長|分局長|司長|主計長|人事長|委員長|中心主任|室主任|站長|廠長|園長|所長|主席|行長|總裁|執行長)$')
STAFF_UNIT_RE = re.compile(r'(?:人事|主計|會計|政風|秘書室|秘書處|總務|資訊室)')

# ---------------------------------------------------------------------------
# 人工修正（manual_fixes.json）
#   動作：新增列／刪除列／改列（依序號覆寫欄位）／改備註／改合計／來源核對
#   每筆修正應附 PDF頁、對源（逐列對源紀錄）、來源（PDF 連結或 FileId）；缺其一者不得作為「可比較」白名單依據。
# ---------------------------------------------------------------------------
FIX_FIELDS = ['單位', '職稱', '官等', '職等', '員額', '員額原文', '括號員額_兼任', '備註']

def apply_fixes(ov, det, fixes_path):
    """套用人工修正。回傳 (ov, det, fixlog)；fixlog[機關] = {'entries': [...], 'source_check': {...}|None}。
    被修改的列保留 '原始列'（修改前欄位）與 '修正紀錄'。"""
    fixlog = {}
    if not fixes_path or not os.path.exists(fixes_path):
        det = det.copy(); det['分表排除'] = False; return ov, det, fixlog
    fixes = json.load(open(fixes_path, encoding='utf-8'))['fixes']
    det = det.copy()
    for col in ('原始列', '修正紀錄'):
        if col not in det.columns: det[col] = None
    det['分表排除'] = False
    add = []
    for f in fixes:
        ag = f['機關']; log = fixlog.setdefault(ag, {'entries': [], 'source_check': None})
        act = f['動作']
        note = f"{act}：{f.get('對源') or f.get('來源') or ''}（PDF 第{f.get('PDF頁', '?')}頁）"
        if act == '新增列':
            sub = det[det['機關名稱'] == ag]
            base = sub.iloc[0].to_dict() if len(sub) else {c: None for c in det.columns}
            mx = pd.to_numeric(sub['序'], errors='coerce').max(); mx = 0 if pd.isna(mx) else int(mx)   # 無任何明細列（需人工輸入）之機關自序 1 起
            row = dict(base); row.update({'機關名稱': ag, '序': str(mx + 1 + len([a for a in add if a['機關名稱'] == ag])),
                       '單位': f.get('單位'), '職稱': f['職稱'], '官等': f.get('官等'), '職等': f.get('職等'), '員額': str(f['員額']),
                       '員額原文': f.get('員額原文'), '括號員額_兼任': f.get('括號員額_兼任'), '備註': f.get('備註'), '原始列': None, '修正紀錄': '人工補登：' + note, 'PDF頁': f.get('PDF頁')})
            add.append(row); log['entries'].append(f)
        elif act == '刪除列':
            mask = (det['機關名稱'] == ag) & (det['職稱'] == f['職稱']) & (det['單位'].fillna('') == (f.get('單位') or ''))
            det = det[~mask]; log['entries'].append(f)
        elif act in ('改列', '改備註'):
            mask = (det['機關名稱'] == ag) & (pd.to_numeric(det['序'], errors='coerce') == float(f['序']))
            idx = det.index[mask]
            if len(idx) != 1:
                print(f'【警告】{ag} 序 {f["序"]} 找不到唯一列，修正未套用'); continue
            i = idx[0]
            orig = {k: (None if pd.isna(det.at[i, k]) else det.at[i, k]) for k in FIX_FIELDS}
            newv = f['新值'] if act == '改列' else {'備註': f.get('備註')}
            for k, v in newv.items():
                det.at[i, k] = None if v is None else str(v)
            if not isinstance(det.at[i, '原始列'], str): det.at[i, '原始列'] = json.dumps(orig, ensure_ascii=False)   # 同列多筆修正：原始列只記第一次修正前的值
            det.at[i, '修正紀錄'] = (det.at[i, '修正紀錄'] + '；' + note) if isinstance(det.at[i, '修正紀錄'], str) else note
            log['entries'].append(f)
        elif act == '改合計':
            i = ov.index[ov['機關'] == ag]
            ov.loc[i, '編制員額合計'] = str(f['編制員額合計']); ov.loc[i, '驗算狀態'] = f.get('驗算狀態', ov.loc[i, '驗算狀態'])
            log['entries'].append(f)
        elif act == '排除分表':   # 審查指示：某分表（如軍職表）不計入法定編制總額；列保留、標記不計入
            mask = (det['機關名稱'] == ag) & (det['分表'].astype(str) == str(f['分表']))
            det.loc[mask, '分表排除'] = True; det.loc[mask, '修正紀錄'] = note; log['entries'].append(f)
        elif act == '來源核對':
            log['source_check'] = f
        else:
            print(f'【警告】不認識的動作 {act}')
    # 原表無法程式讀取（僅空列／「()」）而已人工轉錄補登之機關：原表殘留列標記為轉錄取代，不計入
    det['轉錄取代'] = False
    for ag in {a['機關名稱'] for a in add}:
        if any(f['機關'] == ag and f['動作'] == '改合計' for f in fixes):
            m = (det['機關名稱'] == ag) & det['職稱'].isna() & (det['員額原文'].isna() | det['員額原文'].isin(['()', '（）']))
            det.loc[m, '轉錄取代'] = True
    if add:
        det = pd.concat([det, pd.DataFrame(add)], ignore_index=True)
        det['轉錄取代'] = det['轉錄取代'].fillna(False)
    print(f'套用人工修正 {len(fixes)} 筆（{len(fixlog)} 個機關）')
    return ov, det, fixlog

def fix_documented(entries):
    """白名單條件之一：每筆列層級修正都有 PDF頁 與（對源或來源）。"""
    rows = [e for e in entries if e['動作'] in ('新增列', '刪除列', '改列', '改備註')]
    tot = [e for e in entries if e['動作'] == '改合計']
    ok_rows = all(e.get('PDF頁') and (e.get('對源') or e.get('來源')) for e in rows)
    ok_tot = all(e.get('PDF頁') and e.get('對源') and e.get('來源') for e in tot)
    return bool(rows or tot) and ok_rows and ok_tot

# ---------------------------------------------------------------------------
# 列品質：語意檢查（命中即標記，不靜默刪列）
# ---------------------------------------------------------------------------
TITLE_LIKE_RE = re.compile(r'^(主任|副主任|組員|科員|技士|技佐|書記|辦事員|助理員|專員|秘書|科長|組長|股長|佐理員|管理員|研究員|副研究員|助理研究員)$')
CTRL_WORD_RE = re.compile(r'合計|總計|小計|共計')
HEADER_NOISE_RE = re.compile(r'卷.{0,6}期|公報')

RANK_TOKEN_RE = re.compile(r'(?:簡任|薦任|委任|師級|士\(生\)級|士（生）級|士（生級|警監|警正|警佐|上將|中將|少將|將官|上校|中校|少校|校官|上尉|中尉|少尉|尉官|士官長|士官|士兵|關務監|關務正|關務員|高級關務員|技術監|技術正|技術員|聘任|聘用|派用|特任|雇員|教授|副教授|助理教授|講師|比照|相當|一級|二級|三級|級|或|至|、|，|及|以上|以下|\(|\)|（|）|\s)+')
def rank_abnormal(rank):
    """官等欄不是由已知官等詞彙組成（例：混入鄰列溢出文字、職稱、職等）。"""
    rank = (rank or '').strip()
    return bool(rank) and not RANK_TOKEN_RE.fullmatch(rank)

def row_quality(r, pos):
    """回傳 (列品質, 說明)。pos：{'agency_last','sub_last','page_last'} 布林。
    列品質：None／'錯位'／'官等異常'／'控制列'／'控制列（分表）'／'控制列（跨頁小計）'／'疑似控制列'／'警示：頁眉'。"""
    nz = lambda v: '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
    raw = nz(r['員額原文']); rank = nz(r['官等']); title = nz(r['職稱']); unit = nz(r['單位']); note = nz(r['備註']); grade = nz(r['職等'])
    has_n = pd.notna(r['n'])
    if CTRL_WORD_RE.search(title) or CTRL_WORD_RE.search(unit):
        # 控制列：欄位內容（官等與職等皆空）＋明細結構（員額欄有數字）＋列位置（機關最後一列／分表最後一列／該 PDF 頁最後一列之小計）
        if has_n and not rank.strip() and not grade.strip():
            if pos['agency_last']: return '控制列', f'職稱「{title}」含合計字樣、為機關最後一列、官等職等空白、員額 {int(r["n"])}'
            if pos['sub_last']: return '控制列（分表）', f'職稱「{title}」含合計字樣、為分表 {nz(r["分表"])} 最後一列、官等職等空白、員額 {int(r["n"])}'
            if pos['page_last'] and re.search(r'小計|本頁', title + unit): return '控制列（跨頁小計）', f'職稱「{title}」為第 {nz(r["PDF頁"])} 頁最後一列之小計，員額 {int(r["n"])}'
        return '疑似控制列', f'職稱「{title}」含合計字樣但不符控制列條件（位置／欄位），待審，不自動刪除'
    if rank_abnormal(rank) and not TITLE_LIKE_RE.match(rank) and not rank.endswith('室'):
        if not has_n:
            return '錯位', f'官等欄「{rank[:30]}」非已知官等詞彙且員額欄無數字（整列混排），員額不可信，待審'
        return '官等異常', f'官等欄「{rank}」非已知官等詞彙（疑為鄰列溢出或錯欄）；員額 {int(r["n"])} 為原表已知數，官等分類待審'
    if '職等' in raw:
        return '錯位', f'員額原文「{raw}」含「職等」，疑為欄位右移'
    if TITLE_LIKE_RE.match(rank) or rank.endswith('室'):
        return '錯位', f'官等欄出現職稱樣式「{rank}」，疑為欄位右移'
    if HEADER_NOISE_RE.search(note):
        return '警示：頁眉', f'備註含公報頁眉樣式：「{note[:30]}」（仍計入，請人工確認）'
    return None, None

FRAG_TOKENS = {'職稱', '官等', '職等', '員額', '備考', '備註', '單位', '簡任', '薦任', '委任', '委任或薦任', '薦任至簡任', '委任至薦任', '師級'}
def fragment_kind(r, seen_titles):
    """碎片列：證據明確者才標（表頭殘留／附註拆列／重複擷取）。員額、官等、職等皆空才可能是碎片。"""
    nz = lambda v: '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()
    title, rank, grade, raw = nz(r['職稱']), nz(r['官等']), nz(r['職等']), nz(r['員額原文'])
    if pd.notna(r['n']) or rank or grade or raw: return None
    if title.endswith('編制表'): return '碎片列（表頭殘留）'
    if title.startswith('附註') or re.search(r'本編制表|編制表所列|職務列等表|生效|之規定|出缺後改置|^[一二三四五六七八九十]、', title) or (len(title) > 16 and re.search(r'[，。；]', title)): return '碎片列（附註拆列）'
    if title in FRAG_TOKENS or re.fullmatch(r'[○〇一二三四五六七八九十百0-9]+', title) or re.fullmatch(r'第[一二三四五六七八九十]+職等(?:至第[一二三四五六七八九十]+職等)?', nfkc(title)) or (title in seen_titles):
        return '碎片列（重複擷取）'
    return None

KNOWN_UNITS = ['人事室', '主計室', '政風室', '會計室', '統計室', '人事處', '政風處', '會計處', '統計處', '主計處', '人事機構', '主計機構', '統計資訊處',
               '秘書室', '資訊室', '法制室', '人事科', '主計科', '政風科', '會計科', '統計科']
def reconstruct_units(det):
    """單位標題列：職稱為幕僚單位名稱（或片段＋下一列單位片段可拼成）且員額、原文、官等、職等皆空 → 列品質預設「單位標題列」，
    其後單位空白之列填入該單位名稱，直到下一個有單位之列或下一個標題列。
    單位片段：連續列的單位欄片段依序拼接可成已知單位名稱（如 會＋計室、主＋計室、人＋事室；字序錯置之 人構事機）→ 填入完整名稱。
    原值保留於 單位_原值；變更列記 單位重組說明。"""
    det = det.copy()
    det['單位_原值'] = det['單位']; det['單位重組說明'] = None; det['列品質_預設'] = None
    nz = lambda v: '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()
    empty = lambda r: pd.isna(r['n']) and not nz(r['員額原文']) and not nz(r['官等']) and not nz(r['職等'])
    def match_known(frag):
        if frag in KNOWN_UNITS: return frag, '拼接'
        for k in KNOWN_UNITS:
            if sorted(k) == sorted(frag) and len(frag) >= 3: return k, '字序錯置'
        c = [k for k in KNOWN_UNITS if k.startswith(frag) and len(frag) >= 2]
        if len(c) == 1: return c[0], '片段補齊'
        if frag + '室' in KNOWN_UNITS: return frag + '室', '片段補齊（室）'
        return None, None
    for ag, idx in det.groupby('機關名稱').indices.items():
        rows = det.iloc[idx].sort_values('序'); ids = list(rows.index)
        i = 0; cur_hdr = None
        while i < len(ids):
            r = det.loc[ids[i]]; title = nz(r['職稱']); unit = nz(r['單位'])
            # (a) 單位標題列（職稱＝單位名稱，整列空）
            nxt_frag = next((nz(det.loc[ids[k], '單位']) for k in range(i + 1, min(i + 4, len(ids))) if nz(det.loc[ids[k], '單位'])), '')
            hdr_full = empty(r) and not unit and title in KNOWN_UNITS
            hdr_frag = pd.isna(r['n']) and not nz(r['員額原文']) and not unit and 1 <= len(title) <= 2 and nxt_frag and (title + nxt_frag) in KNOWN_UNITS
            if hdr_full or hdr_frag:
                name = title if hdr_full else title + nxt_frag
                det.at[ids[i], '列品質_預設'] = '單位標題列'; det.at[ids[i], '單位重組說明'] = f'職稱「{title}」為幕僚單位名稱之標題列（整列無員額／官等／職等），其後列單位填「{name}」'
                cur_hdr = name; i += 1
                while i < len(ids):
                    r2 = det.loc[ids[i]]; u2 = nz(r2['單位']); t2 = nz(r2['職稱'])
                    if (u2 and u2 in KNOWN_UNITS) or (empty(r2) and t2 in KNOWN_UNITS): break
                    if u2 and u2 not in KNOWN_UNITS and name.endswith(u2): pass   # 片段（事室／室）併入
                    elif u2: break
                    det.at[ids[i], '單位'] = name; det.at[ids[i], '單位重組說明'] = f'承接單位標題列「{name}」（原單位欄「{u2}」）'; i += 1
                continue
            # (a2) 職稱為單位名稱尾片段（如「室」），與前一有單位片段之列拼成已知單位
            if pd.isna(r['n']) and not nz(r['員額原文']) and not unit and 1 <= len(title) <= 2 and i > 0:
                prev_u = nz(det.loc[ids[i - 1], '單位_原值'])
                if prev_u and prev_u not in KNOWN_UNITS and (prev_u + title) in KNOWN_UNITS:
                    name = prev_u + title
                    det.at[ids[i], '列品質_預設'] = '單位標題列'; det.at[ids[i], '單位重組說明'] = f'職稱「{title}」為單位名稱尾片段，與前列單位片段「{prev_u}」拼成「{name}」'
                    k = i - 1
                    while k >= 0 and nz(det.loc[ids[k], '單位_原值']) == prev_u:
                        det.at[ids[k], '單位'] = name; det.at[ids[k], '單位重組說明'] = f'單位欄片段「{prev_u}」＋後列職稱「{title}」拼成「{name}」'; k -= 1
                    i += 1
                    while i < len(ids) and not nz(det.loc[ids[i], '單位']) and not (pd.isna(det.loc[ids[i], 'n']) and nz(det.loc[ids[i], '職稱']) in KNOWN_UNITS):
                        det.at[ids[i], '單位'] = name; det.at[ids[i], '單位重組說明'] = f'承接單位「{name}」'; i += 1
                    continue
            # (b) 單位欄片段拼接：連續列的不同片段依序拼接
            if unit and unit not in KNOWN_UNITS and len(unit) <= 4:
                j = i; seq = []
                while j < len(ids):
                    u = nz(det.loc[ids[j], '單位'])
                    if not u or u in KNOWN_UNITS or len(u) > 4: break
                    if not seq or seq[-1] != u: seq.append(u)
                    j += 1
                name, how = match_known(''.join(seq))
                if name:
                    for k in range(i, j):
                        det.at[ids[k], '單位'] = name; det.at[ids[k], '單位重組說明'] = f'單位欄片段「{"＋".join(seq)}」{how}為「{name}」'
                i = j; continue
            i += 1
    return det

def mark_merged_rows(det):
    """合併計列：員額與員額原文皆空、無其他列品質、職稱非空，且同機關同分表前一個有員額之列緊鄰（中間只有同類空白列）→
    列品質「合併計列（併入序N）」；錨列備註含「合計／合併／共用／總數／之員額」者為確定，否則為「合併計列（推定，併入序N）」。"""
    det = det.copy(); det['合併計列_併入序'] = None
    nz = lambda v: '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()
    ANCH = re.compile(r'合計|合併|共用|總數|員額上限|之員額|名額')
    for ag, idx in det.groupby('機關名稱').indices.items():
        rows = det.iloc[idx].sort_values('序'); anchor = None
        for i in rows.index:
            r = det.loc[i]
            if pd.notna(r['n']) and r['計入']:
                anchor = i; continue
            if nz(r['列品質']) or not r['計入'] or not nz(r['職稱']) or nz(r['員額原文']) or pd.notna(r['n']):
                if nz(r['列品質']) and r['列品質'] not in ('警示：頁眉',): anchor = None
                continue
            if anchor is None: continue
            if nz(det.at[anchor, '分表']) != nz(r['分表']): continue   # 不跨分表
            strip = lambda t: re.sub(r'[（(].*?[)）]', '', t)
            sure = bool(ANCH.search(nz(det.at[anchor, '備註']))) or bool(re.search(r'[師士生員]$', strip(nz(r['職稱']))) and re.search(r'[師士生員]$', strip(nz(det.at[anchor, '職稱']))))
            seq_a = int(det.at[anchor, '序'])
            det.at[i, '列品質'] = f'合併計列（併入序{seq_a}）' if sure else f'合併計列（推定，併入序{seq_a}）'
            det.at[i, '列品質說明'] = f'職稱「{nz(r["職稱"])}」員額與原文皆空，與序{seq_a}「{nz(det.at[anchor, "職稱"])}」（員額 {int(det.at[anchor, "n"])}）共用一格員額；不拆分、不重複加總' + ('' if sure else '；錨列備註無合計字樣，為推定，請人工確認')
            det.at[i, '合併計列_併入序'] = seq_a
    return det

def classify_rows(det):
    """對整個明細資料框算列品質（需有 機關名稱、序、分表、PDF頁、n、官等、職等、職稱、單位、員額原文、備註 欄）。"""
    seq = pd.to_numeric(det['序'], errors='coerce').fillna(9999)
    agency_last = seq == seq.groupby(det['機關名稱']).transform('max')
    sub_key = det['機關名稱'] + '|' + det['分表'].fillna('').astype(str)
    sub_last = det['分表'].notna() & (seq == seq.groupby(sub_key).transform('max'))
    page_key = det['機關名稱'] + '|' + det['PDF頁'].fillna('').astype(str)
    page_last = det['PDF頁'].notna() & (seq == seq.groupby(page_key).transform('max'))
    out, seen = [], {}
    for i, (_, r) in enumerate(det.iterrows()):
        ag = r['機關名稱']; st = seen.setdefault(ag, set())
        q = row_quality(r, {'agency_last': bool(agency_last.iloc[i]), 'sub_last': bool(sub_last.iloc[i]), 'page_last': bool(page_last.iloc[i])})
        if r.get('列品質_預設'): q = (r['列品質_預設'], r['單位重組說明'])
        if r.get('轉錄取代') is True: q = ('碎片列（原表無法讀取，已人工轉錄）', '原表殘留之空列（職稱空、員額原文「()」），該機關明細已依人工轉錄補登，此列不計入')
        if r.get('分表排除') is True: q = ('分表排除（不計入法定編制總額）', f'分表 {r["分表"]} 依審查指示不計入法定編制總額（{r["修正紀錄"]}）')
        if q[0] is None:
            fk = fragment_kind(r, st)
            if fk: q = (fk, f'職稱「{str(r["職稱"])[:30]}」且員額、官等、職等皆空：{fk[4:-1]}')
        if pd.notna(r['n']): st.add(str(r['職稱']).strip())
        out.append(q)
    return [x[0] for x in out], [x[1] for x in out]

DEPUTY_MAP = {'部長': ['副部長', '政務次長', '常務次長'], '人事長': ['副人事長'], '主計長': ['副主計長'], '總裁': ['副總裁'],
              '署長或主任': ['副署長', '副主任'], '司令': ['副司令']}
def deputy_titles(head):
    if not head: return []
    return DEPUTY_MAP.get(head, ['副' + head])

STAFF_UNIT_NAME_RE = re.compile(r'(秘書室|秘書處|人事|主計|會計|政風|資訊室|資訊處|法制|法規|統計室|總務|文書|公共關係|公關|國會|研考|企劃室|綜合規劃室|訴願)')
UNIT_ART_RE = re.compile(r'設下列[^：:。]{0,25}[：:]')
ITEM_RE = re.compile(r'(?:^|[。：:；\s])([一二三四五六七八九十]{1,3})、([^。；]{1,40})')
ATTACH_UNITS = {}
def unit_structure(art, name):
    """從處務規程／辦事細則「本署設下列組、室：一、…」條文計算內部單位數；條文以附表列單位者改用 ATTACH_UNITS（parse_unit_attachments.py 產出）。"""
    out = {'業務單位數': None, '幕僚單位數': None, '單位數': None, '科數': None, '清單': None, '依據': None}
    if name in ATTACH_UNITS:
        names = ATTACH_UNITS[name]['單位']
        staff = [u for u in names if STAFF_UNIT_NAME_RE.search(u) or re.search(r'(人事|主計|政風|會計)(管理)?員$', u)]
        biz = [u for u in names if u not in staff]
        out.update({'業務單位數': len(biz), '幕僚單位數': len(staff), '單位數': len(names), '清單': '；'.join(names), '依據': ATTACH_UNITS[name]['依據']})
        return out
    sub = art[(art['機關'] == name) & (art['法規類別'] != '組織法規')]
    for _, r in sub.iterrows():
        txt = str(r['條文內容'])
        m = UNIT_ART_RE.search(txt)
        if not m:
            if re.search(r'得?設(?:之)?[^。]{0,30}如附表', txt) and out['依據'] is None:
                out['依據'] = f"{r['法規名稱']}{r['條號']}（單位列於附表，未解析）"
            continue
        body = txt[m.end():]
        items = [x[1].strip() for x in ITEM_RE.findall(body.replace('\n', ' '))]
        if not items: continue
        names = [re.split(r'[，,（(]', it)[0].strip() for it in items]
        staff = [u for u in names if STAFF_UNIT_NAME_RE.search(u)]
        biz = [u for u in names if u not in staff]
        sec = 0
        for it in items:
            for k in re.findall(r'分([一二三四五六七八九十]+)科', it):
                sec += cn2n(k) or 0
        out.update({'業務單位數': len(biz), '幕僚單位數': len(staff), '單位數': len(names), '科數': sec or None,
                    '清單': '；'.join(names), '依據': f"{r['法規名稱']}{r['條號']}"})
        break
    return out

HC_CLAUSE_RE = re.compile(r'([\u4e00-\u9fa5]{2,8}?)([一二三四五六七八九十]+人(?:至[一二三四五六七八九十]+人)?)')
HEAD_TITLES_RE = re.compile(r'(署長|局長|處長|所長|館長|院長|校長|主任委員|部長|委員長|總裁|司令|副署長|副局長|副處長|副所長|副館長|副院長|副校長|副主任委員|政務次長|常務次長|副部長|主任秘書|秘書長|副秘書長)$')
def statutory_basis(art, name):
    """無編制表機關的法定員額依據。回傳 {'有': bool, ...}：
    有＝本機關自己的組織法規條文列有首長副首長以外的員額（含區間），給法規名稱、條號、連結，不加總；
    無＝條文只規定首長、副首長等職稱，或組織依共用法規（法院組織法、駐外機構組織通則），明示原因。"""
    sub = art[(art['機關'] == name) & (art['法規類別'] == '組織法規')]
    if not len(sub): return {'有': False, '說明': '總表無此機關之組織法規條文'}
    law = sub['法規名稱'].iloc[0]; link = sub['連結'].iloc[0]
    if (name[:4] not in law and name[-4:] not in law) or re.search(r'通則|準則', law):
        return {'有': False, '法規名稱': law, '連結': link, '說明': f'組織依共用法規「{law}」（通則／準則或非本機關專屬法規），本系統尚未完成其員額規定之結構化'}
    nos, nonhead = [], 0
    for _, r in sub.iterrows():
        txt = str(r['條文內容']).replace('\n', '')
        for seg in txt.split('。'):
            if '置' not in seg: continue
            cls = HC_CLAUSE_RE.findall(seg[seg.index('置'):])
            if cls and r['條號'] not in nos: nos.append(r['條號'])
            nonhead += sum(1 for t, _ in cls if not HEAD_TITLES_RE.search(t))
    if nonhead >= 2:
        return {'有': True, '法規名稱': law, '條號': '、'.join(nos), '連結': link, '說明': f'{law}{"、".join(nos)}列有員額（含區間），本系統未加總'}
    return {'有': False, '法規名稱': law, '連結': link, '說明': f'「{law}」本系統尚未完成員額結構化（目前僅辨識出首長、副首長職稱條款，未逐條證明法規無其他員額規定）'}

RESULT_ENUM = ['相符', '不相符', '找不到合計', '需人工輸入', '無編制表', '條文解析（無編制表）']
def parse_status(s):
    """驗算狀態字串 → (驗算結果, 品質註記[])。不以前綴猜測：逐一比對列舉值。"""
    s = str(s or '')
    head = re.split(r'[；（(]', s)[0].strip()
    result = head if head in RESULT_ENUM else '未知'
    notes = []
    if 'Codex抽樣不一致' in s: notes.append('Codex抽樣不一致')
    if re.search(r'人工補登|人工校正', s): notes.append('人工補登')
    return result, notes

COUNT_METRICS = ['員額合計', '副首長數', '副首長兼任數', '主任秘書', '組長數', '副組長數', '處長數', '副處長數', '科長數', '股長數', '專門委員',
                 '簡任員額', '簡任主管', '簡任非主管', '簡任員額_法定', '簡任非主管_法定', '得列簡任人數', '得列薦任人數', '薦任員額', '委任員額',
                 '其他官等員額', '幕僚單位員額', '主管員額', '暫列職稱數', '得列人數', '簡任非主管比', '簡任比', '主管比', '幕僚比']
WHITELIST_NOTES = {'人工補登（已對源）', '表內驗算相符（合計取自明細控制列）', '警示：頁眉'}
WHITELIST_PREFIX = ('括號語意待審', '員額回填（原文字形解析', '法定員額（條文區間）', 'Codex差異已釐清', '驗算結果由程式重算')

def build(master, out, fixes_path=None, attach_units_path=None):
    global ATTACH_UNITS
    if attach_units_path and os.path.exists(attach_units_path):
        ATTACH_UNITS = json.load(open(attach_units_path, encoding='utf-8')); print(f'附表單位資料 {len(ATTACH_UNITS)} 個機關')
    ov = pd.read_excel(master, '機關總覽', dtype=str)
    det = pd.read_excel(master, '編制表明細', dtype=str)
    art = pd.read_excel(master, '條文', dtype=str)
    info = pd.read_excel(master, '說明', header=None, dtype=str).iloc[0, 0]
    ov, det, fixlog = apply_fixes(ov, det, fixes_path)
    # 舊體例組織法規（無編制表、員額列於條文）：依條文合成明細列（分表「條文」），區間以 lo-hi 原文表示；
    # 警備隊／聘用約僱／兼任列保留為參考列（不計入專任）。全機關另掃描「聘用／約僱」人數條文。
    det['法定類別'] = None; det['條號'] = None
    STATUTORY_AGENCIES = {}
    add_rows = []
    for _, o in ov.iterrows():
        name = o['機關']
        if not str(o['驗算狀態']).startswith('無編制表'): continue
        own_laws = [x for x in str(o['組織法規名稱']).split('；') if name in x and not re.search(r'(通則|準則)', x)]   # 只解析機關專屬組織法規（共用法規／通則不解析）
        if not own_laws: continue
        rows = [r for r in statutory_parse(art, name) if r['法規'] in own_laws]
        if len(rows) < 5: continue
        STATUTORY_AGENCIES[name] = statutory_summary(rows)
        link = str(o['組織法規連結']).split('；')[0]
        for i, r in enumerate(rows, 1):
            ranks = list(dict.fromkeys(re.findall(r'簡任|薦任|委任|特任|警監|警正|警佐|聘任', r['官等職等'])))
            rank = ('或' if '或' in r['官等職等'] else '至').join(ranks) if ranks else None
            grades = '；'.join(re.findall(r'第[一二三四五六七八九十]+職等(?:至第[一二三四五六七八九十]+職等)?', r['官等職等'])) or None
            counted = r['類別'] in ('文官', '警察官', '教育人員', '未註明')
            conc = r['類別'] == '兼任'   # 兼任列比照編制表慣例：專任 0、括號為兼任人數（備註含「兼任」）
            note = '；'.join(x for x in [f"{r['條號']}", r['其中條款'], ('兼任（條文定由他職兼任或無給職，不計入專任）' if conc else ''), ('' if (counted or conc) else f"{r['類別']}（獨立參考，不計入專任）")] if x)
            add_rows.append({'批次': o['批次'] if '批次' in o else None, '部會': o['部會'], '機關名稱': name, '附件': None, '分表': '條文', '序': str(i), '單位': r['單位'], '職稱': r['職稱'],
                             '官等': rank, '職等': grades, '員額': (str(r['下限']) if (counted and r['下限'] == r['上限']) else ('0' if conc else None)),
                             '員額上限': str(r['上限']), '員額原文': (f"{r['下限']}-{r['上限']}" if (counted and r['下限'] != r['上限']) else (str(r['下限']) if counted else (f"0（{r['下限']}{'-' + str(r['上限']) if r['下限'] != r['上限'] else ''}）" if conc else None))),
                             '括號員額_兼任': None, '備註': note, '同職稱續列': None, 'PDF頁': None, '來源': link, '預算員額': None, '現有員額': None,
                             '原始列': None, '修正紀錄': None, '法定類別': r['類別'], '條號': r['條號'], '轉錄取代': False,
                             '法定下限': r['下限'], '法定上限': r['上限'], '分表排除': False})
    if add_rows:
        det = pd.concat([det, pd.DataFrame(add_rows)], ignore_index=True)
        print(f'法定員額（條文）合成明細：{len(STATUTORY_AGENCIES)} 個機關、{len(add_rows)} 列')
    CONTRACT_CLAUSES = scan_contract_clauses(art)
    det['n'] = pd.to_numeric(det['員額'], errors='coerce')
    det['bracket'] = pd.to_numeric(det['括號員額_兼任'], errors='coerce')   # 既有欄原值（只有阿拉伯數字者可轉）
    det['序'] = pd.to_numeric(det['序'], errors='coerce').fillna(9999)
    # P1-A/B：員額原文結構化（專任與括號分欄）；人工補登列（原文空）以員額欄為專任定額
    hc = det['員額原文'].map(parse_headcount)
    for k in ['專任_min', '專任_max', '專任_is_range', 'paren_raw', 'paren_min', 'paren_max', 'paren_is_range', '可解析']:
        det[k] = [h[k] for h in hc]
    noraw = det['員額原文'].isna() & det['n'].notna()
    det.loc[noraw, '專任_min'] = det.loc[noraw, 'n']; det.loc[noraw, '專任_max'] = det.loc[noraw, 'n']; det.loc[noraw, '可解析'] = True
    # 專任區間列：員額（定額）留空，只給上下限；專任定額列：以原文解析為準（與員額欄不一致者記差異）
    det['員額定額'] = det['n']
    fill = det['n'].isna() & (det['可解析'] == True) & ~(det['專任_is_range'] == True) & det['專任_min'].notna()
    det.loc[fill, '員額定額'] = det.loc[fill, '專任_min']; det['員額回填'] = fill   # 員額欄空、原文可解析（如注音ㄧ）→ 以解析值為定額
    rng_mask = det['專任_is_range'] == True
    det.loc[rng_mask, '員額定額'] = float('nan')
    det['專任差異'] = det['可解析'] & ~rng_mask & det['n'].notna() & (det['專任_min'] != det['n'])
    det['n'] = det['員額定額']   # 後續列品質／控制列判定以定額為準（含回填）
    # 括號語意（只用本列備註；同表慣例為候選證據）
    conc_tbl = det.groupby('機關名稱')['備註'].apply(lambda s: bool(s.fillna('').str.contains(CONC_RE).any())).to_dict()
    pm = [paren_meaning(r['備註'], conc_tbl.get(r['機關名稱'], False), str(r['職稱']).strip() if pd.notna(r['職稱']) else None) if pd.notna(r['paren_min']) else (None, None) for _, r in det.iterrows()]
    det['paren_meaning'] = [x[0] for x in pm]; det['paren_evidence'] = [x[1] for x in pm]
    det['concurrent_min'] = [r['paren_min'] if r['paren_meaning'] == '兼任' else None for _, r in det.iterrows()]
    det['concurrent_max'] = [r['paren_max'] if r['paren_meaning'] == '兼任' else None for _, r in det.iterrows()]
    # 既有「括號員額_兼任」欄原值保留；新解析值與原值（中文或數字）比對，不一致者列入差異清單（不批次覆寫）
    det['括號原值_數值'] = det['括號員額_兼任'].map(lambda v: cn_int(v) if isinstance(v, str) and not re.search(RANGE_SEP, v) else None)
    det['括號差異'] = det['括號員額_兼任'].notna() & (det['paren_min'].isna() | det['括號原值_數值'].isna() | (det['paren_min'] != det['括號原值_數值']))
    det['職等_norm'] = det['職等'].map(nfkc)
    # R3：幕僚單位（人事／主計／政風…）在 PDF 以直書合併儲存格標示單位，解析後可能成為獨立「單位標題列」或單位名稱被拆成片段；
    #      重組後 單位 欄填入完整名稱（原值保留於 單位_原值），標題列標「單位標題列」不計入
    det = reconstruct_units(det)
    # 列品質（語意檢查；單位標題列已預設）
    det['列品質'], det['列品質說明'] = classify_rows(det)
    # 計入（員額）：控制列不是職位；錯位／疑似控制列的員額欄不可信 → 不計；官等異常列的員額是原表已知數 → 計入員額，但不計入官等結構
    det['計入'] = ~det['列品質'].isin(['控制列', '控制列（分表）', '控制列（跨頁小計）', '疑似控制列', '錯位', '單位標題列', '分表排除（不計入法定編制總額）']) & ~det['列品質'].fillna('').str.startswith('碎片列') & ~det['法定類別'].isin(['警備隊', '聘用約僱'])
    ref = det['法定類別'].isin(['警備隊', '聘用約僱']); det.loc[ref, '列品質'] = '法定參考列（' + det.loc[ref, '法定類別'] + '）'; det.loc[ref, '列品質說明'] = '組織法規條文所列之警備隊／聘用約僱員額，獨立參考，不計入專任合計'
    # 計入員額的列：加總用「員額定額」（專任區間列不入定額加總，另入上下限）
    det['n'] = det['員額定額']
    det['計入官等'] = det['計入'] & (det['列品質'] != '官等異常')
    # R2：合併計列（多職稱共用一格員額：醫師、中醫師、牙醫師…）：員額與原文皆空、緊接在有員額之列之後 → 標「合併計列（併入序N）」，不是空白列、不拆、不重複加總
    det = mark_merged_rows(det)
    gr = det['職等'].map(grade_range)   # grade_range 內部已用 NFKC 副本；raw 職等不變
    det['職等下限'] = [g[0] for g in gr]; det['職等上限'] = [g[1] for g in gr]
    # raw 含「至」但 NFKC 後 min==max → 職等區間待審（儲存格截斷等），不猜補
    trunc = det['職等'].fillna('').str.contains('至') & det['職等下限'].notna() & (det['職等下限'] == det['職等上限'])
    det.loc[trunc, '職等下限'] = None; det.loc[trunc, '職等上限'] = None
    det['職等區間待審'] = trunc
    det['官等'] = det['官等'].fillna('')
    det['簡任'] = det['官等'].str.contains('簡任') | (det['職等上限'].fillna(0) >= 10)
    det['薦任'] = ~det['簡任'] & det['官等'].str.contains('薦任')
    det['委任'] = det['官等'].str.fullmatch('委任')
    def deli(row, band):
        n = 0
        for k in re.findall(r'(?:內|其中)([一二三四五六七八九十○〇百]+)人得列' + band, str(row['備註'] or '').replace('内', '內').replace('\u3127', '一')):
            v = cn2n(k.replace('○', '〇')) if k not in ('〇', '○') else 0
            n += v or 0
        cap = row['n'] if pd.notna(row['n']) else 0
        return int(min(n, cap))
    det['得列簡任'] = det.apply(lambda r: 0 if r['簡任'] else deli(r, '簡任'), axis=1)
    det['得列薦任'] = det.apply(lambda r: deli(r, '薦任') if r['委任'] else 0, axis=1)
    det['主管'] = det['職稱'].str.contains(MGR_RE)
    first_idx = det[det['計入']].sort_values('序').groupby('機關名稱').head(1).index
    det['首長'] = False
    det.loc[first_idx, '首長'] = det.loc[first_idx, '職稱'].str.contains(r'(?:長|主任|主任委員|主席|總裁|司令|委員長|理事主席|執行長|局長兼|監獄長)$', regex=True)
    det['幕僚單位'] = det['單位'].fillna('').str.contains(STAFF_UNIT_RE)

    positions, checklog = [], []
    for _, r in det.iterrows():
        positions.append({k: (None if (isinstance(v, float) and pd.isna(v)) or v is None else v) for k, v in {
            '機關': r['機關名稱'], '分表': r['分表'], '序': int(r['序']) if r['序'] != 9999 else None, '單位': r['單位'], '職稱': r['職稱'],
            '官等': r['官等'] or None, '職等': r['職等'], '員額': None if pd.isna(r['n']) else int(r['n']),
            '兼任': None if pd.isna(r['bracket']) else int(r['bracket']), '員額原文': r['員額原文'], 'raw原文': r['員額原文'], '備註': r['備註'],
            '職等下限': r['職等下限'], '職等上限': r['職等上限'], '職等_norm': r['職等_norm'], '職等區間待審': bool(r['職等區間待審']), '簡任': bool(r['簡任']), '主管': bool(r['主管']),
            '專任_min': r['專任_min'], '專任_max': r['專任_max'], '專任_is_range': bool(r['專任_is_range']),
            'paren_raw': r['paren_raw'], 'paren_min': r['paren_min'], 'paren_max': r['paren_max'], 'paren_is_range': bool(r['paren_is_range']),
            'paren_meaning': r['paren_meaning'], 'paren_evidence': r['paren_evidence'], 'concurrent_min': r['concurrent_min'], 'concurrent_max': r['concurrent_max'],
            '括號員額_兼任_原值': r['括號員額_兼任'], '括號差異': bool(r['括號差異']), '專任差異': bool(r['專任差異']),
            '得列簡任': int(r['得列簡任']), '得列薦任': int(r['得列薦任']), 'PDF頁': r['PDF頁'],
            '列品質': r['列品質'], '列品質說明': r['列品質說明'], '計入': bool(r['計入']), '計入官等': bool(r['計入官等']),
            '法定類別': r['法定類別'] if isinstance(r['法定類別'], str) else None, '條號': r['條號'] if isinstance(r['條號'], str) else None,
            '法定下限': (int(r['法定下限']) if pd.notna(r.get('法定下限')) else None), '法定上限': (int(r['法定上限']) if pd.notna(r.get('法定上限')) else None),
            '單位_原值': r['單位_原值'] if isinstance(r['單位_原值'], str) else None, '單位重組說明': r['單位重組說明'] if isinstance(r['單位重組說明'], str) else None,
            '合併計列_併入序': (int(r['合併計列_併入序']) if pd.notna(r['合併計列_併入序']) else None),
            '原始列': (json.loads(r['原始列']) if isinstance(r['原始列'], str) else None), '修正紀錄': r['修正紀錄'] if isinstance(r['修正紀錄'], str) else None}.items()})
        if isinstance(r['列品質'], str) and r['列品質']:
            checklog.append((r['機關名稱'], int(r['序']) if r['序'] != 9999 else None, r['職稱'], r['列品質'], r['列品質說明']))

    agencies = []
    for _, o in ov.iterrows():
        name = o['機關']
        g_all = det[det['機關名稱'] == name]
        ctrl = g_all[g_all['列品質'] == '控制列']
        ctrl_sub = g_all[g_all['列品質'] == '控制列（分表）']
        pending = g_all[g_all['列品質'].isin(['疑似控制列', '錯位'])]          # 員額欄不可信 → 總額不完整
        pending_rank = g_all[g_all['列品質'] == '官等異常']                    # 員額已知、官等分類待審
        g = g_all[g_all['計入']]
        gr_ok = g[g['計入官等']]
        n = g['n'].fillna(0)
        has_numbers = bool(((g['n'].fillna(0) > 0) | (g['n'].notna() & g['bracket'].notna())).any())
        result, notes = parse_status(o['驗算狀態'])
        log = fixlog.get(name, {'entries': [], 'source_check': None})
        # 表列合計：總表合計；總表無合計而明細有控制列者，取控制列（表內數字）
        tbl_total = None if pd.isna(o['編制員額合計']) else int(float(o['編制員額合計']))
        ctrl_num = None
        if len(ctrl):
            c = ctrl.iloc[-1]
            br = None if pd.isna(c['bracket']) else int(c['bracket'])
            if br is None:  # 原文「二一七（六十九）」：括號內為兼任合計
                mb = re.search(r'[（(]([一二三四五六七八九十○〇0-9]+)[）)]', str(c['員額原文'] or ''))
                if mb:
                    t = mb.group(1)
                    br = int(t) if t.isdigit() else (cn2n(t) if '十' in t else int(''.join(str({'○':0,'〇':0,**CN}.get(ch, 0)) for ch in t)))
            ctrl_num = {'專任': int(c['n']), '兼任': br, '序': int(c['序']), '原文': c['員額原文']}
        elif len(ctrl_sub):  # 只有分表合計：以各分表合計相加為表列合計
            ctrl_num = {'專任': int(ctrl_sub['n'].sum()), '兼任': None, '序': [int(x) for x in ctrl_sub['序']], '原文': '；'.join(str(x) for x in ctrl_sub['員額原文']), '分表合計': True}
        if ctrl_num:
            if tbl_total is None:
                tbl_total = ctrl_num['專任']; notes.append('表內驗算相符（合計取自明細控制列）' if int(n.sum()) == tbl_total else '表內驗算不符（合計取自明細控制列）')
                result = '相符' if int(n.sum()) == tbl_total else '不相符'
        # 員額回填列（員額欄空、原文可解析，如注音ㄧ）：以回填後加總重新驗算，並註記
        if bool(g['員額回填'].any()):
            notes.append(f'員額回填（原文字形解析，{int(g["員額回填"].sum())} 列）')
            if tbl_total is not None and has_numbers: result = '相符' if int(n.sum()) == tbl_total else '不相符'
        # 人工修正後重新驗算
        if log['entries']:
            if fix_documented(log['entries']) and tbl_total is not None and has_numbers and int(n.sum()) == tbl_total and len(pending) == 0:
                notes = [x for x in notes if x != '人工補登'] + ['人工補登（已對源）']; result = '相符'
            else:
                notes = [x for x in notes if x != '人工補登'] + ['人工補登（未完成對源或驗算不符）']
                if tbl_total is not None and has_numbers: result = '相符' if int(n.sum()) == tbl_total else '不相符'
        if len(pending): notes.append('列品質待審（員額不完整）')
        if len(pending_rank): notes.append('列品質待審（官等結構）')
        # 來源核對狀態（與表內驗算分開）
        sc = log['source_check']
        src_status = sc['狀態'] if sc else '依總表（2026-10-31 自全國法規資料庫下載之編制表 PDF）'
        if sc and sc.get('狀態', '').startswith('官方合計待核'): notes.append('官方合計待核')
        # Codex 抽樣差異已逐筆釐清（來源核對狀態記載原因）→ 註記改為「已釐清」（白名單）
        if sc and sc.get('狀態', '').startswith('已對源') and 'Codex' in sc.get('狀態', '') and 'Codex抽樣不一致' in notes:
            notes = [x for x in notes if x != 'Codex抽樣不一致'] + ['Codex差異已釐清（已對源）']
        # 總表標「需人工輸入」但明細已有數字且有表列合計者：由程式重算驗算結果並註記
        if result == '需人工輸入' and has_numbers and tbl_total is not None:
            result = '相符' if int(n.sum()) == tbl_total else '不相符'; notes.append('驗算結果由程式重算（總表原標需人工輸入）')
        # 資料狀態
        if not has_numbers:
            data_state = '未取得（需人工輸入）' if result == '需人工輸入' else ('未取得（無編制表）' if result == '無編制表' else '未取得（明細無數字）')
        elif len(pending):
            data_state = '待審（員額不完整）'
        elif len(pending_rank):
            data_state = '待審（官等結構）'
        else:
            data_state = '可用'
        head = g[g['首長']].sort_values('序').head(1)
        head_title = head['職稱'].iloc[0] if len(head) else None
        dep_titles = deputy_titles(head_title)
        dep_rows = g[g['職稱'].isin(dep_titles) & g['單位'].isna()]
        units = unit_structure(art, name)
        tot = int(n.sum()); nr = gr_ok['n'].fillna(0)
        rng_rows = g[g['專任_is_range'] == True]
        hc_min = tot + int(rng_rows['專任_min'].fillna(0).sum()); hc_max = tot + int(rng_rows['專任_max'].fillna(0).sum())
        is_range_agency = len(rng_rows) > 0
        paren_rows = g_all[g_all['paren_min'].notna()]
        conc = paren_rows[paren_rows['paren_meaning'] == '兼任']; unk = paren_rows[paren_rows['paren_meaning'] == 'unknown']
        conc_min = int(conc['concurrent_min'].fillna(0).sum()); conc_max = int(conc['concurrent_max'].fillna(0).sum())
        m = {
            '員額合計': tot,
            '員額區間列': [{'序': int(x['序']), '職稱': x['職稱'], '原文': x['員額原文'], 'min': x['專任_min'], 'max': x['專任_max']} for _, x in rng_rows.iterrows()] or None,
            '兼任合計_已判定': conc_min if conc_min == conc_max else None, '兼任合計_min': conc_min, '兼任合計_max': conc_max,
            '兼任合計': (conc_min if (conc_min == conc_max and len(unk) == 0) else None),
            '括號待審列數': int(len(unk)), '括號列數': int(len(paren_rows)),
            '首長職稱': head_title, '首長職等': head['職等'].iloc[0] if len(head) else None,
            '首長兼任': (True if (len(head) and head['paren_meaning'].iloc[0] == '兼任') else (None if (len(head) and head['paren_meaning'].iloc[0] == 'unknown') else False)),
            '副首長職稱': '、'.join(sorted(set(dep_rows['職稱']))) or ('／'.join(dep_titles) + '（無）' if dep_titles else None),
            '副首長數': int(dep_rows['n'].fillna(0).sum()), '副首長兼任數': (int(dep_rows['concurrent_min'].fillna(0).sum()) if not (dep_rows['paren_meaning'] == 'unknown').any() else None),
            '主任秘書': int(n[g['職稱'] == '主任秘書'].sum()),
            '組長數': int(n[g['職稱'] == '組長'].sum()), '副組長數': int(n[g['職稱'] == '副組長'].sum()),
            '處長數': int(n[g['職稱'] == '處長'].sum()), '副處長數': int(n[g['職稱'] == '副處長'].sum()),
            '科長數': int(n[g['職稱'] == '科長'].sum()), '股長數': int(n[g['職稱'] == '股長'].sum()),
            '專門委員': int(n[g['職稱'] == '專門委員'].sum()),
            '簡任員額': int(nr[gr_ok['簡任']].sum() + gr_ok['得列簡任'].sum()), '簡任主管': int(nr[gr_ok['簡任'] & gr_ok['主管']].sum() + gr_ok.loc[gr_ok['主管'], '得列簡任'].sum()),
            '簡任非主管': int(nr[gr_ok['簡任'] & ~gr_ok['主管']].sum() + gr_ok.loc[~gr_ok['主管'], '得列簡任'].sum()),
            '簡任員額_法定': int(nr[gr_ok['簡任']].sum()), '簡任非主管_法定': int(nr[gr_ok['簡任'] & ~gr_ok['主管']].sum()),
            '得列簡任人數': int(gr_ok['得列簡任'].sum()), '得列薦任人數': int(gr_ok['得列薦任'].sum()),
            '薦任員額': int(nr[gr_ok['薦任']].sum() - gr_ok['得列簡任'].sum() + gr_ok['得列薦任'].sum()), '委任員額': int(nr[gr_ok['委任']].sum() - gr_ok['得列薦任'].sum()),
            '其他官等員額': int(nr[~gr_ok['簡任'] & ~gr_ok['薦任'] & ~gr_ok['委任']].sum()),
            '幕僚單位員額': int(n[g['幕僚單位']].sum()),
            '業務單位數': units['業務單位數'], '幕僚單位數': units['幕僚單位數'], '單位數': units['單位數'], '科數': units['科數'],
            '單位清單': units['清單'], '單位依據': units['依據'],
            '主管員額': int(n[g['主管']].sum()),
            '明細列數': int(len(g_all)), '明細列數_有效': int(len(g)), '碎片列數': int(g_all['列品質'].fillna('').str.startswith('碎片列').sum()), '員額空白列數': int((g['n'].isna() & ~(g['專任_is_range'] == True) & ~g['列品質'].fillna('').str.startswith('合併計列')).sum()), '合併計列數': int(g_all['列品質'].fillna('').str.startswith('合併計列').sum()), '單位標題列數': int((g_all['列品質'] == '單位標題列').sum()),
            '職等區間待審列數': int(g['職等區間待審'].sum()),
            '暫列職稱數': int(g['備註'].fillna('').str.contains('暫列').sum()),
            '得列人數': int(sum(cn2n(x) or 0 for x in re.findall(r'內([一二三四五六七八九十]+)人得列', ' '.join(g['備註'].fillna(''))))),
        }
        if is_range_agency:
            # 區間機關：只有「含區間列」的指標改以 min／max 呈現，其餘定額指標維持；比率一律留空
            RM = {'員額合計': rng_rows.index == rng_rows.index,
                  '副首長數': rng_rows['職稱'].isin(dep_titles) & rng_rows['單位'].isna(),
                  '主任秘書': rng_rows['職稱'] == '主任秘書', '組長數': rng_rows['職稱'] == '組長', '副組長數': rng_rows['職稱'] == '副組長',
                  '處長數': rng_rows['職稱'] == '處長', '副處長數': rng_rows['職稱'] == '副處長', '科長數': rng_rows['職稱'] == '科長', '股長數': rng_rows['職稱'] == '股長',
                  '專門委員': rng_rows['職稱'] == '專門委員',
                  '簡任員額': rng_rows['簡任'], '簡任主管': rng_rows['簡任'] & rng_rows['主管'], '簡任非主管': rng_rows['簡任'] & ~rng_rows['主管'],
                  '簡任員額_法定': rng_rows['簡任'], '簡任非主管_法定': rng_rows['簡任'] & ~rng_rows['主管'],
                  '薦任員額': rng_rows['薦任'], '委任員額': rng_rows['委任'], '其他官等員額': ~rng_rows['簡任'] & ~rng_rows['薦任'] & ~rng_rows['委任'],
                  '幕僚單位員額': rng_rows['幕僚單位'], '主管員額': rng_rows['主管']}
            for k, mask in RM.items():
                lo = int(rng_rows.loc[mask, '專任_min'].fillna(0).sum()); hi = int(rng_rows.loc[mask, '專任_max'].fillna(0).sum())
                if hi > 0:
                    base = m[k] if k != '員額合計' else tot
                    m[k + '_min'] = base + lo; m[k + '_max'] = base + hi; m[k] = None
            tot = 0  # 比率不算
        m['簡任非主管比'] = round(m['簡任非主管'] / tot, 4) if tot else None
        m['簡任比'] = round(m['簡任員額'] / tot, 4) if tot else None
        m['主管比'] = round(m['主管員額'] / tot, 4) if tot else None
        m['幕僚比'] = round(m['幕僚單位員額'] / tot, 4) if tot else None
        RANK_METRICS = ['簡任員額', '簡任主管', '簡任非主管', '簡任員額_法定', '簡任非主管_法定', '得列簡任人數', '得列薦任人數', '薦任員額', '委任員額', '其他官等員額', '簡任非主管比', '簡任比']
        if data_state == '可用' and is_range_agency: data_state = '可用（區間）'
        stat = STATUTORY_AGENCIES.get(name)
        if stat and result == '無編制表':
            result = '條文解析（無編制表）'; notes.append('法定員額（條文區間）')
            data_state = '可用（條文區間）' if has_numbers else data_state
            m['法定員額_條文'] = {**stat, '法規': o['組織法規名稱'], '連結': str(o['組織法規連結']).split('；')[0]}
        cc = CONTRACT_CLAUSES.get(name)
        m['聘用約僱條文'] = cc; m['聘用約僱上限_條文'] = (max(x['上限'] for x in cc) if cc else None)
        if len(unk): notes.append(f'括號語意待審（{len(unk)} 列）')
        if data_state == '待審（官等結構）':   # 員額已知；官等結構不可用
            m['官等結構待審列'] = [{'序': int(x['序']), '職稱': x['職稱'], '員額': None if pd.isna(x['n']) else int(x['n']), '官等原文': x['官等']} for _, x in pending_rank.iterrows()]
            for k in RANK_METRICS: m[k] = None
        elif data_state not in ('可用', '可用（區間）', '可用（條文區間）'):   # 未取得或員額不完整：人數類指標一律 null；已知列小計另列、明示不完整（區間機關不在此列：定額指標維持、含區間列者另給 _min／_max）
            m['已知列小計'] = tot if has_numbers else None
            m['已知列小計說明'] = f'僅 {int(len(g))} 列員額可辨識之加總，不是完整總額' if has_numbers else None
            for k in COUNT_METRICS: m[k] = None
        comparable = (result in ('相符', '條文解析（無編制表）') and data_state in ('可用', '可用（區間）', '可用（條文區間）') and all(x in WHITELIST_NOTES or x.startswith(WHITELIST_PREFIX) for x in notes) and not (sc and sc.get('狀態', '').startswith('官方合計待核')))
        duties = art[(art['機關'] == name) & (art['法規類別'] == '組織法規') & (art['條文內容'].fillna('').str.contains('掌理'))]['條文內容']
        kind = next((k for k in ['分署', '分局', '分院', '分所', '分處', '署', '局', '處', '所', '館', '院', '中心', '園', '場', '隊', '監獄', '學校', '會', '部', '行'] if name.endswith(k)), '其他')
        agencies.append({
            '機關': name, '機關代碼': o['機關代碼'], '部會': o['部會'], '層級': int(o['層級']), '隸屬': o['隸屬'], '類型': kind,
            '組織法規名稱': o['組織法規名稱'], '組織法規連結': o['組織法規連結'], '編制表來源': o['編制表來源'],
            '編制員額合計_總表': None if pd.isna(o['編制員額合計']) else int(float(o['編制員額合計'])),
            '表列合計': tbl_total, '控制數': ctrl_num,
            '驗算狀態': o['驗算狀態'], '驗算結果': result, '品質註記': notes, '可比較': bool(comparable),
            '資料狀態': data_state, '來源核對狀態': src_status, '來源核對說明': (sc or {}).get('說明'),
            '法定員額依據': statutory_basis(art, name) if (result in ('無編制表', '條文解析（無編制表）')) else None,
            '修正紀錄': [f"{e['動作']}{'序'+str(e['序']) if e.get('序') else ''}：{e.get('對源') or e.get('來源') or ''}（PDF 第{e.get('PDF頁','?')}頁）" for e in log['entries']] or None,
            '分表說明': o['分表說明'] if pd.notna(o['分表說明']) else None,
            '組織法規最新異動日': (art[(art['機關'] == name) & (art['法規類別'] == '組織法規')]['最新異動日'].iloc[0] if ((art['機關'] == name) & (art['法規類別'] == '組織法規')).any() else None),
            '掌理事項': duties.iloc[0] if len(duties) else None,
            '指標': m,
        })
    articles = [{'機關': r['機關'], '法規名稱': r['法規名稱'], '法規類別': r['法規類別'], '條號': r['條號'], '條文內容': r['條文內容'], '最新異動日': r['最新異動日'], '連結': r['連結']} for _, r in art.iterrows()]
    def clean(x):  # pandas 的 NaN → null
        if isinstance(x, dict): return {k: clean(v) for k, v in x.items()}
        if isinstance(x, list): return [clean(v) for v in x]
        if isinstance(x, float) and x != x: return None
        return x
    agencies, positions, articles = clean(agencies), clean(positions), clean(articles)
    os.makedirs(out, exist_ok=True)
    json.dump({'metric_definitions': {
        '—（缺值）': '未取得／待人工輸入／待審，不等於 0；人數類指標為 null 時不進比較、平均、中位數與距離排序',
        '員額合計': '編制表明細「員額」加總（括號兼任不計；控制列、錯位列不計）',
        '表列合計': '編制表上的合計數：總表登錄者，或總表無合計時取明細內的合計控制列（此時品質註記標「表內驗算相符（合計取自明細控制列）」，僅表示表內一致，不代表官方來源已核實）',
        '來源核對狀態': '與法規資料庫官方 PDF 的核對情形，與表內驗算分開記錄',
        '驗算結果': '相符／不相符／找不到合計／需人工輸入／無編制表；人工修正或取用控制列者由程式重新驗算',
        '品質註記': 'Codex抽樣不一致／人工補登（已對源）／人工補登（未完成對源或驗算不符）／表內驗算相符（合計取自明細控制列）／官方合計待核／列品質待審（員額不完整：錯位、疑似控制列）／列品質待審（官等結構：官等異常，員額已知）',
        '已知列小計': '員額不完整時，僅可辨識列的加總；明示不是完整總額',
        '法定員額_條文': '舊體例組織法規（無編制表）：依條文逐職稱解析之專任下限／上限（文官＋警察官＋教育人員），警備隊、聘用約僱、兼任另列、不計入；員額合計以區間呈現，不以下限充當定額',
        '聘用約僱條文': '組織法規條文明定聘用／約僱／僱用人數之條款（條號、類型、下限、上限、原句）；一般機關不在組織法列聘用人數，有列者為特例',
        '聘用約僱上限_條文': '上列條款之人數上限（最大值）；空＝組織法規未明定',
        '員額合計_min／max': '機關內有專任區間列（如「七-九」）時，定額列加總＋區間下限／上限；此時「員額合計」為空，不以下限充當定額，預設不進距離排序、平均、中位數與 ±50%（比對頁可勾選「區間取下限」並持續標示口徑）。其他人數指標只有「含區間列」者（例如其他官等員額）同樣改為 _min／_max，其餘定額指標維持；比率一律留空',
        '兼任合計': '括號語意判定為「兼任」（本列備註有兼任字樣）之括號人數加總；有 unknown 括號列時為空並另給「兼任合計_已判定」；兼任永不加回專任',
        'paren_meaning': '兼任｜上限｜unknown；只依本列備註判定，同表慣例只記為候選證據不放行；括號可同時為兼任且為區間（paren_min／max）',
        '括號待審列數': 'paren_meaning=unknown 的列數；只表示括號部分未判定，專任部分照常計入',
        '職等_norm': '職等的 NFKC 解析副本（相容字 六 U+F9D1→六）；顯示與匯出用 raw',
        '碎片列數': '證據明確之表頭殘留／附註拆列／重複擷取列，保留原列、標記不計入，不刪除',
        '官等結構待審列': '官等異常列（員額已知、官等分類待審）；該機關官等類指標為空、員額合計照原表列數計',
        '可比較': '驗算結果為相符、資料狀態可用、品質註記皆屬白名單（人工補登已對源、表內驗算相符、頁眉警示）且無官方合計待核',
        '副首長數': '本機關首長之副手（署長→副署長、部長→副部長／政務次長／常務次長…）且不屬內部單位者之員額；內部單位的副處長、副主任不計',
        '簡任員額': '官等含「簡任」（含薦任至簡任）或職等上限達第十職等以上之員額，加上備註「內 N 人得列簡任」之 N（以上限計算）；不含得列者見「簡任員額_法定」',
        '簡任非主管': '簡任員額中職稱非主管者（專門委員、簡任技正、簡任秘書、參事、研究委員等），含得列簡任之非主管職稱',
        '得列簡任人數': '備註「內 N 人得列簡任…」之 N 加總（僅計官等非簡任之列）',
        '得列薦任人數': '委任職稱備註「內 N 人得列薦任…」之 N 加總',
        '薦任員額': '官等含薦任（含委任或薦任）者，扣除得列簡任、加上委任得列薦任',
        '委任員額': '官等為委任者，扣除得列薦任',
        '主管員額': '職稱以長、主任、股長等結尾者',
        '幕僚單位員額': '單位名稱含人事、主計、會計、政風、秘書室、總務、資訊室者',
        '業務單位數': '處務規程（或辦事細則）「本機關設下列組、室…」所列單位中，非幕僚性質者（組、處、科、中心、大隊…）',
        '幕僚單位數': '同上條文中名稱含秘書室、人事、主計、會計、政風、資訊、法制、統計、總務、公關、國會聯絡、研考者',
        '單位數': '業務單位數＋幕僚單位數；無處務規程或條文無法判讀者為空',
        '科數': '同上條文各單位「分 N 科辦事」之 N 加總；未分科者為空',
        '暫列職稱數': '備註含「暫列」（官等職等暫列）的職稱列數',
        '得列人數': '備註「內 N 人得列…」的 N 加總',
        '法定員額依據': '無編制表機關：有＝本機關組織法規條文辨識出首長副首長以外之員額條款（給條號與連結，未加總）；無＝本系統尚未完成該法規員額結構化（僅辨識出首長職稱條款，或依共用法規），不代表法規無員額規定',
    }, 'agencies': agencies}, open(os.path.join(out, 'agencies.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(positions, open(os.path.join(out, 'positions.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(articles, open(os.path.join(out, 'articles.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump({'總表說明': info, '整備時間': dt.datetime.now().strftime('%Y-%m-%d %H:%M'), '機關數': len(agencies), '明細列數': len(positions), '條文數': len(articles)},
              open(os.path.join(out, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    lines = ['# 建檔檢核（語意檢查命中列）', f'整備時間：{dt.datetime.now():%Y-%m-%d %H:%M}', '',
             '| 機關 | 序 | 職稱 | 列品質 | 說明 |', '|---|---|---|---|---|'] + [f'| {a} | {b} | {c} | {d} | {e} |' for a, b, c, d, e in checklog]
    lines += ['', '## 括號語意待審列（unknown：括號部分未判定，專任照常計入）', '', '| 機關 | 序 | 職稱 | 員額原文 | 括號 | 證據 |', '|---|---|---|---|---|---|'] + \
             [f"| {p['機關']} | {p['序']} | {p['職稱']} | {p['raw原文']} | {p['paren_min']}–{p['paren_max']} | {p['paren_evidence']} |" for p in positions if p['paren_meaning'] == 'unknown']
    lines += ['', '## 職等區間待審列（raw 含「至」但 NFKC 後 min==max）', '', '| 機關 | 序 | 職稱 | 職等 raw |', '|---|---|---|---|'] + \
             [f"| {p['機關']} | {p['序']} | {p['職稱']} | {p['職等']} |" for p in positions if p['職等區間待審']]
    lines += ['', '## 機關層級', '', '| 機關 | 資料狀態 | 驗算結果 | 品質註記 | 可比較 | 來源核對狀態 |', '|---|---|---|---|---|---|'] + \
             [f"| {a['機關']} | {a['資料狀態']} | {a['驗算結果']} | {'；'.join(a['品質註記'])} | {'是' if a['可比較'] else '否'} | {a['來源核對狀態']} |" for a in agencies if not a['可比較']]
    open(os.path.join(out, '建檔檢核.md'), 'w', encoding='utf-8').write('\n'.join(lines))
    print(f'機關 {len(agencies)}、明細 {len(positions)}、條文 {len(articles)}；不可比較 {sum(1 for a in agencies if not a["可比較"])}；列品質命中 {len(checklog)} → {out}')

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--master', required=True); ap.add_argument('--out', default='data'); ap.add_argument('--fixes', default=None)
    ap.add_argument('--attach-units', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'units_from_attachments.json'))
    a = ap.parse_args(); build(a.master, a.out, a.fixes, a.attach_units)

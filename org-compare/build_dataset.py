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

CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
def cn2n(t):
    if t == '十': return 10
    if t.startswith('十'): return 10 + CN[t[1]]
    if '十' in t:
        a, b = t.split('十'); return CN[a] * 10 + (CN[b] if b else 0)
    return CN.get(t)
def grade_range(s):
    m = re.findall(r'第([一二三四五六七八九十]+)職等', str(s))
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
        return ov, det, fixlog
    fixes = json.load(open(fixes_path, encoding='utf-8'))['fixes']
    det = det.copy()
    for col in ('原始列', '修正紀錄'):
        if col not in det.columns: det[col] = None
    add = []
    for f in fixes:
        ag = f['機關']; log = fixlog.setdefault(ag, {'entries': [], 'source_check': None})
        act = f['動作']
        note = f"{act}：{f.get('對源') or f.get('來源') or ''}（PDF 第{f.get('PDF頁', '?')}頁）"
        if act == '新增列':
            sub = det[det['機關名稱'] == ag]
            base = sub.iloc[0].to_dict() if len(sub) else {c: None for c in det.columns}
            row = dict(base); row.update({'序': str(int(pd.to_numeric(sub['序'], errors='coerce').max() or 0) + 1 + len([a for a in add if a['機關名稱'] == ag])),
                       '單位': f.get('單位'), '職稱': f['職稱'], '官等': f.get('官等'), '職等': f.get('職等'), '員額': str(f['員額']),
                       '員額原文': None, '括號員額_兼任': None, '備註': f.get('備註'), '原始列': None, '修正紀錄': '人工補登：' + note, 'PDF頁': f.get('PDF頁')})
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
            det.at[i, '原始列'] = json.dumps(orig, ensure_ascii=False); det.at[i, '修正紀錄'] = note
            log['entries'].append(f)
        elif act == '改合計':
            i = ov.index[ov['機關'] == ag]
            ov.loc[i, '編制員額合計'] = str(f['編制員額合計']); ov.loc[i, '驗算狀態'] = f.get('驗算狀態', ov.loc[i, '驗算狀態'])
            log['entries'].append(f)
        elif act == '來源核對':
            log['source_check'] = f
        else:
            print(f'【警告】不認識的動作 {act}')
    if add:
        det = pd.concat([det, pd.DataFrame(add)], ignore_index=True)
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

def classify_rows(det):
    """對整個明細資料框算列品質（需有 機關名稱、序、分表、PDF頁、n、官等、職等、職稱、單位、員額原文、備註 欄）。"""
    seq = pd.to_numeric(det['序'], errors='coerce').fillna(9999)
    agency_last = seq == seq.groupby(det['機關名稱']).transform('max')
    sub_key = det['機關名稱'] + '|' + det['分表'].fillna('').astype(str)
    sub_last = det['分表'].notna() & (seq == seq.groupby(sub_key).transform('max'))
    page_key = det['機關名稱'] + '|' + det['PDF頁'].fillna('').astype(str)
    page_last = det['PDF頁'].notna() & (seq == seq.groupby(page_key).transform('max'))
    out = [row_quality(r, {'agency_last': bool(agency_last.iloc[i]), 'sub_last': bool(sub_last.iloc[i]), 'page_last': bool(page_last.iloc[i])}) for i, (_, r) in enumerate(det.iterrows())]
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

RESULT_ENUM = ['相符', '不相符', '找不到合計', '需人工輸入', '無編制表']
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

def build(master, out, fixes_path=None, attach_units_path=None):
    global ATTACH_UNITS
    if attach_units_path and os.path.exists(attach_units_path):
        ATTACH_UNITS = json.load(open(attach_units_path, encoding='utf-8')); print(f'附表單位資料 {len(ATTACH_UNITS)} 個機關')
    ov = pd.read_excel(master, '機關總覽', dtype=str)
    det = pd.read_excel(master, '編制表明細', dtype=str)
    art = pd.read_excel(master, '條文', dtype=str)
    info = pd.read_excel(master, '說明', header=None, dtype=str).iloc[0, 0]
    ov, det, fixlog = apply_fixes(ov, det, fixes_path)
    det['n'] = pd.to_numeric(det['員額'], errors='coerce')
    det['bracket'] = pd.to_numeric(det['括號員額_兼任'], errors='coerce')
    det['序'] = pd.to_numeric(det['序'], errors='coerce').fillna(9999)
    # 列品質（語意檢查）
    det['列品質'], det['列品質說明'] = classify_rows(det)
    # 計入（員額）：控制列不是職位；錯位／疑似控制列的員額欄不可信 → 不計；官等異常列的員額是原表已知數 → 計入員額，但不計入官等結構
    det['計入'] = ~det['列品質'].isin(['控制列', '控制列（分表）', '控制列（跨頁小計）', '疑似控制列', '錯位'])
    det['計入官等'] = det['計入'] & (det['列品質'] != '官等異常')
    gr = det['職等'].map(grade_range)
    det['職等下限'] = [g[0] for g in gr]; det['職等上限'] = [g[1] for g in gr]
    det['官等'] = det['官等'].fillna('')
    det['簡任'] = det['官等'].str.contains('簡任') | (det['職等上限'].fillna(0) >= 10)
    det['薦任'] = ~det['簡任'] & det['官等'].str.contains('薦任')
    det['委任'] = det['官等'].str.fullmatch('委任')
    def deli(row, band):
        n = 0
        for k in re.findall(r'(?:內|其中)([一二三四五六七八九十○〇百]+)人得列' + band, str(row['備註'] or '')):
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
            '職等下限': r['職等下限'], '職等上限': r['職等上限'], '簡任': bool(r['簡任']), '主管': bool(r['主管']),
            '得列簡任': int(r['得列簡任']), '得列薦任': int(r['得列薦任']), 'PDF頁': r['PDF頁'],
            '列品質': r['列品質'], '列品質說明': r['列品質說明'], '計入': bool(r['計入']), '計入官等': bool(r['計入官等']),
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
        m = {
            '員額合計': tot,
            '首長職稱': head_title, '首長職等': head['職等'].iloc[0] if len(head) else None,
            '首長兼任': bool(len(head) and pd.notna(head['bracket'].iloc[0])),
            '副首長職稱': '、'.join(sorted(set(dep_rows['職稱']))) or ('／'.join(dep_titles) + '（無）' if dep_titles else None),
            '副首長數': int(dep_rows['n'].fillna(0).sum()), '副首長兼任數': int(dep_rows['bracket'].fillna(0).sum()),
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
            '明細列數': int(len(g_all)), '員額空白列數': int(g['n'].isna().sum()),
            '暫列職稱數': int(g['備註'].fillna('').str.contains('暫列').sum()),
            '得列人數': int(sum(cn2n(x) or 0 for x in re.findall(r'內([一二三四五六七八九十]+)人得列', ' '.join(g['備註'].fillna(''))))),
        }
        m['簡任非主管比'] = round(m['簡任非主管'] / tot, 4) if tot else None
        m['簡任比'] = round(m['簡任員額'] / tot, 4) if tot else None
        m['主管比'] = round(m['主管員額'] / tot, 4) if tot else None
        m['幕僚比'] = round(m['幕僚單位員額'] / tot, 4) if tot else None
        RANK_METRICS = ['簡任員額', '簡任主管', '簡任非主管', '簡任員額_法定', '簡任非主管_法定', '得列簡任人數', '得列薦任人數', '薦任員額', '委任員額', '其他官等員額', '簡任非主管比', '簡任比']
        if data_state == '待審（官等結構）':   # 員額已知；官等結構不可用
            m['官等結構待審列'] = [{'序': int(x['序']), '職稱': x['職稱'], '員額': None if pd.isna(x['n']) else int(x['n']), '官等原文': x['官等']} for _, x in pending_rank.iterrows()]
            for k in RANK_METRICS: m[k] = None
        elif data_state != '可用':             # 未取得或員額不完整：人數類指標一律 null；已知列小計另列、明示不完整
            m['已知列小計'] = tot if has_numbers else None
            m['已知列小計說明'] = f'僅 {int(len(g))} 列員額可辨識之加總，不是完整總額' if has_numbers else None
            for k in COUNT_METRICS: m[k] = None
        comparable = (result == '相符' and data_state == '可用' and all(x in WHITELIST_NOTES for x in notes) and not (sc and sc.get('狀態', '').startswith('官方合計待核')))
        duties = art[(art['機關'] == name) & (art['法規類別'] == '組織法規') & (art['條文內容'].fillna('').str.contains('掌理'))]['條文內容']
        kind = next((k for k in ['分署', '分局', '分院', '分所', '分處', '署', '局', '處', '所', '館', '院', '中心', '園', '場', '隊', '監獄', '學校', '會', '部', '行'] if name.endswith(k)), '其他')
        agencies.append({
            '機關': name, '機關代碼': o['機關代碼'], '部會': o['部會'], '層級': int(o['層級']), '隸屬': o['隸屬'], '類型': kind,
            '組織法規名稱': o['組織法規名稱'], '組織法規連結': o['組織法規連結'], '編制表來源': o['編制表來源'],
            '編制員額合計_總表': None if pd.isna(o['編制員額合計']) else int(float(o['編制員額合計'])),
            '表列合計': tbl_total, '控制數': ctrl_num,
            '驗算狀態': o['驗算狀態'], '驗算結果': result, '品質註記': notes, '可比較': bool(comparable),
            '資料狀態': data_state, '來源核對狀態': src_status, '來源核對說明': (sc or {}).get('說明'),
            '法定員額依據': statutory_basis(art, name) if (not has_numbers and result == '無編制表') else None,
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
    lines += ['', '## 機關層級', '', '| 機關 | 資料狀態 | 驗算結果 | 品質註記 | 可比較 | 來源核對狀態 |', '|---|---|---|---|---|---|'] + \
             [f"| {a['機關']} | {a['資料狀態']} | {a['驗算結果']} | {'；'.join(a['品質註記'])} | {'是' if a['可比較'] else '否'} | {a['來源核對狀態']} |" for a in agencies if not a['可比較']]
    open(os.path.join(out, '建檔檢核.md'), 'w', encoding='utf-8').write('\n'.join(lines))
    print(f'機關 {len(agencies)}、明細 {len(positions)}、條文 {len(articles)}；不可比較 {sum(1 for a in agencies if not a["可比較"])}；列品質命中 {len(checklog)} → {out}')

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--master', required=True); ap.add_argument('--out', default='data'); ap.add_argument('--fixes', default=None)
    ap.add_argument('--attach-units', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'units_from_attachments.json'))
    a = ap.parse_args(); build(a.master, a.out, a.fixes, a.attach_units)

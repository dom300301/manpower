#!/usr/bin/env python3
"""
資料整備：把「組織法編制表_總表.xlsx」整理成查詢系統用的 JSON（不論最後採哪種系統形式都需要）。

用法：
    python3 build_dataset.py --master 總表.xlsx --out data/

輸出：
    data/agencies.json   每機關一筆：基本資料 + 結構指標
    data/positions.json  編制表明細（每職稱一列，含數值化員額、職等上下限、是否主管、是否簡任）
    data/articles.json   組織法規與處務規程條文
    data/meta.json       資料版本（總表產生時間、整備時間、機關數）

指標定義見 agencies.json 內 "metric_definitions"。
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

def apply_fixes(ov, det, fixes_path):
    if not fixes_path or not os.path.exists(fixes_path):
        return ov, det
    fixes = json.load(open(fixes_path, encoding='utf-8'))['fixes']
    add = []
    for f in fixes:
        if f['動作'] == '新增列':
            sub = det[det['機關名稱'] == f['機關']]
            base = sub.iloc[0].to_dict() if len(sub) else {c: None for c in det.columns}
            row = dict(base); row.update({'序': str(int(pd.to_numeric(sub['序'], errors='coerce').max() or 0) + 1 + len(add)), '單位': f.get('單位'), '職稱': f['職稱'],
                       '官等': f.get('官等'), '職等': f.get('職等'), '員額': str(f['員額']), '員額原文': None, '括號員額_兼任': None, '備註': '人工補登：' + f.get('來源', '')})
            add.append(row)
        elif f['動作'] == '刪除列':
            det = det[~((det['機關名稱'] == f['機關']) & (det['職稱'] == f['職稱']) & (det['單位'].fillna('') == (f.get('單位') or '')))]
        elif f['動作'] == '改合計':
            i = ov.index[ov['機關'] == f['機關']]
            ov.loc[i, '編制員額合計'] = str(f['編制員額合計']); ov.loc[i, '驗算狀態'] = f.get('驗算狀態', ov.loc[i, '驗算狀態'])
    if add:
        det = pd.concat([det, pd.DataFrame(add)], ignore_index=True)
    print(f'套用人工修正 {len(fixes)} 筆')
    return ov, det

def build(master, out, fixes_path=None):
    ov = pd.read_excel(master, '機關總覽', dtype=str)
    det = pd.read_excel(master, '編制表明細', dtype=str)
    art = pd.read_excel(master, '條文', dtype=str)
    info = pd.read_excel(master, '說明', header=None, dtype=str).iloc[0, 0]
    ov, det = apply_fixes(ov, det, fixes_path)
    det['n'] = pd.to_numeric(det['員額'], errors='coerce')
    det['bracket'] = pd.to_numeric(det['括號員額_兼任'], errors='coerce')
    det['序'] = pd.to_numeric(det['序'], errors='coerce').fillna(9999)
    gr = det['職等'].map(grade_range)
    det['職等下限'] = [g[0] for g in gr]; det['職等上限'] = [g[1] for g in gr]
    det['官等'] = det['官等'].fillna('')
    det['簡任'] = det['官等'].str.contains('簡任') | (det['職等上限'].fillna(0) >= 10)
    det['薦任'] = ~det['簡任'] & det['官等'].str.contains('薦任')
    det['委任'] = det['官等'].str.fullmatch('委任')
    det['主管'] = det['職稱'].str.contains(MGR_RE)
    det['首長'] = det['職稱'].str.match(HEAD_RE) & (det['序'] <= 2)
    det['副首長'] = det['職稱'].str.match(DEPUTY_RE) & det['單位'].isna()
    det['幕僚單位'] = det['單位'].fillna('').str.contains(STAFF_UNIT_RE)

    positions = []
    for _, r in det.iterrows():
        positions.append({k: (None if pd.isna(v) else v) for k, v in {
            '機關': r['機關名稱'], '分表': r['分表'], '序': int(r['序']) if r['序'] != 9999 else None, '單位': r['單位'], '職稱': r['職稱'],
            '官等': r['官等'] or None, '職等': r['職等'], '員額': None if pd.isna(r['n']) else int(r['n']),
            '兼任': None if pd.isna(r['bracket']) else int(r['bracket']), '員額原文': r['員額原文'], '備註': r['備註'],
            '職等下限': r['職等下限'], '職等上限': r['職等上限'], '簡任': bool(r['簡任']), '主管': bool(r['主管']), 'PDF頁': r['PDF頁']}.items()})

    agencies = []
    for _, o in ov.iterrows():
        g = det[det['機關名稱'] == o['機關']]
        n = g['n'].fillna(0)
        tot = int(n.sum())
        head = g[g['首長']].sort_values('序').head(1)
        m = {
            '員額合計': tot,
            '首長職稱': head['職稱'].iloc[0] if len(head) else None,
            '首長職等': head['職等'].iloc[0] if len(head) else None,
            '首長兼任': bool(len(head) and pd.notna(head['bracket'].iloc[0])),
            '副首長數': int(n[g['副首長']].sum()), '副首長兼任數': int(g.loc[g['副首長'], 'bracket'].fillna(0).sum()),
            '主任秘書': int(n[g['職稱'] == '主任秘書'].sum()),
            '組長數': int(n[g['職稱'] == '組長'].sum()), '副組長數': int(n[g['職稱'] == '副組長'].sum()),
            '處長數': int(n[g['職稱'] == '處長'].sum()), '副處長數': int(n[g['職稱'] == '副處長'].sum()),
            '科長數': int(n[g['職稱'] == '科長'].sum()), '股長數': int(n[g['職稱'] == '股長'].sum()),
            '專門委員': int(n[g['職稱'] == '專門委員'].sum()),
            '簡任員額': int(n[g['簡任']].sum()), '簡任主管': int(n[g['簡任'] & g['主管']].sum()), '簡任非主管': int(n[g['簡任'] & ~g['主管']].sum()),
            '薦任員額': int(n[g['薦任']].sum()), '委任員額': int(n[g['委任']].sum()),
            '其他官等員額': int(n[~g['簡任'] & ~g['薦任'] & ~g['委任']].sum()),
            '幕僚單位員額': int(n[g['幕僚單位']].sum()),
            '單位數': int(g['單位'].dropna().nunique()),
            '主管員額': int(n[g['主管']].sum()),
            '明細列數': int(len(g)), '員額空白列數': int(g['n'].isna().sum()),
            '暫列職稱數': int(g['備註'].fillna('').str.contains('暫列').sum()),
            '得列人數': int(sum(cn2n(x) or 0 for x in re.findall(r'內([一二三四五六七八九十]+)人得列', ' '.join(g['備註'].fillna(''))))),
        }
        m['簡任非主管比'] = round(m['簡任非主管'] / tot, 4) if tot else None
        m['簡任比'] = round(m['簡任員額'] / tot, 4) if tot else None
        m['主管比'] = round(m['主管員額'] / tot, 4) if tot else None
        m['幕僚比'] = round(m['幕僚單位員額'] / tot, 4) if tot else None
        name = o['機關']
        duties = art[(art['機關'] == name) & (art['法規類別'] == '組織法規') & (art['條文內容'].fillna('').str.contains('掌理'))]['條文內容']
        kind = next((k for k in ['分署', '分局', '分院', '分所', '分處', '署', '局', '處', '所', '館', '院', '中心', '園', '場', '隊', '監獄', '學校', '會', '部', '行'] if name.endswith(k)), '其他')
        agencies.append({
            '機關': name, '機關代碼': o['機關代碼'], '部會': o['部會'], '層級': int(o['層級']), '隸屬': o['隸屬'], '類型': kind,
            '組織法規名稱': o['組織法規名稱'], '組織法規連結': o['組織法規連結'], '編制表來源': o['編制表來源'],
            '編制員額合計_總表': None if pd.isna(o['編制員額合計']) else int(float(o['編制員額合計'])),
            '驗算狀態': o['驗算狀態'], '分表說明': o['分表說明'] if pd.notna(o['分表說明']) else None,
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
        '員額合計': '編制表明細「員額」加總（括號兼任不計）',
        '副首長數': '副署長／副局長／副處長等副首長職稱且不屬內部單位者之員額',
        '簡任員額': '官等含「簡任」或職等上限達第十職等以上之員額',
        '簡任非主管': '簡任員額中職稱非主管者（專門委員、簡任技正、簡任秘書、參事、研究委員等）',
        '主管員額': '職稱以長、主任、股長等結尾者',
        '幕僚單位員額': '單位名稱含人事、主計、會計、政風、秘書室、總務、資訊室者',
        '單位數': '明細「單位」欄不同值的數目（編制表未列單位者為 0）',
        '暫列職稱數': '備註含「暫列」（官等職等暫列）的職稱列數',
            '得列人數': int(sum(cn2n(x) or 0 for x in re.findall(r'內([一二三四五六七八九十]+)人得列', ' '.join(g['備註'].fillna(''))))),
    }, 'agencies': agencies}, open(os.path.join(out, 'agencies.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(positions, open(os.path.join(out, 'positions.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(articles, open(os.path.join(out, 'articles.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump({'總表說明': info, '整備時間': dt.datetime.now().strftime('%Y-%m-%d %H:%M'), '機關數': len(agencies), '明細列數': len(positions), '條文數': len(articles)},
              open(os.path.join(out, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'機關 {len(agencies)}、明細 {len(positions)}、條文 {len(articles)} → {out}')

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--master', required=True); ap.add_argument('--out', default='data'); ap.add_argument('--fixes', default=None)
    a = ap.parse_args(); build(a.master, a.out, a.fixes)

#!/usr/bin/env python3
"""
P0 資料層驗收與回歸測試（純 Python，不需 pytest）。
用法：python3 tests/test_p0_dataset.py --after <data目錄> [--before <修改前data目錄>]
"""
import argparse, json, re, sys, collections
ap = argparse.ArgumentParser(); ap.add_argument('--after', required=True); ap.add_argument('--before'); a = ap.parse_args()
A = json.load(open(f'{a.after}/agencies.json', encoding='utf-8'))['agencies']; P = json.load(open(f'{a.after}/positions.json', encoding='utf-8'))
by = {r['機關']: r for r in A}; fails = []; notes = []
def check(cond, msg):
    (notes if cond else fails).append(('PASS ' if cond else 'FAIL ') + msg)

# P0-A 缺值語義
unknown = [r for r in A if r['指標']['員額合計'] is None and r['指標'].get('員額合計_min') is None]  # 區間機關（可用（區間））不算未知
untaken = [r for r in unknown if r['資料狀態'].startswith('未取得')]
pending = [r for r in unknown if r['資料狀態'].startswith('待審')]
excluded = [r for r in unknown if r['資料狀態'].startswith('不適用')]
check(len(untaken) == 0 and len(excluded) == 1 and excluded[0]['機關'] == '駐外機構', f'「未取得」機關數 = {len(untaken)}（P0 診斷 16 → 0：4 份人工轉錄、2 份教育部法規網 HTML、2 份法務部網站編制表、2 份法院組織法附表補登，5 個舊體例機關依條文解析；駐外機構依審查指示列不適用）')
check(len(unknown) == len(untaken) + len(pending) + len(excluded) and all(r['資料狀態'] != '可用' for r in unknown), f'員額合計 null 機關 = 未取得 {len(untaken)} + 待審（員額不完整）{len(pending)}（{[r["機關"] for r in pending]}）；官等結構待審者員額合計不為 null')
check(all(r['指標']['員額合計'] != 0 for r in A), '沒有任何機關的員額合計被寫成 0')
check(by['財政部']['指標']['員額合計'] == 213 and by['財政部']['驗算結果'] == '相符' and '人工補登（已對源）' in by['財政部']['品質註記'] and by['財政部']['可比較'], '財政部：人工轉錄 49 列經確認補登，合計 213 相符、已對源、可比較')
for n, t in [('國家教育研究院', 190), ('交通部鐵道局北部工程分局', 119), ('交通部鐵道局南部工程分局', 123)]:
    check(by[n]['指標']['員額合計'] == t and by[n]['驗算結果'] == '相符' and by[n]['可比較'], f'{n}：人工轉錄補登，合計 {t} 相符')
for r in unknown:
    check(all(r['指標'][k] is None for k in ['簡任員額', '薦任員額', '委任員額', '主管員額', '簡任非主管比']), f'{r["機關"]} 其他人數類指標亦為 null')
    check(not r['可比較'], f'{r["機關"]} 不可比較')
basis = [r for r in unknown if r['法定員額依據']]
basis_yes = [r for r in untaken if r['法定員額依據'] and r['法定員額依據']['有']]
basis_no = [r for r in untaken if r['法定員額依據'] and not r['法定員額依據']['有']]
check(len(basis_yes) == 0 and by['行政院公共工程委員會']['法定員額依據']['條號'].startswith('第8條') and by['行政院公共工程委員會']['資料狀態'] == '可用（條文區間）' and by['駐外機構']['法定員額依據']['有'] is False, f'法定員額依據「有」之未取得機關 {len(basis_yes)} 個（工程會等 5 個已改為可用（條文區間），法定員額依據仍保留）')
check(len(basis_no) == 0 and all('尚未完成' in r['法定員額依據']['說明'] for r in basis_no), f'法定員額依據「無」{len(basis_no)} 個，措辭為「本系統尚未完成員額結構化」而非法律事實：{[r["機關"] for r in basis_no]}')
check(all('headcount' not in json.dumps(r['法定員額依據'] or {}) for r in untaken), '未產生區間 min/max 總額')
# 僅兼任列保留專任 0，但整機關未知不得為 0（鐵道局北部：單列無數字 → 未取得）
check([p for p in P if p['機關'] == '交通部鐵道局北部工程分局' and p['序'] == 1][0]['列品質'] == '碎片列（原表無法讀取，已人工轉錄）' and by['交通部鐵道局北部工程分局']['指標']['兼任合計'] == 36, '鐵道局北部：原表殘留空列標轉錄取代不計入；兼任（括號）36 保留')

# P0-B 品質旗標
mixed = [r for r in A if 'Codex抽樣不一致' in r['品質註記']]
cleared = [r for r in A if 'Codex差異已釐清（已對源）' in r['品質註記']]
check(len(mixed) == 0 and len(cleared) == 12 and all(r['可比較'] for r in cleared if r['驗算結果'] == '相符') and all(r['來源核對狀態'].startswith('已對源（Codex') for r in cleared), f'Codex抽樣不一致 {len(mixed)} 個；12 個機關之 Codex 差異已逐筆釐清並記於來源核對（審查同意 2026-11-07）→ 可比較')
check(by['教育部']['可比較'] and by['教育部']['驗算結果'] == '相符' and 'Codex差異已釐清（已對源）' in by['教育部']['品質註記'], '教育部：Codex 差異已釐清 → 可比較')
dept_group = [r['機關'] for r in A if r['層級'] == 2 and r['類型'] == '部' and r['可比較']]
check('教育部' in dept_group and '財政部' in dept_group and '農業部' in dept_group, f'農業部預設部級群組含教育部（Codex 已釐清）、財政部（已補登）：{dept_group}')
check(all(r['驗算結果'] in ('相符', '不相符', '找不到合計', '需人工輸入', '無編制表', '條文解析（無編制表）', '員額表區間') for r in A), '驗算結果皆為列舉值')
check(all(isinstance(r['可比較'], bool) for r in A), '可比較為布林')
check(all(r['可比較'] == (r['驗算結果'] in ('相符', '條文解析（無編制表）', '員額表區間') and not any('類別待確認' in x for x in r['品質註記']) and r['資料狀態'] in ('可用', '可用（區間）', '可用（條文區間）') and all(x in {'人工補登（已對源）', '表內驗算相符（合計取自明細控制列）', '警示：頁眉'} or x.startswith(('括號語意待審', '員額回填（原文字形解析', '法定員額（條文區間）', 'Codex差異已釐清', '驗算結果由程式重算', '法定員額（附表區間）')) for x in r['品質註記']) and not r['來源核對狀態'].startswith('官方合計待核')) for r in A), '可比較 == 規則重算結果（驗算相符 ∧ 可用／可用（區間） ∧ 註記皆白名單或括號語意待審 ∧ 非官方合計待核）')
pg = by['行政院人事行政總處公務人力發展學院']
check(pg['可比較'] and '人工補登（已對源）' in pg['品質註記'] and pg['指標']['員額合計'] == 91, '公務人力發展學院：人工補登有來源／頁碼／對源且驗算相符 → 可比較')
n_flag = sum(1 for r in A if not r['可比較'])
notes.append(f'INFO 不可比較機關數 = {n_flag}（由修正後資料推導，不設固定目標；舊快照 31+12=43 僅供參考）')
# 官等異常：全庫不得有未標記的異常官等列計入
ab = [p for p in P if p['列品質'] == '官等異常']
check(all(p['計入'] and not p['計入官等'] for p in ab), f'官等異常列 {len(ab)} 列：員額計入、官等不計入（機關：{sorted(set(p["機關"] for p in ab))}）')
yl = by['臺北榮民總醫院玉里分院']; ylr = next(p for p in P if p['機關'] == '臺北榮民總醫院玉里分院' and p['序'] == 38)
check(ylr['列品質'] is None and ylr['員額'] == 3 and ylr['計入'] and ylr['修正紀錄'] and ylr['原始列'] and ylr['原始列'].get('員額') is None, f'玉里分院序 38：原錯位列經人工確認改列（員額 3、官等 委任或薦任），原始列保留：{ylr["原始列"]}')
check(yl['資料狀態'] == '可用' and yl['指標']['員額合計'] == 465 and yl['驗算結果'] == '相符' and yl['可比較'] and '人工補登（已對源）' in yl['品質註記'], f'玉里分院：改列後 465 相符、已對源、可比較（表列 {yl["表列合計"]}）')
check(len(pending) == 0, f'待審（員額不完整）機關目前 {len(pending)} 個（錯位列均已人工確認改列）；錯位→待審機制由 tests/test_control_rows.py 單元測試保護')
check(by['衛生福利部臺中醫院']['可比較'] is True and by['衛生福利部臺中醫院']['來源核對狀態'].startswith('已對源（官方附件 FileId 0000427371'), '臺中醫院：官方附件 115-10-30 生效版已線上取得並逐列比對相同 → 已對源、可比較（2026-11-07）')
inc = [r for r in A if r['資料狀態'] == '待審（員額不完整）']
check(all(r['指標']['員額合計'] is None and (r['指標'].get('已知列小計') is None or '不是完整總額' in r['指標']['已知列小計說明']) for r in inc), f'員額不完整者 {len(inc)} 個：總額 null，已知列小計明示不是完整總額')
hcr = {p['序']: p for p in P if p['機關'] == '衛生福利部恆春旅遊醫院'}
check(hcr[27]['官等'] == '委任' and hcr[27]['原始列']['官等'] == '師委任級(或士' and hcr[28]['官等'] == '薦任', f'恆春 序27/28 官等依 PDF 校正並保留原始列：{hcr[27]["原始列"]["官等"]}→{hcr[27]["官等"]}、{hcr[28]["原始列"]["官等"]}→{hcr[28]["官等"]}')
hcm = by['衛生福利部恆春旅遊醫院']['指標']
check(hcm['委任員額'] == 2 and hcm['其他官等員額'] == 86 and hcm['薦任員額'] == 6, f'恆春 校正後 簡/薦/委/其他 = {hcm["簡任員額"]}/{hcm["薦任員額"]}/{hcm["委任員額"]}/{hcm["其他官等員額"]}（校正前 0/6/1/87：書記誤入其他官等）')

# P0-C 藥試所
ya = by['農業部農業藥物試驗所']; rows = [p for p in P if p['機關'] == '農業部農業藥物試驗所']
check(ya['指標']['員額合計'] == 79 and ya['表列合計'] == 79 and ya['驗算結果'] == '相符', f'藥試所 員額合計 {ya["指標"]["員額合計"]} == 表列合計 {ya["表列合計"]}（PDF 七十九）')
import re as _re
_cn = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
_br = sum(_cn.get((_re.search(r'[（(]([一二三四五六七八九])[）)]', str(p['raw原文'] or '')) or [None, ''])[1], 0) for p in rows)
check(_br == 7, f'藥試所 兼任合計（依 raw原文 括號）= {_br}（PDF (七)）；註：總表「括號員額_兼任」欄此機關為中文數字，數值化留待後續批次')
check(all(not p['列品質'] for p in rows), '藥試所無錯位列')
check(not any('卷' in (p['備註'] or '') for p in rows), '藥試所備註無頁眉文字')
fixed = [p for p in rows if p['修正紀錄']]
check(len(fixed) == 6 and all(p['原始列'] for p in fixed if p['修正紀錄'].startswith('改列')), f'藥試所 6 列人工修正均保留原始列與修正紀錄')
check(all(p['raw原文'] is not None or p['員額原文'] is None for p in rows), 'raw原文 欄逐字保留')
r13 = next(p for p in rows if p['序'] == 13); check(r13['職稱'] == '書記' and r13['官等'] == '委任' and r13['員額'] == 1 and r13['原始列']['職等'] == '委任', f'序13 校正：{r13["單位"]}/{r13["職稱"]}/{r13["官等"]}/{r13["職等"]}/{r13["員額"]}；原始列職等={r13["原始列"]["職等"]}')

# P0-D 控制列
ctrl = [p for p in P if p['列品質'] == '控制列']
check(len(ctrl) == 2 and all(not p['計入'] for p in ctrl), f'控制列 {len(ctrl)} 列且不計入')
check(not any(re.search(r'合計|總計|小計|共計', str(p['職稱'])) and p['計入'] for p in P), '職稱含合計字樣的列皆未計入職位加總')
tc = by['衛生福利部臺中醫院']; hc = by['衛生福利部恆春旅遊醫院']
check(tc['指標']['員額合計'] == 217 and tc['控制數']['專任'] == 217 and tc['控制數']['兼任'] == 69, f'臺中醫院 員額合計 {tc["指標"]["員額合計"]}、控制數 {tc["控制數"]}（不再翻倍 434）')
check(hc['指標']['員額合計'] == 94 and hc['控制數']['專任'] == 94 and hc['控制數']['兼任'] == 27, f'恆春旅遊醫院 員額合計 {hc["指標"]["員額合計"]}、控制數 {hc["控制數"]}（不再翻倍 188）')
check(tc['可比較'] and tc['來源核對狀態'].startswith('已對源') and '表內驗算相符（合計取自明細控制列）' in tc['品質註記'] and [p for p in P if p['機關'] == '衛生福利部臺中醫院' and p['序'] == 29][0]['職稱'] == '技術員', '臺中醫院：表內驗算相符且官方附件已對源 → 可比較；序29 職稱依官方附件改為技術員')
check(hc['可比較'] and hc['來源核對狀態'].startswith('官方PDF核對一致'), '恆春旅遊醫院：官方 PDF 11/06 重抓核對一致 → 可比較')
check(all('官方來源已核實' not in x for r in A for x in r['品質註記']), '品質註記不出現「官方來源已核實」字樣（表內驗算與來源核對分開）')

# 全庫守恆
for r in A:
    m = r['指標']
    if m['員額合計'] is None or m['簡任員額'] is None: continue  # 未取得／員額不完整／官等結構待審者跳過
    check(m['簡任員額'] + m['薦任員額'] + m['委任員額'] + m['其他官等員額'] == m['員額合計'], f'{r["機關"]} 官等加總 == 員額合計') if (m['簡任員額'] + m['薦任員額'] + m['委任員額'] + m['其他官等員額'] != m['員額合計']) else None
notes.append('PASS 全庫官等加總守恆（簡＋薦＋委＋其他 == 員額合計；未取得、員額不完整、官等結構待審者跳過）' if not any('官等加總' in f for f in fails) else 'FAIL 守恆')

# 回歸：與修改前比較
if a.before:
    B = {r['機關']: r for r in json.load(open(f'{a.before}/agencies.json', encoding='utf-8'))['agencies']}
    allowed = {r['機關'] for r in unknown} | {'衛生福利部臺中醫院', '衛生福利部恆春旅遊醫院', '農業部農業藥物試驗所'} | {p['機關'] for p in P if p['列品質'] in ('官等異常', '錯位', '疑似控制列')} | {r['機關'] for r in A if r['指標'].get('員額合計_min') is not None}
    # P1 資料回歸
    ey = by['行政院']; check(ey['指標']['員額合計'] is None and ey['指標']['員額合計_min'] == 635 and ey['指標']['員額合計_max'] == 637 and ey['資料狀態'] == '可用（區間）', f'行政院：員額合計空、區間 {ey["指標"]["員額合計_min"]}–{ey["指標"]["員額合計_max"]}（不以下限充當定額）')
    for n, exp in [('不當黨產處理委員會', 9), ('國家運輸安全調查委員會', None), ('核能安全委員會', 331), ('中央選舉委員會', 60)]:
        if exp is not None: check(by[n]['指標']['員額合計'] == exp and by[n]['指標']['員額合計'] == B[n]['指標']['員額合計'], f'{n} 專任合計 {by[n]["指標"]["員額合計"]} 不變（括號區間另列）')
    bk = [p for p in P if p['機關'] == '不當黨產處理委員會' and p['序'] == 3][0]
    check(bk['專任_min'] == 3 and bk['paren_min'] == 6 and bk['paren_max'] == 8 and bk['paren_meaning'] == '兼任' and bk['concurrent_min'] == 6 and bk['concurrent_max'] == 8 and bk['員額'] == 3, f'黨產會委員「三（六－八）」：專任 3 保留、括號 6–8 為兼任委員人數規模（審查指示），不計入專任：{bk["paren_evidence"]}')
    for n, lo, hi in [('核能安全委員會', 3, 5), ('中央選舉委員會', 7, 9)]:
        r = [p for p in P if p['機關'] == n and p['職稱'] == '委員'][0]; check(r['員額'] == 0 and r['paren_meaning'] == '兼任' and r['concurrent_min'] == lo and r['concurrent_max'] == hi, f'{n} 委員「({lo}~{hi})」：專任 0、兼任 {lo}–{hi} 保留供查照')
    hj = [p for p in P if p['機關'] == '海洋委員會海巡署' and p['序'] == 1][0]
    check(hj['paren_meaning'] == '兼任' and hj['concurrent_min'] == 1 and hj['員額'] == 0, '海巡署署長「（一）」＋備註兼任 → 兼任 1、專任 0')
    ya2 = [p for p in P if p['機關'] == '農業部農業藥物試驗所' and p['paren_min'] is not None]
    check(all(p['paren_meaning'] == '兼任' for p in ya2) and sum(p['concurrent_min'] for p in ya2) == 7 and by['農業部農業藥物試驗所']['指標']['員額合計'] == 79, '農藥所括號 3 列皆兼任（備註由研究員兼任）合計 7；專任 79 不變')
    unk = [p for p in P if p['paren_meaning'] == 'unknown']
    check(all(p['concurrent_min'] is None for p in unk) and all(p['員額'] == (p['專任_min'] if not p['專任_is_range'] else None) for p in unk if p['專任_min'] is not None), f'unknown 括號 {len(unk)} 列：concurrent 空、專任部分照常計入')
    check(all(p['兼任'] == (int(p['括號員額_兼任_原值']) if (p['括號員額_兼任_原值'] or '').isdigit() else None) for p in P), '既有「兼任」欄維持原值（只有阿拉伯數字原值可轉），未批次覆寫')
    nf = [p for p in P if p['職等'] and '\uf9d1' in p['職等']]
    check(len(nf) == 52 and all(p['職等_norm'] == p['職等'].replace('\uf9d1', '六') for p in nf), f'相容字 U+F9D1 列 {len(nf)}（另 1 列僅含全形括號相容字）：raw 不變、職等_norm 為 NFKC 副本')
    fp = [p for p in P if p['機關'] == '公平交易委員會' and p['職稱'] == '設計師'][0]
    check(fp['職等下限'] == 6 and fp['職等上限'] == 8 and '\uf9d1' in fp['職等'], f'公平會設計師：區間 {fp["職等下限"]}–{fp["職等上限"]}，raw 逐字不變')
    tr = [p for p in P if p['職等區間待審']]
    check(len(tr) == 4 and all(p['職等下限'] is None for p in tr), f'職等區間待審 {len(tr)} 列（截斷），下限上限留空不猜補：{[(p["機關"], p["序"]) for p in tr]}')
    fr = [p for p in P if p['列品質'] and p['列品質'].startswith('碎片列')]
    check(all(not p['計入'] and (p['員額'] is None or p['列品質'].startswith('碎片列（原表無法讀取')) for p in fr) and len(fr) > 0, f'碎片列 {len(fr)} 列：保留、不計入、員額皆空（原表無法讀取之殘留列除外）')
    wm = by['交通部公路局工程材料技術所']['指標']; check(wm['明細列數_有效'] == 15 and wm['員額合計'] == 39, f'工程材料技術所 有效列 {wm["明細列數_有效"]}、加總 {wm["員額合計"]}（碎片列不計入）')
    med = [p for p in P if p['機關'] == '臺北榮民總醫院' and p['職稱'] == '中醫師'][0]; check((med['列品質'] or '').startswith('合併計列（併入序') and med['員額'] is None and med['計入'], f'醫療合併計列「中醫師」標「{med["列品質"]}」、不拆分、員額仍空（總額不變）')
    mg = [p for p in P if (p['列品質'] or '').startswith('合併計列')]; check(all(p['員額'] is None and not p['員額原文'] for p in mg) and not any('推定' in p['列品質'] for p in mg), f'合併計列 {len(mg)} 列：員額與原文皆空、無推定列')
    hd = [p for p in P if p['列品質'] == '單位標題列']; check(len(hd) == 6 and all(not p['計入'] and p['員額'] is None for p in hd), f'單位標題列 {len(hd)} 列（東區養護 2、臺中區監理所 2、高雄市區監理所 1、高雄監獄 1）不計入')
    dq = [p for p in P if p['機關'] == '交通部公路局東區養護工程分局' and p['序'] in (20, 21, 22, 23)]; check(all(p['單位'] == '人事室' and p['單位_原值'] is None for p in dq), '東區養護工程分局 序20–23 承接單位標題列「人事室」（原值保留為空）')
    kg = [p for p in P if p['機關'] == '法務部矯正署高雄監獄' and p['序'] in (28, 29, 31)]; check(all(p['單位'] == '會計室' for p in kg), '高雄監獄 會計＋室 片段重組為會計室')
    yz = [p for p in P if p['機關'] == '內政部警政署鐵路警察局' and p['職稱'] in ('副局長', '秘書')]; check(all(p['員額'] == 1 and p['員額原文'] == 'ㄧ' for p in yz) and by['內政部警政署鐵路警察局']['驗算結果'] == '相符' and by['內政部警政署鐵路警察局']['指標']['員額合計'] == 924, '鐵路警察局：注音ㄧ 列回填 1、raw 原文不變、驗算相符 924')
    for r in A:  # 官等結構待審者：員額合計須與修改前相同（不得因排除異常列而少算）；員額不完整者：已知列小計 == 修改前加總（未另行刪減）
        if r['資料狀態'] == '待審（官等結構）':
            b = B[r['機關']]; check(r['指標']['員額合計'] == b['指標']['員額合計'], f'{r["機關"]} 員額合計 {r["指標"]["員額合計"]} 與修改前 {b["指標"]["員額合計"]} 相同（官等異常列員額仍計入）')
        if r['資料狀態'] == '待審（員額不完整）':
            b = B[r['機關']]; base = b['指標']['員額合計'] if b['指標']['員額合計'] is not None else b['指標'].get('已知列小計'); check(r['指標']['已知列小計'] == base, f'{r["機關"]} 已知列小計 {r["指標"]["已知列小計"]} == 修改前 {base}（只是改標示為不完整，未少算）')
    changed = []
    P1_KEYS = {'副首長兼任數', '首長兼任', '明細列數', '員額空白列數', '幕僚單位員額', '幕僚比', '兼任合計', '兼任合計_已判定', '兼任合計_min', '兼任合計_max', '括號待審列數', '合併計列數', '單位標題列數'}  # P1／規則修正：括號語意、合併計列、單位重組；其餘指標不得變動
    allowed |= {r['機關'] for r in A if any(x.startswith('人工補登') for x in r['品質註記'])} | {r['機關'] for r in A if r['指標'].get('法定員額_條文')}
    st = [r for r in A if r['指標'].get('法定員額_條文')]
    check(len(st) == 5 and all(r['資料狀態'] == '可用（條文區間）' and r['指標']['員額合計'] is None and r['指標']['員額合計_min'] == r['指標']['法定員額_條文']['專任下限'] and r['指標']['員額合計_max'] == r['指標']['法定員額_條文']['專任上限'] for r in st), f'法定員額（條文區間）機關 {len(st)} 個：員額合計空、區間＝條文專任下限／上限：{[(r["機關"], r["指標"]["員額合計_min"], r["指標"]["員額合計_max"]) for r in st]}')
    check(by['行政院公共工程委員會']['指標']['員額合計_min'] == 149 and by['行政院公共工程委員會']['指標']['員額合計_max'] == 199 and by['行政院公共工程委員會']['指標']['法定員額_條文']['聘用約僱上限'] == 40 and by['行政院公共工程委員會']['指標']['聘用約僱上限_條文'] == 40, '工程會：專任 149–199；聘用專業人員 35–40 另列（第14條），不入專任')
    check(by['臺灣警察專科學校']['指標']['法定員額_條文']['警備隊下限'] == 44 and by['臺灣警察專科學校']['指標']['法定員額_條文']['警備隊上限'] == 60 and all(not p['計入'] for p in P if p['機關'] == '臺灣警察專科學校' and p['法定類別'] == '警備隊'), '警專：警衛隊＋警察樂隊 44–60 獨立參考，不計入專任')
    hj = [p for p in P if p['機關'] == '法務部調查局' and p['職稱'] == '副處長'][0]; check(hj['員額'] == 0 and hj['paren_meaning'] == '兼任' and hj['concurrent_min'] == 30 and '15 人：得由專門委員兼任' in hj['備註'], f'調查局副處長：條文定由專門委員兼任 → 專任 0、兼任 30，其中條款保留：{hj["備註"][:60]}')
    cc = [r for r in A if r['指標'].get('聘用約僱條文')]; check(len(cc) == 12 and by['數位發展部']['指標']['聘用約僱上限_條文'] == 100 and by['經濟部']['指標']['聘用約僱上限_條文'] == 86, f'組織法規明定聘用／約僱人數之機關 {len(cc)} 個（數位部 100、經濟部 55–86…）')
    # 三項修正（基準 c29f5e7）
    mil = [r['機關'] for r in A if '軍事／國防' in (r.get('特殊類別') or [])]
    check(sorted(mil) == sorted(['國防部', '國防部政治作戰局', '國防部軍備局', '國防部主計局', '國防部軍醫局', '國防部全民防衛動員署', '國家軍事博物館籌備處']) and not any('退除役' in m for m in mil), f'軍事／國防以部會欄判定：{len(mil)} 個國防部系統機關，不含退輔會 53 個')
    check(all(r['特殊類別依據'] for r in A if r['特殊類別']) and all(r['部會'] == '國防部' for r in A if r['特殊類別']), '特殊類別皆附判定依據（部會欄）')
    bad = [(r['機關'], x) for r in A for x in (r['組織法規來源'] or []) if x['連結'] and ('；' in x['連結'] or not x['連結'].startswith('http') or x['連結'].count('http') != 1)]
    check(not bad and all(len(r['組織法規來源']) == len(str(r['組織法規名稱']).split('；')) for r in A if r['組織法規名稱']), f'法規來源一法規一 URL：585 機關結構掃描，異常 {len(bad)} 筆；名稱數＝來源數')
    check(sum(1 for r in A if r['法規連結待審']) == 0 and sum(1 for r in A if len(r['組織法規來源']) > 1) == 227, f'法規連結待審 {sum(1 for r in A if r["法規連結待審"])} 個；多法規機關 {sum(1 for r in A if len(r["組織法規來源"]) > 1)} 個（候選）')
    tc2 = by['衛生福利部臺中醫院']; check(tc2['編制表來源'].endswith('FileId=0000427371') and tc2['編制表來源_歷史'] and tc2['編制表來源_歷史']['連結'].endswith('FileId=0000368769') and '115 年 10 月 30 日' in tc2['編制表來源_現行說明'] and tc2['指標']['員額合計'] == 217, '臺中醫院：編制表來源改為新附件 0000427371（115-10-30 版），舊 0000368769 為歷史被取代來源；217 不變')
    check(by['衛生福利部恆春旅遊醫院']['編制表來源'].endswith('FileId=0000368778') and by['衛生福利部恆春旅遊醫院']['編制表來源_歷史'] is None and by['衛生福利部恆春旅遊醫院']['指標']['員額合計'] == 94, '恆春：來源不變（0000368778）、94 不變')
    check(by['農業部農業藥物試驗所']['指標']['員額合計'] == 79 and by['財政部']['指標']['員額合計'] == 213 and by['臺北榮民總醫院玉里分院']['指標']['員額合計'] == 465, '回歸：農藥所 79、財政部 213、玉里 465')
    check(by['最高檢察署']['資料狀態'] == '可用（區間）' and by['最高檢察署']['驗算結果'] == '員額表區間' and by['最高檢察署']['指標']['員額合計_min'] == 107 and by['最高檢察署']['指標']['員額合計_max'] == 202 and by['最高檢察署']['可比較'], '最高檢察署：法院組織法第75條附表員額表 107–202（法務部網站整合檔），區間、可比較')
    check(by['臺灣高等檢察署']['指標']['員額合計_min'] == 742 and by['臺灣高等檢察署']['指標']['員額合計_max'] == 1407 and by['臺灣高等檢察署']['可比較'] and not any('類別待確認' in x for x in by['臺灣高等檢察署']['品質註記']), '臺灣高等檢察署：第74條附表第一類 742–1407，審查確認第一類 → 可比較')
    check(by['駐外機構']['資料狀態'] == '不適用（依審查指示排除）' and not by['駐外機構']['可比較'] and any(x.startswith('依審查指示排除') for x in by['駐外機構']['品質註記']), '駐外機構：依審查指示列不適用（通則僅為設置標準、無固定員額、多屬密件），保留註記')
    allowed |= {p['機關'] for p in P if p['單位重組說明'] or p['列品質'] == '單位標題列'} | {r['機關'] for r in A if any(x.startswith('員額回填') for x in r['品質註記'])} | {p['機關'] for p in P if '内' in (p['備註'] or '') or '\u3127' in (p['備註'] or '')}
    FRAG_KEYS = {'首長職稱', '首長職等', '副首長職稱', '副首長數', '員額空白列數'}  # 碎片列（表頭殘留等）排除後，首長判定與空白列數預期變動
    frag_ag = {r['機關'] for r in A if r['指標'].get('碎片列數')}
    for r in A:
        b = B[r['機關']]
        for k, v in r['指標'].items():
            if k in b['指標'] and b['指標'][k] != v and r['機關'] not in allowed and k not in P1_KEYS and not (r['機關'] in frag_ag and k in FRAG_KEYS):
                changed.append((r['機關'], k, b['指標'][k], v))
    frag_changes = [(r['機關'], k, B[r['機關']]['指標'][k], v) for r in A if r['機關'] in frag_ag for k, v in r['指標'].items() if k in FRAG_KEYS and k in B[r['機關']]['指標'] and B[r['機關']]['指標'][k] != v]
    notes.append(f'INFO 碎片列排除後的預期變動 {len(frag_changes)} 筆（首長判定／空白列數）：' + '；'.join(f'{a} {k} {x}→{y}' for a, k, x, y in frag_changes))
    check(not changed, f'回歸：允許清單外的機關指標無變動（變動 {len(changed)} 筆）' + ('' if not changed else '：' + str(changed[:5])))
    diffs = []
    for r in A:
        b = B[r['機關']]
        if b['指標']['員額合計'] != r['指標']['員額合計']: diffs.append((r['機關'], b['指標']['員額合計'], r['指標']['員額合計']))
    notes.append('INFO 員額合計前後差異：' + '；'.join(f'{n} {x}→{y}' for n, x, y in diffs))

print('\n'.join(notes)); print('\n'.join(fails))
print(f'\n結果：PASS {len(notes)}、FAIL {len(fails)}')
sys.exit(1 if fails else 0)

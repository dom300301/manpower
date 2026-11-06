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
unknown = [r for r in A if r['指標']['員額合計'] is None]
untaken = [r for r in unknown if r['資料狀態'].startswith('未取得')]
pending = [r for r in unknown if r['資料狀態'].startswith('待審')]
check(len(untaken) == 16, f'「未取得」機關數 = {len(untaken)}（本次診斷 16）')
check(len(unknown) == len(untaken) + len(pending) and all(r['資料狀態'] != '可用' for r in unknown), f'null 機關 = 未取得 {len(untaken)} + 待審 {len(pending)}（{[r["機關"] for r in pending]}）')
check(all(r['指標']['員額合計'] != 0 for r in A), '沒有任何機關的員額合計被寫成 0')
check(by['財政部']['指標']['員額合計'] is None and by['財政部']['資料狀態'] == '未取得（需人工輸入）', '財政部員額合計 null、資料狀態=未取得（需人工輸入）')
for r in unknown:
    check(all(r['指標'][k] is None for k in ['簡任員額', '薦任員額', '委任員額', '主管員額', '簡任非主管比']), f'{r["機關"]} 其他人數類指標亦為 null')
    check(not r['可比較'], f'{r["機關"]} 不可比較')
basis = [r for r in unknown if r['法定員額依據']]
basis_yes = [r for r in untaken if r['法定員額依據'] and r['法定員額依據']['有']]
basis_no = [r for r in untaken if r['法定員額依據'] and not r['法定員額依據']['有']]
check(len(basis_yes) == 5 and by['行政院公共工程委員會']['法定員額依據']['條號'].startswith('第8條'), f'法定員額依據「有」{len(basis_yes)} 個：{[r["機關"] for r in basis_yes]}')
check(len(basis_no) == 7 and all('未列可結構化員額' in r['法定員額依據']['說明'] or '共用法規' in r['法定員額依據']['說明'] for r in basis_no), f'法定員額依據「無」{len(basis_no)} 個並明示原因：{[r["機關"] for r in basis_no]}')
check(all('headcount' not in json.dumps(r['法定員額依據'] or {}) for r in untaken), '未產生區間 min/max 總額')
# 僅兼任列保留專任 0，但整機關未知不得為 0（鐵道局北部：單列無數字 → 未取得）
check(by['交通部鐵道局北部工程分局']['指標']['員額合計'] is None, '鐵道局北部工程分局（明細僅一列無數字）為未取得，不是 0')

# P0-B 品質旗標
mixed = [r for r in A if 'Codex抽樣不一致' in r['品質註記']]
check(len(mixed) == 14 and all(not r['可比較'] for r in mixed), f'Codex抽樣不一致 {len(mixed)} 個機關全部不可比較（12 相符混合 + 工程材料技術所 + 疾管署）')
check(not by['教育部']['可比較'] and by['教育部']['驗算結果'] == '相符', '教育部：驗算結果相符但品質註記 Codex → 不可比較')
dept_group = [r['機關'] for r in A if r['層級'] == 2 and r['類型'] == '部' and r['可比較']]
check('教育部' not in dept_group and '財政部' not in dept_group and '農業部' in dept_group, f'農業部預設部級群組不含教育部、財政部：{dept_group}')
check(all(r['驗算結果'] in ('相符', '不相符', '找不到合計', '需人工輸入', '無編制表') for r in A), '驗算結果皆為列舉值')
check(all(isinstance(r['可比較'], bool) for r in A), '可比較為布林')
check(all(r['可比較'] == (r['驗算結果'] == '相符' and r['資料狀態'] == '可用' and all(x in {'人工補登（已對源）', '表內驗算相符（合計取自明細控制列）', '警示：頁眉'} for x in r['品質註記']) and not r['來源核對狀態'].startswith('官方合計待核')) for r in A), '可比較 == 規則重算結果（驗算相符 ∧ 可用 ∧ 註記皆白名單 ∧ 非官方合計待核）')
pg = by['行政院人事行政總處公務人力發展學院']
check(pg['可比較'] and '人工補登（已對源）' in pg['品質註記'] and pg['指標']['員額合計'] == 91, '公務人力發展學院：人工補登有來源／頁碼／對源且驗算相符 → 可比較')
n_flag = sum(1 for r in A if not r['可比較'])
notes.append(f'INFO 不可比較機關數 = {n_flag}（由修正後資料推導，不設固定目標；舊快照 31+12=43 僅供參考）')
# 官等異常：全庫不得有未標記的異常官等列計入
ab = [p for p in P if p['列品質'] == '官等異常']
check(all(not p['計入'] for p in ab), f'官等異常列 {len(ab)} 列均不計入（機關：{sorted(set(p["機關"] for p in ab))}）')
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
check(not tc['可比較'] and tc['來源核對狀態'].startswith('官方合計待核') and '表內驗算相符（合計取自明細控制列）' in tc['品質註記'], '臺中醫院：表內驗算相符但官方合計待核 → 不可比較')
check(hc['可比較'] and hc['來源核對狀態'].startswith('官方PDF核對一致'), '恆春旅遊醫院：官方 PDF 11/06 重抓核對一致 → 可比較')
check(all('官方來源已核實' not in x for r in A for x in r['品質註記']), '品質註記不出現「官方來源已核實」字樣（表內驗算與來源核對分開）')

# 全庫守恆
for r in A:
    m = r['指標']
    if m['員額合計'] is None: continue
    check(m['簡任員額'] + m['薦任員額'] + m['委任員額'] + m['其他官等員額'] == m['員額合計'], f'{r["機關"]} 官等加總 == 員額合計') if (m['簡任員額'] + m['薦任員額'] + m['委任員額'] + m['其他官等員額'] != m['員額合計']) else None
notes.append('PASS 全庫官等加總守恆（簡＋薦＋委＋其他 == 員額合計，null 機關跳過）' if not any('官等加總' in f for f in fails) else 'FAIL 守恆')

# 回歸：與修改前比較
if a.before:
    B = {r['機關']: r for r in json.load(open(f'{a.before}/agencies.json', encoding='utf-8'))['agencies']}
    allowed = {r['機關'] for r in unknown} | {'衛生福利部臺中醫院', '衛生福利部恆春旅遊醫院', '農業部農業藥物試驗所'} | {p['機關'] for p in P if p['列品質'] in ('官等異常', '錯位', '疑似控制列')}
    changed = []
    for r in A:
        b = B[r['機關']]
        for k, v in r['指標'].items():
            if k in b['指標'] and b['指標'][k] != v and r['機關'] not in allowed:
                changed.append((r['機關'], k, b['指標'][k], v))
    check(not changed, f'回歸：允許清單外的機關指標無變動（變動 {len(changed)} 筆）' + ('' if not changed else '：' + str(changed[:5])))
    diffs = []
    for r in A:
        b = B[r['機關']]
        if b['指標']['員額合計'] != r['指標']['員額合計']: diffs.append((r['機關'], b['指標']['員額合計'], r['指標']['員額合計']))
    notes.append('INFO 員額合計前後差異：' + '；'.join(f'{n} {x}→{y}' for n, x, y in diffs))

print('\n'.join(notes)); print('\n'.join(fails))
print(f'\n結果：PASS {len(notes)}、FAIL {len(fails)}')
sys.exit(1 if fails else 0)

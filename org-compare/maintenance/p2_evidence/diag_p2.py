import json, re, collections, sys, unicodedata
import pandas as pd
S = '/tmp/claude-0/-home-user-manpower/4c1fe7a7-cb5e-55f8-b5c1-b63a2b48cd38/scratchpad'
R = '/home/user/manpower/org-compare'
OUT = f'{S}/diag/p2'
import os; os.makedirs(OUT, exist_ok=True)
A = json.load(open(f'{S}/diag/after/agencies.json', encoding='utf-8'))['agencies']
AG = {a['機關']: a for a in A}
P = json.load(open(f'{S}/diag/after/positions.json', encoding='utf-8'))
MGR_RE = re.compile(r'(?:主任秘書|署長|局長|處長|所長|館長|院長|場長|校長|主任|秘書長|組長|科長|課長|股長|隊長|總隊長|分隊長|中隊長|大隊長|典獄長|分署長|分局長|司長|主計長|人事長|委員長|中心主任|室主任|站長|廠長|園長|所長|主席|行長|總裁|執行長)$')
rep = []
def H(t): rep.append('\n' + t + '\n')
def T(rows, hdr):
    rep.append('| ' + ' | '.join(hdr) + ' |'); rep.append('|' + '---|' * len(hdr))
    for r in rows: rep.append('| ' + ' | '.join('' if v is None else str(v) for v in r) + ' |')

# ---------------- 1. 主管指標 ----------------
H('## 1. 主管指標是否漏列首長、副首長')
byag = collections.defaultdict(list)
for p in P: byag[p['機關']].append(p)
head_not_mgr, dep_not_mgr, dep_mgr, head_mgr = [], [], [], []
head_titles = collections.Counter(); dep_titles_c = collections.Counter()
for n, rows in byag.items():
    a = AG[n]; ht = a['指標'].get('首長職稱'); dts = (a['指標'].get('副首長職稱') or '')
    for p in rows:
        if not p['計入']: continue
        if p.get('首長'):
            head_titles[(p['職稱'], p['主管'])] += 1
            (head_mgr if p['主管'] else head_not_mgr).append((n, p['序'], p['職稱'], p['員額']))
        elif p['職稱'] in dts.split('、') and not p['單位'] and dts and '（無）' not in dts:
            dep_titles_c[(p['職稱'], p['主管'])] += 1
            (dep_mgr if p['主管'] else dep_not_mgr).append((n, p['序'], p['職稱'], p['員額']))
rep.append(f'現行規則：`主管` = 職稱符合 MGR_RE（以「…長／主任／主席／總裁／執行長」等結尾），不含「首長」「副首長」判定；`主管員額` = 計入列中 主管=True 之員額加總；`主管比` = 主管員額／員額合計。')
rep.append(f'- 首長列（首長=True）被判為主管：{len(head_mgr)} 列；未判為主管：{len(head_not_mgr)} 列。')
rep.append(f'- 副首長列（職稱屬副首長職稱、無單位）被判為主管：{len(dep_mgr)} 列；未判為主管：{len(dep_not_mgr)} 列。')
rep.append('\n首長職稱 × 是否判為主管（列數）：')
T([(t, '是' if m else '否', c) for (t, m), c in head_titles.most_common()], ['首長職稱', '現行判為主管', '列數'])
rep.append('\n副首長職稱 × 是否判為主管（列數）：')
T([(t, '是' if m else '否', c) for (t, m), c in dep_titles_c.most_common()], ['副首長職稱', '現行判為主管', '列數'])
rep.append('\n首長未判為主管之機關（受影響清單，節錄前 40；完整見 p2_1_首長未判主管.csv）：')
T(head_not_mgr[:40], ['機關', '序', '職稱', '員額'])
pd.DataFrame(head_not_mgr, columns=['機關', '序', '職稱', '員額']).to_csv(f'{OUT}/p2_1_首長未判主管.csv', index=False)
pd.DataFrame(dep_not_mgr, columns=['機關', '序', '職稱', '員額']).to_csv(f'{OUT}/p2_1_副首長未判主管.csv', index=False)
# 非首長、非副首長但被 MGR_RE 以「副」職稱判為主管的列
vice = [(n, p['序'], p['職稱'], p['員額']) for n, rows in byag.items() for p in rows if p['計入'] and p['主管'] and p['職稱'].startswith('副')]
rep.append(f'\n職稱以「副」開頭卻因字尾（副署長→署長、副組長→組長…）被判為主管者：{len(vice)} 列（副首長 {len(dep_mgr)} 列 + 副單位主管 {len(vice)-len(dep_mgr)} 列）。職稱別：')
T(collections.Counter(v[2] for v in vice).most_common(25), ['職稱', '列數'])
# 預期差異：規則 R2 = 現行 + 首長 + 副首長
diff = []
for n, rows in byag.items():
    a = AG[n]
    if a['指標'].get('主管員額') is None: continue
    add = sum((p['員額'] or 0) for p in rows if p['計入'] and not p['主管'] and (p.get('首長') or (p['職稱'] in (a['指標'].get('副首長職稱') or '').split('、') and not p['單位'])))
    if add: diff.append((n, a['指標']['主管員額'], a['指標']['主管員額'] + add, a['指標'].get('主管比')))
rep.append(f'\n若採「主管員額 = 現行 + 首長列 + 副首長列」，主管員額改變之機關：{len(diff)} 個（完整見 p2_1_預期差異.csv；前 20）：')
T(diff[:20], ['機關', '現行主管員額', '擬改後', '現行主管比'])
pd.DataFrame(diff, columns=['機關', '現行主管員額', '擬改後', '現行主管比']).to_csv(f'{OUT}/p2_1_預期差異.csv', index=False)

# ---------------- 2. 軍事／國防 ----------------
H('## 2. 「軍事／國防」排除規則')
mil = [a for a in A if re.search(r'國防部|軍', a['機關']) and not re.search(r'國防部$', a['機關'])]
rep.append(f'現行規則（org_template.html 第 217 行）：`/國防部|軍/.test(機關) && !/國防部$/.test(機關)`。命中 {len(mil)} 個機關：')
T([(a['機關'], a.get('部會'), a.get('層級'), a['指標'].get('員額合計'), '含「軍」但非國防部' if '國防部' not in a['機關'] else '國防部所屬') for a in mil], ['機關', '部會', '層級', '員額合計', '命中原因'])
vac = [a['機關'] for a in A if a.get('部會') == '國軍退除役官兵輔導委員會' or a['機關'].startswith('國軍退除役官兵輔導委員會')]
rep.append(f'\n退輔會系統機關共 {len(vac)} 個，其中被規則命中 {sum(1 for a in mil if a["機關"] in vac)} 個。')
nd = [a['機關'] for a in A if a.get('部會') == '國防部' or a['機關'].startswith('國防部')]
rep.append(f'國防部系統機關共 {len(nd)} 個（{"、".join(nd)}）。')
# 候選規則：依部會欄或官等欄位證據（軍階）
mil_rank = collections.Counter()
for p in P:
    if re.search(r'將|校|尉|士官|軍', (p['官等'] or '')): mil_rank[p['機關']] += 1
rep.append(f'明細「官等」含軍階字（將／校／尉／士官／軍）之機關：{len(mil_rank)} 個：' + '、'.join(f'{k}（{v} 列）' for k, v in mil_rank.most_common()))

# ---------------- 3. 得列人數 ----------------
H('## 3. 「得列人數」說明與計算是否一致')
rep.append('現行三種計算：')
rep.append('- `得列簡任`（列層級）：備註 `(?:內|其中)N人得列簡任`，僅官等非簡任之列，並以該列員額為上限（cap）。')
rep.append('- `得列薦任`（列層級）：備註 `(?:內|其中)N人得列薦任`，僅官等為「委任」之列，cap 同上。')
rep.append('- `得列人數`（機關層級）：全機關備註串接後以 `內N人得列` 取 N 加總；不含「其中」寫法、不設 cap、不分官等。說明文字「備註『內 N 人得列…』的 N 加總」。')
pat_all = re.compile(r'得列')
kinds = collections.Counter(); rows_d = []
for p in P:
    b = p['備註'] or ''
    if '得列' not in b: continue
    forms = re.findall(r'((?:內|其中)?[一二三四五六七八九十○〇百0-9]*人?得列[^，。；、）)]{0,8})', b)
    for f in forms: kinds[re.sub(r'[一二三四五六七八九十○〇百0-9]+', 'N', f)] += 1
    rows_d.append(p)
rep.append(f'\n備註含「得列」之列：{len(rows_d)} 列、{len(set(p["機關"] for p in rows_d))} 個機關。寫法型態（數字以 N 取代）：')
T(kinds.most_common(40), ['寫法', '列數'])
# 不一致清單
inc = []
for a in A:
    m = a['指標']
    if m.get('得列人數') is None: continue
    s = (m.get('得列簡任人數') or 0) + (m.get('得列薦任人數') or 0)
    if s != m['得列人數']:
        rs = [p for p in byag[a['機關']] if '得列' in (p['備註'] or '')]
        why = set()
        for p in rs:
            b = p['備註']
            if '其中' in b and '得列' in b: why.add('「其中」寫法只入列層級')
            if p['簡任'] and re.search(r'得列簡任', b): why.add('簡任列之得列簡任歸零')
            if (p['官等'] or '') != '委任' and re.search(r'得列薦任', b): why.add('非委任列之得列薦任歸零')
            if re.search(r'得列(?!簡任|薦任)', b): why.add('得列其他（非簡任／薦任）')
            nn = sum(int(x) for x in [str(cn) for cn in []]) if False else None
            ns = [t for t in re.findall(r'(?:內|其中)([一二三四五六七八九十○〇百]+)人得列', b)]
            if p['員額'] is not None and ns:
                from build_dataset import cn2n
                if sum((cn2n(t) or 0) for t in ns) > p['員額']: why.add('N 超過該列員額（cap）')
        inc.append((a['機關'], m['得列人數'], m.get('得列簡任人數'), m.get('得列薦任人數'), '；'.join(sorted(why)) or '待查'))
rep.append(f'\n`得列人數` ≠ `得列簡任人數`＋`得列薦任人數` 之機關：{len(inc)} 個（完整見 p2_3_得列不一致.csv；前 30）：')
T(inc[:30], ['機關', '得列人數', '得列簡任人數', '得列薦任人數', '原因（程式層）'])
pd.DataFrame(inc, columns=['機關', '得列人數', '得列簡任人數', '得列薦任人數', '原因']).to_csv(f'{OUT}/p2_3_得列不一致.csv', index=False)
both = [(p['機關'], p['序'], p['職稱'], p['官等'], p['員額'], p['備註']) for p in rows_d if re.search(r'得列簡任', p['備註']) and re.search(r'得列薦任', p['備註'])]
rep.append(f'\n同一列備註同時含「得列簡任」與「得列薦任」（重疊可能）：{len(both)} 列：')
T(both[:20], ['機關', '序', '職稱', '官等', '員額', '備註'])
ov = [(p['機關'], p['序'], p['職稱'], p['官等'], p['員額'], p['得列簡任'], p['得列薦任']) for p in P if (p.get('得列簡任') or 0) > 0 and (p.get('得列薦任') or 0) > 0]
rep.append(f'現行程式同一列 得列簡任>0 且 得列薦任>0：{len(ov)} 列（程式以官等互斥，委任列不可能得列簡任，故為 0 是規則結果，不是證實互斥）。')
rep.append(f'備註「得列簡任」出現於官等含簡任之列（被歸零）：{sum(1 for p in rows_d if p["簡任"] and "得列簡任" in p["備註"])} 列；「得列薦任」出現於非委任列（被歸零）：{sum(1 for p in rows_d if (p['官等'] or '') != '委任' and '得列薦任' in p['備註'])} 列。')

# ---------------- 4. 條文有、機關清單無 ----------------
H('## 4. 有條文但機關清單無入口')
X = pd.ExcelFile(f'{R}/data/組織法編制表_總表_20261031.xlsx')
ov = X.parse('機關總覽', dtype=str); art = X.parse('條文', dtype=str); exc = X.parse('例外', dtype=str); oth = X.parse('其他', dtype=str)
names = set(ov['機關']); art_ag = art.groupby('機關').agg(法規=('法規名稱', lambda s: '；'.join(sorted(set(s)))), 條數=('條號', 'size'), 類別=('法規類別', lambda s: '；'.join(sorted(set(s))))).reset_index()
missing = art_ag[~art_ag['機關'].isin(names)].copy()
def norm(s): return unicodedata.normalize('NFKC', str(s)).replace('台', '臺').replace(' ', '')
nn = {norm(x): x for x in names}
chlaw = {l['LawName']: l for l in json.load(open(f'{S}/moj/chlaw/ChLaw.json', encoding='utf-8-sig'))['Laws']}
chord = {l['LawName']: l for l in json.load(open(f'{S}/moj/chorder/ChOrder.json', encoding='utf-8-sig'))['Laws']}
def lawinfo(name):
    l = chlaw.get(name) or chord.get(name)
    return (l['LawAbandonNote'], l['LawCategory'], l['LawModifiedDate']) if l else (None, None, None)
cls = []
for _, r in missing.iterrows():
    n = r['機關']; laws = r['法規'].split('；')
    infos = [lawinfo(x) for x in laws]
    if norm(n) in nn: c = '名稱對應（NFKC／臺台）→ ' + nn[norm(n)]
    elif any(k in r['法規'] for k in ('通則', '準則', '各')): c = '共用法規（通則／準則／各…）'
    elif any(i[0] == '廢' or (i[1] or '').startswith('廢止') for i in infos): c = '歷史機關（法規資料庫標廢止）'
    elif n in set(exc['推定機關名稱']): c = '例外表已列（' + exc[exc['推定機關名稱'] == n]['狀態'].iloc[0] + '）'
    elif n in set(oth['機關名稱']): c = '其他表已列（' + oth[oth['機關名稱'] == n]['類別'].iloc[0] + '）'
    elif any('組織' not in x for x in laws) and all('組織' not in x for x in laws): c = '非組織法規（辦事細則等）'
    else: c = '待查（可能真正缺漏）'
    cls.append((n, r['法規'][:60], r['條數'], r['類別'], '；'.join(str(i[0] or '') for i in infos), c))
rep.append(f'條文表機關數 {art_ag.shape[0]}，其中不在機關總覽（585）者 {len(missing)} 個。分類（依名稱正規化、法規名稱、法規資料庫廢止註記、例外表／其他表）：')
T(collections.Counter(c[5].split('→')[0] for c in cls).most_common(), ['分類', '機關數'])
rep.append('\n清單（完整見 p2_4_條文無入口.csv；前 40）：')
T(cls[:40], ['條文機關', '法規名稱', '條數', '類別', '廢止註記', '分類'])
pd.DataFrame(cls, columns=['條文機關', '法規名稱', '條數', '類別', '廢止註記', '分類']).to_csv(f'{OUT}/p2_4_條文無入口.csv', index=False)
noart = [n for n in names if n not in set(art['機關'])]
rep.append(f'\n反向：機關總覽有、條文表無任何條文之機關 {len(noart)} 個：' + '、'.join(noart[:30]) + ('…' if len(noart) > 30 else ''))
rep.append(f'例外表 199 列狀態分布：' + '、'.join(f'{k} {v}' for k, v in exc['狀態'].value_counts().items()))

# ---------------- 5. 組織法 vs 組織條例 ----------------
H('## 5. 同時存在組織法與組織條例的機關')
org = art[art['法規類別'] == '組織法規'].groupby('機關')['法規名稱'].agg(lambda s: sorted(set(s))).reset_index()
multi = org[org['法規名稱'].apply(len) > 1]
def hist_last(l):
    h = (l or {}).get('LawHistories', '') if l else ''
    lines = [x.strip() for x in h.replace('\r', '').split('\n') if x.strip()]
    return lines[-1][:70] if lines else ''
rows5 = []
for _, r in multi.iterrows():
    for ln in r['法規名稱']:
        l = chlaw.get(ln) or chord.get(ln)
        ovn = ov[ov['機關'] == r['機關']]['組織法規名稱'].iloc[0] if (ov['機關'] == r['機關']).any() else ''
        rows5.append((r['機關'], ln, '法律' if ln in chlaw else ('命令' if ln in chord else '不在開放資料'), l['LawModifiedDate'] if l else '', l['LawEffectiveDate'] if l else '', (l['LawEffectiveNote'] or '')[:40] if l else '', l['LawAbandonNote'] if l else '', (l['LawCategory'] or '') if l else '', hist_last(l), '是' if ln == ovn else ''))
rep.append(f'條文表中同一機關掛有 ≥2 部「組織法規」者：{len(multi)} 個機關、{len(rows5)} 部法規。開放資料欄位對照（LawModifiedDate＝最新異動（修正）日；LawEffectiveDate／Note＝施行日（多為空白，施行日在 LawHistories 末筆）；LawAbandonNote＝廢止註記）：')
T(rows5, ['機關', '法規名稱', '層級', '最新異動日', '施行日欄', '施行註記', '廢止註記', '法規分類', '沿革末筆', '總覽採用'])
pd.DataFrame(rows5, columns=['機關', '法規名稱', '層級', '最新異動日', '施行日欄', '施行註記', '廢止註記', '法規分類', '沿革末筆', '總覽採用']).to_csv(f'{OUT}/p2_5_組織法條例並存.csv', index=False)
rep.append(f'\n現行程式使用：`組織法規最新異動日` 取條文表該機關組織法規之 `最新異動日` 第一筆（不分部法）；狀態頁／詳情未標示「現行」字樣者：程式中「現行」出現次數見下。')
# 現行 wording usage
cnt = 0
for f in ['build_dataset.py', 'org_template.html', 'build_org_search.py']:
    t = open(f'{R}/{f}', encoding='utf-8').read(); c = t.count('現行'); cnt += c; rep.append(f'- `{f}`：「現行」{c} 處')
# 施行日 for the 法律 set with 施行註記
eff = sum(1 for r in rows5 if r[4] or r[5])
rep.append(f'上表 {len(rows5)} 部法規中開放資料有施行日欄或施行註記者 {eff} 部；其餘施行日只能自 LawHistories 沿革文字解析或查公報，未核實前不得標「現行」。')

# ---------------- 證據待補 ----------------
H('## 6. 證據待補（P1 未獨立驗證項目）')
med = [p for p in P if p['員額'] is None and not p['員額原文'] and not p['列品質'] and p['計入']]
rep.append(f'- 醫療／矯正合併計算列：P1 報告引用 P1 診斷計畫之估計 852 列／123 機關，未在 P1 測試中逐列驗證。本批重算「計入、員額空、員額原文空、無列品質標記」之列：{len(med)} 列、{len(set(p["機關"] for p in med))} 個機關（與 852 不一致，需以明確規則（職稱＋上一列員額共用）重新定義並出清單）。')
rep.append('- grade-check：P1 報告稱「572 列逐列相同」，依據為同一總表重跑 check_grades.py 的輸出比對（diag/grade vs diag/grade2），但該比對未納入測試檔、未留 SHA；需補：兩次輸出之檔案 SHA-256、差異筆數 0 之腳本紀錄，並確認 grade-check 讀取欄位（職稱、官等、職等）不受 build_dataset 之 NFKC 副本影響（它直接讀 Excel，獨立於 agencies.json）。')
open(f'{OUT}/p2_evidence.md', 'w', encoding='utf-8').write('\n'.join(rep))
print('written', OUT)

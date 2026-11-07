import json, re, collections, csv, os
import pandas as pd
S = '/tmp/claude-0/-home-user-manpower/4c1fe7a7-cb5e-55f8-b5c1-b63a2b48cd38/scratchpad'
R = '/home/user/manpower/org-compare'
OUT = f'{S}/diag/p2b'; os.makedirs(OUT, exist_ok=True)
A = {a['機關']: a for a in json.load(open(f'{S}/diag/after/agencies.json', encoding='utf-8'))['agencies']}
P = json.load(open(f'{S}/diag/after/positions.json', encoding='utf-8'))
P0 = json.load(open(f'{S}/diag/before_p1/positions.json', encoding='utf-8'))
X = pd.ExcelFile(f'{R}/data/組織法編制表_總表_20261031.xlsx')
ov = X.parse('機關總覽', dtype=str); art = X.parse('條文', dtype=str); oth = X.parse('其他', dtype=str); fa = X.parse('行政法人', dtype=str)
def W(name, hdr, rows):
    with open(f'{OUT}/{name}', 'w', newline='', encoding='utf-8-sig') as f: csv.writer(f).writerows([hdr] + rows)
    print(name, len(rows))
log = {}

# ===== A. 共用法規掛接 492 筆逐筆判定 =====
org = art[art['法規類別'] == '組織法規']
first_law = org.groupby('機關')['法規名稱'].first()
ovlaw = ov.set_index('機關')['組織法規名稱'].fillna('')
scope_re = re.compile(r'特設(?:所屬)?(?:各)?(?:區)?([^，。（(、]{1,12}?)(?:（|,|，|。|$)')
rows = []
for (ag, law), _ in org.groupby(['機關', '法規名稱']):
    m = re.search(r'(?:各區|各|所屬|附屬)(.+?)組織(準則|通則)$', law)
    if not m: continue
    a1 = org[(org['法規名稱'] == law) & (org['條號'] == '第1條')]['條文內容']
    a1 = a1.iloc[0] if len(a1) else ''
    sm = scope_re.search(a1.replace('\n', ''))
    scope = sm.group(1) if sm else ''
    kind = m.group(1)
    in_ov = law in ovlaw.get(ag, '')
    name_ok = any(k and k in ag for k in [kind, re.sub(r'^(公路|氣象|農業|榮民|榮譽)', '', kind), kind[-3:], kind[-2:]])
    scope_ok = bool(scope) and (scope[-2:] in ag or scope in ag)
    a = A.get(ag, {})
    affected = []
    if first_law.get(ag) == law: affected.append('組織法規最新異動日（本法為該機關第一筆）')
    if a.get('資料狀態', '').startswith('未取得（無編制表）'): affected.append('法定員額依據（無編制表機關）')
    if org[(org['法規名稱'] == law) & (org['條文內容'].fillna('').str.contains('掌理'))].shape[0]: affected.append('掌理事項（詳情頁業務關鍵字）')
    if in_ov: concl = '維持（總覽組織法規名稱列有本法）'
    elif name_ok or scope_ok: concl = '待審（總覽未列本法；名稱或適用範圍相符）'
    else: concl = '待審（總覽未列本法；名稱與適用範圍皆不符）'
    rows.append((ag, law, kind, scope, '是' if in_ov else '否', '是' if name_ok else '否', '是' if scope_ok else '否', concl, '；'.join(affected) or '無（非第一筆、有編制表、無掌理條）', ov[ov['機關'] == ag]['組織法規連結'].iloc[0] if (ov['機關'] == ag).any() else ''))
W('p2b_1_共用法規掛接全清單.csv', ['機關', '法規名稱', '準則所指類型', '第1條適用範圍（特設…）', '總覽組織法規名稱列有本法', '名稱型別相符', '適用範圍相符', '判定結論', '受影響欄位', '總覽組織法規連結'], rows)
c = collections.Counter(r[7] for r in rows); log['A'] = dict(c)
print(c)
sus = [r for r in rows if r[7].startswith('待審')]
print('待審機關數', len({r[0] for r in sus}), '法規數', len({r[1] for r in sus}))
print('受影響欄位分布', collections.Counter(x for r in sus for x in r[8].split('；')))
# 252 heuristic set vs new set
old = {(r['機關'], r['法規名稱']) for r in csv.DictReader(open(f'{S}/diag/p2/p2_4_共用法規疑似誤掛.csv', encoding='utf-8'))}
new = {(r[0], r[1]) for r in sus}
print('252 啟發式 ∩ 新待審', len(old & new), '| 啟發式有、新規則維持', len(old - new), '| 新規則待審、啟發式無', len(new - old))
W('p2b_1_啟發式252對照.csv', ['機關', '法規名稱', '啟發式252', '本輪判定'], [(r[0], r[1], '是' if (r[0], r[1]) in old else '否', r[7]) for r in rows if (r[0], r[1]) in old or r[7].startswith('待審')])

# ===== B. 主管四分項（互斥） =====
MGR_RE = re.compile(r'(?:主任秘書|署長|局長|處長|所長|館長|院長|場長|校長|主任|秘書長|組長|科長|課長|股長|隊長|總隊長|分隊長|中隊長|大隊長|典獄長|分署長|分局長|司長|主計長|人事長|委員長|中心主任|室主任|站長|廠長|園長|所長|主席|行長|總裁|執行長)$')
by = collections.defaultdict(list)
for p in P: by[p['機關']].append(p)
cls_rows = []; agg = []
for ag, rs in by.items():
    m = A[ag]['指標']; ht = m.get('首長職稱'); dts = m.get('副首長職稱') or ''
    dts = [] if '（無）' in dts else [d for d in dts.split('、') if d]
    rs = sorted(rs, key=lambda p: p['序']); first = next((p for p in rs if p['計入']), None)
    cnt = collections.Counter(); hc = collections.Counter()
    for p in rs:
        if not p['計入']: continue
        t = p['職稱']; u = p['單位']
        if first is p and t == ht: k, basis = '首長', '序最小之計入列且職稱＝首長職稱（HEAD_RE）'
        elif t in dts and not u: k, basis = '副首長', '職稱屬 DEPUTY_MAP[首長職稱] 且單位空白'
        elif t == '主任秘書' and not u: k, basis = '幕僚長', '職稱＝主任秘書且單位空白'
        elif u and t.startswith('副') and MGR_RE.search(t): k, basis = '單位副主管', '有單位、職稱以副開頭、字尾屬主管職稱'
        elif u and MGR_RE.search(t): k, basis = '單位主管', '有單位、字尾屬主管職稱、非副'
        elif not u and MGR_RE.search(t): k, basis = '無單位之主管職稱', '單位空白但字尾屬主管職稱（非首長副首長）→ 待審'
        else: k, basis = '非主管', '不符上列任一'
        cnt[k] += p['員額'] or 0; hc[k] += 1
        cls_rows.append((ag, p['序'], u or '', t, p['員額'], k, basis, '是' if p['主管'] else '否'))
    agg.append((ag, m.get('主管員額'), cnt['首長'], cnt['副首長'], cnt['幕僚長'], cnt['單位主管'], cnt['單位副主管'], cnt['無單位之主管職稱'], hc['無單位之主管職稱'], m.get('員額合計')))
W('p2b_2_逐列主管分類.csv', ['機關', '序', '單位', '職稱', '員額', '分類', '分類依據', '舊主管旗標'], cls_rows)
W('p2b_2_機關四分項.csv', ['機關', '舊主管員額', '首長', '副首長', '幕僚長', '單位主管', '單位副主管', '無單位之主管職稱員額', '無單位之主管職稱列數', '員額合計'], agg)
kc = collections.Counter(r[5] for r in cls_rows); print('分類列數', kc)
print('無單位之主管職稱 職稱別', collections.Counter(r[3] for r in cls_rows if r[5] == '無單位之主管職稱').most_common(20))
print('舊旗標=是 但新分類=非主管', collections.Counter(r[3] for r in cls_rows if r[7] == '是' and r[5] == '非主管').most_common(10))
print('舊旗標=否 但新分類∈首長/副首長/單位主管', collections.Counter((r[5], r[3]) for r in cls_rows if r[7] == '否' and r[5] in ('首長', '副首長', '單位主管', '單位副主管')).most_common(15))
# 口徑比較
def agg_sum(k): return sum(a[k] for a in agg)
print('全庫員額：首長', agg_sum(2), '副首長', agg_sum(3), '幕僚長', agg_sum(4), '單位主管', agg_sum(5), '單位副主管', agg_sum(6), '無單位主管職稱', agg_sum(7))
eq = sum(1 for a in agg if a[1] is not None and a[1] == a[5] + a[6] + a[2] + a[3] + a[4] + a[7])
print('舊主管員額 == 六分項合計之機關數', eq, '/', sum(1 for a in agg if a[1] is not None))

# ===== C. 得列備註型態學 =====
LEVEL = [('文官-簡任', r'得列簡任'), ('文官-薦任', r'得列薦任'), ('文官-委任', r'得列委任'), ('警察官-警正', r'得列警正'), ('警察官-警監', r'得列警監'), ('軍階', r'得列(上校|中校|少校|上尉|軍職)'), ('醫事-師級', r'得列師'), ('關務', r'得列.{0,8}關務')]
CN = r'[一二三四五六七八九十○〇百0-9]+'
drows = []
for p in P:
    b = p['備註'] or ''
    if '得列' not in b: continue
    levels = [n for n, rx in LEVEL if re.search(rx, b)]
    segs = re.findall(r'(?:^|[一二三四五六七八九十]、)', b)
    n_seg = len(re.findall(r'[一二三四五六七八九十]、', b))
    n_hits = len(re.findall(r'人得列', b))
    ctx = []
    if re.search(r'出缺|改置', b): ctx.append('出缺改置前後（多情境）')
    if re.search(r'合併計給|合併計算', b): ctx.append('與他職稱合併計給')
    if re.search(r'其中', b) and re.search(r'其中' + CN + r'人', b): ctx.append('「其中N人」子集')
    if re.search(r'或上|以上', b): ctx.append('或以上寫法')
    if re.search(r'現職', b): ctx.append('現職人員條件')
    if re.search(r'^得列|[。；]得列', b): ctx.append('無「內N人」前綴（整列得列）')
    if n_hits >= 2: ctx.append(f'同列 {n_hits} 個得列句')
    ns = re.findall(r'(?:內|其中)(' + CN + r')人得列', b)
    deterministic = (n_hits == 1 and len(levels) == 1 and not any(c.startswith(('出缺', '與他', '或以上')) for c in ctx) and bool(ns))
    reason = '' if deterministic else ('；'.join(ctx) or ('多等級' if len(levels) > 1 else '無法取 N'))
    drows.append((p['機關'], p['序'], p['職稱'], p['官等'], p['員額'], '、'.join(levels) or '未分類', '、'.join(ns), '；'.join(ctx), '可判定' if deterministic else '待審', reason, p['得列簡任'], p['得列薦任'], b))
W('p2b_4_得列備註逐列分類.csv', ['機關', '序', '職稱', '官等', '員額', '得列等級', 'N 值', '情境', '判定', '待審原因', '現行得列簡任', '現行得列薦任', '備註原文'], drows)
print('得列列數', len(drows), '可判定', sum(1 for r in drows if r[8] == '可判定'), '待審', sum(1 for r in drows if r[8] == '待審'))
print('等級分布', collections.Counter(r[5] for r in drows).most_common())
print('待審原因', collections.Counter(r[9] for r in drows if r[8] == '待審').most_common(12))
print('官等×等級（得列薦任）', collections.Counter(r[3] for r in drows if '薦任' in r[5]).most_common(8))
print('官等×等級（得列簡任）', collections.Counter(r[3] for r in drows if '簡任' in r[5]).most_common(8))

# ===== E. 合併計算列 865 / 800 =====
def blank(p): return p['員額'] is None and not p['員額原文']
def cat(n): return '醫療' if re.search('醫院|療養院|醫療|疾病管制|衛生福利部', n) else '矯正' if re.search('監獄|看守所|戒治所|矯正|技能訓練所|少年|輔育院|觀護所', n) else '榮家等' if '退除役' in n else '其他'
d1 = [p for p in P if blank(p)]; d2 = [p for p in P if blank(p) and not p['列品質'] and p['計入']]
d1b = [p for p in P0 if blank(p)]
print('定義一（員額空∧原文空）P1 產物', len(d1), '機關', len({p['機關'] for p in d1}), '| 同定義於 P0 產物', len(d1b), collections.Counter(cat(p['機關']) for p in d1b))
print('定義二（定義一 ∧ 無列品質 ∧ 計入）', len(d2), '機關', len({p['機關'] for p in d2}))
diff = [p for p in d1 if not (not p['列品質'] and p['計入'])]
print('差異列', len(diff), collections.Counter((p['列品質'] or '無標記', p['計入']) for p in diff).most_common())
W('p2b_7_合併計算列_定義一.csv', ['機關', '類別', '序', '單位', '職稱', '官等', '職等', '列品質', '計入', '上一列職稱', '上一列員額'], [(p['機關'], cat(p['機關']), p['序'], p['單位'] or '', p['職稱'], p['官等'] or '', p['職等'] or '', p['列品質'] or '', p['計入'], *(lambda q: (q['職稱'], q['員額']) if q else ('', ''))(next((q for q in by[p['機關']] if q['序'] == p['序'] - 1), None))) for p in d1])
W('p2b_7_合併計算列_差異65.csv', ['機關', '序', '職稱', '列品質', '計入', '差異原因'], [(p['機關'], p['序'], p['職稱'], p['列品質'] or '', p['計入'], '列品質標記' if p['列品質'] else '計入=false') for p in diff])
# 定義二中「其他」28 列
oth28 = [p for p in d2 if cat(p['機關']) == '其他']
print('定義二其他類', len(oth28), collections.Counter(p['職稱'] for p in oth28).most_common())

# ===== F. 國防部 7 機關與部會欄 =====
nd = ov[(ov['部會'] == '國防部') | ov['機關'].str.startswith('國防部')]
print(nd[['機關', '機關代碼', '層級', '隸屬', '部會', '組織法規名稱']].to_string())
mil = collections.Counter()
for p in P:
    if re.search(r'將|校|尉|士官', p['官等'] or ''): mil[p['機關']] += 1
print('官等含軍階列數', {k: v for k, v in mil.items() if k in set(nd['機關'])})
vac = ov[ov['部會'] == '國軍退除役官兵輔導委員會']; print('退輔會部會欄機關數', len(vac), '隸屬值', vac['隸屬'].value_counts().to_dict())
print('部會欄空值數', ov['部會'].isna().sum(), '| 機關代碼空值', ov['機關代碼'].isna().sum())
json.dump(log, open(f'{OUT}/log.json', 'w', encoding='utf-8'), ensure_ascii=False)

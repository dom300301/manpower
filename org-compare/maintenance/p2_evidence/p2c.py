import json, re, collections, csv, os
import pandas as pd
S = '/tmp/claude-0/-home-user-manpower/4c1fe7a7-cb5e-55f8-b5c1-b63a2b48cd38/scratchpad'
R = '/home/user/manpower/org-compare'
OUT = f'{S}/diag/p2b'
A = {a['機關']: a for a in json.load(open(f'{S}/diag/after/agencies.json', encoding='utf-8'))['agencies']}
P = json.load(open(f'{S}/diag/after/positions.json', encoding='utf-8'))
X = pd.ExcelFile(f'{R}/data/組織法編制表_總表_20261031.xlsx')
ov = X.parse('機關總覽', dtype=str); art = X.parse('條文', dtype=str)
def W(name, hdr, rows):
    with open(f'{OUT}/{name}', 'w', newline='', encoding='utf-8-sig') as f: csv.writer(f).writerows([hdr] + rows)
    print(name, len(rows))

# ===== A2. 共用法規掛接：以法規適用範圍判定 =====
org = art[art['法規類別'] == '組織法規']
first_law = org.groupby('機關')['法規名稱'].first()
ovlaw = ov.set_index('機關')['組織法規名稱'].fillna('')
def scope_of(law):
    a1 = org[(org['法規名稱'] == law) & (org['條號'] == '第1條')]['條文內容']
    t = (a1.iloc[0] if len(a1) else '').replace('\n', '')
    m = re.search(r'特設(?:所屬)?(?:各)?(?:區)?(?:地區)?([^，。（(、；]{1,14}?)(?:（以下|，|。|；|$)', t)
    return (m.group(1) if m else ''), t[:120]
def kind_of(law):
    m = re.search(r'(?:各區|各|所屬|附屬)(.+?)組織(準則|通則)$', law); return m.group(1) if m else ''
def type_match(ag, kind, scope):
    cands = set()
    for k in (kind, scope):
        if not k: continue
        k = re.sub(r'^(各區|各|所屬|地區)', '', k)
        cands |= {k, k[-3:], k[-2:]}
        # 同義：局→分署（112 年改制）、醫院→榮民總醫院、氣象測報機構→氣象站／中心
        if k.endswith('局'): cands.add(k[:-1] + '分署')
        if '氣象測報' in k: cands |= {'氣象站', '雷達站', '測報中心', '預報中心', '氣象中心'}
        if '福利機構' in k or '老人' in k: cands |= {'老人之家', '教養院', '養護中心', '兒童之家', '少年之家'}
    cands = {c for c in cands if len(c) >= 2}
    hit = [c for c in cands if c in ag]
    return hit
rows = []
for ag, laws in org.groupby('機關')['法規名稱'].agg(lambda s: list(dict.fromkeys(s))).items():
    shared = [l for l in laws if kind_of(l)]
    if not shared: continue
    judged = []
    for l in laws:
        kind = kind_of(l); scope, a1 = scope_of(l)
        hit = type_match(ag, kind, scope) if kind else []
        judged.append((l, kind, scope, hit))
    matched = [j for j in judged if j[3]]
    own = [l for l in laws if not kind_of(l)]
    for l, kind, scope, hit in judged:
        if not kind: continue
        flagged = '（上級機關訂的共用準則/通則，需確認）' in ovlaw.get(ag, '')
        if hit: concl = '相符（適用範圍／型別與機關名稱一致）'
        elif own: concl = f'待審（機關另有專屬法規 {own[0]}；本共用法規適用範圍「{scope or kind}」與機關名稱不符）'
        elif matched: concl = f'待審（本法適用範圍「{scope or kind}」不符；同機關相符之共用法規：{matched[0][0]}）'
        else: concl = f'待審（本法適用範圍「{scope or kind}」不符；同機關無相符法規，需查機關代碼表或編制表標題）'
        aff = []
        if first_law.get(ag) == l: aff.append('組織法規最新異動日（本法為第一筆）')
        if A.get(ag, {}).get('資料狀態', '').startswith('未取得（無編制表）'): aff.append('法定員額依據')
        if org[(org['法規名稱'] == l) & (org['條文內容'].fillna('').str.contains('掌理'))].shape[0]: aff.append('掌理事項關鍵字')
        rows.append((ag, l, kind, scope, '、'.join(hit), '是' if flagged else '否', concl, '；'.join(aff) or '無', ov[ov['機關'] == ag]['編制表來源'].iloc[0][:80] if (ov['機關'] == ag).any() else ''))
W('p2b_1_共用法規掛接全清單.csv', ['機關', '法規名稱', '準則名稱所指類型', '第1條適用範圍（特設…）', '機關名稱命中詞', '總覽註記需確認', '判定結論', '受影響欄位（現行程式）', '編制表來源'], rows)
c = collections.Counter(r[6].split('（')[0] for r in rows); print(c)
sus = [r for r in rows if r[6].startswith('待審')]
print('待審 筆數', len(sus), '機關數', len({r[0] for r in sus}), '法規數', len({r[1] for r in sus}))
print('待審子類', collections.Counter(re.sub(r'「.*?」|\s+\S+$', '', r[6])[:30] for r in sus).most_common())
print('受影響欄位', collections.Counter(x for r in sus for x in r[7].split('；')))
print('第一筆為待審法規之機關數', len({r[0] for r in sus if '第一筆' in r[7]}))
old = {(r['機關'], r['法規名稱']) for r in csv.DictReader(open(f'{S}/diag/p2/p2_4_共用法規疑似誤掛.csv', encoding='utf-8'))}
new = {(r[0], r[1]) for r in sus}
print('252 ∩ 新待審', len(old & new), '| 252 中本輪判相符', len(old - new), '| 新待審但 252 無', len(new - old))
print('252 中本輪判相符之法規', collections.Counter(l for a, l in (old - new)).most_common(6))
print('新待審但 252 無之法規', collections.Counter(l for a, l in (new - old)).most_common(6))
W('p2b_1_啟發式252對照.csv', ['機關', '法規名稱', '啟發式252', '本輪判定'], [(r[0], r[1], '是' if (r[0], r[1]) in old else '否', r[6]) for r in rows if (r[0], r[1]) in old or r[6].startswith('待審')])

# ===== B2. 主管分類（單位向下填補） =====
MGR_RE = re.compile(r'(?:主任秘書|署長|局長|處長|所長|館長|院長|場長|校長|主任|秘書長|組長|科長|課長|股長|隊長|總隊長|分隊長|中隊長|大隊長|典獄長|分署長|分局長|司長|主計長|人事長|委員長|中心主任|室主任|站長|廠長|園長|所長|主席|行長|總裁|執行長)$')
by = collections.defaultdict(list)
for p in P: by[p['機關']].append(p)
cls_rows = []; agg = []
for ag, rs in by.items():
    m = A[ag]['指標']; ht = m.get('首長職稱'); dts = m.get('副首長職稱') or ''
    dts = [] if '（無）' in dts else [d for d in dts.split('、') if d]
    rs = sorted(rs, key=lambda p: p['序']); first = next((p for p in rs if p['計入']), None)
    cnt = collections.Counter(); hc = collections.Counter(); cur = None; seen_unit = False
    for p in rs:
        if p['單位']: cur = p['單位']; seen_unit = True
        if not p['計入']: continue
        t = p['職稱']; u_raw = p['單位']; u = cur
        if first is p and t == ht: k, basis = '首長', '序最小之計入列且職稱＝首長職稱'
        elif t in dts and not u_raw and not seen_unit: k, basis = '副首長', '職稱屬副首長職稱、位於首個單位出現前'
        elif t == '主任秘書' and not seen_unit: k, basis = '幕僚長', '職稱＝主任秘書、位於首個單位出現前'
        elif u and t.startswith('副') and MGR_RE.search(t): k, basis = '單位副主管', f'單位「{u}」（{"本列" if u_raw else "向下填補"}）、副＋主管字尾'
        elif u and MGR_RE.search(t): k, basis = '單位主管', f'單位「{u}」（{"本列" if u_raw else "向下填補"}）、主管字尾'
        elif MGR_RE.search(t): k, basis = '無單位之主管職稱', '全表無單位欄或位於單位前，主管字尾 → 待審'
        else: k, basis = '非主管', '不符上列任一'
        cnt[k] += p['員額'] or 0; hc[k] += 1
        cls_rows.append((ag, p['序'], u_raw or '', u or '', t, p['員額'], k, basis, '是' if p['主管'] else '否'))
    agg.append((ag, m.get('主管員額'), cnt['首長'], cnt['副首長'], cnt['幕僚長'], cnt['單位主管'], cnt['單位副主管'], cnt['無單位之主管職稱'], hc['無單位之主管職稱'], m.get('員額合計'), '是' if any(p['單位'] for p in rs) else '否'))
W('p2b_2_逐列主管分類.csv', ['機關', '序', '單位（原值）', '單位（向下填補）', '職稱', '員額', '分類', '分類依據', '舊主管旗標'], cls_rows)
W('p2b_2_機關六分項.csv', ['機關', '舊主管員額', '首長', '副首長', '幕僚長', '單位主管', '單位副主管', '無單位之主管職稱員額', '無單位之主管職稱列數', '員額合計', '表內有單位欄'], agg)
print('分類列數', collections.Counter(r[6] for r in cls_rows))
print('全表無單位欄之機關數', sum(1 for a in agg if a[10] == '否'), '其 無單位主管職稱 員額', sum(a[7] for a in agg if a[10] == '否'))
print('有單位欄但仍有無單位主管職稱之機關數', sum(1 for a in agg if a[10] == '是' and a[8]), '列數', sum(a[8] for a in agg if a[10] == '是'))
print('無單位主管職稱 職稱別（有單位欄機關）', collections.Counter(r[4] for r in cls_rows if r[6] == '無單位之主管職稱' and r[0] in {a[0] for a in agg if a[10] == '是'}).most_common(12))
print('全庫員額：首長', sum(a[2] for a in agg), '副首長', sum(a[3] for a in agg), '幕僚長', sum(a[4] for a in agg), '單位主管', sum(a[5] for a in agg), '單位副主管', sum(a[6] for a in agg), '無單位主管職稱', sum(a[7] for a in agg))
dup = collections.Counter((r[0], r[1]) for r in cls_rows); print('同一列多分類', sum(1 for v in dup.values() if v > 1))

# ===== C2. 法規沿革解析（9 機關 18 部）=====
chlaw = {l['LawName']: l for l in json.load(open(f'{S}/moj/chlaw/ChLaw.json', encoding='utf-8-sig'))['Laws']}
chord = {l['LawName']: l for l in json.load(open(f'{S}/moj/chorder/ChOrder.json', encoding='utf-8-sig'))['Laws']}
CNUM = '[○〇零一二三四五六七八九十百]+'
def cn(s):
    s = s.replace('○', '〇').replace('零', '〇'); d = {'〇': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
    if '百' in s or '十' in s:
        n = 0; t = s
        if '百' in t: a, t = t.split('百'); n += (d[a] if a else 1) * 100
        if '十' in t: a, t = t.split('十'); n += (d[a] if a else 1) * 10
        if t: n += d[t[-1]]
        return n
    return int(''.join(str(d[ch]) for ch in s))
def roc(m): return f'{cn(m.group(1)) + 1911:04d}-{cn(m.group(2)):02d}-{cn(m.group(3)):02d}'
DATE = r'中華民國(' + CNUM + ')年(' + CNUM + ')月(' + CNUM + ')日'
def parse_hist(h):
    h = h.replace('\r', '')
    items = re.split(r'\n(?=\d+\.)', h.strip())
    out = []
    for it in items:
        it1 = re.sub(r'\s+', '', it)
        dates = [roc(m) for m in re.finditer(DATE, it1)]
        kind = '制定公布' if re.search(r'制定公布|訂定發布', it1) else '修正公布' if re.search(r'修正公布|修正發布', it1) else '廢止' if '廢止' in it1 else '其他'
        eff = None
        m = re.search(r'定自(' + CNUM + ')年(' + CNUM + ')月(' + CNUM + ')日(?:起)?施行', it1)
        if m: eff = f'{cn(m.group(1)) + 1911:04d}-{cn(m.group(2)):02d}-{cn(m.group(3)):02d}'
        elif re.search(r'自公布日(?:起)?施行|自發布日(?:起)?施行', it1): eff = dates[0] + '（公布日）' if dates else '公布日'
        elif re.search(r'施行日期，?由行政院(?:以命令)?定之|施行日期由行政院定之', it1): eff = '待行政院令（沿革無後續令）'
        out.append({'項': it[:3], '日期': dates, '類型': kind, '施行': eff, '原文': it1[:160]})
    return out
rows5 = []
for n in ['交通部民用航空局', '交通部民用航空局民航人員訓練所', '交通部民用航空局飛航服務總臺', '交通部運輸研究所', '內政部消防署', '經濟部智慧財產局', '經濟部標準檢驗局', '經濟部水利署', '經濟部產業園區管理局']:
    laws = [l for l in org[org['機關'] == n]['法規名稱'].drop_duplicates() if n in l]
    for l in laws:
        rec = chlaw.get(l) or chord.get(l)
        if not rec: rows5.append((n, l, '不在開放資料', '', '', '', '', '', '')); continue
        hist = parse_hist(rec['LawHistories'])
        enact = next((h['日期'][0] for h in hist if h['類型'] == '制定公布' and h['日期']), '')
        amend = [h['日期'][0] for h in hist if h['類型'] == '修正公布' and h['日期']]
        effs = [(h['日期'][0] if h['日期'] else '', h['施行']) for h in hist if h['施行']]
        aband = [h['原文'] for h in hist if h['類型'] == '廢止']
        rows5.append((n, l, '法律' if l in chlaw else '命令', enact, amend[-1] if amend else '', rec['LawModifiedDate'], '；'.join(f'{d}→{e}' for d, e in effs) or '沿革無施行句', rec['LawAbandonNote'] or '空', '；'.join(aband) or '沿革無廢止句', rec['LawURL']))
W('p2b_5_九機關法規日期.csv', ['機關', '法規名稱', '層級', '制定公布日', '最新修正公布日', '開放資料 LawModifiedDate', '施行句（公布日→施行日）', '廢止註記', '沿革廢止句', '連結'], rows5)
for r in rows5: print(r[:2], r[3], r[4], '|', r[6][:90], '|', r[7], r[8][:40])

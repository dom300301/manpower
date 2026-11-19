#!/usr/bin/env python3
"""
考試院核議標準（通案決議）檢核規則 C2～C17。依 rules/council_standards.json 之決議內容實作。
每條規則回傳 finding（與 check_grades.finding 相同欄位）。
"""
import collections
import re

from check_grades import DE_LIE, HEAD_TITLES, STAFF_HEAD, c2n, finding, grades_of

AUX_UNIT = re.compile(r'人事|主計|會計|政風|秘書|統計')
AUX_HEAD_TITLES = ('主任', '室主任')
BIZ_MGR = {'2': ('司長', '處長', '組長'), '3': ('組長', '處長'), '4': ('科長', '課長', '主任')}
BASIC_LAW_EXEMPT = re.compile(r'國防部|外交部|警察|警政|消防|檢察|調查局|調查處|海巡|海洋委員會海巡署')
ENG_TITLE = re.compile(r'工程司|工程員|工務員')


def gmax(z):
    g = grades_of(z)
    return max(g) if g else None


def gmin(z):
    g = grades_of(z)
    return min(g) if g else None


def is_aux_head(r):
    return r['職稱'] in AUX_HEAD_TITLES and bool(AUX_UNIT.search(r.get('單位') or ''))


def engineering_share(a, rows, total):
    """工程類職稱員額 ÷（編制員額 − 首長副首長 − 一級單位主管）。回傳 (share%, eng, heads, first_level)。"""
    level = a['層級']
    head = rows[0] if rows else None
    heads = [rows[0]] if rows else []
    heads += [r for r in rows if head and r['職稱'] == '副' + head['職稱']]
    first_level = [r for r in rows if r['職稱'] in ('司長', '處長', '組長', '主任', '室主任') or (level == '4' and r['職稱'] in ('科長', '課長'))]
    base = total - sum(r['員額'] for r in heads) - sum(r['員額'] for r in first_level)
    eng = sum(r['員額'] for r in rows if ENG_TITLE.search(r['職稱']))
    share = round(eng / base * 100, 1) if base > 0 else None
    return share, eng, sum(r['員額'] for r in heads), sum(r['員額'] for r in first_level)


def council_checks(a, rows, cat, category, ctx):
    """ctx：{'children': {機關: [子機關 dict]}, 'agencies': {機關: dict}, 'total_of': fn}。"""
    F = []
    level = a['層級']
    name = a['機關']
    head = rows[0] if rows else None
    head_max = gmax(head['職等']) if head else None
    cnt = collections.Counter()
    for r in rows:
        cnt[r['職稱']] += r['員額']

    # ---- C2 雙副主管（二-1）
    sig = []
    for m_, d_ in [('司長', '副司長'), ('處長', '副處長'), ('組長', '副組長'), ('局長', '副局長'), ('主任', '副主任'), ('科長', '副科長')]:
        if cnt[d_] > cnt[m_] > 0:
            sig.append(f'{m_} {cnt[m_]}：{d_} {cnt[d_]}')
    if sig:
        F.append(finding('C2', '考試院101.4.26第11屆第185次會議', '一級單位雙副主管', '副主管員額多於主管員額', '；'.join(sig), '1單位1副主管為原則',
                         '需確認', '', '例外四情形：原經核備且仍有必要／立法院附帶決議／職掌複雜或專業領域不同／單位預算員額達50人以上。請機關敘明符合何者並附單位預算員額。'))

    # ---- C3 三級署 一級業務單位主管 11-12（三-5）
    if level == '3':
        hi_mgr = [r for r in rows if r['職稱'] in BIZ_MGR['3'] and grades_of(r['職等']) == {11, 12}]
        if hi_mgr:
            kids = ctx['children'].get(name, [])
            total_all = ctx['total_of'](a) + sum(ctx['total_of'](k) for k in kids)
            cond1 = head_max == 14 or bool(head and re.search(r'十四職等', (head['職等'] or '') + (head['備註'] or '')))
            cond2 = total_all >= 4000
            ok = cond1 and cond2
            F.append(finding('C3', '考試院109.1.9第12屆第269次會議', '三級署一級業務單位主管列簡任第11至12職等之要件', f'首長上限 {head_max}（須14或比照14）；暨附屬機關員額 {total_all}（須≥4000，附屬機關 {len(kids)} 個）',
                             '、'.join(sorted(set(r['職稱'] for r in hi_mgr))) + ' 列11-12', '首長上限14且員額≥4000', '符合' if ok else '需確認', '',
                             '' if ok else '未同時符合兩要件，請查明是否另經考試院同意（如相當三級獨立機關）'))

    # ---- C4 四級機關首長13之配套（三-6）
    if level == '4' and head_max:
        dep = [r for r in rows if r['職稱'] == '副' + head['職稱']]
        dep_max = max((gmax(r['職等']) or 0) for r in dep) if dep else None
        staff = [r for r in rows if r['職稱'] in STAFF_HEAD]
        staff_max = max((gmax(r['職等']) or 0) for r in staff) if staff else None
        biz = [r for r in rows[1:] if r['職稱'] in BIZ_MGR['4'] and not is_aux_head(r) and r['職稱'] != '副' + head['職稱'] and r['職稱'] != head['職稱']]
        biz_max = max((gmax(r['職等']) or 0) for r in biz) if biz else None
        if (dep_max and dep_max >= 12) or (staff_max and staff_max >= 11) or (biz_max and biz_max >= 11):
            ok = head_max >= 13
            F.append(finding('C4', '考試院112.6.29第13屆第143次會議', '四級機關副首長列12、幕僚長或一級業務單位主管列11之要件', f'首長上限 {head_max}；副首長 {dep_max}；幕僚長 {staff_max}；一級業務主管 {biz_max}',
                             '副首長／幕僚長／業務主管達12／11', '首長（相當）13且業務於同層級僅由該機關辦理', '需確認' if ok else '不符', '',
                             '請確認是否負責全國性業務之規劃督導（如刑事警察局）；首長未達13者不適用' if ok else '首長未達簡任第13職等'))

    # ---- C5 公職律師（三-7）
    for r in rows:
        if r['職稱'] == '公職律師' and r['員額'] > 0:
            up = sum(c2n(m.group(1)) for m in DE_LIE.finditer(r['備註'] or '') if m.group(2) == '簡任')
            cap = r['員額'] // 2
            F.append(finding('C5', '考試院113.8.15第13屆第198次會議', '公職律師得列簡任員額', f'員額 {r["員額"]}，備註得列簡任 {up}', str(up), f'≤{cap}（員額之1/2）', '符合' if up <= cap else '不符', '' if up <= cap else f'超過 {up - cap} 人'))

    # ---- C6 四級一級業務（派出）單位主管上限8→8-9（三-8）
    if level == '4':
        parent = ctx['agencies'].get(a.get('隸屬') or '', {})
        parent_is_bureau = bool(re.search(r'署$|局$', a.get('隸屬') or ''))
        eff = '114.8.1' if parent_is_bureau else '115.2.1'
        pend = [r for r in rows if r['職稱'] in BIZ_MGR['4'] and not is_aux_head(r) and (r['官等'] or '').strip() == '薦任' and gmax(r['職等']) == 8]
        if pend:
            F.append(finding('C6', '考試院114.5.8第14屆第19次、114.9.4第36次會議', '四級機關一級業務（派出）單位主管列等調整', '仍列上限薦任第8職等之主管職稱',
                             '；'.join(f"{r['職稱']}（{r['職等']}）{r['員額']}人" for r in pend), f'可調整為薦任第8至9職等（{"署局所屬" if parent_is_bureau else "非署局所屬"}自 {eff} 實施）',
                             '需確認', '', '依決議由銓敘部通函、機關修編辦理；本表為修編前資料。主任若非業務單位主管請忽略。'))

    # ---- C7 四級設室輔助單位主管列等一致、不高於業務單位主管（四-1、四-7）
    if level == '4':
        aux = [r for r in rows if is_aux_head(r) and grades_of(r['職等'])]
        biz = [r for r in rows if r['職稱'] in BIZ_MGR['4'] and not is_aux_head(r) and grades_of(r['職等'])]
        if aux:
            codes = sorted(set(f"{gmin(r['職等'])}-{gmax(r['職等'])}" for r in aux))
            consistent = len(codes) == 1
            biz_max = max(gmax(r['職等']) for r in biz) if biz else None
            aux_max = max(gmax(r['職等']) for r in aux)
            higher = biz_max is not None and aux_max > biz_max
            res = '符合' if consistent and not higher else ('不符' if not consistent else '需確認')
            F.append(finding('C7', '考試院99.10.14第11屆第107次、114.9.4第14屆第36次會議', '四級機關設室之輔助單位主管列等', f'輔助單位主管列等 {"、".join(codes)}；業務單位主管上限 {biz_max}',
                             '一致' if consistent else '不一致', '彼此一致，且得與業務單位主管一致（不高於）', res, '',
                             ('輔助單位主管高於業務單位主管，請確認是否屬組改降級、首長或業務主管兼任等特殊情形' if higher else '')))

    # ---- C8 三級首長13 輔助單位主管 9-10／9（四-2）
    if level == '3' and head_max == 13:
        aux = [r for r in rows if is_aux_head(r) and grades_of(r['職等'])]
        if aux:
            total = ctx['total_of'](a)
            has_kids = bool(ctx['children'].get(name))
            expect = (9, 10) if (total >= 300 or (total >= 150 and has_kids)) else (9, 9)
            exp_txt = '薦任第9職等至簡任第10職等' if expect == (9, 10) else '薦任第9職等'
            over = [r for r in aux if (gmax(r['職等']) or 0) > expect[1]]
            under = [r for r in aux if (gmax(r['職等']) or 0) < expect[1]]
            single_level = cnt['科長'] == 0 and cnt['股長'] == 0
            if single_level:
                res, note = '不適用', '內部單位僅一層級（無科長），依七-1c 不適用配套列等，維持組改前列等'
            elif over:
                res, note = '需確認', '高於通案標準，請查明是否經考試院同意'
            elif under:
                res, note = '符合', '低於通案標準（修編時得依標準調整）'
            else:
                res, note = '符合', ''
            F.append(finding('C8', '考試院100.3.24第11屆第129次會議（96.6.28核議標準）', '三級機關（首長13）輔助單位主管列等', f'編制員額 {total}，{"有" if has_kids else "無"}附屬機關 → 通案 {exp_txt}',
                             '；'.join(f"{r['單位']}{r['職稱']} {r['職等']}" for r in aux[:6]), exp_txt, res, '', note))

    # ---- C9 輔助單位主管職稱 主任／室主任（四-3、四-4）
    aux = [r for r in rows if is_aux_head(r)]
    if aux and head:
        head_is_zhuren = head['職稱'] in ('主任', '中心主任')
        other_zhuren = any(r['職稱'] == '主任' and not is_aux_head(r) and r['員額'] > 0 and r is not head for r in rows)
        titles = sorted(set(r['職稱'] for r in aux))
        if head_is_zhuren and '主任' in titles:
            res, want, note = '需確認', '室主任', '首長職稱為「主任」，輔助單位主管應稱「室主任」以資區隔'
        elif not head_is_zhuren and '室主任' in titles and not other_zhuren:
            res, want, note = '需確認', '主任', '機關無其他「主任」職稱，輔助單位主管原則簡併為「主任」'
        else:
            res, want, note = '符合', '室主任' if (head_is_zhuren or other_zhuren) else '主任', ''
        F.append(finding('C9', '考試院101.1.19第11屆第172次、101.3.1第177次會議', '輔助單位主管職稱', f'首長職稱 {head["職稱"]}；其他單位{"有" if other_zhuren else "無"}「主任」職稱',
                         '、'.join(titles), f'原則「{want}」', res, '', note))

    # ---- C10 一條鞭單位主管與科長列等相同（四-5）
    by_unit = collections.defaultdict(list)
    for r in rows:
        if r.get('單位') and AUX_UNIT.search(r['單位']):
            by_unit[r['單位']].append(r)
    clash = []
    for u, rs in by_unit.items():
        hd = [r for r in rs if r['職稱'] in AUX_HEAD_TITLES]
        sc = [r for r in rs if r['職稱'] == '科長' and r['員額'] > 0]
        if hd and sc and gmax(hd[0]['職等']) and gmax(hd[0]['職等']) <= max(gmax(s['職等']) or 0 for s in sc):
            clash.append(f'{u}：主任 {hd[0]["職等"]}／科長 {sc[0]["職等"]}')
    if clash:
        F.append(finding('C10', '考試院102.6.13第11屆第240次會議', '一條鞭單位主管與所屬科長列等', '；'.join(clash), '相同或科長較高', '主管應高於科長', '不符', '', '嗣後類此情形不予核備，現職人員循一條鞭系統安置'))

    # ---- C11 研究員列等（五-1）
    if level in ('3', '4') and '醫療' not in category and not re.search(r'醫院', name):
        for r in rows:
            if r['職稱'] == '研究員' and r['員額'] > 0 and grades_of(r['職等']) and '聘任' not in (r['備註'] or ''):
                g = grades_of(r['職等'])
                is_bureau = bool(re.search(r'署$|局$', name))
                if g == {10}:
                    continue
                if g == {10, 11}:
                    ok = level == '3' and (is_bureau or ('研究' in category and (head_max or 0) >= 13))
                    F.append(finding('C11', '考試院101.2.16第11屆第175次會議', '研究員列簡任第10至11職等之要件', f'層級 {level}；{"署局" if is_bureau else "非署局"}；首長上限 {head_max}',
                                     r['職等'], '三級署局，或三級研究機構（全國唯一、組改前即有11、首長≥13）', '需確認' if ok else '不符', '',
                                     '請確認組改前是否原即置有上限簡任第11職等之研究員' if ok else '其餘三、四級機關研究員列簡任第10職等'))
                else:
                    F.append(finding('C11', '考試院101.2.16第11屆第175次會議', '研究員列等', r['職等'], r['職等'], '簡任第10職等（或10至11）', '需確認', '', '與通案列等不同，請查明依據（如組織法律所定、雙軌聘任）'))

    # ---- C12 聘任備註「以上」（五-2）
    bad = [r for r in rows if re.search(r'比照(教授|副教授|助理教授|講師)以上', r['備註'] or '') and '組織法律所定' not in (r['備註'] or '')]
    if bad:
        F.append(finding('C12', '考試院101.9.20第11屆第205次會議', '研究類職稱比照聘任等級體例', '備註含「比照○○以上」', '、'.join(sorted(set(r['職稱'] for r in bad))), '「必要時得比照副教授或教授之資格聘任」等，不加「以上」', '不符', '', '修編時修正備註文字'))

    # ---- C13 參議列等、社會工作師（六）
    for r in rows:
        if r['職稱'] == '參議' and level == '3' and r['員額'] > 0 and grades_of(r['職等']) != {10, 11}:
            F.append(finding('C13', '考試院114.10.23第14屆第43次會議', '三級署局參議列等', r['職等'], r['職等'], '簡任第10至11職等', '不符'))
    sw = [r for r in rows if r['職稱'] == '社會工作師' and r['員額'] > 0 and (r['官等'] or '').strip() == '委任或薦任' and level in ('3', '4')]
    if sw:
        F.append(finding('C13', '考試院114.10.23第14屆第43次會議', '社會工作師列等', '現列委任第5職等或薦任第6至7職等', f'{sum(r["員額"] for r in sw)} 人', '下次修編改列薦任第6至7職等', '需確認', '',
                         '改列後委任員額減少，請同時檢視委任比率（R2）與委四至五職稱員額（R5）'))

    # ---- C14 三級社教機構（七）
    if level == '3' and '社教' in category:
        for r in rows:
            if r['職稱'] == '組長' and r['員額'] > 0 and grades_of(r['職等']) and grades_of(r['職等']) != {9, 10}:
                F.append(finding('C14', '考試院101.1.5第11屆第170次會議', '三級社教機構一級業務單位主管列等', r['職等'], r['職等'], '薦任第9職等至簡任第10職等（傳藝中心維持簡任第11職等）',
                                 '符合' if '傳統藝術中心' in name else '需確認', '', '' if '傳統藝術中心' in name else '請查明是否經考試院同意'))
        other_mgr = sorted(set(r['職稱'] for r in rows if r['職稱'] in ('處長', '科長', '課長') and r['員額'] > 0 and not is_aux_head(r)))
        if other_mgr:
            F.append(finding('C14', '考試院101.1.5第11屆第170次會議', '三級社教機構一級業務單位主管職稱', '置有組長以外之業務主管職稱', '、'.join(other_mgr), '均置「組長」', '需確認', '', '文化部所屬機構職稱簡併原則'))
        # 研究類兩兩合併之比例（以備註文字判讀）
        for r in rows:
            b = r['備註'] or ''
            m = re.search(r'研究員.{0,6}不得(高於|超過)', b)
            if r['職稱'] in ('研究員', '副研究員', '助理研究員', '研究助理') and m:
                F.append(finding('C14', '考試院101.5.24第11屆第189次會議', '研究類職稱兩兩合併之員額上限', r['職稱'], b[:80], '研究員≤(研究員+副研究員)/2；助理研究員≤(助理研究員+研究助理)×2/3', '需確認', '', '請以備註數字人工核對'))
                break

    # ---- C15 工程機關認定（八）
    total = ctx['total_of'](a)
    share, eng, n_heads, n_first = engineering_share(a, rows, total)
    is_eng_cat = '工程' in category
    if share is not None and (is_eng_cat or share >= 50):
        if is_eng_cat and share < 50:
            res, note = '需確認', '歸類為工程機關但工程類職稱員額未達50%，請確認類別（名稱含「養護」者可能非工程機關）'
        elif not is_eng_cat and share >= 50:
            res, note = '需確認', f'工程類職稱員額達50%以上，可能屬附表三「工程機關」（委任下限 {"5" if level == "3" else "10"}%，現依「{category}」計算）；另需業務單位50%以上辦理工程'
        else:
            res, note = '符合', '署、局具工程機關性質者依處內決定（2026-11-19）以工程機關類別計算比率' if cat.get('初判依據', '').startswith('工程類職稱') else ''
        F.append(finding('C15', '附表三附註六(一)；考試院93.11.4第10屆第107次會議', '工程機關認定（工程類職稱員額比例）', f'工程類職稱 {eng} ÷（編制員額 {total} − 首長副首長 {n_heads} − 一級單位主管 {n_first}）',
                         f'{share}%', '≥50%', res, '', note))

    # ---- C16 體例（九）
    issues = []
    for r in rows:
        b = r['備註'] or ''
        if re.search(r'得列(簡任|薦任)(?!第)', b):
            issues.append(f"{r['職稱']}：得列未載職等")
    if issues:
        F.append(finding('C16', '考試院100.12.15第11屆第167次、100.3.24第129次會議', '備註體例', '；'.join(issues[:8]), f'{len(issues)} 列', '「內○人得列○任第○職等」「內○人出缺後改置為○」', '需確認', '', '101.1.1 以後生效之編制表應依體例'))

    # ---- C17 四級機關主任秘書（十）
    if level == '4' and cnt['主任秘書'] > 0:
        exempt = bool(BASIC_LAW_EXEMPT.search(name)) or bool(BASIC_LAW_EXEMPT.search(a.get('隸屬') or ''))
        F.append(finding('C17', '考試院109.7.9第12屆第292次會議', '四級機關置主任秘書', f'機關 {name}', '置主任秘書', '限基準法第2條但書機關（國防、外交駐外、警察、檢察、調查、海巡）或原核備有案者',
                         '符合' if exempt else '需確認', '', '' if exempt else '請確認是否原經考試院核備有案（如關務署各關）'))
    return F

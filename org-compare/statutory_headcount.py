"""舊體例組織法規（員額列於條文、未另訂編制表）之法定員額解析，以及全機關「聘用／約僱」條文人數掃描。

只讀總表「條文」分頁，不改任何資料。輸出供 build_dataset.py 產生「法定員額（條文區間）」明細與指標。

列類別（雙軌制機關如警大、警專）：
  文官      官等為簡任／薦任／委任
  警察官    官等為警監／警正／警佐
  教育人員  聘任（教授、教官等依教育人員任用條例）
  警備隊    單位名稱含警衛隊／警備隊／樂隊 → 獨立參考，不計入專任合計
  聘用約僱  條文明定聘用／約僱／僱用人數 → 另列，不計入專任合計
  兼任      由他職兼任、派兼、無給職 → 不計入專任合計
"""
import re
import pandas as pd

CN = '[一二三四五六七八九十百]+'
CNUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
def cn2int(s):
    if not s: return None
    n = 0; cur = 0
    for ch in s:
        if ch == '百': n += (cur or 1) * 100; cur = 0
        elif ch == '十': n += (cur or 1) * 10; cur = 0
        elif ch in CNUM: cur = CNUM[ch]
        else: return None
    return n + cur

ITEM = re.compile(r'([一-鿿]{2,12}?)(' + CN + r')人(?:(至|或)(' + CN + r')人)?')
GRADE_RE = re.compile(r'(職務(?:均)?(?:比照)?列[^，；。]*職等[^，；。]*|(?:均為?|均列)?(?:簡任|薦任|委任|特任|警監|警正|警佐|聘任)(?:或(?:簡任|薦任|委任|警監|警正|警佐))?(?:第' + CN + r'職等(?:至第' + CN + r'職等)?)?)')
VERB_PREFIX = re.compile(r'^(?:本會|本局|本所|本館|本校|本大學|本署|本處|本中心|各組|各科|各學院|各學系|各研究所|之研究所|圖書館|班及分部|分部|學各學院|所|會|局|署|館|校)?(?:各)?(?:置|另置|各置|並置|設(?!計))?')
UNIT_RE = re.compile(r'(?:本會|本局|本所|本校|本大學|本署|本館|本處)?設([\u4e00-\u9fff（）]{2,10}?(?:室|隊|會|處|組|中心|館|部))[，、；]')
SPECIAL_UNIT_RE = re.compile(r'警衛隊|警備隊|樂隊')
CONTRACT_RE = re.compile(r'聘用人員聘用條例|約僱|僱用|聘用')

def _grade_class(grade, seg):
    g = grade or seg
    if re.search(r'警監|警正|警佐', g): return '警察官'
    if re.search(r'簡任|薦任|委任|特任', g): return '文官'
    if re.search(r'聘任|教育人員任用條例|教授|教官|講師|助教', g): return '教育人員'
    return '未註明'

def _within_clause(seg):
    """「其中秘書二人，技正十六人，職務得列簡任第十職等至第十一職等」→ [(秘書,2,條件),(技正,16,條件)]"""
    out = []
    for m in re.finditer(r'其中((?:[^，；。]*?' + CN + r'人[，、])*[^，；。]*?' + CN + r'人)[，、]?([^；。]*?(?:得列|比照|得由|由)[^；。]*)', seg):
        body, cond = m.group(1), m.group(2).strip('，、 ')
        for t, n in re.findall(r'([一-鿿]{0,6}?)(' + CN + r')人', body):
            t = t.strip('，、及與')
            out.append((t or '（本職稱）', cn2int(n), cond[:60]))
    return out

def parse_agency(art, name):
    """回傳 list of dict：單位、職稱、官等職等、下限、上限、類別、條號、寫法、其中條款、原句。"""
    sub = art[(art['機關'] == name) & (art['法規類別'] == '組織法規')]
    rows = []
    for _, r in sub.drop_duplicates(['法規名稱', '條號']).iterrows():
        text = str(r['條文內容']).replace('\n', ' ')
        um = UNIT_RE.search(text); unit = um.group(1) if um else None
        for para in re.split(r'[。]', text):
            if '人' not in para: continue
            segs = [x.strip() for x in re.split(r'[；]', para) if x.strip()]
            # 段末「均警監」「均由…兼任之」：適用於本段先前各句
            tail_grade = next((x for x in reversed(segs) if re.fullmatch(r'均?(?:警監|警正|警佐|簡任|薦任|委任)(?:或(?:警監|警正|警佐|簡任|薦任|委任))?', x)), '')
            tail_conc = any(re.search(r'^均由.{1,20}兼任', x) for x in segs)
            for seg in segs:
                gm = GRADE_RE.search(seg); grade = gm.group(1) if gm else tail_grade
                within = _within_clause(seg)
                cut = re.search(r'其中.*?(得列|比照|得由|由.{0,12}兼)', seg)
                main = seg[:cut.start()] if cut else seg
                contract = bool(CONTRACT_RE.search(seg)) and not re.search(r'必要時得依聘用', seg)
                for m in ITEM.finditer(main):
                    pre = main[:m.start()]
                    if re.search(r'(?:其中|內)$', pre): continue
                    title = re.sub(r'^.*?(?:各置|並置|另置|置)', '', m.group(1)) if re.search(r'置', m.group(1)) else VERB_PREFIX.sub('', m.group(1))
                    title = re.sub(r'^[，、及與或為]+', '', title); title = re.sub(r'各$', '', title)
                    if not title or re.fullmatch(r'[一二三四五六七八九十百]*(?:人至)?', title) or re.search(r'其中|以上|以下|得列|合計|總數|之內|員額', m.group(0)) or title.endswith(('其中', '內')): continue
                    if title.startswith(('並以', '以')) and re.search(r'兼任', seg[m.end():m.end() + 6]): continue   # 「並以醫師一人兼任主任」非職稱列
                    lo = cn2int(m.group(2)); hi = cn2int(m.group(4)) if m.group(4) else lo
                    if lo is None: continue
                    titles = [x for x in re.split(r'[及、與]', title) if x] if (re.search(r'[及、與]', title) and '或' not in title) else [title]
                    for t in titles:
                        t = re.sub(r'^[者為]+', '', t[-8:])
                        conc = (bool(re.search(r'由[^，；]{1,14}(?:兼任|派兼|聘兼)|無給職', seg)) and not re.search(r'以[^，；]{1,8}兼任', seg)) or tail_conc
                        if (unit and SPECIAL_UNIT_RE.search(unit)) or SPECIAL_UNIT_RE.search(t): cls = '警備隊'
                        elif contract: cls = '聘用約僱'
                        elif conc: cls = '兼任'
                        else: cls = _grade_class(grade, seg)
                        wc = '；'.join(f'{a} {b} 人：{c}' for a, b, c in within if a in ('（本職稱）', t) or a in t) if within else ''
                        if within and not wc: wc = '同句其中條款：' + '；'.join(f'{a} {b} 人：{c}' for a, b, c in within)
                        rows.append({'單位': unit, '職稱': t, '官等職等': grade[:40], '下限': lo, '上限': hi, '類別': cls, '條號': r['條號'], '法規': r['法規名稱'], '寫法': m.group(0), '其中條款': wc, '原句': seg[:140]})
    return rows

def summarize(rows):
    full = [x for x in rows if x['類別'] in ('文官', '警察官', '教育人員', '未註明')]
    return {'專任下限': sum(x['下限'] for x in full), '專任上限': sum(x['上限'] for x in full),
            '警備隊下限': sum(x['下限'] for x in rows if x['類別'] == '警備隊'), '警備隊上限': sum(x['上限'] for x in rows if x['類別'] == '警備隊'),
            '聘用約僱下限': sum(x['下限'] for x in rows if x['類別'] == '聘用約僱'), '聘用約僱上限': sum(x['上限'] for x in rows if x['類別'] == '聘用約僱'),
            '兼任列數': sum(1 for x in rows if x['類別'] == '兼任'), '列數': len(rows)}

CONTRACT_SENT_RE = re.compile(r'(聘用人員聘用條例|約僱|僱用|聘用)')
def scan_contract_clauses(art):
    """全機關：組織法規條文中明定聘用／約僱／僱用「人數」之句子 → {機關: [{條號, 法規, 類型, 下限, 上限, 原句}]}。
    一般機關不在組織法列聘用人數，有列者為特例（員額超過 5% 的可能原因之一）。"""
    out = {}
    org = art[art['法規類別'] == '組織法規']
    for _, r in org.drop_duplicates(['機關', '法規名稱', '條號']).iterrows():
        text = str(r['條文內容']).replace('\n', ' ')
        for sent in re.split(r'[。]', text):
            if not CONTRACT_SENT_RE.search(sent): continue
            if re.search(r'必要時得依聘用人員聘用條例', sent) and not re.search(r'約僱|僱用', sent): continue   # 編制職缺「必要時得聘用」非聘用員額
            m = re.search(r'(聘用人員聘用條例|約僱|僱用|聘用)', sent)
            after = sent[m.start():]
            nums = re.findall(r'(?:不得超過|至多)?(' + CN + r')人(?:至(' + CN + r')人)?', after)
            if not nums: continue
            if re.search(r'人兼任', after) and len(nums) == 1: continue   # 「以醫師一人兼任主任」非聘用人數
            kind = '約僱／僱用' if re.search(r'約僱|僱用', sent) else '聘用'
            lo = min(cn2int(a) for a, b in nums); hi = max(cn2int(b or a) for a, b in nums)
            cap = bool(re.search(r'不得超過|至多|上限', after))
            out.setdefault(r['機關'], []).append({'條號': r['條號'], '法規': r['法規名稱'], '類型': kind, '下限': 0 if cap else lo, '上限': hi, '原句': sent.strip()[:160]})
    return out

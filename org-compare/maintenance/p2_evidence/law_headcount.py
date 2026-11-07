"""舊體例組織法規（員額列於條文）之職稱員額解析：輸出每職稱之下限／上限、官等職等、條號、原句。只讀條文表，不改任何資料。"""
import re, json, sys, collections
import pandas as pd
S = '/tmp/claude-0/-home-user-manpower/4c1fe7a7-cb5e-55f8-b5c1-b63a2b48cd38/scratchpad'
R = '/home/user/manpower/org-compare'
sys.path.insert(0, R)
from build_dataset import cn_int
art = pd.read_excel(f'{R}/data/組織法編制表_總表_20261031.xlsx', '條文', dtype=str)
CN = r'[一二三四五六七八九十百]+'
GRADE = r'(?:職務(?:均)?(?:比照)?列)?(?:簡任|薦任|委任|特任|警監|警正|警佐|聘任)?(?:第' + CN + r'職等(?:至(?:簡任|薦任)?第' + CN + r'職等)?)?(?:或(?:簡任|薦任|委任|警監|警正|警佐)(?:第' + CN + r'職等(?:至第' + CN + r'職等)?)?)*'
ITEM = re.compile(r'([一-鿿]{2,12}?)(' + CN + r')人(?:(至|或)(' + CN + r')人)?')
SKIP_TITLE = re.compile(r'^(其中|置|各置|另置|均|並|得|分別|合計|共|以上|以下|內|前項|本|依|由|及|或)')
def parse_agency(name, laws=None):
    sub = art[(art['機關'] == name) & (art['法規類別'] == '組織法規')]
    if laws: sub = sub[sub['法規名稱'].isin(laws)]
    rows = []
    for _, r in sub.drop_duplicates(['法規名稱', '條號']).iterrows():
        text = str(r['條文內容']).replace('\n', ' ')
        for para in re.split(r'[。]', text):
            if '人' not in para: continue
            # 「其中 N 人得列／由…兼任」等子句不產生職稱列，另記為備註
            for seg in re.split(r'[；]', para):
                seg = seg.strip()
                if not seg: continue
                grade_m = re.search(r'(職務(?:均)?(?:比照)?列[^，；。]*職等[^，；。]*|(?:均為?|均列)?(?:簡任|薦任|委任|特任|警監|警正|警佐|聘任)(?:或(?:簡任|薦任|委任|警監|警正|警佐))?(?:第' + CN + r'職等(?:至第' + CN + r'職等)?)?)', seg)
                grade = grade_m.group(1) if grade_m else ''
                # 「其中…得列／比照…」子句整段不產生職稱列（例：其中秘書二人，技正十六人，職務得列簡任）
                cut = re.search(r'其中.*?(得列|比照|得由|由.{0,12}兼)', seg)
                seg_main = seg[:cut.start()] if cut else seg
                seg_rest = seg[cut.start():] if cut else ''
                for m in ITEM.finditer(seg_main):
                    pre = seg_main[:m.start()]
                    if re.search(r'(?:其中|內)$', pre): continue
                    title = re.sub(r'^(?:本會|本局|本所|本館|本校|本大學|本署|本處|各組|各科|各學院|各學系|各研究所|之研究所|圖書館|班及分部|分部|學各學院)?(?:各)?(?:置|另置|各置|並置|設(?!計))?', '', m.group(1))
                    title = re.sub(r'^[，、及與或]+', '', title); title = re.sub(r'各$', '', title)
                    if re.fullmatch(r'[一二三四五六七八九十百]+人至', title) or re.fullmatch(r'[一二三四五六七八九十百]*', title): continue
                    if not title or SKIP_TITLE.match(title) or re.search(r'其中|以上|以下|得列|合計|總數|之內|員額', m.group(0)) or title.endswith(('其中', '內')): continue
                    lo = cn_int(m.group(2)); hi = cn_int(m.group(4)) if m.group(4) else lo
                    if lo is None: continue
                    note = ''
                    if re.search(r'由[^，；]{1,14}(?:兼任|派兼|聘兼)|無給職', seg) and not re.search(r'以[^，；]{1,8}兼任', seg): note = '兼任／無給職（不計入專任）'
                    if re.search(r'得列|其中', seg): note += ('；' if note else '') + '條文另有「其中…得列」或條件（見原句）'
                    titles = [x for x in re.split(r'[及、與]', title) if x] if ('各' in m.group(0) or re.search(r'[及、與]', title)) and not re.search(r'或', title) else [title]
                    for title in titles:
                      rows.append({'機關': name, '法規': r['法規名稱'], '條號': r['條號'], '職稱': title[-6:] if len(title) > 6 else title, '官等職等（原句摘）': grade[:40], '下限': lo, '上限': hi, '寫法': m.group(0), '備註': note + (('；其中條款：' + seg_rest[:60]) if seg_rest else ''), '原句': seg[:120]})
    return rows
if __name__ == '__main__':
    out = {}
    for name in ['行政院公共工程委員會', '法務部調查局', '法務部調查局幹部訓練所', '中央警察大學', '臺灣警察專科學校', '法務部行政執行署', '法務部矯正署', '國立海洋生物博物館', '國立臺灣藝術教育館']:
        rows = parse_agency(name)
        full = [x for x in rows if not x['備註'].startswith('兼任')]
        out[name] = {'rows': rows, '專任下限合計': sum(x['下限'] for x in full), '專任上限合計': sum(x['上限'] for x in full), '兼任列': [x for x in rows if x['備註'].startswith('兼任')]}
        print(f"\n## {name}：{len(rows)} 列；專任下限 {out[name]['專任下限合計']}／上限 {out[name]['專任上限合計']}；兼任／無給職 {len(out[name]['兼任列'])} 列")
        for x in rows: print(f"  {x['條號']:<7}{x['職稱']:<8}{x['下限']:>3}–{x['上限']:<3} {x['官等職等（原句摘）'][:28]:<30}{x['備註'][:30]:<30}| {x['寫法']}")
    json.dump(out, open(f'{S}/diag/law_headcount.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

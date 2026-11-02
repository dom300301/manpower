#!/usr/bin/env python3
"""
解析主計總處中央政府總預算案參考表「中央政府機關總員額法員額彙計表」（raw/stats/dgbas/，100～116 年度），
追加至 data/headcount.csv（先備份），並把來源追加到 data/headcount_sources.json。
重複執行時會先移除先前由本腳本寫入的列（source_name 含「總員額法員額彙計表」）再追加。
執行：python3 -I contract-manpower/scripts/build_dgbas_headcount.py
"""
import csv, json, os, re, sys, glob, datetime, shutil, warnings
warnings.filterwarnings('ignore')

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RAW = os.path.join(BASE, 'raw', 'stats', 'dgbas')
DATA = os.path.join(BASE, 'data')
CSV = os.path.join(DATA, 'headcount.csv')
SRC = os.path.join(DATA, 'headcount_sources.json')
TODAY = datetime.date.today().isoformat()
FIELDS = ['year', 'year_ad', 'scope', 'agency_group', 'category', 'measure', 'value', 'unit',
          'source_name', 'source_url', 'note']
COLS = ['職員', '警察', '法警', '駐警', '工友', '技工', '駕駛', '聘用', '約僱', '駐外雇員', '合計']
C2 = ['駐警', '工友', '技工', '駕駛', '聘用', '約僱', '駐外雇員']
DETAIL_NAME = {'駐警': '駐衛警察', '駐外雇員': '駐外雇員'}
TAG = '總員額法員額彙計表'

# 各年度檔案來源（版本 b=預算案、c=法定預算）
URLS = {
    100: ('c', 'https://ws.dgbas.gov.tw/public/data/dgbas01/100/100ctab/100c機關總員額法員額彙計表.xls',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=103533'),
    101: ('b', 'https://ws.dgbas.gov.tw/public/data/dgbas01/101/101btab/101b機關總員額法員額彙計表.xls',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=103577'),
    102: ('b', 'https://ws.dgbas.gov.tw/public/data/dgbas01/102/102btab/102b中央政府機關總員額法員額彙計表.xls',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=103603'),
    103: ('b', 'https://ws.dgbas.gov.tw/public/data/dgbas01/103/103btab/103b中央政府機關總員額法員額彙計表.xls',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=103638'),
    104: ('b', 'https://ws.dgbas.gov.tw/public/data/dgbas01/104/104btab/104b中央政府機關總員額法員額彙計表.xls',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=103672'),
    105: ('b', 'https://ws.dgbas.gov.tw/public/data/dgbas01/105/105btab/105b中央政府機關總員額法員額彙計表.xls',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=103706'),
    106: ('b', 'https://ws.dgbas.gov.tw/public/data/dgbas01/106/106btab/106b中央政府機關總員額法員額彙計表.xls',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=103742'),
    107: ('b', 'https://ws.dgbas.gov.tw/public/data/dgbas01/107/107btab/107b機關總員額法員額彙計表.xls',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=103776'),
    108: ('b', 'https://ws.dgbas.gov.tw/public/data/dgbas01/108/108btab/108b機關總員額法員額彙計表.xls',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=103788'),
    109: ('b', 'https://ws.dgbas.gov.tw/public/data/dgbas01/109/109btab/109b機關總員額法員額彙計表.xls',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=104328'),
    110: ('b', 'https://ws.dgbas.gov.tw/public/data/dgbas01/110/110btab/110b機關總員額法員額彙計表.xls',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=103831'),
    111: ('b', 'https://ws.dgbas.gov.tw/public/data/dgbas01/111/111btab/111b機關總員額法員額彙計表.xlsx',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=103801'),
    112: ('b', 'https://ws.dgbas.gov.tw/public/data/dgbas01/112/112btab/112b機關總員額法員額彙計表.xlsx',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=227801'),
    113: ('b', 'https://ws.dgbas.gov.tw/001/Upload/461/relfile/11333/231560/b機關總員額法員額彙計表.xlsx',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=231560'),
    114: ('b', 'https://ws.dgbas.gov.tw/001/Upload/461/relfile/11333/233556/b機關總員額法員額彙計表.xlsx',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=233556'),
    115: ('b', 'https://ws.dgbas.gov.tw/001/Upload/461/relfile/11333/235176/b機關總員額法員額彙計表.xlsx',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=235176'),
    116: ('b', 'https://ws.dgbas.gov.tw/001/Upload/461/relfile/11333/236582/b機關總員額法員額彙計表.xlsx',
          'https://www.dgbas.gov.tw/News_Content.aspx?n=3625&s=236582'),
}


def load(path):
    if path.lower().endswith('.xls'):
        import xlrd
        sh = xlrd.open_workbook(path).sheet_by_index(0)
        return [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]
    import openpyxl
    ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    return [list(r) for r in ws.iter_rows(values_only=True)]


def norm(s):
    if s is None:
        return ''
    return re.sub(r'(_x000D_|[\s　])+', '', str(s))


def num(v):
    if v is None or v == '' or v == '-':
        return 0
    if isinstance(v, (int, float)):
        return int(round(v))
    s = str(v).replace(',', '').strip()
    if s in ('', '-', '－'):
        return 0
    return int(round(float(s)))


def is_num(v):
    if isinstance(v, (int, float)) and v != '':
        return True
    return bool(re.match(r'^[\d,]+$', str(v).strip())) if v not in (None, '') else False


def parse(path):
    """回傳 [(機關名稱, 類別區塊 '1+2'/'3'/'4'/'5'/None, {欄位: 數值})]，以及備註文字。"""
    rows = load(path)
    hi = next(i for i, r in enumerate(rows) if any(norm(c) == '職員' for c in r))
    hdr = [norm(c) for c in rows[hi]]
    cidx = {}
    for name in COLS:
        for j, h in enumerate(hdr):
            if h.replace('衛', '') == name:
                cidx[name] = j
                break
    assert len(cidx) == 11, (path, hdr)
    lc = cidx['職員'] - 1
    out, block, pending, notes, just_added = [], None, None, [], False
    for r in rows[hi + 1:]:
        label = norm(r[lc])
        vals = [r[cidx[c]] for c in COLS]
        numeric = any(is_num(v) for v in vals)
        if label.startswith('備註'):
            notes = [' '.join(str(c) for c in rr if c not in (None, '')) for rr in rows[rows.index(r):]]
            break
        if label and not numeric:
            if '第一類及第二類' in label:
                block = '1+2'
            elif label.startswith('第三類'):
                block = '3'
            elif label.startswith('第四類'):
                block = '4'
            elif label.startswith('第五類'):
                block = '5'
            if pending is not None:
                pending += label          # 機關名稱跨兩列、數字在其後
            elif just_added and len(label) <= 4 and not label.startswith('第'):
                out[-1] = (out[-1][0] + label, out[-1][1], out[-1][2])  # 名稱折行到數字列之後
            else:
                pending = label
            just_added = False
            continue
        if not label and numeric and pending:
            label = pending
        if not label:
            just_added = False
            continue
        pending = None
        just_added = True
        if label.startswith('第三類'):
            block = '3'
        elif label.startswith('第四類'):
            block = '4'
        elif label.startswith('第五類'):
            block = '5'
        out.append((label, block, {c: num(v) for c, v in zip(COLS, vals)}))
    return out, '\n'.join(notes)


def is_top(label):
    """主管機關層級列：「○○主管」，以及 100～107 年度獨立列示的「省市地方政府」（臺灣省政府、省諮議會、福建省政府）。"""
    return label.endswith('主管') or label == '省市地方政府'


def main():
    new_rows, sources, summary = [], [], {}
    for y in sorted(URLS):
        ver, url, page = URLS[y]
        files = glob.glob(os.path.join(RAW, f'dgbas_總員額法員額彙計表_{y}{ver}.xls*'))
        if not files:
            print(y, '缺檔'); continue
        path = files[0]
        res, notes = parse(path)
        ver_name = '法定預算' if ver == 'c' else '預算案'
        sname = f'主計總處 {y}年度中央政府總預算{ver_name} 參考表 中央政府機關總員額法員額彙計表'
        if y <= 109:
            law = '108.12.31修法前分類定義（第一類含公立醫院職員；總數高限173,000、第一類86,700、第二類41,200）'
        else:
            law = '108.12.31修法後分類定義（第一類不含公立醫院職員；總數高限160,900、第一類74,600、第二類40,100）'
        base_note = f'預算員額（{ver_name}）；{law}'
        if ver == 'c':
            base_note += '；100年度預算案頁無本表，採法定預算版'

        def add(agency, category, value, extra=''):
            new_rows.append({'year': y, 'year_ad': y + 1911, 'scope': '中央', 'agency_group': agency,
                             'category': category, 'measure': '預算員額', 'value': int(value), 'unit': '人',
                             'source_name': sname, 'source_url': url,
                             'note': base_note + (('；' + extra) if extra else '')})

        tot = next(v for l, b, v in res if l.startswith('合計'))
        c12 = next(v for l, b, v in res if l.startswith('第一類及第二類'))
        c3 = next(v for l, b, v in res if l.startswith('第三類'))
        c4 = next(v for l, b, v in res if l.startswith('第四類'))
        c5 = next(v for l, b, v in res if l.startswith('第五類'))
        c1v, c2v = c12['職員'], sum(c12[k] for k in C2)
        assert c1v + c2v + c3['合計'] + c4['合計'] + c5['合計'] == tot['合計'], y
        # 主管機關列加總檢查
        for blk, ref in (('1+2', c1v + c2v), ('3', c3['合計']), ('4', c4['合計']), ('5', c5['合計'])):
            s = sum((v['職員'] + sum(v[k] for k in C2)) if blk == '1+2' else v['合計']
                    for l, b, v in res if is_top(l) and b == blk)
            if s != ref:
                print(f'  警告 {y} 第{blk}類 主管機關加總 {s} != {ref}')
        ag = '總員額法適用機關合計'
        add(ag, '總員額法員額總計', tot['合計'])
        for c in COLS[:-1]:
            add(ag, f'總員額法員額總計－{DETAIL_NAME.get(c, c)}', tot[c], '各類員額合計之細項')
        add(ag, '總員額法第一類員額', c1v, '表內「第一類人員」欄（職員）')
        add(ag, '總員額法第二類員額', c2v, '表內「第二類人員」駐警+工友+技工+駕駛+聘用+約僱+駐外雇員')
        for c in C2:
            add(ag, f'總員額法第二類員額－{DETAIL_NAME.get(c, c)}', c12[c])
        add(ag, '總員額法第二類員額－聘僱人員(聘用+約僱)', c12['聘用'] + c12['約僱'], '由細項加總')
        add(ag, '總員額法第二類員額－工友(含技工、駕駛)', c12['工友'] + c12['技工'] + c12['駕駛'], '由細項加總')
        for k, cv in (('三', c3), ('四', c4), ('五', c5)):
            add(ag, f'總員額法第{k}類員額', cv['合計'])
            for c in COLS[:-1]:
                if cv[c]:
                    add(ag, f'總員額法第{k}類員額－{DETAIL_NAME.get(c, c)}', cv[c])
        # 主管機關
        for l, b, v in res:
            if not is_top(l):
                continue
            name = l[:-2] if l.endswith('主管') else l
            ex = '主管機關列（含所屬機關）；主管機關歸類依該年度表格'
            if b == '1+2':
                add(name, '總員額法第一類員額', v['職員'], ex)
                add(name, '總員額法第二類員額', sum(v[k] for k in C2), ex)
                for c in C2:
                    if v[c]:
                        add(name, f'總員額法第二類員額－{DETAIL_NAME.get(c, c)}', v[c], ex)
                add(name, '總員額法第二類員額－聘僱人員(聘用+約僱)', v['聘用'] + v['約僱'], ex + '；由細項加總')
                add(name, '總員額法第二類員額－工友(含技工、駕駛)', v['工友'] + v['技工'] + v['駕駛'], ex + '；由細項加總')
            elif b in ('3', '4', '5'):
                k = {'3': '三', '4': '四', '5': '五'}[b]
                add(name, f'總員額法第{k}類員額', v['合計'], ex)
                for c in COLS[:-1]:
                    if v[c]:
                        add(name, f'總員額法第{k}類員額－{DETAIL_NAME.get(c, c)}', v[c], ex)
        summary[y] = {'總計': tot['合計'], '第一類': c1v, '第二類': c2v, '第三類': c3['合計'], '第四類': c4['合計'],
                      '第五類': c5['合計'], '聘用': c12['聘用'], '約僱': c12['約僱'], '駐警': c12['駐警'],
                      '工友': c12['工友'], '技工': c12['技工'], '駕駛': c12['駕駛'], '駐外雇員': c12['駐外雇員']}
        pdf = glob.glob(os.path.join(RAW, f'dgbas_總員額法員額彙計表_{y}{ver}.pdf'))
        sources.append({'name': sname, 'download_url': url, 'page_url': page, 'download_date': TODAY,
                        'years_covered': str(y),
                        'local_path': 'contract-manpower/raw/stats/dgbas/' + os.path.basename(path)
                        + ((' ; ' + 'contract-manpower/raw/stats/dgbas/' + os.path.basename(pdf[0])) if pdf else ''),
                        'parse_method': 'xlrd/openpyxl 讀第一工作表；合計列、第一類及第二類人員列、第三～五類人員列、各「主管」列',
                        'note': base_note})
        print(y, summary[y])

    # 寫入 csv（先備份）
    bak = CSV + '.bak_' + datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    shutil.copy2(CSV, bak)
    old = [r for r in csv.DictReader(open(CSV, encoding='utf-8-sig')) if TAG not in r['source_name']]
    with open(CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in old + new_rows:
            w.writerow(r)
    print(f'備份 {bak}；原列 {len(old)}，新增 {len(new_rows)}，合計 {len(old) + len(new_rows)}')
    # sources
    srcs = [s for s in json.load(open(SRC, encoding='utf-8')) if TAG not in s['name']]
    srcs += sources
    with open(SRC, 'w', encoding='utf-8') as f:
        json.dump(srcs, f, ensure_ascii=False, indent=1)
    print('sources', len(srcs))
    with open(os.path.join(DATA, 'dgbas_總員額法摘要.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

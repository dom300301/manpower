#!/usr/bin/env python3
"""契約人力制度查詢系統　建檔程式

讀取 data/ 內的資料檔，嵌入 template.html，產出 output/index.html（離線單檔網頁）。
用法：python3 build.py            → 產出 output/index.html
      python3 build.py --check    → 只檢查資料檔格式，不產出

資料檔（缺少者會以空資料建檔並在畫面提示）：
  data/laws.json        法規全文與沿革
  data/timeline.json    法制沿革時間軸
  data/drafts.json      歷次專法草案
  data/comparison.json  各類人員權益對照
  data/headcount.csv    員額統計時間序列
  data/local_gov.json   22 縣市契約人力樣態
  data/reports.json     立法院法制局／預算中心報告（補抓後）
  data/reports_oversight.json 監察院／審計部文件（補抓後）
  data/literature.json  學術文獻（補抓後）
"""
import csv
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
OUT = os.path.join(HERE, 'output')


def load_json(name, default):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        print(f'  [缺] {name}（以空資料代替）')
        return default
    with open(path, encoding='utf-8-sig') as f:
        obj = json.load(f)
    # 容許 {"meta":..., "laws":[...]} 這類包一層的格式（comparison.json 除外）
    if isinstance(obj, dict) and 'dimensions' not in obj:
        lists = [v for v in obj.values() if isinstance(v, list)]
        if lists:
            obj = max(lists, key=len)
    n = len(obj) if isinstance(obj, list) else len(obj.get('dimensions', obj))
    print(f'  [讀] {name}：{n} 筆')
    return obj


def load_headcount():
    path = os.path.join(DATA, 'headcount.csv')
    if not os.path.exists(path):
        print('  [缺] headcount.csv（以空資料代替）')
        return []
    rows = []
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            try:
                r['value'] = float(str(r.get('value', '')).replace(',', ''))
            except ValueError:
                continue
            for k in ('year', 'year_ad'):
                try:
                    r[k] = int(float(r[k]))
                except (ValueError, KeyError, TypeError):
                    r[k] = None
            if r['year'] is None and r['year_ad']:
                r['year'] = r['year_ad'] - 1911
            if r['year_ad'] is None and r['year']:
                r['year_ad'] = r['year'] + 1911
            rows.append(r)
    print(f'  [讀] headcount.csv：{len(rows)} 筆')
    rows += derived_rows(rows)
    return rows


def derived_rows(rows):
    """為「目的二對照」合成可並列的序列（來源列不動，合成列 note 標示「build.py 合成」）：
    1. 約用人員各年第 4 季底人數 → 併入「中央／行政院所屬／實有人數」群組，方便與聘僱、事務性人力同圖。
    2. 第二類員額近似值 = 聘用 + 約僱 + 事務性人力（行政院所屬與地方政府合計）。
    """
    out = []
    q4 = {}
    for r in rows:
        if r['category'] == '臨時人員(約用)' and r['agency_group'].startswith('行政院所屬') and '第4季' in (r.get('note') or ''):
            q4[(r['agency_group'], r['year'])] = r
    names = {'行政院所屬合計': '約用人員(合計,Q4)', '行政院所屬-行政機關': '約用人員(行政機關,Q4)',
             '行政院所屬-公立學校': '約用人員(公立學校,Q4)', '行政院所屬-公立衛生醫療機構': '約用人員(醫療機構,Q4)'}
    for (g, y), r in q4.items():
        if g in names:
            out.append({**r, 'agency_group': '行政院所屬', 'measure': '實有人數', 'category': names[g],
                        'note': 'build.py 合成：取年報附表 6 第 4 季底全日工時人數；' + (r.get('note') or '')})
    for scope, group in (('中央', '行政院所屬'), ('地方', '地方政府合計')):
        by_year = {}
        for r in rows:
            if r['scope'] == scope and r['agency_group'] == group and r['measure'] == '實有人數' and r['category'] in ('聘用', '約僱', '技工工友駐衛警(事務性人力)'):
                by_year.setdefault(r['year'], {})[r['category']] = r
        for y, d in by_year.items():
            if len(d) == 3:
                base = d['聘用']
                out.append({**base, 'category': '第二類員額近似(聘用+約僱+事務性)', 'value': sum(x['value'] for x in d.values()),
                            'note': 'build.py 合成：聘用＋約僱＋技工工友駐衛警；總員額法第二類定義為聘僱人員、駐衛警察及工友，此為實有人數近似值'})
    print(f'  [合成] 目的二對照序列：{len(out)} 筆')
    return out


def main():
    check_only = '--check' in sys.argv
    print('讀取資料檔…')
    payload = {
        'built': date.today().isoformat(),
        'laws': load_json('laws.json', []),
        'timeline': load_json('timeline.json', []),
        'drafts': load_json('drafts.json', []),
        'comparison': load_json('comparison.json', {'meta': {'personnel_types': []}, 'dimensions': []}),
        'headcount': load_headcount(),
        'local_gov': load_json('local_gov.json', []),
        'reports': load_json('reports.json', []) + load_json('reports_oversight.json', []),
        'literature': load_json('literature.json', []),
    }
    if check_only:
        print('檢查完成。')
        return
    with open(os.path.join(HERE, 'template.html'), encoding='utf-8') as f:
        tpl = f.read()
    blob = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    blob = blob.replace('</script', '<\\/script')  # 避免提前結束 script 標籤
    html = tpl.replace('/*__DATA__*/null', blob)
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, 'index.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'已產出 {out}（{os.path.getsize(out) / 1024:.0f} KB）')


if __name__ == '__main__':
    main()

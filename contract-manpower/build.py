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
    return rows


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

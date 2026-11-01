#!/usr/bin/env python3
"""
建檔：檢核結果 + 職稱列等對照表 → 查詢網頁 output/index.html（離線單檔；放到 GitHub Pages 即線上版）

用法：
  python3 grade-check/check_grades.py          # 先產生 output/check_results.json
  python3 grade-check/build_grade_site.py      # 再嵌入網頁
資料以 gzip+base64 嵌入，瀏覽器用 DecompressionStream 解壓（Chrome/Edge 80+、Safari 16.4+、Firefox 113+）。
"""
import argparse
import base64
import csv
import datetime as dt
import gzip
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', default=os.path.join(HERE, 'output', 'check_results.json'))
    ap.add_argument('--out', default=os.path.join(HERE, 'output', 'index.html'))
    ap.add_argument('--template', default=os.path.join(HERE, 'grade_template.html'))
    a = ap.parse_args()
    res = json.load(open(a.results, encoding='utf-8'))
    titles = json.load(open(os.path.join(HERE, 'rules', 'title_grades.json'), encoding='utf-8'))
    ratio = json.load(open(os.path.join(HERE, 'rules', 'ratio_table.json'), encoding='utf-8'))
    cats = list(csv.DictReader(open(os.path.join(HERE, 'rules', 'agency_category.csv'), encoding='utf-8-sig')))
    data = {'meta': res['meta'], 'results': res['results'], 'titles': titles, 'ratio': ratio, 'categories': cats,
            'built': dt.datetime.now().strftime('%Y-%m-%d %H:%M')}
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    payload = base64.b64encode(gzip.compress(raw, 9)).decode('ascii')
    html = open(a.template, encoding='utf-8').read().replace('/*__DATA__*/', payload)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, 'w', encoding='utf-8').write(html)
    print(f'完成：{a.out}（{os.path.getsize(a.out) / 1e6:.1f} MB；機關 {len(res["results"])}，原始資料 {len(raw) / 1e6:.1f} MB）')


if __name__ == '__main__':
    main()

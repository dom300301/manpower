#!/usr/bin/env python3
"""
verify_oversight.py — 驗證 data/reports_oversight.json 與 data/literature.json：
  1. reports_oversight.json：每筆必備欄位（id, org, case_no, date, title, url, local_path,
     agencies_involved, personnel_types, summary, findings, recommendations, numbers）是否齊全、
     summary 是否 ≤300 字、findings/recommendations 是否為非空清單、local_path（含 extra_files）是否存在。
  2. literature.json：每筆必備欄位（title, author, year, school, degree, abstract, keywords, url,
     findings_relevant）是否齊全、year 是否在近 15 年內（以 2026 為基準）、abstract 是否非空、
     若有 local_path 是否存在。
結果寫入 research/03_法制沿革與草案分析.md 末尾「驗證結果（verify_oversight.py）」段（若已存在則整段取代）。

用法：python3 -I scripts/verify_oversight.py [--root contract-manpower]
"""
import argparse, json, os, re, datetime as dt

REQ_R = ['id', 'org', 'case_no', 'date', 'title', 'url', 'local_path', 'agencies_involved',
         'personnel_types', 'summary', 'findings', 'recommendations', 'numbers']
REQ_L = ['title', 'author', 'year', 'school', 'degree', 'abstract', 'keywords', 'url', 'findings_relevant']
HEAD = '## 驗證結果（verify_oversight.py）'


def check_reports(root):
    p = os.path.join(root, 'data', 'reports_oversight.json')
    data = json.load(open(p, encoding='utf-8'))
    rows, ok = [], 0
    for r in data['reports']:
        probs = []
        for k in REQ_R:
            if k not in r or r[k] in ('', None):
                probs.append(f'缺 {k}')
        if len(r.get('summary', '')) > 300:
            probs.append(f'summary {len(r["summary"])} 字 >300')
        if not r.get('findings'):
            probs.append('findings 空')
        if not isinstance(r.get('numbers'), list):
            probs.append('numbers 非清單')
        paths = [r.get('local_path')] + [x.get('local_path') for x in r.get('extra_files', [])]
        for lp in paths:
            if lp and not os.path.exists(os.path.join(root, lp)):
                probs.append(f'檔案不存在 {lp}')
        if not probs:
            ok += 1
        rows.append((r.get('id', '?'), r.get('case_no', ''), '、'.join(probs) or '通過'))
    return rows, ok, len(data['reports'])


def check_literature(root):
    p = os.path.join(root, 'data', 'literature.json')
    data = json.load(open(p, encoding='utf-8'))
    items = data['items'] if isinstance(data, dict) else data
    rows, ok = [], 0
    this_year = 2026
    for r in items:
        probs = []
        for k in REQ_L:
            if k not in r or r[k] in ('', None, []):
                probs.append(f'缺 {k}')
        try:
            y = int(str(r.get('year', ''))[:4])
            if this_year - y > 15:
                probs.append(f'year {y} 超過 15 年')
        except ValueError:
            probs.append('year 非年份')
        if r.get('abstract_source') and r['abstract_source'] != '原文':
            probs.append(f'摘要來源：{r["abstract_source"]}')
        lp = r.get('local_path')
        if lp and not os.path.exists(os.path.join(root, lp)):
            probs.append(f'檔案不存在 {lp}')
        hard = [x for x in probs if not x.startswith('摘要來源')]
        if not hard:
            ok += 1
        rows.append((r.get('title', '?')[:40], str(r.get('year', '')), '、'.join(probs) or '通過'))
    return rows, ok, len(items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    r_rows, r_ok, r_n = check_reports(root)
    l_rows, l_ok, l_n = check_literature(root)

    out = [HEAD, '',
           f'執行時間：{dt.datetime.now():%Y-%m-%d %H:%M}；'
           f'reports_oversight.json {r_ok}/{r_n} 筆通過；literature.json {l_ok}/{l_n} 筆通過（「摘要來源」為提示，不計入未通過）。',
           '', '### reports_oversight.json', '', '| id | 案號 | 結果 |', '|---|---|---|']
    out += [f'| {i} | {c} | {res} |' for i, c, res in r_rows]
    out += ['', '### literature.json', '', '| 題名 | 年 | 結果 |', '|---|---|---|']
    out += [f'| {t} | {y} | {res} |' for t, y, res in l_rows]
    text = '\n'.join(out) + '\n'

    md = os.path.join(root, 'research', '03_法制沿革與草案分析.md')
    body = open(md, encoding='utf-8').read()
    if HEAD in body:
        body = body[:body.index(HEAD)].rstrip() + '\n\n' + text
    else:
        body = body.rstrip() + '\n\n' + text
    open(md, 'w', encoding='utf-8').write(body)
    print(text)


if __name__ == '__main__':
    main()

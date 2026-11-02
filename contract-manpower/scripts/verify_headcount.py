#!/usr/bin/env python3
"""驗證 data/headcount.csv：必要欄位齊全、年份合理、同一來源同年同類別無重複。
執行：python3 -I contract-manpower/scripts/verify_headcount.py"""
import csv, os, sys, collections
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PATH = os.path.join(BASE, 'data', 'headcount.csv')
REQUIRED = ['year', 'year_ad', 'scope', 'agency_group', 'category', 'measure', 'value', 'unit', 'source_name', 'source_url']
SCOPES = {'中央', '地方', '全國'}
MEASURES = {'預算員額', '現有員額', '實際人數', '實有人數'}
errors, warns = [], []
rows = list(csv.DictReader(open(PATH, encoding='utf-8-sig')))
keys = collections.Counter()
for i, r in enumerate(rows, start=2):
    for f in REQUIRED:
        if r.get(f, '') == '':
            errors.append(f'第{i}列 缺欄位 {f}')
    try:
        y = int(r['year']); ad = int(r['year_ad'])
        if not (80 <= y <= 116):
            errors.append(f'第{i}列 年份不合理 {y}')
        if ad != y + 1911:
            errors.append(f'第{i}列 year_ad 與 year 不符')
    except ValueError:
        errors.append(f'第{i}列 年份非整數')
    try:
        v = int(r['value'])
        if v < 0:
            errors.append(f'第{i}列 數值為負')
        if v > 2_000_000:
            warns.append(f'第{i}列 數值異常大 {v}')
    except ValueError:
        errors.append(f'第{i}列 value 非整數')
    if r['scope'] not in SCOPES:
        errors.append(f'第{i}列 scope 不在允許值 {r["scope"]}')
    if r['measure'] not in MEASURES:
        errors.append(f'第{i}列 measure 不在允許值 {r["measure"]}')
    keys[(r['source_name'], r['year'], r['scope'], r['agency_group'], r['category'], r['measure'], r['note'])] += 1
dups = [(k, c) for k, c in keys.items() if c > 1]
for k, c in dups:
    errors.append(f'重複 {c} 次: {k[:6]}')
# 摘要
by_src = collections.Counter(r['source_name'].split(' ')[0] for r in rows)
years = sorted({int(r['year']) for r in rows})
print(f'總列數 {len(rows)}；年份範圍 {years[0]}-{years[-1]}；來源機關別列數 {dict(by_src)}')
print(f'錯誤 {len(errors)} 筆；警告 {len(warns)} 筆')
for e in errors[:30]:
    print('  ERROR', e)
for w in warns[:10]:
    print('  WARN', w)
sys.exit(1 if errors else 0)

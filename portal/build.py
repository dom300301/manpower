#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""整合入口（第一層）建檔程式 —— 概念驗證版

做什麼：
  唯讀取用四個現行系統（第二層）已產出的 index.html，把內嵌資料解出來，
  以「機關代碼」為主鍵彙整成一份小型整合資料，再套入 template.html 產生
  portal/output/index.html（單一檔案、可離線開啟）。

不做什麼：
  不修改 org-compare/、grade-check/、contract-manpower/、staffing/ 任何檔案。

用法：
  python3 portal/build.py                    # 產生 portal/output/index.html
  python3 portal/build.py --artifact 目錄     # 另外輸出預覽用版本（資料與頁面分開）
  python3 portal/build.py --extra 某檔.csv    # 改用指定的「新增人力資料」檔（測試用）
"""
import argparse
import base64
import collections
import csv
import gzip
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent

# 新增人力資料接口（約用、承攬、派遣等）的欄位與允許值
EXTRA_COLUMNS = ['年度', '基準日', '機關代碼', '機關名稱', '人力類別', '口徑', '人數', '來源', '備註']
EXTRA_TYPES = ['約用', '勞務承攬', '勞動派遣', '聘用', '約僱', '技工', '工友', '駕駛', '其他']
EXTRA_SCOPES = ['本機關', '含所屬']


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def json_after(text, marker):
    """從 marker 之後第一個 { 開始解析一個 JSON 物件。"""
    i = text.index(marker)
    obj, _ = json.JSONDecoder().raw_decode(text[text.index('{', i):])
    return obj


# ---------- 讀取第二層四個系統的產出（唯讀） ----------
def load_org():
    s = read('org-compare/output/index.html')
    m = re.search(r'<script id="data"[^>]*>(.*?)</script>', s, re.S)
    return json.loads(gzip.decompress(base64.b64decode(m.group(1).strip())))


def load_grade():
    s = read('grade-check/output/index.html')
    b = re.search(r"const B64='([^']+)'", s).group(1)
    return json.loads(gzip.decompress(base64.b64decode(b)))


def load_contract():
    return json_after(read('contract-manpower/output/index.html'), 'DATA')


def load_staffing():
    s = read('staffing/output/index.html')
    return json_after(s, 'D = {' if 'D = {' in s else 'D={')


# ---------- 彙整 ----------
def build_agencies(org, grade):
    gres = {r['機關']: r for r in grade['results']}
    out = []
    for a in org['agencies']['agencies']:
        k = a.get('指標') or {}
        g = gres.get(a['機關'])
        laws = a.get('組織法規來源') or []
        rec = {
            'code': a['機關代碼'], 'name': a['機關'], 'min': a['部會'],
            'lv': int(a['層級']), 'up': a.get('隸屬'), 'type': a.get('類型'),
            'law': a.get('組織法規名稱'),
            'lawUrl': (laws[0].get('連結') if laws and isinstance(laws[0], dict) else None) or a.get('組織法規連結'),
            'tblUrl': a.get('編制表來源'),
            'hc': k.get('員額合計'), 'hcMin': k.get('員額合計_min'), 'hcMax': k.get('員額合計_max'),
            'k': k.get('簡任員額'), 'j': k.get('薦任員額'), 'w': k.get('委任員額'),
            'units': k.get('單位數'), 'capClause': k.get('聘用約僱上限_條文'),
            'chk': a.get('驗算結果'), 'cmp': bool(a.get('可比較')), 'status': a.get('資料狀態'),
            'special': a.get('特殊類別'),
        }
        if g:
            rec['g'] = {
                'cat': g.get('類別'), 'kr': g.get('簡任比率'), 'kmax': g.get('簡任上限'),
                'wr': g.get('委任比率'), 'wmin': g.get('委任下限'),
                'bad': g.get('不符數'), 'ask': g.get('需確認數'), 'rules': g.get('不符規則'),
            }
        out.append(rec)
    return out


def build_ministries(contract, ministry_names):
    """契約人力系統的統計是「主管機關」口徑：只取名稱與部會完全相同者。"""
    H = [h for h in contract['headcount'] if h['scope'] == '中央']
    groups = collections.Counter(h['agency_group'] for h in H)
    out = {}
    for m in ministry_names:
        rows = [h for h in H if h['agency_group'] == m and h['year'] >= 107]
        if not rows:
            continue
        budget, actual, src = {}, {}, {}
        for h in rows:
            tgt = budget if h['measure'] == '預算員額' else actual
            cat = h['category'].replace('總員額法', '').replace('員額－', '－').replace('員額', '')
            tgt.setdefault(cat, {}).setdefault(str(h['year']), h['value'])
            key = 'budget' if tgt is budget else 'actual'
            if key not in src or h['year'] > src[key]['year']:
                src[key] = {'year': h['year'], 'name': h['source_name'], 'url': h['source_url']}
        out[m] = {'budget': budget, 'actual': actual, 'src': src}
    unmatched = sorted(g for g in groups if g not in ministry_names)
    return out, unmatched


def build_national(staff, contract):
    law = {}
    for y, v in staff['law'].items():
        law[y] = {'version': v['version'], 'total': v['total'], 'ceil': v['ceil']['total'],
                  'staff': v['staff'], 'c': [v['c1'], v['c2'], v['c3'], v['c4'], v['c5']],
                  'cceil': [v['ceil'][f'c{i}'] for i in range(1, 6)]}
    H = contract['headcount']

    def series(cat, group=None):
        d = {}
        for h in H:
            if h['category'] == cat and (group is None or h['agency_group'] == group):
                d.setdefault(str(h['year']), h['value'])
        return dict(sorted(d.items(), key=lambda kv: int(kv[0])))
    return {
        'law': law, 'generated': staff.get('generated'),
        'yueyong': series('約用人員(合計,Q4)'),
        'dispatch': series('勞力派遣人員'),
    }


def build_coverage(contract):
    """各人力類別在契約人力系統中的資料顆粒度，供「資料接入狀況」呈現。"""
    cov = {}
    for h in contract['headcount']:
        c = cov.setdefault(h['category'], {'n': 0, 'groups': set(), 'years': set(), 'scopes': set()})
        c['n'] += 1
        c['groups'].add(h['agency_group'])
        c['years'].add(h['year'])
        c['scopes'].add(h['scope'])
    return {k: {'n': v['n'], 'groups': len(v['groups']), 'y0': min(v['years']), 'y1': max(v['years']),
                'scopes': sorted(v['scopes'])} for k, v in cov.items()}


def load_extra(path, by_code):
    """讀取新增人力資料接口檔，並以機關主檔檢核。回傳（資料列, 問題清單）。"""
    rows, problems = [], []
    if not path.exists():
        return rows, [f'找不到接口檔 {path.name}']
    with open(path, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(line for line in f if not line.startswith('#'))
        missing = [c for c in EXTRA_COLUMNS if c not in (rd.fieldnames or [])]
        if missing:
            return rows, [f'接口檔缺少欄位：{"、".join(missing)}']
        for n, r in enumerate(rd, start=2):
            if not any((v or '').strip() for v in r.values()):
                continue
            code = (r['機關代碼'] or '').strip()
            where = f'第 {n} 列'
            if code not in by_code:
                problems.append(f'{where}：機關代碼「{code}」不在機關主檔內（{r["機關名稱"]}）')
                continue
            if r['機關名稱'].strip() and r['機關名稱'].strip() != by_code[code]:
                problems.append(f'{where}：機關名稱「{r["機關名稱"]}」與主檔「{by_code[code]}」不同，已以代碼為準')
            if r['人力類別'].strip() not in EXTRA_TYPES:
                problems.append(f'{where}：人力類別「{r["人力類別"]}」不在允許清單（{"、".join(EXTRA_TYPES)}）')
                continue
            if r['口徑'].strip() not in EXTRA_SCOPES:
                problems.append(f'{where}：口徑「{r["口徑"]}」須為 {"／".join(EXTRA_SCOPES)}')
                continue
            try:
                val = float(r['人數'])
                year = int(r['年度'])
            except ValueError:
                problems.append(f'{where}：年度或人數不是數字')
                continue
            rows.append({'y': year, 'date': r['基準日'].strip(), 'code': code, 'type': r['人力類別'].strip(),
                         'scope': r['口徑'].strip(), 'v': int(val) if val == int(val) else val,
                         'src': r['來源'].strip(), 'note': r['備註'].strip()})
    return rows, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--artifact', help='另外輸出預覽版到此目錄（index.html 與 portal-data.json）')
    ap.add_argument('--extra', help='新增人力資料接口檔（預設 portal/data/manpower_extra.csv）')
    args = ap.parse_args()

    org, grade, contract, staff = load_org(), load_grade(), load_contract(), load_staffing()
    agencies = build_agencies(org, grade)
    by_code = {a['code']: a['name'] for a in agencies}
    ministry_names = sorted({a['min'] for a in agencies})
    ministries, unmatched = build_ministries(contract, set(ministry_names))
    extra_path = Path(args.extra) if args.extra else HERE / 'data' / 'manpower_extra.csv'
    extra, problems = load_extra(extra_path, by_code)

    data = {
        'built': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'layer2': {
            'org': {'built': org.get('built'), 'n': len(agencies)},
            'grade': {'built': grade.get('built'), 'n': len(grade['results']), 'ver': grade['meta'].get('準則版本')},
            'contract': {'built': contract.get('built'), 'n': len(contract['headcount'])},
            'staffing': {'built': staff.get('generated'), 'years': staff.get('years')},
        },
        'agencies': agencies,
        'ministries': ministries,
        'ministryNoStat': [m for m in ministry_names if m not in ministries],
        'unmatchedGroups': unmatched,
        'national': build_national(staff, contract),
        'coverage': build_coverage(contract),
        'extra': extra,
        'extraProblems': problems,
        'extraSpec': {'columns': EXTRA_COLUMNS, 'types': EXTRA_TYPES, 'scopes': EXTRA_SCOPES},
    }

    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    tpl = (HERE / 'template.html').read_text(encoding='utf-8')
    inline = tpl.replace('/*__DATA__*/null', payload.replace('</', '<\\/'))
    page = ('<!DOCTYPE html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '</head>\n<body>\n' + inline + '\n</body>\n</html>\n')
    out = HERE / 'output' / 'index.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding='utf-8')

    if args.artifact:
        d = Path(args.artifact)
        d.mkdir(parents=True, exist_ok=True)
        (d / 'index.html').write_text(tpl, encoding='utf-8')
        (d / 'portal-data.json').write_text(payload, encoding='utf-8')

    # ---------- 建檔檢核（印在畫面上，方便確認） ----------
    no_grade = [a['name'] for a in agencies if 'g' not in a]
    print(f'機關主檔            {len(agencies)} 個機關，機關代碼缺 {sum(1 for a in agencies if not a["code"])}、'
          f'重複 {len(agencies) - len(by_code)}')
    print(f'官職等檢核對上      {len(agencies) - len(no_grade)} 個；未對上 {len(no_grade)} 個：{"、".join(no_grade)}')
    print(f'主管機關統計對上    {len(ministries)}/{len(ministry_names)} 個部會；未對上：{"、".join(data["ministryNoStat"])}')
    print(f'契約人力統計中無法對到機關主檔的分組 {len(unmatched)} 個（舊名、非行政院、合計列等）')
    print(f'新增人力資料接口    {len(extra)} 列有效，{len(problems)} 個問題')
    for p in problems:
        print('   -', p)
    print(f'輸出 {out.relative_to(ROOT)}  {out.stat().st_size / 1024:.0f} KB')
    return 0


if __name__ == '__main__':
    sys.exit(main())

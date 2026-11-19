#!/usr/bin/env python3
"""
共用資料載入：總表 Excel ＋ org-compare/manual_fixes.json（人工補登／修正）→ 機關清單與每機關的編制表列。

為什麼：組織法規查詢系統的人工補登（例如公務人力發展學院漏讀的科員 32 人、矯正署與行政執行署的補登）
不改總表 Excel，而是在建檔時套用；本系統若直接讀 Excel 會漏掉這些修正，官等比率就會算錯。
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ORG = os.path.join(ROOT, 'org-compare')
sys.path.insert(0, ORG)
try:
    from build_dataset import apply_fixes  # noqa: E402
except Exception:  # noqa: BLE001
    apply_fixes = None

DEFAULT_MASTER = os.path.join(ORG, 'data', '組織法編制表_總表_20261031.xlsx')
DEFAULT_FIXES = os.path.join(ORG, 'manual_fixes.json')


def _none(v):
    return None if (v is None or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and v.strip() == '')) else v


def load(master=DEFAULT_MASTER, fixes=DEFAULT_FIXES):
    """回傳 (agencies, rows_by_agency, fixlog)。
    agencies：list of dict（機關總覽欄位，層級為字串）。
    rows_by_agency：{機關: [ {序, 單位, 職稱, 官等, 職等, 員額(int), 備註, 修正紀錄}, ... ]}，依序號排序，
                    已排除「分表排除」「轉錄取代」之列。"""
    ov = pd.read_excel(master, '機關總覽', dtype=str)
    det = pd.read_excel(master, '編制表明細', dtype=str)
    fixlog = {}
    if apply_fixes and fixes and os.path.exists(fixes):
        ov, det, fixlog = apply_fixes(ov, det, fixes)
    else:
        det = det.copy(); det['分表排除'] = False; det['轉錄取代'] = False
    for col in ('分表排除', '轉錄取代', '修正紀錄'):
        if col not in det.columns:
            det[col] = False if col != '修正紀錄' else None
    det = det[~det['分表排除'].fillna(False).astype(bool) & ~det['轉錄取代'].fillna(False).astype(bool)]
    det['_n'] = pd.to_numeric(det['員額'], errors='coerce').fillna(0).astype(int)
    det['_seq'] = pd.to_numeric(det['序'], errors='coerce').fillna(9999)
    det = det.sort_values(['機關名稱', '_seq'])
    agencies = []
    for _, o in ov.iterrows():
        d = {k: _none(v) for k, v in o.items()}
        d['層級'] = str(d.get('層級') or '')
        agencies.append(d)
    rows_by = {}
    for name, g in det.groupby('機關名稱', sort=False):
        rows_by[name] = [{'序': _none(r['序']), '單位': _none(r['單位']), '職稱': (r['職稱'] or '').strip() if isinstance(r['職稱'], str) else '',
                          '官等': _none(r['官等']), '職等': _none(r['職等']), '員額': int(r['_n']), '備註': (r['備註'] if isinstance(r['備註'], str) else '') or '',
                          '修正紀錄': _none(r.get('修正紀錄'))} for _, r in g.iterrows() if isinstance(r['職稱'], str) and r['職稱'].strip()]
    return agencies, rows_by, fixlog


if __name__ == '__main__':
    a, r, f = load()
    print(f'機關 {len(a)}，有明細者 {len(r)}，明細列 {sum(len(v) for v in r.values())}，人工修正機關 {len(f)}')

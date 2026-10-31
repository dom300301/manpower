#!/usr/bin/env python3
"""
PoC：從「組織法編制表_總表.xlsx」直接計算同層級機關的組織結構指標。

用法：
    python3 compare_poc.py 總表.xlsx                      # 預設：三級、以「署」結尾
    python3 compare_poc.py 總表.xlsx --level 3 --suffix 局
    python3 compare_poc.py 總表.xlsx --level 3 --suffix 署 --out 結果.csv

指標定義（草案，待確認）：
    員額合計      = 編制表明細「員額」加總（括號兼任不計）
    副首長數      = 職稱為「副署長／副局長／副處長／副所長／副館長／副院長／副主任」之員額
    組長數、副組長數、科長數 = 職稱完全等於該字之員額
    簡任員額      = 官等含「簡任」或職等最高達第十職等以上之員額
    簡任非主管    = 簡任員額中，職稱不是主管職稱（署長…股長、主任、室主任等）者
"""
import argparse, re
import pandas as pd

CN = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
def cn2n(t):
    if t == '十': return 10
    if t.startswith('十'): return 10 + CN[t[1]]
    if '十' in t:
        a, b = t.split('十'); return CN[a]*10 + (CN[b] if b else 0)
    return CN.get(t)
def grade_max(s):
    m = re.findall(r'第([一二三四五六七八九十]+)職等', str(s))
    return max(cn2n(t) for t in m) if m else None

MGR_RE = re.compile(r'(?:署長|副署長|局長|副局長|處長|副處長|組長|副組長|科長|主任|副主任|主任秘書|秘書長|副秘書長|隊長|副隊長|所長|副所長|館長|副館長|場長|副場長|院長|副院長|分署長|副分署長|股長|室主任|中心主任|總隊長|副總隊長)$')
DEPUTY_RE = re.compile(r'^副(署長|局長|處長|所長|館長|院長|主任)$')

def profile(g):
    n = g['n']
    simren = g['官等'].fillna('').str.contains('簡任') | (g['gmax'].fillna(0) >= 10)
    mgr = g['職稱'].str.contains(MGR_RE)
    first = g.sort_values('序').iloc[0]
    return pd.Series({
        '員額合計': n.sum(),
        '首長職稱': first['職稱'], '首長職等': first['職等'],
        '副首長數': n[g['職稱'].str.match(DEPUTY_RE)].sum(),
        '主任秘書': n[g['職稱'] == '主任秘書'].sum(),
        '組長數': n[g['職稱'] == '組長'].sum(), '副組長數': n[g['職稱'] == '副組長'].sum(),
        '科長數': n[g['職稱'] == '科長'].sum(),
        '簡任員額': n[simren].sum(), '簡任非主管': n[simren & ~mgr].sum(),
        '專門委員': n[g['職稱'] == '專門委員'].sum(),
        '薦任員額': n[g['官等'].fillna('').str.contains('薦任') & ~simren].sum(),
        '委任員額': n[g['官等'].fillna('').str.fullmatch('委任')].sum(),
    })

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xlsx'); ap.add_argument('--level', default='3'); ap.add_argument('--suffix', default='署')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    ov = pd.read_excel(a.xlsx, '機關總覽', dtype=str)
    d = pd.read_excel(a.xlsx, '編制表明細', dtype=str)
    d['n'] = pd.to_numeric(d['員額'], errors='coerce').fillna(0)
    d['序'] = pd.to_numeric(d['序'], errors='coerce').fillna(9999)
    d['gmax'] = d['職等'].map(grade_max)
    p = d.groupby('機關名稱').apply(profile, include_groups=False).reset_index().rename(columns={'機關名稱': '機關'})
    p = p.merge(ov[['機關', '部會', '層級', '隸屬', '驗算狀態']], on='機關')
    p['簡任非主管比'] = (p['簡任非主管'] / p['員額合計']).round(3)
    sel = p[(p['層級'] == a.level) & p['機關'].str.endswith(a.suffix)].sort_values('員額合計')
    cols = ['部會', '機關', '員額合計', '首長職等', '副首長數', '主任秘書', '組長數', '副組長數', '科長數', '簡任員額', '簡任非主管', '專門委員', '簡任非主管比', '驗算狀態']
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
    print(sel[cols].to_string(index=False))
    if a.out:
        sel[cols].to_csv(a.out, index=False, encoding='utf-8-sig'); print('已輸出', a.out)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
P1 單元測試（合成資料）：員額區間、括號語意、職等 NFKC、碎片列。
用法：python3 tests/test_p1_headcount.py
"""
import os, sys, unicodedata, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from build_dataset import parse_headcount, paren_meaning, grade_range, classify_rows, cn_int, nfkc
fails, passes = [], []
def check(c, m): (passes if c else fails).append(('PASS ' if c else 'FAIL ') + m)
P = parse_headcount
r = P('七'); check(r['專任_min'] == 7 and r['專任_max'] == 7 and not r['專任_is_range'] and r['paren_min'] is None, f"'七' → 專任 7 定額：{r}")
r = P('七-九'); check(r['專任_min'] == 7 and r['專任_max'] == 9 and r['專任_is_range'] and r['paren_min'] is None, f"'七-九' → 專任區間 7–9（不以下限充當定額）：{r}")
r = P('三（六－八）'); check(r['專任_min'] == 3 and not r['專任_is_range'] and r['paren_min'] == 6 and r['paren_max'] == 8 and r['paren_is_range'], f"'三（六－八）' → 專任 3 定額、括號區間 6–8：{r}")
r = P('（七-九）'); check(r['專任_min'] == 0 and r['paren_min'] == 7 and r['paren_max'] == 9 and r['paren_is_range'], f"'（七-九）' → 專任 0、括號區間 7–9：{r}")
r = P('(三~五)'); check(r['專任_min'] == 0 and r['paren_min'] == 3 and r['paren_max'] == 5, f"'(三~五)' → 專任 0、括號 3–5：{r}")
r = P('七（一）'); check(r['專任_min'] == 7 and r['paren_min'] == 1 and not r['paren_is_range'], f"'七（一）' → 專任 7、括號 1（非區間）：{r}")
r = P('二十（八）'); check(r['專任_min'] == 20 and r['paren_min'] == 8, f"'二十（八）' → 專任 20、括號 8：{r}")
r = P('(一Ｏ一)'); check(r['專任_min'] == 0 and r['paren_min'] == 101, f"'(一Ｏ一)' → 括號 101（全形 O）：{r}")
r = P('一○三'); check(r['專任_min'] == 103, f"'一○三' → 103：{r}")
r = P('二一七（六十九）'); check(r['專任_min'] == 217 and r['paren_min'] == 69, f"'二一七（六十九）' → 217、括號 69：{r}")
r = P(None); check(not r['可解析'], 'None → 不可解析')
r = P('第一職等至第三職等'); check(not r['可解析'], '錯位文字 → 不可解析，不猜數字')
# 括號語意：只依本列備註；同表慣例只記候選
m, e = paren_meaning('由海洋委員會副主任委員其中一人兼任。', False); check(m == '兼任' and '兼' in e, f'海巡署署長備註兼任 → {m}（{e}）')
m, e = paren_meaning('由研究員兼任。', False); check(m == '兼任', f'農藥所「由研究員兼任」→ {m}')
m, e = paren_meaning(None, True); check(m == 'unknown' and '候選' in e, f'無備註、同表有兼任證據 → {m}（{e}）')
m, e = paren_meaning('', False); check(m == 'unknown', f'無備註、同表無證據 → {m}')
m, e = paren_meaning('一、由行政院院長派聘。二、得於總數內調整專（兼）任。', True); check(m == 'unknown', f'黨產會「專（兼）任」非兼任定語 → {m}（待審，不放行）')
m, e = paren_meaning('護理師員額上限為一一八四人', False); check(m == '上限', f'備註上限 → {m}')
# 職等 NFKC：相容字 U+F9D1
raw = '第六職等至第八職等'; check(ord(raw[1]) == 0xF9D1 and unicodedata.normalize('NFKC', raw[1]) == '六', '測試樣本確為 U+F9D1 六，NFKC → 六（U+516D）')
check(grade_range(raw) == (6, 8), f'{raw!r} → {grade_range(raw)}（期望 (6, 8)）')
check(grade_range('第五職等或第六職等至第七職等') == (5, 7), '含相容字但 min/max 由其他數字決定者不變 (5,7)')
check(nfkc(raw) != raw and raw == '第六職等至第八職等', 'raw 字串未被改動（NFKC 只用於副本）')
check(grade_range('第三職等至第五職') == (3, 3), '截斷「第三職等至第五職」解析 (3,3) → 由 build 標職等區間待審，不猜補')
# 碎片列
cols = ['機關名稱', '序', '分表', 'PDF頁', '單位', '職稱', '官等', '職等', '員額', '員額原文', '備註']
rows = [
 ('X', 1, None, 1, None, 'X編制表', None, None, None, None, None),                # 表頭殘留
 ('X', 2, None, 1, None, '所長', '簡任', '第十職等', '1', '一', None),
 ('X', 3, None, 1, None, '中醫師', None, None, None, None, None),               # 合併計算列：保留、不標碎片
 ('X', 4, None, 1, None, '附註：', None, None, None, None, None),               # 附註拆列
 ('X', 5, None, 1, None, '一、本編制表所列職稱、官等職等，應適用', None, None, None, None, None),
 ('X', 6, None, 1, None, '所長', None, None, None, None, None),                 # 重複擷取（同職稱已計入）
 ('X', 7, None, 1, None, '薦任', None, None, None, None, None),                 # 重複擷取（官等詞）
 ('X', 8, None, 1, None, '合計', None, None, '1', '一', None),
]
d = pd.DataFrame(rows, columns=cols); d['n'] = pd.to_numeric(d['員額'], errors='coerce'); q, _ = classify_rows(d); d['q'] = q
g = lambda i: (None if (d['q'][i] is None or (isinstance(d['q'][i], float) and pd.isna(d['q'][i]))) else d['q'][i])
check(g(0) == '碎片列（表頭殘留）' and g(3) == '碎片列（附註拆列）' and g(4) == '碎片列（附註拆列）', f'表頭／附註碎片：{g(0)}, {g(3)}, {g(4)}')
check(g(5) == '碎片列（重複擷取）' and g(6) == '碎片列（重複擷取）', f'重複擷取碎片：{g(5)}, {g(6)}')
check(g(2) is None, f'合併計算列「中醫師」不標碎片（{g(2)}）')
check(g(7) == '控制列' and len(d) == 8, '控制列維持，碎片列未被刪除（仍 8 列）')
print('\n'.join(passes + fails)); print(f'\n結果：PASS {len(passes)}、FAIL {len(fails)}'); sys.exit(1 if fails else 0)

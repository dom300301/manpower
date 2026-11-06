#!/usr/bin/env python3
"""
控制列辨識單元測試（合成資料，不需總表）。
用法：python3 tests/test_control_rows.py
情境：A 機關末列合計；B 分表各自合計；C 跨頁小計；D 備註提及合計但為正常列；E 合計字樣但官等有值（疑似，待審不刪）；F 官等異常
"""
import os, sys, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from build_dataset import classify_rows, rank_abnormal

def df(rows):
    cols = ['機關名稱', '序', '分表', 'PDF頁', '單位', '職稱', '官等', '職等', '員額', '員額原文', '備註']
    d = pd.DataFrame(rows, columns=cols); d['n'] = pd.to_numeric(d['員額'], errors='coerce'); return d

fails, passes = [], []
def check(c, m): (passes if c else fails).append(('PASS ' if c else 'FAIL ') + m)

rows = [
 ('A', 1, None, 1, None, '所長', '簡任', '第十二職等', '1', '一', None),
 ('A', 2, None, 1, None, '科員', '委任或薦任', '第五職等至第七職等', '3', '三', '醫師、中醫師及牙醫師之合計員額'),   # D：備註提及合計
 ('A', 3, None, 1, None, '等合計', None, None, '4', '四（一）', None),                                             # A：末列合計
 ('B', 1, '1', 1, None, '局長', '簡任', '第十二職等', '1', '一', None),
 ('B', 2, '1', 1, None, '合計', None, None, '1', '一', None),                                                     # B：分表 1 合計
 ('B', 3, '2', 2, None, '軍職', '上校', None, '5', '五', None),
 ('B', 4, '2', 2, None, '合計', None, None, '5', '五', None),                                                     # B：分表 2 合計（亦為機關末列）
 ('C', 1, None, 1, None, '處長', '簡任', '第十一職等', '1', '一', None),
 ('C', 2, None, 1, None, '本頁小計', None, None, '1', '一', None),                                                # C：跨頁小計（第 1 頁末）
 ('C', 3, None, 2, None, '科員', '委任或薦任', '第五職等至第七職等', '2', '二', None),
 ('C', 4, None, 2, None, '合計', None, None, '3', '三', None),                                                    # C：末列總計
 ('E', 1, None, 1, None, '科長', '薦任', '第九職等', '1', '一', None),
 ('E', 2, None, 1, None, '合計', '薦任', None, '1', '一', None),                                                  # E：合計字樣但官等有值 → 疑似
 ('E', 3, None, 1, None, '書記', '委任', '第一職等至第三職等', '1', '一', None),
 ('F', 1, None, 1, None, '書記', '師委任級(或士', '第一職等至第三職等', '1', '一', None),                            # F：官等異常
 ('F', 2, None, 1, None, '主任', '簡任或少將', '第十職等', '1', '一', None),                                       # 軍文並列：合法
]
d = df(rows); q, why = classify_rows(d); d['列品質'] = q
def get(ag, seq):
    v = d[(d['機關名稱'] == ag) & (d['序'] == seq)]['列品質'].iloc[0]
    return None if (v is None or (isinstance(v, float) and pd.isna(v))) else v
check(get('A', 3) == '控制列', f"A 末列「等合計」→ {get('A', 3)}")
check(get('A', 2) is None, f"D 備註提及合計的正常列不被當控制列 → {get('A', 2)}")
check(get('B', 2) == '控制列（分表）' and get('B', 4) == '控制列', f"B 分表 1 合計→{get('B', 2)}；分表 2（機關末列）→{get('B', 4)}")
check(get('C', 2) == '控制列（跨頁小計）', f"C 第 1 頁末「本頁小計」→ {get('C', 2)}")
check(get('C', 4) == '控制列', f"C 末列總計→ {get('C', 4)}")
check(get('E', 2) == '疑似控制列', f"E 合計字樣但官等有值 → {get('E', 2)}（待審）")
check(len(d[d['機關名稱'] == 'E']) == 3, 'E 疑似控制列未被刪除，仍在明細中')
check(get('F', 1) == '官等異常' and get('F', 2) is None, f"F 溢出官等→{get('F', 1)}；軍文並列「簡任或少將」→{get('F', 2)}（合法）")
check(rank_abnormal('（生）級)薦任') and not rank_abnormal('委任或薦任或警佐或警正或尉官、士官') and not rank_abnormal('師級(或士（生）級)'), '官等詞彙規則：溢出字樣異常；軍警並列與師級(或士（生）級)合法')
print('\n'.join(passes + fails)); print(f'\n結果：PASS {len(passes)}、FAIL {len(fails)}'); sys.exit(1 if fails else 0)

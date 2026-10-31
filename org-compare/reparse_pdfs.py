#!/usr/bin/env python3
"""
第二階段驗證（二）：以 pdfplumber 獨立重新解析編制表 PDF，與總表「編制表明細」逐職稱比對。

用法：
    python3 reparse_pdfs.py --master 總表.xlsx --online 編制表線上比對.csv --pdf-dir pdfs --out 重解析比對.csv

比對方式：每個機關取（職稱, 員額）多重集合，列出「只在PDF」「只在總表」的差異；
並比較合計（PDF「合計」列 vs 重解析逐列加總 vs 總表合計）。
"""
import argparse, csv, os, re
from collections import Counter
import pdfplumber
import pandas as pd

CN = {'○': 0, '〇': 0, '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}

def cn_num(s):
    """中文數字 → 整數。支援「十七」「一○三」「一一八四」「二十」「一百二十」；括號視為兼任回 None。"""
    s = re.sub(r'\s', '', s or '')
    if not s or s.startswith('（') or s.startswith('('):
        return None
    s = re.sub(r'[（(][^（）()]*[）)]$', '', s)  # 「一七九（十）」→ 一七九
    s = re.split(r'[－—～~-]', s)[0]  # 「七－九」範圍取下限
    s = s.replace('之', '')
    if re.fullmatch(r'[0-9]+', s):
        return int(s)
    if not re.fullmatch(r'[○〇零一二三四五六七八九十百千]+', s):
        return None
    if '十' not in s and '百' not in s and '千' not in s:
        if all(c in CN for c in s):
            return int(''.join(str(CN[c]) for c in s))
        return None
    total, num = 0, 0
    for c in s:
        if c in CN:
            num = CN[c]
        elif c == '十':
            total += (num if num else 1) * 10; num = 0
        elif c == '百':
            total += (num if num else 1) * 100; num = 0
        elif c == '千':
            total += (num if num else 1) * 1000; num = 0
    return total + num

HEADER_SET = {'職稱', '官等', '職等', '員額', '備考', '備註', '單位', '員額備考', '職稱官等', '官等職等'}
NUM_RE = re.compile(r'^[（(]?(?:[○〇零一二三四五六七八九十百千]+|[0-9]{1,4})(?:[－—-](?:[○〇零一二三四五六七八九十百千]+|[0-9]{1,4}))?[）)]?(?:[（(][○〇零一二三四五六七八九十百千0-9～－—-]+[）)])?$')

def parse_pdf(path):
    """回傳 (rows, total)；rows = [(單位, 職稱, 官等, 職等, 員額int|None, 員額原文)]
    版面固定為 [單位] 職稱 官等 職等 員額 備考；員額欄＝由右往左第一個「純數字（含括號）」儲存格。"""
    rows, total, unit = [], None, ''
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for raw in table:
                    cells = [re.sub(r'\s', '', c or '') for c in raw]
                    if not any(cells):
                        continue
                    nonempty = [c for c in cells if c]
                    if len(cells) > 8 or re.fullmatch(r'[0-9]+', nonempty[0]):
                        continue  # 公報頁首／頁碼雜訊列
                    if all(c in HEADER_SET for c in nonempty):
                        continue  # 表頭列
                    if nonempty[0].startswith('合計'):
                        nums = [cn_num(c) for c in cells[1:] if re.match(r'^[○〇零一二三四五六七八九十百千0-9]', c) and cn_num(c) is not None]
                        if nums: total = nums[-1]
                        continue
                    n_idx = None
                    for i in range(len(cells) - 1, 0, -1):
                        if NUM_RE.match(cells[i]):
                            n_idx = i; break
                    if n_idx is None or n_idx < 3:
                        continue
                    grade, rank, title = cells[n_idx - 1], cells[n_idx - 2], cells[n_idx - 3]
                    if not title and n_idx >= 4 and cells[n_idx - 4]:
                        title, unit = cells[n_idx - 4], ''   # 無單位的列：職稱印在單位欄
                    elif n_idx >= 4 and cells[n_idx - 4]:
                        unit = cells[n_idx - 4]
                    elif n_idx < 4:
                        unit = ''
                    # 修補 pdfplumber 把「職稱 官」「等 職等」切錯欄的情形（例：院長簡 / 任第十三職等）
                    if not rank and re.search(r'[簡薦委聘派]$', title) and grade.startswith('任'):
                        rank, title, grade = title[-1] + '任', title[:-1], grade[1:]
                    elif rank and re.search(r'[簡薦委聘派]$', rank) and grade.startswith('任') and re.search(r'(室|組|處|中心|科|課)$', title):
                        unit, title, rank, grade = title, rank[:-1], rank[-1] + '任', grade[1:]
                    if not title or title in HEADER_SET:
                        continue
                    rows.append((unit, title, rank, grade, cn_num(cells[n_idx]), cells[n_idx]))
    return rows, total

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--master', required=True); ap.add_argument('--online', required=True)
    ap.add_argument('--pdf-dir', default='pdfs'); ap.add_argument('--out', default='重解析比對.csv')
    ap.add_argument('--only', default=None, help='只處理機關名稱含此字串者')
    a = ap.parse_args()
    det = pd.read_excel(a.master, '編制表明細', dtype=str)
    det['n'] = pd.to_numeric(det['員額'], errors='coerce')
    ov = pd.read_excel(a.master, '機關總覽', dtype=str).set_index('機關')
    online = pd.read_csv(a.online, dtype=str).fillna('')
    out = []
    for _, r in online.iterrows():
        name = r['機關名稱']
        if a.only and a.only not in name:
            continue
        fid = (r['線上_FileId'].split(';') or [''])[0]
        path = os.path.join(a.pdf_dir, f"{r['編制表pcode']}_{fid}.pdf") if fid else ''
        rec = {'機關名稱': name, '狀態': '', 'PDF合計列': '', 'PDF逐列加總': '', '總表合計': ov['編制員額合計'].get(name, ''),
               'PDF列數': '', '總表列數': '', '只在PDF': '', '只在總表': ''}
        if not path or not os.path.exists(path):
            rec['狀態'] = '無PDF'; out.append(rec); continue
        try:
            rows, total = parse_pdf(path)
        except Exception as e:
            rec['狀態'] = f'解析失敗:{e}'; out.append(rec); continue
        pdf_ms = Counter((t, n) for _, t, _, _, n, _ in rows if n is not None)
        sub = det[det['機關名稱'] == name]
        my_ms = Counter((t, int(n)) for t, n in zip(sub['職稱'], sub['n']) if pd.notna(n) and n > 0)
        only_pdf = pdf_ms - my_ms; only_me = my_ms - pdf_ms
        rec.update({'PDF合計列': total if total is not None else '', 'PDF逐列加總': sum(n for _, _, _, _, n, _ in rows if n),
                    'PDF列數': len(rows), '總表列數': len(sub),
                    '只在PDF': '；'.join(f'{t}{n}' for (t, n), c in only_pdf.items() for _ in range(c)),
                    '只在總表': '；'.join(f'{t}{n}' for (t, n), c in only_me.items() for _ in range(c))})
        rec['狀態'] = '一致' if not only_pdf and not only_me else '有差異'
        out.append(rec)
        print(name, rec['狀態'], rec['只在PDF'][:60], rec['只在總表'][:60], flush=True)
    with open(a.out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print('狀態統計：', dict(Counter(r['狀態'] for r in out)))

if __name__ == '__main__':
    main()

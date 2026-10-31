#!/usr/bin/env python3
"""
第二階段驗證（一）：逐一檢查全國法規資料庫上的「編制表」頁面，
比對雲端硬碟總表所記錄的 PDF 附件（FileId）與修正日期是否仍為現行版，並下載 PDF 備查。

用法：
    python3 verify_tables_online.py --sources sources_all.csv --master 總表.xlsx --pdf-dir pdfs --out 編制表線上比對.csv

sources_all.csv 由各批次檔「2_公開來源清單」合併而成（欄位：機關名稱、編制表連結、編制表最新異動日、編制表PDF）。
"""
import argparse, csv, hashlib, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

UA = {'User-Agent': 'Mozilla/5.0 (DGPA org-compare verifier)'}
BASE = 'https://law.moj.gov.tw/LawClass/'

def roc_to_iso(s):
    m = re.search(r'民國\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日', s)
    return f'{int(m.group(1))+1911:04d}{int(m.group(2)):02d}{int(m.group(3)):02d}' if m else ''

class _Resp:
    def __init__(self, content): self.content = content; self.text = content.decode('utf-8', 'replace')

def fetch(url, retries=3):
    """以 curl 下載（本環境的 Python requests 無法通過代理憑證驗證，curl 可以）。"""
    for i in range(retries):
        r = subprocess.run(['curl', '-sS', '-L', '--max-time', '60', '-A', UA['User-Agent'], url], capture_output=True)
        if r.returncode == 0 and r.stdout:
            return _Resp(r.stdout)
        time.sleep(2 * (i + 1))
    return None

def parse_table_page(html):
    text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))
    name = re.search(r'法規名稱：\s*(\S+)', text)
    mod = re.search(r'(修正日期|發布日期|公布日期)：\s*(民國[^法]+?日)', text)
    files = re.findall(r'LawGetFile\.ashx\?FileId=(\d+)', html)
    abolished = '廢止' in text[:800]
    return (name.group(1) if name else ''), (roc_to_iso(mod.group(2)) if mod else ''), sorted(set(files)), abolished

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sources', required=True); ap.add_argument('--pdf-dir', default='pdfs')
    ap.add_argument('--out', default='編制表線上比對.csv'); ap.add_argument('--sleep', type=float, default=0.4); ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    os.makedirs(a.pdf_dir, exist_ok=True)
    rows = list(csv.DictReader(open(a.sources, encoding='utf-8')))

    def work(item):
        i, r = item
        link = r.get('編制表連結') or ''
        m = re.search(r'pcode=([A-Z]\d{7})', link)
        rec = {'機關名稱': r['機關名稱'], '批次': r.get('批次', ''), '編制表pcode': m.group(1) if m else '',
               '總表_編制表異動日': r.get('編制表最新異動日', ''), '總表_FileId': '', '線上_法規名稱': '', '線上_修正日期': '',
               '線上_FileId': '', '狀態': '', 'PDF_sha256': ''}
        fm = re.search(r'FileId=(\d+)', r.get('編制表PDF') or '')
        rec['總表_FileId'] = fm.group(1) if fm else ''
        if not m:
            rec['狀態'] = '總表無編制表連結'; return rec
        resp = fetch(BASE + f'LawAll.aspx?pcode={m.group(1)}')
        if resp is None:
            rec['狀態'] = '頁面無法下載'; return rec
        name, mod, files, abolished = parse_table_page(resp.text)
        rec['線上_法規名稱'], rec['線上_修正日期'], rec['線上_FileId'] = name, mod, ';'.join(files)
        if abolished:
            rec['狀態'] = '線上標示廢止'
        elif not files:
            rec['狀態'] = '線上無附檔'
        elif rec['總表_FileId'] and rec['總表_FileId'] in files and mod == rec['總表_編制表異動日']:
            rec['狀態'] = '一致'
        elif rec['總表_FileId'] and rec['總表_FileId'] in files:
            rec['狀態'] = 'FileId相同但日期不同'
        else:
            rec['狀態'] = '附件已更新（FileId不同）'
        fid = files[0] if files else ''
        if fid:
            p = os.path.join(a.pdf_dir, f'{m.group(1)}_{fid}.pdf')
            if not os.path.exists(p):
                pr = fetch(BASE + f'LawGetFile.ashx?FileId={fid}&lan=C')
                if pr is not None and pr.content[:4] == b'%PDF':
                    open(p, 'wb').write(pr.content)
            if os.path.exists(p):
                rec['PDF_sha256'] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
        print(f'[{i}/{len(rows)}] {r["機關名稱"]}: {rec["狀態"]}', flush=True)
        time.sleep(a.sleep)
        return rec

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        out = list(ex.map(work, enumerate(rows, 1)))
    with open(a.out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    from collections import Counter
    print('完成。狀態統計：', dict(Counter(r['狀態'] for r in out)))

if __name__ == '__main__':
    main()

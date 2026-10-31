#!/usr/bin/env python3
"""
考試院「公報開放資料」與「院會紀錄」的下載與關鍵字索引（供更新偵測）。

做什麼：
  1. 下載考試院公報開放資料（112 年 1 月起全部，JSON），列出標題含關鍵字（預設：列等、配置準則）的公報項目與 PDF 網址。
  2. 翻閱考試院會議紀錄清單（約 60 頁），下載第 12 屆以後的紀錄 PDF，擷取文字並搜尋關鍵字，輸出索引。

為什麼需要：職務列等的實際調整，多以「考試院會議決議＋銓敘部通函」辦理，不會回填到法規系統的「職務列等表」；
要掌握現行規則，必須從公報與院會紀錄追蹤。

用法：
  python3 grade-check/fetch_exam_council.py --out grade-check/exam_cache/council [--kw 列等,配置準則] [--since-term 13]
需要網路可連 www.exam.gov.tw、gazette.exam.gov.tw、ws.exam.gov.tw。
ws.exam.gov.tw 的憑證鏈缺中繼憑證（TWCA Secure SSL CA）；本程式會自動從 law.exam.gov.tw 取得該中繼憑證補齊後再驗證，不會關閉驗證。
"""
import argparse
import glob
import html
import io
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.parse
import zipfile

GAZ_OPEN = 'https://gazette.exam.gov.tw/cp.aspx?n=3883'
MINUTES_LIST = 'https://www.exam.gov.tw/News.aspx?n=3820&sms=8957&page={page}&PageSize=20'


def ca_bundle(out):
    """組一份含代理憑證、系統憑證與 TWCA 中繼憑證的 CA 檔。"""
    path = os.path.join(out, 'ca-bundle-plus-twca.crt')
    if os.path.exists(path):
        return path
    parts = []
    for p in [os.environ.get('SSL_CERT_FILE'), '/etc/ssl/certs/ca-certificates.crt', '/etc/ssl/cert.pem']:
        if p and os.path.exists(p):
            parts.append(open(p).read())
    proxy = os.environ.get('HTTPS_PROXY', '').replace('http://', '')
    cmd = ['openssl', 's_client', '-connect', 'law.exam.gov.tw:443', '-servername', 'law.exam.gov.tw', '-showcerts']
    if proxy:
        cmd[2:2] = ['-proxy', proxy]
    r = subprocess.run(cmd, input=b'', capture_output=True, timeout=60).stdout.decode('utf-8', 'ignore')
    certs = re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', r, flags=re.S)
    parts += certs[1:]  # 第 0 張是站台憑證，其餘為中繼
    open(path, 'w').write('\n'.join(parts))
    return path


def curl(url, out_path, ca):
    r = subprocess.run(['curl', '-sS', '-L', '-m', '300', '--cacert', ca, url, '-o', out_path], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode('utf-8', 'ignore')[:200])


def text_of(path):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return '\n'.join((p.extract_text() or '') for p in pdf.pages)


def gazette(out, ca, kws):
    page = os.path.join(out, 'gazette_open.html'); curl(GAZ_OPEN, page, ca)
    s = open(page, encoding='utf-8', errors='ignore').read()
    m = re.search(r'href="(https://ws\.exam\.gov\.tw/Download\.ashx[^"]+)"[^>]*>\s*112年1月起所有公報資料下載', s)
    if not m:
        print('找不到公報開放資料連結'); return []
    z = os.path.join(out, 'gazette_opendata.zip'); curl(html.unescape(m.group(1)), z, ca)
    items = []
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            if n.endswith('.json'):
                d = json.loads(zf.read(n).decode('utf-8-sig'))
                items += d if isinstance(d, list) else d.get('data', [])
    hits = [x for x in items if any(k in (x.get('Title') or '') for k in kws)]
    hits.sort(key=lambda x: x.get('Date_Published', ''))
    json.dump(hits, open(os.path.join(out, 'gazette_hits.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'公報項目 {len(items)} 筆，命中 {len(hits)} 筆 → gazette_hits.json')
    return hits


def minutes(out, ca, kws, since_term):
    idx = {}
    for p in range(1, 80):
        f = os.path.join(out, f'minutes_list_{p}.html')
        if not os.path.exists(f):
            curl(MINUTES_LIST.format(page=p), f, ca)
        s = open(f, encoding='utf-8', errors='ignore').read()
        found = 0
        for a, t in re.findall(r'<a[^>]*href=["\'](https://ws\.exam\.gov\.tw/Download\.ashx[^"\']+)["\'][^>]*>(.*?)</a>', s, flags=re.S):
            t = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', t))).strip(); a = html.unescape(a)
            m = re.search(r'第(\d+)屆第(\d+)次', t) or re.search(r'^(1[0-9])(\d{3})紀錄', t)
            if not m:
                continue
            found += 1
            term, no = int(m.group(1)), int(m.group(2))
            if term < since_term:
                continue
            key = f'{term:02d}_{no:03d}'
            if 'pdf' in a.lower() or key not in idx:
                idx[key] = a
        if found == 0:
            break
    pdf_dir = os.path.join(out, 'minutes_pdf'); os.makedirs(pdf_dir, exist_ok=True)
    hits = []
    for key, url in sorted(idx.items()):
        p = os.path.join(pdf_dir, key + '.pdf')
        if not os.path.exists(p):
            try:
                curl(url, p, ca)
            except Exception as e:  # noqa: BLE001
                print('下載失敗', key, e); continue
        try:
            t = text_of(p)
        except Exception:  # noqa: BLE001
            continue
        m = re.search(r'時\s*間[：:]\s*中華民國\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日', t)
        date = f'{m.group(1)}.{m.group(2)}.{m.group(3)}' if m else '?'
        snippets = [mm.group(0).replace('\n', ' ')[:300] for mm in re.finditer(r'[^\n]*(?:' + '|'.join(map(re.escape, kws)) + r')[^\n]*(?:\n[^\n]*){0,3}', t)]
        if snippets:
            hits.append({'meeting': key, 'date': date, 'snippets': snippets[:12]})
    json.dump(hits, open(os.path.join(out, 'minutes_hits.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'會議紀錄 {len(idx)} 次，命中 {len(hits)} 次 → minutes_hits.json')
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exam_cache', 'council'))
    ap.add_argument('--kw', default='列等,配置準則')
    ap.add_argument('--since-term', type=int, default=13)
    ap.add_argument('--skip-minutes', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ca = ca_bundle(a.out)
    kws = [k for k in a.kw.split(',') if k]
    gazette(a.out, ca, kws)
    if not a.skip_minutes:
        minutes(a.out, ca, kws, a.since_term)


if __name__ == '__main__':
    sys.exit(main())

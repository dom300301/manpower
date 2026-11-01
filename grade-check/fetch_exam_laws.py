#!/usr/bin/env python3
"""
從「考試院主管法規共用系統」開放資料下載本系統需要的法規全文，存成 Markdown。

資料來源（XML，每日更新）：
  https://law.exam.gov.tw/OpenDataWeb.aspx
    考試院主管法規_命令.xml      （含 職務列等表、各機關職稱及官等職等員額配置準則、師級醫事配置準則）
    考試院主管法規_行政規則.xml  （含 各機關組織法規涉及考銓業務事項作業要點、地方機關職稱選用作業原則）

用法：
  python3 grade-check/fetch_exam_laws.py              # 下載並寫入 grade-check/regs/
  python3 grade-check/fetch_exam_laws.py --cache 目錄  # XML 另存到指定目錄（預設 grade-check/exam_cache，已列入 .gitignore）

需要網路可連 law.exam.gov.tw。
"""
import argparse
import html
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REGS = os.path.join(HERE, 'regs')
BASE = 'https://law.exam.gov.tw//Opendata/'
FILES = {'命令': '考試院主管法規_命令.xml', '行政規則': '考試院主管法規_行政規則.xml'}

# 法規名稱 → 輸出檔名
WANT = {
    '職務列等表': '職務列等表_說明及目錄.md',
    '各機關職稱及官等職等員額配置準則': '各機關職稱及官等職等員額配置準則_考試院版.md',
    '各機關師級醫事職務級別員額配置準則': '各機關師級醫事職務級別員額配置準則.md',
    '各機關組織法規涉及考銓業務事項作業要點': '各機關組織法規涉及考銓業務事項作業要點.md',
    '地方立法、行政機關訂定組織自治條例、組織規程及其編制表有關職稱選用及官等職等訂列作業原則':
        '地方機關組織自治條例組織規程編制表職稱選用及官等職等訂列作業原則.md',
}


def _ctx():
    """SSL 設定：若環境指定了憑證檔（例如雲端工作階段的代理憑證）就使用它，否則用系統預設。"""
    for k in ('SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE'):
        if os.environ.get(k) and os.path.exists(os.environ[k]):
            return ssl.create_default_context(cafile=os.environ[k])
    return ssl.create_default_context()


def fetch(url, timeout=300):
    """先用 Python 內建下載；若憑證驗證失敗（部分代理環境會發生），改用系統的 curl。"""
    try:
        with urllib.request.urlopen(url, timeout=timeout, context=_ctx()) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        import subprocess
        r = subprocess.run(['curl', '-sS', '-L', '-m', str(timeout), url], capture_output=True)
        if r.returncode != 0 or not r.stdout:
            raise RuntimeError(f'下載失敗 {url}: {e}; curl: {r.stderr.decode("utf-8", "ignore")[:200]}')
        return r.stdout


def download(url, path):
    if os.path.exists(path):
        return
    print('下載', url)
    with open(path, 'wb') as f:
        f.write(fetch(url))


def law_body(raw):
    b = html.unescape(re.sub(r'<br\s*/?>', '\n', raw or ''))
    b = re.sub(r'<[^>]+>', '', b)
    return re.sub(r'\n{3,}', '\n\n', b).strip()


def attachments(law_url):
    """讀法規頁面，列出附件（Download.ashx）連結。失敗時回傳空清單。"""
    try:
        s = fetch(law_url, timeout=60).decode('utf-8', 'ignore')
    except Exception as e:  # noqa: BLE001
        print('  附件清單讀取失敗：', e)
        return []
    out = []
    for m in re.finditer(r'href="(Download\.ashx\?FileID=(\d+)[^"]*)"[^>]*>(.*?)</a>', s, flags=re.S):
        title = html.unescape(re.sub(r'<[^>]+>', '', m.group(3))).strip()
        out.append({'FileID': m.group(2), 'url': 'https://law.exam.gov.tw/' + html.unescape(m.group(1)), 'title': title})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', default=os.path.join(HERE, 'exam_cache'))
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    os.makedirs(REGS, exist_ok=True)

    found = {}
    for kind, fn in FILES.items():
        path = os.path.join(a.cache, fn)
        download(BASE + urllib.parse.quote(fn), path)
        root = ET.parse(path).getroot()
        print(f'{fn}: 共 {len(root)} 筆，更新 {root.get("UpdateDate")}')
        for law in root:
            name = law.findtext('法規名稱')
            if name in WANT:
                found[name] = {c.tag: (c.text or '').strip() for c in law}

    index = {}
    for name, out in WANT.items():
        d = found.get(name)
        if not d:
            print('找不到：', name)
            continue
        atts = attachments(d['資料網址'])
        md = (f"# {name}\n\n來源：考試院主管法規共用系統 {d['資料網址']} （開放資料 XML）\n"
              f"最新異動日期：{d['最新異動日期']}　發文字號：{d['發文字號']}\n\n"
              f"## 沿革\n\n```\n{d['法規沿革']}\n```\n\n## 內容\n\n```\n{law_body(d['法規內容'])}\n```\n")
        if atts:
            md += '\n## 附件\n\n' + '\n'.join(f"- {x['title']}（{x['url']}）" for x in atts) + '\n'
        with open(os.path.join(REGS, out), 'w', encoding='utf-8') as f:
            f.write(md)
        index[name] = {'檔案': out, '最新異動日期': d['最新異動日期'], '資料網址': d['資料網址'], '附件': atts}
        print('已寫出', out, '| 最新異動', d['最新異動日期'], '| 附件', len(atts))

    with open(os.path.join(REGS, '考試院法規_索引.json'), 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    sys.exit(main())

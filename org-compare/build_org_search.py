#!/usr/bin/env python3
"""
建檔：總表 Excel → 查詢網頁 output/index.html（離線單檔，亦可直接上傳主機成為線上版）

用法：
    python3 build_org_search.py --master 總表.xlsx [--fixes manual_fixes.json] [--out output/index.html] [--no-compress]

流程：build_dataset.build() 產生 JSON → gzip+base64 嵌入 org_template.html。
瀏覽器以原生 DecompressionStream 解壓（Chrome 80+、Edge 80+、Safari 16.4+、Firefox 113+）；
若需支援更舊的瀏覽器，加 --no-compress（檔案約 15 MB）。
"""
import argparse, base64, datetime as dt, gzip, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_dataset import build

HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--master', required=True); ap.add_argument('--fixes', default=os.path.join(HERE, 'manual_fixes.json'))
    ap.add_argument('--out', default=os.path.join(HERE, 'output', 'index.html')); ap.add_argument('--no-compress', action='store_true')
    ap.add_argument('--template', default=os.path.join(HERE, 'org_template.html'))
    a = ap.parse_args()
    tmp = tempfile.mkdtemp()
    build(a.master, tmp, a.fixes)
    data = {k: json.load(open(os.path.join(tmp, f'{k}.json'), encoding='utf-8')) for k in ['agencies', 'positions', 'articles', 'meta']}
    data['built'] = dt.datetime.now().strftime('%Y-%m-%d %H:%M')
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    html = open(a.template, encoding='utf-8').read()
    if a.no_compress:
        payload = raw.decode('utf-8').replace('</script', '<\\/script')
        html = html.replace('/*__MODE__*/', 'plain').replace('/*__DATA__*/', payload)
    else:
        payload = base64.b64encode(gzip.compress(raw, 9)).decode('ascii')
        html = html.replace('/*__MODE__*/', 'gzip').replace('/*__DATA__*/', payload)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, 'w', encoding='utf-8').write(html)
    print(f'完成：{a.out}（{os.path.getsize(a.out)/1e6:.1f} MB；機關 {len(data["agencies"]["agencies"])}，明細 {len(data["positions"])}，條文 {len(data["articles"])}）')

if __name__ == '__main__':
    main()

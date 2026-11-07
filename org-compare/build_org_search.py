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
    ap.add_argument('--template', default=os.path.join(HERE, 'org_template.html')); ap.add_argument('--source-commit', default=None)
    a = ap.parse_args()
    tmp = tempfile.mkdtemp()
    build(a.master, tmp, a.fixes, os.path.join(HERE, 'units_from_attachments.json'))
    data = {k: json.load(open(os.path.join(tmp, f'{k}.json'), encoding='utf-8')) for k in ['agencies', 'positions', 'articles', 'meta']}
    data['built'] = dt.datetime.now().strftime('%Y-%m-%d %H:%M')
    # 來源提交：程式與總表所在的 git 提交（有未提交變更時加 +dirty）；可用 --source-commit 覆寫
    if a.source_commit:
        data['source_commit'] = a.source_commit

    else:
        try:
            import subprocess
            h = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=HERE, capture_output=True, text=True).stdout.strip()
            dirty = subprocess.run(['git', 'status', '--porcelain', '--', HERE], cwd=HERE, capture_output=True, text=True).stdout.strip()
            dirty = '\n'.join(l for l in dirty.splitlines() if 'output/' not in l)
            data['source_commit'] = h + ('+dirty' if dirty else '') if h else None
        except Exception:
            data['source_commit'] = None
    mp = os.path.join(HERE, 'manifest', 'sources.json')
    if os.path.exists(mp):   # manifest 摘要（更新作業面板用）
        import hashlib as _h
        _m = json.load(open(mp, encoding='utf-8'))
        data['manifest_info'] = {'generated_at': _m.get('generated_at'), 'agencies': len(_m.get('agencies', [])), 'laws': sum(len(x['laws']) for x in _m.get('agencies', [])),
                                 'shared_laws': len(_m.get('shared_laws', {})), 'overrides': sum(len(x['overrides']) for x in _m.get('agencies', [])),
                                 'sha256': _h.sha256(open(mp, 'rb').read()).hexdigest()[:12], 'master_sha256': (_m.get('master') or {}).get('sha256', '')[:12]}
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
    chk = os.path.join(tmp, '建檔檢核.md')
    if os.path.exists(chk):
        import shutil; shutil.copy(chk, os.path.join(os.path.dirname(a.out), '建檔檢核.md'))
    import hashlib
    print(f'完成：{a.out}（{os.path.getsize(a.out)/1e6:.1f} MB；機關 {len(data["agencies"]["agencies"])}，明細 {len(data["positions"])}，條文 {len(data["articles"])}；來源提交 {data.get("source_commit")}；SHA-256 {hashlib.sha256(open(a.out,"rb").read()).hexdigest()[:16]}…）')

if __name__ == '__main__':
    main()

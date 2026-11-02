#!/usr/bin/env python3
"""
verify_laws.py — 驗證 data/laws.json：
  1. 每筆是否有條文（articles 非空）；行政規則若無條文，檢查 note 是否說明來源。
  2. PCode 是否能在全國法規資料庫 API 清單（raw/laws/api/ChLaw.json、ChOrder.json）找到，
     且名稱、最近修正日與 API 一致、未廢止。
  3. 行政規則／公告：來源檔案是否存在於 raw/laws/。
結果寫入 research/01_法規清冊與沿革.md 末尾「驗證結果」段（若已存在則整段取代）。

用法：python3 -I scripts/verify_laws.py [--root contract-manpower]
"""
import argparse, json, os, re, datetime as dt

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    data = json.load(open(os.path.join(root, 'data', 'laws.json'), encoding='utf-8'))
    laws = data['laws']

    idx = {}
    for n in ('ChLaw', 'ChOrder'):
        p = os.path.join(root, 'raw', 'laws', 'api', n + '.json')
        if not os.path.exists(p):
            print('缺少', p, '（請先執行 build_laws.py 前的下載步驟）'); continue
        j = json.loads(open(p, 'rb').read().decode('utf-8-sig'))
        for L in j['Laws']:
            idx[re.search(r'pcode=([A-Z]\d{7})', L['LawURL']).group(1)] = L

    rows, n_ok = [], 0
    for r in laws:
        problems = []
        n_art = len(r.get('articles', []))
        pc = r.get('pcode', '')
        in_api = bool(re.fullmatch(r'[A-Z]\d{7}', pc)) and pc in idx
        if re.fullmatch(r'[A-Z]\d{7}', pc or ''):
            if not in_api:
                problems.append('PCode 不在 API 清單')
            else:
                L = idx[pc]
                if L['LawName'] != r['name']:
                    problems.append(f'名稱不符（API：{L["LawName"]}）')
                md = f'{L["LawModifiedDate"][:4]}-{L["LawModifiedDate"][4:6]}-{L["LawModifiedDate"][6:]}'
                if md != r['modified_date']:
                    problems.append(f'修正日不符（API：{md}）')
                if L['LawAbandonNote']:
                    problems.append('API 標示已廢止')
                n_api = sum(1 for x in L['LawArticles'] if x['ArticleType'] == 'A')
                if n_art == 0:
                    problems.append('無條文')
                elif n_art < n_api and not r.get('note', '').startswith('僅收錄'):
                    problems.append(f'條文數 {n_art} 少於 API {n_api}')
        else:
            # 行政規則／公告：不在全國法規資料庫
            if n_art == 0 and '來源' not in r.get('note', ''):
                problems.append('無條文且 note 未說明來源')
            m = re.search(r'raw/laws/[^\s，。；）]+', r.get('note', ''))
            if m and not os.path.exists(os.path.join(root, m.group(0))):
                problems.append(f'來源檔不存在：{m.group(0)}')
        if not r.get('history'):
            problems.append('無沿革')
        status = '通過' if not problems else '；'.join(problems)
        n_ok += not problems
        rows.append(f'| {r["id"]} | {r["name"]} | {pc or "—"} | {"是" if in_api else "否"} | {n_art} | {len(r.get("history", []))} | {status} |')

    out = ['## 驗證結果', '',
           f'執行時間：{dt.datetime.now():%Y-%m-%d %H:%M}；比對來源：全國法規資料庫 API 清單（更新日 {data["meta"]["api_update_date"].get("ChLaw", "?")}），共 {len(idx)} 筆法規。',
           f'laws.json 共 {len(laws)} 筆，通過 {n_ok} 筆，未通過 {len(laws) - n_ok} 筆。', '',
           '| 編號 | 法規 | PCode | API 可查 | 條文數 | 沿革筆數 | 結果 |', '|---|---|---|---|---|---|---|'] + rows + ['']
    md_path = os.path.join(root, 'research', '01_法規清冊與沿革.md')
    text = open(md_path, encoding='utf-8').read() if os.path.exists(md_path) else '# 法規清冊與沿革\n\n'
    text = re.split(r'\n## 驗證結果\n', text)[0].rstrip('\n') + '\n\n' + '\n'.join(out)
    open(md_path, 'w', encoding='utf-8').write(text)
    print('\n'.join(out))

if __name__ == '__main__':
    main()

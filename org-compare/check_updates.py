#!/usr/bin/env python3
"""
更新偵測：下載全國法規資料庫開放資料（ChLaw.json、ChOrder.json），與總表比對，列出：
  1. 組織法規／處務規程「最新異動日」或條文有變動者
  2. 編制表附件（PDF FileId）或修正日期有變動者
  3. 已廢止的法規
  4. 開放資料「組織目」中新出現、總表尚未收錄的組織法規／編制表／處務規程（可能是新機關）

用法：
    python3 check_updates.py --master 總表.xlsx [--cache 資料夾] [--out 更新偵測報告.md] [--offline]

需要網路（law.moj.gov.tw）；--offline 時使用 cache 內既有的 ChLaw.json / ChOrder.json。
"""
import argparse, io, json, os, re, subprocess, sys, zipfile, datetime as dt
import pandas as pd

API = {'ChLaw': 'https://law.moj.gov.tw/api/Ch/Law/json', 'ChOrder': 'https://law.moj.gov.tw/api/Ch/Order/json'}
ORG_SUFFIX = ('組織法', '組織條例', '組織規程', '組織準則', '組織通則', '編制表', '編組表', '處務規程', '辦事細則', '組織自治條例')

def download(url, dest):
    r = subprocess.run(['curl', '-sS', '-L', '--max-time', '900', '-A', 'Mozilla/5.0', '-o', dest, url])
    if r.returncode != 0 or not os.path.exists(dest):
        sys.exit(f'下載失敗：{url}')

def load_open_data(cache, offline):
    idx = {}
    for name, url in API.items():
        zp = os.path.join(cache, name + '.zip'); jp = os.path.join(cache, name + '.json')
        if not offline:
            download(url, zp)
            with zipfile.ZipFile(zp) as z:
                open(jp, 'wb').write(z.read(name + '.json'))
        if not os.path.exists(jp):
            sys.exit(f'找不到 {jp}，請先不加 --offline 執行一次')
        j = json.loads(open(jp, 'rb').read().decode('utf-8-sig'))
        for L in j['Laws']:
            pc = re.search(r'pcode=([A-Z]\d{7})', L['LawURL']).group(1)
            idx[pc] = L
        print(f'{name}: 更新日 {j["UpdateDate"]}，{len(j["Laws"])} 筆')
    return idx

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--master', required=True); ap.add_argument('--cache', default='moj_cache')
    ap.add_argument('--out', default='更新偵測報告.md'); ap.add_argument('--offline', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    idx = load_open_data(a.cache, a.offline)
    art = pd.read_excel(a.master, '條文', dtype=str)
    ov = pd.read_excel(a.master, '機關總覽', dtype=str)
    ex = pd.read_excel(a.master, '例外', dtype=str)
    art['pcode'] = art['連結'].str.extract(r'pcode=([A-Z]\d{7})')[0]
    known = set(art['pcode'].dropna()) | set(ex['連結'].str.extract(r'pcode=([A-Z]\d{7})')[0].dropna())
    fid2pcode = {}
    for pc, L in idx.items():
        for att in L['LawAttachements']:
            m = re.search(r'FileId=(\d+)', att['FileURL'])
            if m: fid2pcode[m.group(1)] = pc
    for fid_url in ov['編制表來源'].dropna():
        m = re.search(r'FileId=(\d+)', str(fid_url))
        if m and m.group(1) in fid2pcode:
            known.add(fid2pcode[m.group(1)])  # 總表已收錄的編制表（以附件 FileId 反查 pcode）
    lines = [f'# 組織法規更新偵測報告', f'產生時間：{dt.datetime.now():%Y-%m-%d %H:%M}', '']

    # 1. 條文類法規
    changed, abolished = [], []
    for pc, g in art.groupby('pcode'):
        L = idx.get(pc); name = g['法規名稱'].iloc[0]; agency = g['機關'].iloc[0]; d0 = g['最新異動日'].iloc[0]
        if L is None:
            changed.append((agency, name, pc, d0, '', '開放資料查無（可能已廢止或改名）')); continue
        if L['LawAbandonNote']:
            abolished.append((agency, name, pc, L['LawAbandonNote'])); continue
        online = {x['ArticleNo'].replace(' ', ''): re.sub(r'\s+', '', x['ArticleContent']) for x in L['LawArticles'] if x['ArticleType'] == 'A'}
        mine = {str(k).replace(' ', ''): re.sub(r'\s+', '', str(v)) for k, v in zip(g['條號'], g['條文內容']) if '章節' not in str(k)}
        text_diff = sum(1 for k in set(online) | set(mine) if online.get(k) != mine.get(k))
        if L['LawModifiedDate'] != d0 or text_diff:
            changed.append((agency, name, pc, d0, L['LawModifiedDate'], f'條文差異 {text_diff} 條'))
    lines += ['## 一、組織法規／處務規程有異動', '']
    lines += ['| 機關 | 法規 | 總表異動日 | 線上異動日 | 說明 |', '|---|---|---|---|---|'] + \
             [f'| {x[0]} | [{x[1]}](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode={x[2]}) | {x[3]} | {x[4]} | {x[5]} |' for x in changed] if changed else ['（無）']
    lines += ['', '## 二、已廢止', ''] + ([f'- {x[0]}：{x[1]}（{x[3]}）' for x in abolished] or ['（無）'])

    # 2. 編制表附件
    tbl = []
    for _, r in ov.iterrows():
        m = re.search(r'FileId=(\d+)', str(r['編制表來源']))
        if not m: continue
        fid = m.group(1); pc = fid2pcode.get(fid)
        if pc is None:
            tbl.append((r['機關'], fid, '', '', '開放資料附件清單已無此 FileId（編制表可能已修正，請重新下載）')); continue
        L = idx[pc]
        if L['LawAbandonNote']:
            tbl.append((r['機關'], fid, pc, L['LawModifiedDate'], '編制表法規已廢止'))
    lines += ['', '## 三、編制表附件有異動', '']
    lines += ['| 機關 | 總表FileId | 編制表pcode | 線上修正日 | 說明 |', '|---|---|---|---|---|'] + \
             [f'| {x[0]} | {x[1]} | {x[2]} | {x[3]} | {x[4]} |' for x in tbl] if tbl else ['（無）']

    # 3. 新出現的組織類法規
    new = []
    for pc, L in idx.items():
        if pc in known or L['LawAbandonNote']: continue
        cat = L['LawCategory'].strip()
        if not (cat.startswith('行政') and '組織目' in cat): continue
        if not L['LawName'].endswith(ORG_SUFFIX): continue
        new.append((cat.split('＞')[1] if '＞' in cat else '', L['LawName'], pc, L['LawModifiedDate']))
    new.sort()
    lines += ['', '## 四、開放資料「組織目」中總表未收錄的組織類法規（請判斷是否為新機關或應納入）', '']
    lines += ['| 主管機關 | 法規 | 異動日 |', '|---|---|---|'] + \
             [f'| {x[0]} | [{x[1]}](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode={x[2]}) | {x[3]} |' for x in new] if new else ['（無）']
    open(a.out, 'w', encoding='utf-8').write('\n'.join(lines))
    print(f'異動法規 {len(changed)}、廢止 {len(abolished)}、編制表異動 {len(tbl)}、未收錄 {len(new)} → {a.out}')

if __name__ == '__main__':
    main()

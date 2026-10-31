#!/usr/bin/env python3
"""
補入新機關：讀 new_agencies.json，從開放資料（ChLaw/ChOrder JSON）取條文與編制表附件，下載 PDF 並解析，
寫入總表的「機關總覽」「編制表明細」「條文」「檢核_待人工確認」，另存新檔。

用法：
    python3 add_agencies.py --master 總表.xlsx --config new_agencies.json --cache moj_cache --pdf-dir pdfs --out 總表_新.xlsx [--offline]
"""
import argparse, datetime as dt, hashlib, json, os, re, subprocess, sys, time, zipfile
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reparse_pdfs import parse_pdf, cn_num
from check_updates import load_open_data

BASE = 'https://law.moj.gov.tw/LawClass/'

def curl(url, dest=None):
    cmd = ['curl', '-sS', '-L', '--max-time', '120', '-A', 'Mozilla/5.0', url] + (['-o', dest] if dest else [])
    for i in range(3):
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0 and (dest is None or os.path.exists(dest)):
            return r.stdout
        time.sleep(3 * (i + 1))
    return None

def articles_of(L, agency, batch):
    rows = []
    for x in L['LawArticles']:
        if x['ArticleType'] != 'A': continue
        rows.append({'批次': batch, '機關': agency, '法規名稱': L['LawName'],
                     '法規類別': '組織法規' if re.search(r'組織|設置條例', L['LawName']) else '處務規程/辦事細則',
                     '條號': x['ArticleNo'].replace(' ', ''), '條文內容': x['ArticleContent'].strip(),
                     '最新異動日': L['LawModifiedDate'], '連結': L['LawURL']})
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--master', required=True); ap.add_argument('--config', required=True)
    ap.add_argument('--cache', default='moj_cache'); ap.add_argument('--pdf-dir', default='pdfs')
    ap.add_argument('--out', required=True); ap.add_argument('--offline', action='store_true', help='不重新下載開放資料'); ap.add_argument('--no-pdf', action='store_true', help='不下載 PDF'); ap.add_argument('--batch', default='4'); ap.add_argument('--replace', action='store_true', help='機關已存在時先刪除舊資料再重新寫入（更新用）')
    a = ap.parse_args()
    os.makedirs(a.pdf_dir, exist_ok=True)
    idx = load_open_data(a.cache, a.offline)
    cfg = json.load(open(a.config, encoding='utf-8'))['agencies']
    sheets = pd.read_excel(a.master, sheet_name=None, dtype=str)
    ov, det, art, chk = sheets['機關總覽'], sheets['編制表明細'], sheets['條文'], sheets['檢核_待人工確認']
    existing = set(ov['機關'])
    now = dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00')
    new_ov, new_det, new_art, new_chk = [], [], [], []
    for c in cfg:
        name = c['機關']
        if name in existing and not a.replace:
            print('已存在，略過：', name); continue
        if name in existing:
            ov = ov[ov['機關'] != name]; det = det[det['機關名稱'] != name]; art = art[art['機關'] != name]; chk = chk[chk['機關名稱'] != name]
            print('更新（刪除舊資料）：', name)
        Lorg = idx.get(c['組織法規']); Lproc = idx.get(c['處務規程']) if c.get('處務規程') else None
        Ltab = idx.get(c['編制表']) if c.get('編制表') else None
        if Lorg is None: print('找不到組織法規', name, c['組織法規']); continue
        new_art += articles_of(Lorg, name, a.batch)
        if Lproc: new_art += articles_of(Lproc, name, a.batch)
        total, status, src, fid, rows = None, '無編制表', None, None, []
        if Ltab and Ltab['LawAttachements']:
            fid = re.search(r'FileId=(\d+)', Ltab['LawAttachements'][0]['FileURL']).group(1)
            src = f'{BASE}LawGetFile.ashx?FileId={fid}'
            p = os.path.join(a.pdf_dir, f"{c['編制表']}_{fid}.pdf")
            if not os.path.exists(p) and not a.no_pdf:
                curl(src + '&lan=C', p)
            if os.path.exists(p):
                rows, pdf_total = parse_pdf(p)
                for i, (unit, title, rank, grade, n, raw) in enumerate(rows, 1):
                    bm = re.search(r'[（(]([^（）()]+)[）)]', raw)
                    br = cn_num(re.split(r'[～~－—-]', bm.group(1))[0]) if bm else None
                    new_det.append({'批次': a.batch, '部會': c['部會'], '機關名稱': name, '附件': Ltab['LawAttachements'][0]['FileName'], '分表': None, '序': str(i),
                                    '單位': unit or None, '職稱': title, '官等': rank or None, '職等': grade or None,
                                    '員額': str(n) if n is not None else (('0') if br is not None else None), '員額上限': None, '員額原文': raw,
                                    '括號員額_兼任': str(br) if br is not None else None, '備註': None, '同職稱續列': None, 'PDF頁': None, '來源': src, '預算員額': None, '現有員額': None})
                s = sum(n for *_, n, _ in rows if n)
                total = pdf_total if pdf_total is not None else s
                status = '相符' if pdf_total == s else ('找不到合計' if pdf_total is None else '不相符')
                if status != '相符':
                    new_chk.append({'優先序': '3_合計不符或找不到', '批次': a.batch, '機關名稱': name, '類型': '人數合計檢查',
                                    '白話說明': f'每一列加起來是 {s} 人，表上「合計」為 {pdf_total}', '程式處理結果': status, '影響範圍': '總人數', 'PDF頁碼': '全部', 'PDF連結': src, '需要你做什麼': '請對照 PDF 核對'})
            else:
                status = '需人工輸入'
        new_ov.append({'批次': a.batch, '部會': c['部會'], '機關': name, '機關代碼': c['機關代碼'], '層級': str(c['層級']), '隸屬': c['隸屬'],
                       '組織法規名稱': Lorg['LawName'] + ('（上級機關訂的共用準則/通則，需確認）' if re.search(r'準則|通則', Lorg['LawName']) else ''),
                       '組織法規連結': Lorg['LawURL'], '編制表來源': src, '編制表下載時間': now if src else None,
                       '編制員額合計': str(total) if total is not None else None, '編制員額上限': str(total) if total is not None else None,
                       '預算員額': None, '現有員額': None, '驗算狀態': status, '分表說明': c.get('備註')})
        print(f'{name}: 條文 {len([r for r in new_art if r["機關"]==name])} 條，編制表 {len(rows)} 列，合計 {total}，{status}')
    sheets['機關總覽'] = pd.concat([ov, pd.DataFrame(new_ov)], ignore_index=True)
    sheets['編制表明細'] = pd.concat([det, pd.DataFrame(new_det)], ignore_index=True)
    sheets['條文'] = pd.concat([art, pd.DataFrame(new_art)], ignore_index=True)
    if new_chk: sheets['檢核_待人工確認'] = pd.concat([chk, pd.DataFrame(new_chk)], ignore_index=True)
    note = sheets['說明']
    sheets['說明'] = pd.concat([note, pd.DataFrame([[f'{dt.datetime.now():%Y-%m-%d %H:%M} 由 add_agencies.py 補入第 {a.batch} 批 {len(new_ov)} 個機關（{", ".join(x["機關"] for x in new_ov[:5])}…）']], columns=note.columns)], ignore_index=True)
    with pd.ExcelWriter(a.out, engine='openpyxl') as w:
        for sh, df in sheets.items():
            df.to_excel(w, sheet_name=sh, index=False, header=(sh != '說明'))
    print('已寫出', a.out, '新增機關', len(new_ov))

if __name__ == '__main__':
    main()

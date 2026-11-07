#!/usr/bin/env python3
"""產生更新用 manifest（manifest/sources.json）：每個機關採用哪個法規 pcode／附件 FileId／版本／hash／施行日，
以及共用法規依賴、人工 override 綁定、改制前後繼關係。只讀總表、開放資料快取、manual_fixes，不上網、不改資料。

用法：
    python3 update_manifest.py --master data/總表.xlsx --cache moj_cache [--pdf-dir moj_cache/pdfs] [--fixes manual_fixes.json] [--out manifest/sources.json]

欄位說明見 maintenance/2026-11-07_更新能力盤點與manifest規格.md 第二節。
semantic_sha256：以總表「編制表明細」該機關各列 (單位,職稱,官等,職等,員額原文,備註) 正規化後計算；
dry-run 對新 PDF 以 reparse_pdfs.parse_pdf 解析後用同一函式計算，相同即視為「內容相同（版面重排）」。
"""
import argparse, csv, datetime as dt, glob, hashlib, json, os, re, sys, unicodedata
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from check_updates import load_open_data

CN = '[○〇零一二三四五六七八九十百]+'
CNUM = {'〇': 0, '○': 0, '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
def cn_int(s):
    s = s.strip()
    if '百' in s or '十' in s:
        n, t = 0, s
        if '百' in t: a, t = t.split('百'); n += (CNUM[a] if a else 1) * 100
        if '十' in t: a, t = t.split('十'); n += (CNUM[a] if a else 1) * 10
        if t: n += CNUM[t[-1]]
        return n
    return int(''.join(str(CNUM[c]) for c in s))
DATE = re.compile(r'中華民國(' + CN + ')年(' + CN + ')月(' + CN + ')日')
def roc_iso(m): return f'{cn_int(m.group(1)) + 1911:04d}-{cn_int(m.group(2)):02d}-{cn_int(m.group(3)):02d}'

def parse_history(h):
    """LawHistories 沿革 → {promulgated, amended, effective, effective_basis, abolished}；解析不到留 None（不猜）。"""
    out = {'promulgated': None, 'amended': None, 'effective': None, 'effective_basis': None, 'abolished': None}
    if not h: return out
    items = re.split(r'\n(?=\d+\.)', h.replace('\r', '').strip())
    for it in items:
        t = re.sub(r'\s+', '', it); dates = [roc_iso(m) for m in DATE.finditer(t)]
        if not dates: continue
        if re.search(r'制定公布|訂定發布', t) and not out['promulgated']: out['promulgated'] = dates[0]
        if re.search(r'修正公布|修正發布', t): out['amended'] = dates[0]
        if '廢止' in t: out['abolished'] = dates[0]
        m = re.search(r'(?:定|並)自(' + CN + ')年(' + CN + ')月(' + CN + ')日(?:起)?施行', t)
        if m: out['effective'] = roc_iso(m); out['effective_basis'] = '沿革「' + m.group(0) + '」'
        elif re.search(r'自(?:公布|發布)日(?:起)?施行', t): out['effective'] = dates[0]; out['effective_basis'] = '沿革「自公布日施行」'
        elif re.search(r'施行日期，?由行政院(?:以命令)?定之', t) and not out['effective']: out['effective_basis'] = '沿革「施行日期由行政院定之」（尚無後續令，待核）'
    return out

def nz(v): return '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
def semantic_hash(rows):
    """rows: iterable of (單位, 職稱, 官等, 職等, 員額原文, 備註)；NFKC、去空白、去「ㄧ」字形差異後逐列串接。"""
    norm = lambda s: re.sub(r'\s+', '', unicodedata.normalize('NFKC', nz(s))).replace('ㄧ', '一')
    body = '\n'.join('|'.join(norm(x) for x in r) for r in rows)
    return hashlib.sha256(body.encode('utf-8')).hexdigest()
def sha_file(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
def pcode_of(url):
    m = re.search(r'pcode=([A-Z]\d{7})', nz(url)); return m.group(1) if m else None
def fileid_of(url):
    m = re.search(r'FileId=(\d+)', nz(url)); return m.group(1) if m else None
SHARED_RE = re.compile(r'(各|通則|準則)')

def build_manifest(master, cache, fixes_path, pdf_dir=None, judg_csv=None):
    idx = load_open_data(cache, offline=True)
    ov = pd.read_excel(master, '機關總覽', dtype=str); det = pd.read_excel(master, '編制表明細', dtype=str)
    art = pd.read_excel(master, '條文', dtype=str); exc = pd.read_excel(master, '例外', dtype=str)
    fixes = json.load(open(fixes_path, encoding='utf-8'))['fixes'] if fixes_path and os.path.exists(fixes_path) else []
    tbl_pcode = {L['LawName']: pc for pc, L in idx.items() if L['LawName'].endswith('編制表')}
    judg = {}
    if judg_csv and os.path.exists(judg_csv):
        for r in csv.DictReader(open(judg_csv, encoding='utf-8-sig')): judg[(r['機關'], r['法規名稱'])] = r['判定結論']
    # 改制前後繼（例外分頁）
    lineage = {}
    for _, r in exc[exc['狀態'] == '已由新組織法取代'].iterrows():
        codes = re.findall(r'\(([0-9A-Z]{10}),?\d*\)', nz(r['依據']))
        lineage.setdefault(nz(r['取代機關']), []).append({'predecessor': nz(r['推定機關名稱']), 'predecessor_code': codes[0] if codes else None, 'law': nz(r['組織法規']), 'basis': nz(r['依據'])[:160]})
    pdf_index = {}
    if pdf_dir and os.path.isdir(pdf_dir):
        for p in glob.glob(os.path.join(pdf_dir, '*.pdf')):
            fid = fileid_of(p) or (re.search(r'_(\d{10})\.pdf$', p) or [None, None])[1]
            if fid: pdf_index[fid] = p
    agencies, shared = [], {}
    art_by = {k: g for k, g in art.groupby('機關')}
    det_by = {k: g for k, g in det.groupby('機關名稱')}
    fix_by = {}
    for i, f in enumerate(fixes): fix_by.setdefault(f['機關'], []).append((f'mf-{i:04d}', f))
    for _, o in ov.iterrows():
        name = o['機關']; g = art_by.get(name)
        laws = []
        if g is not None:
            for (ln, cat, link), gg in g.groupby(['法規名稱', '法規類別', '連結']):
                pc = pcode_of(link); L = idx.get(pc) if pc else None
                h = parse_history(L['LawHistories']) if L else parse_history('')
                laws.append({'role': cat, 'pcode': pc, 'name': ln, 'promulgated': h['promulgated'], 'amended': h['amended'], 'effective': h['effective'], 'effective_basis': h['effective_basis'],
                             'status': ('廢止（開放資料註記）' if (L and L['LawAbandonNote'] == '廢') else ('開放資料未標廢止' if L else '不在開放資料')),
                             'open_data_modified': L['LawModifiedDate'] if L else None, 'master_modified': nz(gg['最新異動日'].iloc[0]) or None,
                             'articles_hash': hashlib.sha256('\n'.join(nz(x) for x in gg.sort_values('條號')['條文內容']).encode('utf-8')).hexdigest(),
                             'shared': bool(SHARED_RE.search(ln)) and cat == '組織法規'})
        sc = next((f for _, f in fix_by.get(name, []) if f['動作'] == '來源核對'), None)
        src_url = o['編制表來源']; superseded = []
        if sc and sc.get('取代編制表來源') and sc.get('來源'):
            superseded.append({'file_id': fileid_of(src_url), 'url': nz(src_url) or None, 'note': sc.get('歷史來源說明')}); src_url = sc['來源']
        fid = fileid_of(src_url)
        d = det_by.get(name)
        rows = [(r['單位'], r['職稱'], r['官等'], r['職等'], r['員額原文'], r['備註']) for _, r in d.sort_values(pd.to_numeric(d['序'], errors='coerce').sort_values().index if False else '序').iterrows()] if d is not None else []
        eff = None
        if d is not None:
            m = re.search(r'本編制表自(' + CN + ')年(' + CN + ')月(' + CN + ')日(?:起)?生效', ' '.join(nz(x) for x in pd.concat([d['備註'], d['職稱']])))
            if m: eff = roc_iso(m)
        st = {'pcode': tbl_pcode.get(name + '編制表'), 'file_id': fid, 'url': nz(src_url) or None,
              'byte_sha256': sha_file(pdf_index[fid]) if fid and fid in pdf_index else None,
              'semantic_sha256': semantic_hash(rows) if rows else None, 'row_count_master': len(rows),
              'effective': eff, 'effective_basis': '附註「本編制表自…生效」' if eff else None, 'fetched_at': nz(o.get('編制表下載時間')) or None, 'superseded': superseded}
        deps = []
        for l in laws:
            if l['shared'] and l['pcode']:
                jd = judg.get((name, l['name']), '')
                pending = jd.startswith('待審')
                deps.append({'pcode': l['pcode'], 'name': l['name'], 'pending': pending, 'judgement': jd or None})
                s = shared.setdefault(l['pcode'], {'name': l['name'], 'applies_to': [], 'pending': []})
                (s['pending'] if pending else s['applies_to']).append(o['機關代碼'])
        overrides = []
        for fid_, f in fix_by.get(name, []):
            if f['動作'] == '來源核對': continue
            scope = {k: f[k] for k in ('序', '職稱', '單位', '分表') if k in f and f[k] is not None}
            if f['動作'] == '改列': scope['欄位'] = list(f.get('新值', {}).keys())
            vf = (re.search(r'(2026-\d{2}-\d{2}|20\d{2}-\d{2}-\d{2})', nz(f.get('對源'))) or [None])[0] if f.get('對源') else None
            overrides.append({'fix_id': fid_, 'action': f['動作'], 'bound_to': {'file_id': fileid_of(f.get('來源')) or fid, 'semantic_sha256': st['semantic_sha256']},
                              'scope': scope, 'valid_from': vf, 'valid_until': None, 'evidence': {'PDF頁': f.get('PDF頁'), '來源': f.get('來源')}})
        agencies.append({'agency_id': o['機關代碼'], 'name': name, 'level': int(o['層級']), 'parent': o['隸屬'], 'ministry': o['部會'],
                         'lineage': {'predecessors': lineage.get(name, []), 'successors': []},
                         'laws': laws, 'staffing_table': st, 'shared_law_dependencies': deps, 'overrides': overrides})
    # successors 反向
    by_name = {a['name']: a for a in agencies}
    for a in agencies:
        for p in a['lineage']['predecessors']:
            pass  # 前身多已不在總覽；若在總覽則補 successors
    return {'schema': 1, 'generated_at': dt.datetime.now().astimezone().isoformat(timespec='seconds'),
            'master': {'path': os.path.relpath(master, HERE), 'sha256': sha_file(master)},
            'open_data': {'cache': os.path.relpath(cache, HERE), 'laws_in_cache': len(idx)},
            'agencies': agencies, 'shared_laws': shared}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--master', required=True); ap.add_argument('--cache', default=os.path.join(HERE, 'moj_cache'))
    ap.add_argument('--pdf-dir', default=None); ap.add_argument('--fixes', default=os.path.join(HERE, 'manual_fixes.json'))
    ap.add_argument('--judgements', default=os.path.join(HERE, 'maintenance', 'p2_evidence', 'p2b_1_共用法規掛接全清單.csv'))
    ap.add_argument('--out', default=os.path.join(HERE, 'manifest', 'sources.json'))
    a = ap.parse_args()
    m = build_manifest(a.master, a.cache, a.fixes, a.pdf_dir, a.judgements)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(m, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n_pdf = sum(1 for x in m['agencies'] if x['staffing_table']['byte_sha256']); n_ov = sum(len(x['overrides']) for x in m['agencies'])
    print(f"manifest：機關 {len(m['agencies'])}、法規 {sum(len(x['laws']) for x in m['agencies'])}、附件有 byte hash {n_pdf}、共用法規 {len(m['shared_laws'])}、override {n_ov} → {a.out}")

if __name__ == '__main__':
    main()

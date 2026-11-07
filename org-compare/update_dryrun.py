#!/usr/bin/env python3
"""更新 dry-run：由便宜到貴逐層比對，未變即停；只產報告與 pending_updates.json，不改總表、不改 manual_fixes、不建檔、不發布。

用法：
    python3 update_dryrun.py --manifest manifest/sources.json --master data/總表.xlsx --cache moj_cache [--offline] [--pdf-dir moj_cache/pdfs] [--out reports/dryrun_<日期>]

層級：
  1 開放資料（LawModifiedDate／附件 FileId／廢止）→ 無差異即停
  2 附件 byte hash（只對 FileId 變更者；--offline 時只查本地 pdf-dir）→ 相同即停（重傳同檔）
  3 語意 hash（pdfplumber 解析後正規化）→ 相同只更新 manifest；不同則逐列 diff
  4 解析失敗頁 → 標「需人工轉錄／OCR」，不自動處理
影響閉包：變更法規 → 專屬採用機關＋共用法規「相符」掛接機關（待審掛接不列入）；變更附件 → 該機關。
override：受影響機關之 override 綁定 FileId／semantic hash 與新值不符 → 待審（不套用、不刪除）。
"""
import argparse, collections, datetime as dt, hashlib, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from update_manifest import parse_history, semantic_hash, fileid_of

def attachments_of(L):
    out = []
    for att in (L or {}).get('LawAttachements') or []:
        m = re.search(r'FileId=(\d+)', att.get('FileURL', ''))
        if m: out.append(m.group(1))
    return out

def run_dryrun(manifest, open_idx, today, fetch_pdf=None, parse_pdf=None, offline=False):
    """純函式：manifest(dict)、open_idx({pcode: Law})、today(date)、fetch_pdf(file_id)->bytes|None、parse_pdf(bytes)->rows|None。
    回傳 summary dict。"""
    S = {'checked_at': dt.datetime.now().astimezone().isoformat(timespec='seconds'), 'today': today.isoformat(), 'offline': offline,
         'layer1_changes': [], 'layer2': [], 'layer3': [], 'affected_agencies': [], 'override_pending': [],
         'needs_ocr_or_transcription': [], 'published_not_effective': [], 'abolished': [], 'stopped_at': None, 'would_rebuild': False}
    ag_by_id = {a['agency_id']: a for a in manifest['agencies']}
    # ---- layer 1：法規與附件 ----
    law_changed = {}   # pcode -> change
    for a in manifest['agencies']:
        for l in a['laws']:
            pc = l['pcode']
            if not pc or pc in law_changed: continue
            L = open_idx.get(pc)
            if L is None:
                law_changed[pc] = {'pcode': pc, 'name': l['name'], 'kind': 'missing_in_open_data', 'old': l['open_data_modified'], 'new': None}; continue
            if L.get('LawAbandonNote') == '廢' and not l['status'].startswith('廢止'):
                law_changed[pc] = {'pcode': pc, 'name': l['name'], 'kind': 'abolished', 'old': l['status'], 'new': '廢'}; S['abolished'].append(pc); continue
            if L.get('LawModifiedDate') != l['open_data_modified']:
                h = parse_history(L.get('LawHistories', ''))
                ch = {'pcode': pc, 'name': l['name'], 'kind': 'law_modified', 'old': l['open_data_modified'], 'new': L.get('LawModifiedDate'), 'effective': h['effective'], 'effective_basis': h['effective_basis']}
                if h['effective'] and h['effective'] > today.isoformat():
                    ch['published_not_effective'] = True; S['published_not_effective'].append({'pcode': pc, 'name': l['name'], 'effective': h['effective']})
                law_changed[pc] = ch
        st = a['staffing_table']
        if st.get('pcode'):
            L = open_idx.get(st['pcode']); atts = attachments_of(L)
            if L is not None and st.get('file_id') and atts and st['file_id'] not in atts:
                S['layer1_changes'].append({'agency_id': a['agency_id'], 'name': a['name'], 'pcode': st['pcode'], 'kind': 'attachment_fileid', 'old': st['file_id'], 'new': atts[-1], 'candidates': atts})
    S['layer1_changes'] = list(law_changed.values()) + S['layer1_changes']
    if not S['layer1_changes']:
        S['stopped_at'] = 'layer1'; return S
    # ---- 影響閉包 ----
    affected = collections.OrderedDict()
    for ch in S['layer1_changes']:
        if ch['kind'] in ('law_modified', 'abolished', 'missing_in_open_data'):
            pc = ch['pcode']
            for a in manifest['agencies']:
                own = any(l['pcode'] == pc and not l['shared'] for l in a['laws'])
                dep_ok = any(d['pcode'] == pc and not d['pending'] for d in a['shared_law_dependencies'])
                if own or dep_ok:
                    affected.setdefault(a['agency_id'], {'agency_id': a['agency_id'], 'name': a['name'], 'reasons': [], 'action': 'review_articles'})['reasons'].append(f"{ch['kind']}:{pc}")
        elif ch['kind'] == 'attachment_fileid':
            affected.setdefault(ch['agency_id'], {'agency_id': ch['agency_id'], 'name': ch['name'], 'reasons': [], 'action': 'fetch_pdf'})['reasons'].append(f"attachment_fileid:{ch['old']}→{ch['new']}")
    # ---- layer 2／3：只對附件變更 ----
    for ch in [c for c in S['layer1_changes'] if c['kind'] == 'attachment_fileid']:
        a = ag_by_id[ch['agency_id']]; st = a['staffing_table']; rec = {'agency_id': a['agency_id'], 'file_id': ch['new']}
        data = fetch_pdf(ch['new']) if fetch_pdf else None
        if data is None:
            rec['byte_changed'] = None; rec['note'] = '離線或無法取得新附件，無法比對' ; S['layer2'].append(rec)
            affected[a['agency_id']]['action'] = 'fetch_pdf_manually'; continue
        b = hashlib.sha256(data).hexdigest(); rec['byte_sha256'] = b; rec['byte_changed'] = (b != st.get('byte_sha256')); S['layer2'].append(rec)
        if not rec['byte_changed']:
            affected[a['agency_id']]['action'] = 'update_manifest_only'; continue
        rows = parse_pdf(data) if parse_pdf else None
        r3 = {'agency_id': a['agency_id'], 'file_id': ch['new']}
        if rows is None:
            r3['semantic_changed'] = None; r3['note'] = '文字層無法解析'; S['layer3'].append(r3); S['needs_ocr_or_transcription'].append({'agency_id': a['agency_id'], 'name': a['name'], 'file_id': ch['new']})
            affected[a['agency_id']]['action'] = 'transcribe_manually'; continue
        sh = semantic_hash(rows); r3['semantic_sha256'] = sh; r3['semantic_changed'] = (sh != st.get('semantic_sha256'))
        if r3['semantic_changed']:
            old_rows = None
            r3['row_count_new'] = len(rows); r3['row_count_old'] = st.get('row_count_master'); affected[a['agency_id']]['action'] = 'reparse_and_review'; S['would_rebuild'] = True
        else:
            r3['note'] = '內容相同（版面重排或重傳）'; affected[a['agency_id']]['action'] = 'update_manifest_only'
        S['layer3'].append(r3)
        # override 檢查：語意相同（重傳／版面重排）時 override 仍有效，只需改綁新 FileId；語意變更或無法判定才列待審
        if r3.get('semantic_changed') is False: continue
        for ov in a['overrides']:
            bt = ov['bound_to']
            if (bt.get('file_id') and bt['file_id'] != ch['new']) or (bt.get('semantic_sha256') and r3.get('semantic_sha256') and bt['semantic_sha256'] != r3['semantic_sha256']):
                S['override_pending'].append({'agency_id': a['agency_id'], 'name': a['name'], 'fix_id': ov['fix_id'], 'action': ov['action'], 'scope': ov['scope'], 'bound_file_id': bt.get('file_id'), 'new_file_id': ch['new']})
    for a_id, rec in affected.items():
        if rec['action'] == 'review_articles': S['would_rebuild'] = True
    S['affected_agencies'] = list(affected.values())
    S['stopped_at'] = 'layer3' if S['layer3'] else ('layer2' if S['layer2'] else 'layer1+articles')
    return S

def write_reports(S, manifest, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    json.dump(S, open(os.path.join(out_dir, 'summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    L = [f"# 更新 dry-run 差異報告（{S['checked_at'][:10]}，manifest {manifest['generated_at'][:10]}，master {manifest['master']['sha256'][:12]}…）", '',
         f"停止層級：{S['stopped_at']}；是否需重建：{'是' if S['would_rebuild'] else '否'}；離線模式：{S['offline']}", '',
         f"## 第一層變更（{len(S['layer1_changes'])}）", '', '| 類型 | pcode／機關 | 舊 | 新 | 說明 |', '|---|---|---|---|---|']
    for c in S['layer1_changes']:
        L.append(f"| {c['kind']} | {c.get('name','')} {c.get('pcode','')} | {c.get('old')} | {c.get('new')} | {'已公布未施行 ' + str(c.get('effective')) if c.get('published_not_effective') else (c.get('effective_basis') or '')} |")
    L += ['', f"## 受影響機關（{len(S['affected_agencies'])}）", '', '| 機關代碼 | 機關 | 變更來源 | 建議動作 |', '|---|---|---|---|']
    L += [f"| {a['agency_id']} | {a['name']} | {'；'.join(a['reasons'])} | {a['action']} |" for a in S['affected_agencies']]
    L += ['', f"## 附件比對（第二／三層）", '', '| 機關代碼 | FileId | byte 變更 | 語意變更 | 說明 |', '|---|---|---|---|---|']
    l3 = {r['agency_id']: r for r in S['layer3']}
    L += [f"| {r['agency_id']} | {r['file_id']} | {r.get('byte_changed')} | {l3.get(r['agency_id'], {}).get('semantic_changed')} | {r.get('note') or l3.get(r['agency_id'], {}).get('note') or ''} |" for r in S['layer2']]
    L += ['', f"## override 待審（{len(S['override_pending'])}）", ''] + ([f"- {o['name']} {o['fix_id']} {o['action']} {o['scope']}：綁定 FileId {o['bound_file_id']} → 新 {o['new_file_id']}" for o in S['override_pending']] or ['（無）'])
    L += ['', f"## 需人工轉錄／OCR（{len(S['needs_ocr_or_transcription'])}）", ''] + ([f"- {x['name']} FileId {x['file_id']}" for x in S['needs_ocr_or_transcription']] or ['（無）'])
    L += ['', f"## 已公布未施行（{len(S['published_not_effective'])}）", ''] + ([f"- {x['name']} {x['pcode']} 施行 {x['effective']}" for x in S['published_not_effective']] or ['（無）'])
    L += ['', '本報告不改總表、不改 manual_fixes、不建檔、不發布；核准後依操作手冊第四節執行更新。']
    open(os.path.join(out_dir, 'diff.md'), 'w', encoding='utf-8').write('\n'.join(L))
    # pending_updates.json（沿用 add_agencies 格式）
    ag_by_id = {a['agency_id']: a for a in manifest['agencies']}
    pend = []
    for a in S['affected_agencies']:
        if a['action'] in ('update_manifest_only',): continue
        m = ag_by_id[a['agency_id']]
        pick = lambda role: next((l['pcode'] for l in m['laws'] if l['role'] == role and not l['shared']), None) or next((l['pcode'] for l in m['laws'] if l['role'] == role), '')
        pend.append({'機關': m['name'], '機關代碼': m['agency_id'], '層級': m['level'], '隸屬': m['parent'], '部會': m['ministry'], '組織法規': pick('組織法規'), '處務規程': pick('處務規程/辦事細則') or pick('處務規程'), '編制表': m['staffing_table'].get('pcode') or '', '備註': '；'.join(a['reasons']) + '｜' + a['action']})
    json.dump({'_說明': '由 update_dryrun.py 產生（尚未核准）：受影響機關；核准後執行 add_agencies.py --config pending_updates.json --replace', 'agencies': pend}, open(os.path.join(out_dir, 'pending_updates.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', default=os.path.join(HERE, 'manifest', 'sources.json')); ap.add_argument('--master', default=None)
    ap.add_argument('--cache', default=os.path.join(HERE, 'moj_cache')); ap.add_argument('--offline', action='store_true'); ap.add_argument('--pdf-dir', default=None)
    ap.add_argument('--out', default=os.path.join(HERE, 'reports', 'dryrun_' + dt.date.today().strftime('%Y%m%d')))
    a = ap.parse_args()
    from check_updates import load_open_data
    manifest = json.load(open(a.manifest, encoding='utf-8'))
    idx = load_open_data(a.cache, offline=a.offline)
    def fetch_pdf(fid):
        if a.pdf_dir:
            import glob
            for p in glob.glob(os.path.join(a.pdf_dir, f'*{fid}*.pdf')): return open(p, 'rb').read()
        if a.offline: return None
        from verify_tables_online import fetch
        r = fetch(f'https://law.moj.gov.tw/LawClass/LawGetFile.ashx?FileId={fid}')
        return r.content if r else None
    def parse_pdf(data):
        import tempfile
        from reparse_pdfs import parse_pdf as pp
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as t: t.write(data); path = t.name
        try:
            rows, total = pp(path)
            return [(u, t_, r_, g_, raw, '') for (u, t_, r_, g_, n_, raw) in rows] if rows else None
        except Exception: return None
        finally: os.unlink(path)
    S = run_dryrun(manifest, idx, dt.date.today(), fetch_pdf=fetch_pdf, parse_pdf=parse_pdf, offline=a.offline)
    write_reports(S, manifest, a.out)
    print(f"dry-run：第一層變更 {len(S['layer1_changes'])}、受影響機關 {len(S['affected_agencies'])}、override 待審 {len(S['override_pending'])}、停止於 {S['stopped_at']} → {a.out}")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""更新 dry-run 與 manifest 測試（離線、合成 fixture）。
用法：python3 tests/test_update_dryrun.py [--manifest manifest/sources.json]"""
import argparse, datetime as dt, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from update_dryrun import run_dryrun
from update_manifest import semantic_hash, parse_history
P = F = 0
def check(c, msg):
    global P, F
    print(('PASS ' if c else 'FAIL ') + msg); P += c; F += (not c)

TODAY = dt.date(2026, 11, 7)
ROWS_A = [('', '署長', '簡任', '第十三職等', '一', ''), ('', '科員', '委任或薦任', '第五職等', '十', '')]
ROWS_A2 = [('', '署長', '簡任', '第十三職等', '一', ''), ('', '科員', '委任或薦任', '第五職等', '十二', '')]
def mk_manifest():
    laws_shared = {'role': '組織法規', 'pcode': 'S0000001', 'name': '某部各醫院組織準則', 'open_data_modified': '20230101', 'status': '開放資料未標廢止', 'shared': True}
    return {'generated_at': '2026-11-07T00:00:00+08:00', 'master': {'sha256': 'x' * 64}, 'agencies': [
        {'agency_id': 'A00000001A', 'name': '甲醫院', 'level': 4, 'parent': '某部', 'ministry': '某部', 'laws': [laws_shared],
         'staffing_table': {'pcode': 'T0000001', 'file_id': '0000000001', 'byte_sha256': 'b1', 'semantic_sha256': semantic_hash(ROWS_A), 'row_count_master': 2},
         'shared_law_dependencies': [{'pcode': 'S0000001', 'name': laws_shared['name'], 'pending': False}],
         'overrides': [{'fix_id': 'mf-0001', 'action': '改列', 'bound_to': {'file_id': '0000000001', 'semantic_sha256': semantic_hash(ROWS_A)}, 'scope': {'序': 2}}]},
        {'agency_id': 'A00000002A', 'name': '乙老人之家', 'level': 4, 'parent': '某部', 'ministry': '某部', 'laws': [dict(laws_shared)],
         'staffing_table': {'pcode': 'T0000002', 'file_id': '0000000002', 'byte_sha256': 'b2', 'semantic_sha256': 'h2', 'row_count_master': 3},
         'shared_law_dependencies': [{'pcode': 'S0000001', 'name': laws_shared['name'], 'pending': True}], 'overrides': []},
        {'agency_id': 'A00000003A', 'name': '丙署', 'level': 3, 'parent': '某部', 'ministry': '某部',
         'laws': [{'role': '組織法規', 'pcode': 'O0000003', 'name': '丙署組織法', 'open_data_modified': '20200101', 'status': '開放資料未標廢止', 'shared': False}],
         'staffing_table': {'pcode': 'T0000003', 'file_id': '0000000003', 'byte_sha256': 'b3', 'semantic_sha256': 'h3', 'row_count_master': 5}, 'shared_law_dependencies': [], 'overrides': []}],
        'shared_laws': {'S0000001': {'applies_to': ['A00000001A'], 'pending': ['A00000002A']}}}
def law(mod, hist='', ab=''): return {'LawModifiedDate': mod, 'LawHistories': hist, 'LawAbandonNote': ab, 'LawAttachements': []}
def tbl(fids): return {'LawModifiedDate': '20230101', 'LawHistories': '', 'LawAbandonNote': '', 'LawAttachements': [{'FileURL': f'https://law.moj.gov.tw/LawClass/LawGetFile.ashx?FileId={f}'} for f in fids]}
BASE = {'S0000001': law('20230101'), 'O0000003': law('20200101'), 'T0000001': tbl(['0000000001']), 'T0000002': tbl(['0000000002']), 'T0000003': tbl(['0000000003'])}

# 1 未變即停
S = run_dryrun(mk_manifest(), BASE, TODAY)
check(S['stopped_at'] == 'layer1' and not S['layer1_changes'] and not S['affected_agencies'] and not S['would_rebuild'], '開放資料無差異 → 停在第一層，無下載、無受影響機關')
# 2 共用法規改一處：只影響「相符」掛接之甲醫院，不污染待審掛接之乙老人之家
idx = dict(BASE); idx['S0000001'] = law('20260601', '1.中華民國一百十二年一月一日訂定發布\n2.中華民國一百十五年六月一日修正發布第三條；並自發布日施行')
S = run_dryrun(mk_manifest(), idx, TODAY)
names = [a['name'] for a in S['affected_agencies']]
check(names == ['甲醫院'] and S['would_rebuild'] and not S['published_not_effective'], f'共用法規異動 → 受影響只有相符掛接之甲醫院（{names}），待審掛接之乙老人之家不列入')
# 3 已公布未施行
idx = dict(BASE); idx['O0000003'] = law('20261101', '1.中華民國一百零九年一月一日制定公布\n2.中華民國一百十五年十一月一日修正公布全文；施行日期由行政院定之\n  中華民國一百十五年十一月五日行政院令發布定自一百十六年一月一日施行')
S = run_dryrun(mk_manifest(), idx, TODAY)
check(len(S['published_not_effective']) == 1 and S['published_not_effective'][0]['effective'] == '2027-01-01' and S['layer1_changes'][0].get('published_not_effective'), '已公布未施行（施行 2027-01-01）→ 列待施行，不提前生效')
# 4 附件重傳同檔 → 第二層停，只更新 manifest
idx = dict(BASE); idx['T0000001'] = tbl(['0000000009'])   # 舊附件已自清單移除、換新 FileId
fetch = lambda fid: b'PDFBYTES-SAME'
import hashlib; m = mk_manifest(); m['agencies'][0]['staffing_table']['byte_sha256'] = hashlib.sha256(b'PDFBYTES-SAME').hexdigest()
S = run_dryrun(m, idx, TODAY, fetch_pdf=fetch, parse_pdf=lambda d: ROWS_A)
check(S['layer2'][0]['byte_changed'] is False and S['affected_agencies'][0]['action'] == 'update_manifest_only' and not S['override_pending'] and not S['would_rebuild'], '附件重傳同檔（byte 相同）→ 只更新 manifest，override 不受影響')
# 5 byte 不同但語意相同 → 只更新 manifest
S = run_dryrun(mk_manifest(), idx, TODAY, fetch_pdf=lambda f: b'OTHERBYTES', parse_pdf=lambda d: ROWS_A)
check(S['layer2'][0]['byte_changed'] and S['layer3'][0]['semantic_changed'] is False and S['affected_agencies'][0]['action'] == 'update_manifest_only' and not S['override_pending'], 'byte 不同、語意相同（版面重排）→ 只更新 manifest，override 維持')
# 6 語意不同 → 重解析待審，override 綁定 hash 不符 → 待審（不套用、不刪除）
S = run_dryrun(mk_manifest(), idx, TODAY, fetch_pdf=lambda f: b'OTHERBYTES', parse_pdf=lambda d: ROWS_A2)
check(S['layer3'][0]['semantic_changed'] and S['affected_agencies'][0]['action'] == 'reparse_and_review' and len(S['override_pending']) == 1 and S['override_pending'][0]['fix_id'] == 'mf-0001' and S['would_rebuild'], '語意變更 → 重解析待審；override mf-0001 因 hash／FileId 不符列待審')
# 7 解析失敗 → 需人工轉錄，不自動處理
S = run_dryrun(mk_manifest(), idx, TODAY, fetch_pdf=lambda f: b'IMG', parse_pdf=lambda d: None)
check(S['needs_ocr_or_transcription'] and S['affected_agencies'][0]['action'] == 'transcribe_manually', '文字層無法解析 → 標需人工轉錄／OCR，不自動處理')
# 8 離線且無本地檔 → 不比對、標人工取得
S = run_dryrun(mk_manifest(), idx, TODAY, fetch_pdf=lambda f: None, offline=True)
check(S['layer2'][0]['byte_changed'] is None and S['affected_agencies'][0]['action'] == 'fetch_pdf_manually', '離線無附件 → 不猜，標人工取得')
# 9 廢止
idx = dict(BASE); idx['O0000003'] = law('20200101', ab='廢')
S = run_dryrun(mk_manifest(), idx, TODAY)
check(S['abolished'] == ['O0000003'] and [a['name'] for a in S['affected_agencies']] == ['丙署'], '法規廢止 → 列廢止並只影響採用機關')
# 沿革解析
h = parse_history('1.中華民國一百十二年六月七日總統令制定公布全文 7 條；施行日期，由行政院以命令定之\n  中華民國一百十二年七月二十日行政院令發布定自一百十二年九月十五日施行')
check(h['promulgated'] == '2023-06-07' and h['effective'] == '2023-09-15' and h['amended'] is None, f'沿革解析：公布 {h["promulgated"]}、施行 {h["effective"]}、修正 {h["amended"]}（分欄，不合成）')
h2 = parse_history('1.中華民國一百十年十二月十五日總統令修正公布名稱及全文 15 條；施行日期由行政院定之')
check(h2['effective'] is None and '待核' in (h2['effective_basis'] or ''), '施行日由行政院定之且無後續令 → 施行日留空並標待核')

# 結構檢查（實際 manifest）
ap = argparse.ArgumentParser(); ap.add_argument('--manifest', default=os.path.join(ROOT, 'manifest', 'sources.json')); a = ap.parse_args()
if os.path.exists(a.manifest):
    M = json.load(open(a.manifest, encoding='utf-8')); A = {x['name']: x for x in M['agencies']}
    check(len(M['agencies']) == 585 and all(re.fullmatch(r'[A-Z0-9]{10}', x['agency_id']) for x in M['agencies']), 'manifest：585 機關、機關代碼格式一致')
    check(all((l['pcode'] is None or re.fullmatch(r'[A-Z]\d{7}', l['pcode'])) for x in M['agencies'] for l in x['laws']), 'manifest：每部法規一個 pcode')
    tc = A['衛生福利部臺中醫院']['staffing_table']
    check(tc['file_id'] == '0000427371' and tc['superseded'] and tc['superseded'][0]['file_id'] == '0000368769' and tc['byte_sha256'] == '354915997b8ec5026a62500c271097798e91bfd6ddf32a711df6f90bac296e8a', '臺中醫院：manifest FileId 0000427371（hash 一致），0000368769 為 superseded')
    fx = json.load(open(os.path.join(ROOT, 'manual_fixes.json'), encoding='utf-8'))['fixes']
    check(sum(len(x['overrides']) for x in M['agencies']) == sum(1 for f in fx if f['動作'] != '來源核對') and all(o['bound_to']['semantic_sha256'] or o['bound_to']['file_id'] for x in M['agencies'] for o in x['overrides'] if x['staffing_table']['row_count_master']), 'manifest：override 數＝manual_fixes 列層級修正數，且皆有綁定（FileId／semantic hash）')
    check(all(len(x['laws']) >= 1 for x in M['agencies']) and all(l['promulgated'] is None or re.fullmatch(r'\d{4}-\d{2}-\d{2}', l['promulgated']) for x in M['agencies'] for l in x['laws']), 'manifest：法規日期為 ISO 或空（不合成）')
    check(all(x['staffing_table']['semantic_sha256'] for x in M['agencies'] if x['staffing_table']['row_count_master']), 'manifest：有明細之機關皆有 semantic hash')
print(f'結果：PASS {P}、FAIL {F}')
sys.exit(1 if F else 0)

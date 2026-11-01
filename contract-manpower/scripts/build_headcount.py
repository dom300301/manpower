#!/usr/bin/env python3
"""
將 raw/stats/ 下載的官方統計檔（人事總處年報、銓敘部年報／概況統計、data.gov.tw 連結檔）
解析成 data/headcount.csv，並產生 data/headcount_sources.json。
執行：python3 -I contract-manpower/scripts/build_headcount.py
"""
import csv, json, os, re, sys, datetime, zipfile, warnings
import xml.etree.ElementTree as ET
warnings.filterwarnings('ignore')

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RAW = os.path.join(BASE, 'raw', 'stats')
DATA = os.path.join(BASE, 'data')
TODAY = datetime.date.today().isoformat()
FIELDS = ['year', 'year_ad', 'scope', 'agency_group', 'category', 'measure', 'value', 'unit',
          'source_name', 'source_url', 'note']
rows = []
sources = {}

DGPA_YB_PID = {114: 12873, 113: 12313, 112: 11812, 111: 11300, 110: 10939, 109: 10602, 108: 10130, 107: 9757}
DGPA_LOC_PID = {114: 12889, 113: 12308, 112: 11823, 111: 11320, 110: 10942, 109: 10601, 108: 9834, 107: 9673, 106: 8043, 105: 7360}


def yb_url(y):
    return f'https://www.dgpa.gov.tw/mp/info?mid=328&uid=499&pid={DGPA_YB_PID[y]}'


def loc_url(y):
    return f'https://www.dgpa.gov.tw/mp/info?mid=328&uid=331&pid={DGPA_LOC_PID[y]}'


def add(year, scope, agency, category, measure, value, source_name, source_url, note='', unit='人'):
    if value is None or value == '':
        return
    try:
        v = float(value)
    except (TypeError, ValueError):
        return
    if v != v:  # NaN
        return
    rows.append({'year': int(year), 'year_ad': int(year) + 1911, 'scope': scope, 'agency_group': agency,
                 'category': category, 'measure': measure, 'value': int(round(v)), 'unit': unit,
                 'source_name': source_name, 'source_url': source_url, 'note': note})


def reg_source(local, name, url, page_url, years, method, note=''):
    key = local
    sources[key] = {'name': name, 'download_url': url, 'page_url': page_url, 'download_date': TODAY,
                    'years_covered': years, 'local_path': 'contract-manpower/raw/stats/' + local,
                    'parse_method': method, 'note': note}


def norm(s):
    return re.sub(r'[\s　]+', '', str(s)) if s is not None else ''


def read_table(path):
    """回傳 list of rows（第一個工作表）。支援 xls / xlsx。"""
    if path.lower().endswith('.xls'):
        import xlrd
        sh = xlrd.open_workbook(path).sheet_by_index(0)
        return [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sh = wb.worksheets[0]
    return [list(r) for r in sh.iter_rows(values_only=True)]


def find_file(prefix):
    for f in sorted(os.listdir(RAW)):
        if f.startswith(prefix):
            return os.path.join(RAW, f)
    return None


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).replace(',', '').replace(' ', '').replace('　', '').strip()
    if s in ('', '-', '－', '…'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


CAT_MAP = {
    '實有總數': '實有總數(公教人力)', '政務人員': '政務人員', '公務人員': '公務人員', '警察人員': '警察人員',
    '醫事人員': '醫事人員', '法官': '法官', '檢察官': '檢察官', '教師': '教師', '聘用人員': '聘用', '約僱人員': '約僱',
    '事務性人力': '技工工友駐衛警(事務性人力)', '清潔隊員': '清潔隊員', '測量助理': '測量助理',
}

# ---------------------------------------------------------------- DGPA 年報 表1 / 表9（近十年）
def parse_yb_tenyear(y, table, scope, agency, note_extra=''):
    tag = {'表1': '表1_近十年行政院所屬公教人力實有人數', '表9': '表9_近十年地方政府所屬公教人力實有人數'}[table]
    path = find_file(f'dgpa_年報{y}_{tag}')
    if not path:
        return
    rs = read_table(path)
    hdr = None
    for i, r in enumerate(rs):
        if any(norm(c) == '實有總數' for c in r):
            hdr = i
            break
    cols = {j: CAT_MAP.get(norm(c)) for j, c in enumerate(rs[hdr]) if norm(c) in CAT_MAP}
    src = f'人事總處 {y}年行政院所屬及地方政府公教人力統計年報 {table}'
    out = []
    for r in rs[hdr + 1:]:
        yr = num(r[0])
        if yr is None or not (80 <= yr <= 120):
            continue
        for j, cat in cols.items():
            v = num(r[j]) if j < len(r) else None
            if v is not None:
                out.append((int(yr), cat, v))
    for yr, cat, v in out:
        add(yr, scope, agency, cat, '實有人數', v, src, yb_url(y), '年底實有人數(預算員額內實際在職)' + note_extra)
    reg_source(os.path.basename(path), src, yb_url(y), yb_url(y), f'{min(o[0] for o in out)}-{max(o[0] for o in out)}',
               'read_table→表頭對應欄位', '年報各年度皆重疊，headcount.csv 以涵蓋該年度之最新年報為準')
    return out


def pick_latest_tenyear(table, scope, agency):
    """同一年度若多本年報皆有，取最新年報的值；同時檢查舊年報數值是否一致。"""
    all_vals = {}
    for y in sorted(DGPA_YB_PID):
        tag = {'表1': '表1_', '表9': '表9_'}[table]
        path = find_file(f'dgpa_年報{y}_{tag}')
        if not path:
            continue
        rs = read_table(path)
        hdr = next(i for i, r in enumerate(rs) if any(norm(c) == '實有總數' for c in r))
        cols = {j: CAT_MAP.get(norm(c)) for j, c in enumerate(rs[hdr]) if norm(c) in CAT_MAP}
        for r in rs[hdr + 1:]:
            yr = num(r[0])
            if yr is None or not (80 <= yr <= 120):
                continue
            for j, cat in cols.items():
                v = num(r[j]) if j < len(r) else None
                if v is not None:
                    all_vals.setdefault((int(yr), cat), []).append((y, v, path))
    inconsistent = []
    for (yr, cat), lst in sorted(all_vals.items()):
        lst.sort()
        yb, v, path = lst[-1]
        vals = {int(x[1]) for x in lst}
        note = '年底實有人數(預算員額內實際在職)'
        if len(vals) > 1:
            note += '；舊年報數值不同:' + ','.join(f'{x[0]}年報={int(x[1])}' for x in lst[:-1])
            inconsistent.append((yr, cat, lst))
        src = f'人事總處 {yb}年行政院所屬及地方政府公教人力統計年報 {table}'
        add(yr, scope, agency, cat, '實有人數', v, src, yb_url(yb), note)
        reg_source(os.path.basename(path), src, yb_url(yb), yb_url(yb),
                   '近十年', 'read_table→表頭對應欄位', '各年度年報涵蓋近十年，csv 取涵蓋該年之最新年報')
    return inconsistent


# ---------------------------------------------------------------- DGPA 年報 表2 / 表10 / 附表1（各機關別）
def parse_yb_bygroup(y, table, scope_of_label, note=''):
    tag = {'表2': '表2_', '表10': '表10_', '附表1': '附表1_'}[table]
    path = find_file(f'dgpa_年報{y}_{tag}')
    if not path:
        return
    rs = read_table(path)
    hdr = next(i for i, r in enumerate(rs) if any(norm(c) == '實有總數' for c in r))
    cols = {j: CAT_MAP.get(norm(c)) for j, c in enumerate(rs[hdr]) if norm(c) in CAT_MAP}
    first_col = min(cols)
    src = f'人事總處 {y}年行政院所屬及地方政府公教人力統計年報 {table}'
    n = 0
    for r in rs[hdr + 1:]:
        labels = [norm(c) for c in r[:first_col] if isinstance(c, str) and norm(c)]
        if not labels:
            continue
        label = labels[-1]
        if table in ('表2', '表10') and label == '合計':
            continue  # 合計列已由表1/表9 涵蓋
        scope, agency = scope_of_label(label)
        for j, cat in cols.items():
            v = num(r[j]) if j < len(r) else None
            if v is not None:
                add(y, scope, agency, cat, '實有人數', v, src, yb_url(y), note)
                n += 1
    reg_source(os.path.basename(path), src, yb_url(y), yb_url(y), str(y), 'read_table→表頭對應欄位，列標籤為機關')
    return n


def scope_tbl2(label):
    return ('中央', label)


def scope_tbl10(label):
    return ('地方', label)


def scope_app1(label):
    if label.startswith('中央') or label in ('總統府所屬', '行政院所屬', '立法院所屬', '司法院所屬', '考試院所屬', '監察院所屬'):
        return ('中央', label)
    if label.startswith('地方'):
        return ('地方', label)
    return ('地方', label)


# ---------------------------------------------------------------- 附表5 預算員額
def parse_app5():
    all_vals = {}
    for y in sorted(DGPA_YB_PID):
        path = find_file(f'dgpa_年報{y}_附表5_')
        if not path:
            continue
        rs = read_table(path)
        for r in rs:
            yr = num(r[0])
            if yr is None or not (80 <= yr <= 120):
                continue
            vals = [num(c) for c in r[1:5]]
            all_vals.setdefault(int(yr), []).append((y, vals, path))
    groups = [('行政院所屬合計', '合計(公務預算+作業基金)'), ('行政院所屬-公務預算', '公務預算'),
              ('行政院所屬-作業基金', '作業基金'), ('行政院以外機關合計', '總統府、立法院、司法院、考試院、監察院及所屬')]
    for yr, lst in sorted(all_vals.items()):
        lst.sort()
        yb, vals, path = lst[-1]
        src = f'人事總處 {yb}年行政院所屬及地方政府公教人力統計年報 附表5'
        for (g, gnote), v in zip(groups, vals):
            note = f'中央政府總預算案編列之預算員額（各類人員合計）；{gnote}'
            older = [x for x in lst[:-1] if x[1][groups.index((g, gnote))] != v]
            if older:
                note += '；舊年報數值不同:' + ','.join(f'{x[0]}年報={int(x[1][groups.index((g, gnote))])}' for x in older)
            add(yr, '中央', g, '全體(預算員額)', '預算員額', v, src, yb_url(yb), note)
        reg_source(os.path.basename(path), src, yb_url(yb), yb_url(yb), '近十年', 'read_table')


# ---------------------------------------------------------------- 附表6 臨時/約用人員
def parse_app6():
    for y in sorted(DGPA_YB_PID):
        path = find_file(f'dgpa_年報{y}_附表6_')
        if not path:
            continue
        rs = read_table(path)
        title = norm(rs[0][0])
        hdr = next(i for i, r in enumerate(rs) if any('季' in norm(c) for c in r))
        qcols = {j: norm(c) for j, c in enumerate(rs[hdr]) if '季' in norm(c)}
        src = f'人事總處 {y}年行政院所屬及地方政府公教人力統計年報 附表6({"約用人員" if "約用" in title else "臨時人員"})'
        for r in rs[hdr + 1:]:
            labels = [norm(c) for c in r[:min(qcols)] if isinstance(c, str) and norm(c)]
            if not labels or labels[-1].startswith('註'):
                continue
            label = labels[-1]
            agency = '行政院所屬合計' if '合計' in label else '行政院所屬-' + label
            for j, q in qcols.items():
                v = num(r[j]) if j < len(r) else None
                if v is not None:
                    note = f'{q}底全日工時人數；' + ('107年第2季起調查' if y == 107 else '') + (
                        '113年起名稱由臨時人員改為約用人員（依約用人員進用及運用要點）' if y >= 113 else '依臨時人員進用及運用要點進用之全日工時人員')
                    add(y, '中央', agency, '臨時人員(約用)', '實際人數', v, src, yb_url(y), note.replace('；113', '；113').strip('；'))
        reg_source(os.path.basename(path), src, yb_url(y), yb_url(y), str(y), 'read_table（各季）')


# ---------------------------------------------------------------- 地方要覽 依員額統計
LOC_CAT = {'總計': ('實有總數(員工)', '實有人數'), '正式職(教)員': ('正式職(教)員', '實有人數'), '民選首長': ('民選首長', '實有人數'),
           '政務人員': ('政務人員', '實有人數'), '職員': ('職員(含警察、醫事等正式職員)', '實有人數'), '校長及教師': ('教師', '實有人數'),
           '聘用人員': ('聘用', '實有人數'), '約僱人員': ('約僱', '實有人數'), '技工': ('技工', '實有人數'), '駕駛': ('駕駛', '實有人數'),
           '工友': ('工友', '實有人數'), '正式工員(船員)': ('正式工員(船員)', '實有人數'), '駐衛警': ('駐衛警', '實有人數'),
           '測量助理': ('測量助理', '實有人數')}


def parse_local_overview():
    for y in sorted(DGPA_LOC_PID):
        path = find_file(f'dgpa_地方要覽{y}_依員額統計.xls')
        if not path:
            continue
        rs = read_table(path)
        hdr = next(i for i, r in enumerate(rs) if any(norm(c) == '聘用人員' for c in r))
        sub = rs[hdr + 1]
        cols = {}
        for j, c in enumerate(rs[hdr]):
            c = norm(c)
            if c in LOC_CAT and c != '正式職(教)員':
                cols[j] = LOC_CAT[c]
        for j, c in enumerate(sub):
            c = norm(c)
            if c == '合計':
                cols[j] = LOC_CAT['正式職(教)員']
            elif c in LOC_CAT:
                cols[j] = LOC_CAT[c]
        # 預算員額欄（表頭上一列「正式職(教)員預算員額」）
        bcol = None
        for i in range(hdr - 2, hdr):
            for j, c in enumerate(rs[i]):
                if '預算員額' in norm(c):
                    bcol = j
        src = f'人事總處 {y}年直轄市、各縣市統計要覽 依員額統計'
        seen_total = False
        for r in rs[hdr + 2:]:
            label = norm(r[0]) if r and isinstance(r[0], str) else ''
            if not label or label in ('男', '女') or '審核' in label or '統計人員' in label:
                continue
            if label == '合計':
                if seen_total:
                    continue
                seen_total = True
                agency = '地方政府合計'
            else:
                agency = label
            if bcol is not None:
                v = num(r[bcol])
                if v is not None:
                    add(y, '地方', agency, '正式職(教)員', '預算員額', v, src, loc_url(y), '直轄市、縣市所屬機關學校正式職(教)員預算員額（不含鄉鎮市）')
            for j, (cat, meas) in cols.items():
                v = num(r[j]) if j < len(r) else None
                if v is not None:
                    add(y, '地方', agency, cat, meas, v, src, loc_url(y), '年底實有員工數；統計範圍為直轄市、縣市政府所屬機關學校（不含鄉鎮市及議會）')
        reg_source(os.path.basename(path), src, loc_url(y), loc_url(y), str(y), 'read_table→表頭對應欄位')


# ---------------------------------------------------------------- 銓敘部 表10 歷年全國公務人力概況（PDF→文字）
def parse_mocs_t10():
    path = find_file('mocs_概況統計_表10歷')
    txt = pdf_text(path)
    page1 = txt.split('=== page 2 ===')[0]
    url = 'https://www.mocs.gov.tw/FileUpload/1090-4043/Documents//表10歷年全國公務人力概況.pdf'
    page = 'https://www.mocs.gov.tw/pages/list.aspx?Node=1090&Type=1&Index=1'
    src = '銓敘部 統計專題-公務人員概況統計 表10 歷年全國公務人力概況'
    cols = [('公務人員(銓敘部定義,含公營事業)', '全體'), ('公務人員(銓敘部定義)', '行政機關'), ('公務人員(銓敘部定義)', '公營事業機構'),
            ('公務人員(銓敘部定義)', '衛生醫療機構'), ('公務人員(銓敘部定義)', '公立學校職員'), ('其他公務人力合計', '全體'),
            ('聘用+約僱(約聘僱人員)', '全體'), ('技工工友(職工)', '全體'), ('駐衛警', '全體'), ('臨時人員(約用)', '全體'),
            ('勞力派遣人員', '全體'), ('教師(公立學校)', '全體'), ('軍職人員', '全體')]
    years = []
    for line in page1.splitlines():
        m = re.match(r'民國\s*(\d+)年\s+\d{4}\s+(.*)', line)
        if not m:
            continue
        yr = int(m.group(1))
        toks = m.group(2).split()
        vals = []
        for t in toks:
            if t == '1' and len(vals) >= 12:  # 註腳標記「1」
                continue
            vals.append(num(t))
        if len(vals) != len(cols):
            print('warn t10', yr, len(vals), file=sys.stderr)
        years.append(yr)
        for (cat, agency), v in zip(cols, vals):
            note = '年底人數；全國（中央+地方+公營事業）；資料來源全國公務人力資料庫、退撫基金、人事總處'
            if cat == '臨時人員(約用)':
                note += '；101年起統計，臨時人員(全日工時)，113年起改稱約用人員'
            if cat == '勞力派遣人員':
                note += '；101-109年統計，110年起不再列計'
            if cat == '軍職人員':
                note += '；參加退撫基金之軍職人數'
            if cat == '公務人員(銓敘部定義,含公營事業)':
                note += '；銓敘部公務人員=送審之職員(含警察、法警)+公營事業+衛生醫療+公立學校職員，不含教師、聘僱、工友'
            add(yr, '全國', agency, cat, '實際人數', v, src, url, note)
    reg_source(os.path.basename(path), src, url, page, f'{min(years)}-{max(years)}', 'pdfplumber 文字→正規表示式逐列解析')


def parse_mocs_t1():
    path = find_file('mocs_概況統計_表1歷')
    txt = pdf_text(path)
    page1 = txt.split('=== page 2 ===')[0]
    url = 'https://www.mocs.gov.tw/FileUpload/1090-4043/Documents//表1歷年全國公務人員人數按機關別分.pdf'
    page = 'https://www.mocs.gov.tw/pages/list.aspx?Node=1090&Type=1&Index=1'
    src = '銓敘部 統計專題-公務人員概況統計 表1 歷年全國公務人員人數按機關別分'
    # 欄位：總計 男 女 中央 地方計 臺灣各縣市 新北 臺北 桃園 臺中 臺南 高雄 金門連江 行政機關計 中央 地方 公營計 中央 地方 衛生計 中央 地方 學校計 中央 地方
    spec = [(0, '全國', '全體'), (3, '中央', '中央各機關'), (4, '地方', '地方各機關合計'), (5, '地方', '臺灣各縣市機關'),
            (6, '地方', '新北市各機關'), (7, '地方', '臺北市各機關'), (8, '地方', '桃園市各機關'), (9, '地方', '臺中市各機關'),
            (10, '地方', '臺南市各機關'), (11, '地方', '高雄市各機關'), (12, '地方', '金門縣、連江縣各機關'),
            (13, '全國', '行政機關'), (14, '中央', '行政機關'), (15, '地方', '行政機關'), (16, '全國', '公營事業機構'),
            (17, '中央', '公營事業機構'), (18, '地方', '公營事業機構'), (19, '全國', '衛生醫療機構'), (20, '中央', '衛生醫療機構'),
            (21, '地方', '衛生醫療機構'), (22, '全國', '公立學校職員'), (23, '中央', '公立學校職員'), (24, '地方', '公立學校職員')]
    years = []
    for line in page1.splitlines():
        m = re.match(r'民國\s*(\d+)年\s+\d{4}\s+(.*)', line)
        if not m:
            continue
        yr = int(m.group(1))
        vals = [num(t) for t in m.group(2).split()]
        if len(vals) < 25:
            continue
        years.append(yr)
        for idx, scope, agency in spec:
            add(yr, scope, agency, '公務人員(銓敘部定義,含公營事業)', '實際人數', vals[idx], src, url,
                '年底人數；銓敘部定義公務人員（送審職員含警察、法警，含公營事業、衛生醫療、學校職員，不含教師、聘僱、工友）')
    reg_source(os.path.basename(path), src, url, page, f'{min(years)}-{max(years)}', 'pdfplumber 文字→正規表示式逐列解析')


def parse_mocs_99():
    path = find_file('mocs_年報99_表1-14')
    sheets = read_ods(path)
    name = next(n for n in sheets if n.startswith('表1'))
    url = 'https://www.mocs.gov.tw/FileUpload/937-2856/Documents//表1～表14.ods'
    page = 'https://www.mocs.gov.tw/pages/list.aspx?Node=937&Type=1&Index=1'
    src = '銓敘部 99年銓敘統計年報 表1 全國公務人員人數按年別分'
    years = []
    for r in sheets[name]:
        if not r or not isinstance(r[0], str) or not r[0].startswith('民國'):
            continue
        m = re.match(r'民國(\d+)年', r[0])
        if not m:
            continue
        yr = int(m.group(1))
        if yr >= 95:
            continue  # 95年以後以概況統計 PDF 為準
        vals = [num(c) for c in r[2:]]
        tot, cen = vals[0], vals[2]
        loc = tot - cen  # 99年報表1無「地方合計」欄，以總計減中央計算（=臺灣各縣市+臺北市+高雄市+金門連江）
        years.append(yr)
        for scope, agency, v in [('全國', '全體', tot), ('中央', '中央各機關', cen), ('地方', '地方各機關合計', loc)]:
            add(yr, scope, agency, '公務人員(銓敘部定義,含公營事業)', '實際人數', v, src, url,
                '年底人數；銓敘部定義公務人員；地方各機關合計=總計-中央各機關（年報無合計欄）')
    reg_source(os.path.basename(path), src, url, page, f'{min(years)}-{max(years)}', '自製 ODS 讀取器(content.xml)')


# ---------------------------------------------------------------- data.gov.tw 68029 行政院及所屬各主管機關臨時人員人數(107Q1)
def parse_datagov_68029():
    page = 'https://data.gov.tw/dataset/68029'
    for fn, scope_agency in [('dgpa_datagov68029_1-15-1', '行政院所屬'), ('dgpa_datagov68029_1-15-2', '行政院以外中央機關')]:
        path = find_file(fn)
        raw = open(path, 'rb').read()
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = raw.decode('cp950')
        src = f'data.gov.tw 68029 行政院及所屬各主管機關臨時人員人數({scope_agency},107年第1季)'
        url = 'https://data.gov.tw/dataset/68029'
        n = 0
        for i, r in enumerate(csv.reader(text.splitlines())):
            if i == 0 or not r or not r[0].strip():
                continue
            agency = r[0].strip()
            if scope_agency == '行政院所屬':
                for col, kind in zip(r[1:4], ['行政機關', '公立學校', '公立醫療機構']):
                    v = num(col)
                    if v is not None:
                        add(107, '中央', f'{agency}-{kind}', '臨時人員(約用)', '實際人數', v, src, url, '107年第1季；人事總處開放資料集(現已下架之舊版資料)')
                        n += 1
            else:
                v = num(r[1])
                if v is not None:
                    add(107, '中央', agency, '臨時人員(約用)', '實際人數', v, src, url, '107年第1季；人事總處開放資料集')
                    n += 1
        reg_source(os.path.basename(path), src, url, page, '107', 'csv(cp950)')


# ---------------------------------------------------------------- 人事總處 政府員額管理相關資訊 PDF (115.9.8) 手動摘錄
def manual_dgpa_pdf():
    url = 'https://www.dgpa.gov.tw/FileConversion?filename=dgpa/files/202609/a0cc5b49-3c37-4201-95fd-78ec3f50ea95.pdf&nfix=&name=11508政府員額管理相關資訊.pdf'
    page = 'https://www.dgpa.gov.tw/information?uid=375&pid=13101'
    src = '人事總處 政府員額管理相關資訊(115.9.8)'
    note_pdf = '自 PDF 文字摘錄'
    add(99, '中央', '中央政府各機關(總預算)', '全體(預算員額)', '預算員額', 232978, src, url, note_pdf + '；99年度中央政府總預算預算員額總數')
    add(101, '中央', '中央政府各機關(總預算)', '全體(預算員額)', '預算員額', 233204, src, url, note_pdf + '；101年度（行政院組織調整啟動時）')
    add(116, '中央', '中央政府各機關(總預算)', '全體(預算員額)', '預算員額', 220743, src, url, note_pdf + '；116年度中央政府總預算案')
    add(99, '中央', '總員額法適用範圍', '全體(預算員額)', '預算員額', 164587, src, url, note_pdf + '；總員額法施行日99.4.1適用範圍預算員額')
    add(116, '中央', '總員額法適用範圍', '全體(預算員額)', '預算員額', 138061, src, url, note_pdf + '；116年度；108.12.31修法後公立醫院職員排除於適用範圍')
    add(99, '中央', '非總員額法適用範圍', '全體(預算員額)', '預算員額', 68631, src, url, note_pdf + '；99.4.1')
    add(116, '中央', '非總員額法適用範圍', '全體(預算員額)', '預算員額', 82682, src, url, note_pdf + '；116年度')
    add(115, '全國', '公部門整體(不含軍職)', '全體(各類人力)', '實際人數', 914995, src, url, note_pdf + '；115年1月；含中央、地方、事業機構')
    add(115, '中央', '中央機關(整體人力)', '全體(各類人力)', '實際人數', 283749, src, url, note_pdf + '；115年1月；職員(含警察法警教師)+其他人力')
    add(115, '地方', '地方政府(整體人力)', '全體(各類人力)', '實際人數', 490215, src, url, note_pdf + '；115年1月')
    add(115, '全國', '事業機構(整體人力)', '全體(各類人力)', '實際人數', 141031, src, url, note_pdf + '；115年1月；事業機構臨時職員含聘用及約僱')
    add(104, '中央', '中央各機關', '公務人員(銓敘部定義,含公營事業)', '實際人數', 187054, src, url, note_pdf + '；引用銓敘統計年報')
    add(114, '中央', '中央各機關', '公務人員(銓敘部定義,含公營事業)', '實際人數', 190588, src, url, note_pdf + '；引用銓敘統計年報')
    add(104, '地方', '地方各機關合計', '公務人員(銓敘部定義,含公營事業)', '實際人數', 160498, src, url, note_pdf + '；引用銓敘統計年報')
    add(114, '地方', '地方各機關合計', '公務人員(銓敘部定義,含公營事業)', '實際人數', 169492, src, url, note_pdf + '；引用銓敘統計年報')
    reg_source('dgpa_11508政府員額管理相關資訊.pdf', src, url, page, '99-116(部分年度)', 'pdfplumber 文字→人工摘錄數字')


# ---------------------------------------------------------------- WebSearch 摘要（未取得原文，僅供參考）
def manual_websearch():
    n = 'WebSearch 搜尋摘要；原始網域(ly.gov.tw / 新聞網站)本環境無法連線，數字未經原文核對'
    src1 = '立法院預算中心 中央政府聘用及約僱人力運用情形之探討(114.7)【搜尋摘要】'
    u1 = 'https://www.ly.gov.tw/Pages/Detail.aspx?nodeid=56067&pid=252977'
    add(110, '中央', '中央機關(總預算)', '聘用+約僱(約聘僱人員)', '預算員額', 15770, src1, u1, n)
    add(114, '中央', '中央機關(總預算)', '聘用+約僱(約聘僱人員)', '預算員額', 16249, src1, u1, n)
    add(110, '中央', '中央機關(總預算)', '職員(總員額法用語)', '預算員額', 186389, src1, u1, n)
    add(114, '中央', '中央機關(總預算)', '職員(總員額法用語)', '預算員額', 191435, src1, u1, n)
    src2 = '人事總處新聞澄清(114.10.22，中央社/自由時報/風傳媒轉述)【搜尋摘要】'
    u2 = 'https://www.cna.com.tw/news/aipl/202510220259.aspx'
    add(115, '中央', '中央機關(總預算)', '聘用+約僱(約聘僱人員)', '預算員額', 16375, src2, u2, n + '；115年度中央政府機關總預算案所列聘僱人數')
    sources['websearch_摘要'] = {'name': '搜尋摘要來源', 'download_url': [u1, u2, 'https://www.storm.mg/lifestyle/11075798',
                                 'https://news.ltn.com.tw/news/politics/breakingnews/5220469'],
                                 'page_url': '', 'download_date': TODAY, 'years_covered': '110-115', 'local_path': '',
                                 'parse_method': 'WebSearch 摘要人工抄錄', 'note': '網域被擋，未能下載原文'}


# ---------------------------------------------------------------- helpers
def pdf_text(path):
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        for i, pg in enumerate(pdf.pages):
            out.append(f'=== page {i + 1} ===\n' + (pg.extract_text() or ''))
    return '\n'.join(out)


NS = {'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0', 'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
      'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0'}


def read_ods(path):
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read('content.xml'))
    sheets = {}
    for t in root.iter('{%s}table' % NS['table']):
        name = t.get('{%s}name' % NS['table'])
        rs = []
        for r in t.iter('{%s}table-row' % NS['table']):
            row = []
            for c in r:
                if not (c.tag.endswith('table-cell') or c.tag.endswith('covered-table-cell')):
                    continue
                rep = int(c.get('{%s}number-columns-repeated' % NS['table'], '1'))
                v = c.get('{%s}value' % NS['office'])
                if v is None:
                    v = ''.join(c.itertext())
                else:
                    v = float(v)
                row.extend([v] * min(rep, 100))
            while row and row[-1] in ('', None):
                row.pop()
            rs.append(row)
        sheets[name] = rs
    return sheets


# ---------------------------------------------------------------- main
def main():
    inc1 = pick_latest_tenyear('表1', '中央', '行政院所屬')
    inc9 = pick_latest_tenyear('表9', '地方', '地方政府合計')
    for y in sorted(DGPA_YB_PID):
        parse_yb_bygroup(y, '表2', scope_tbl2, '年底實有人數；行政院各部會所屬（含所屬機關、學校、醫療機構）')
        parse_yb_bygroup(y, '表10', scope_tbl10, '年底實有人數；各地方政府所屬（含所屬機關、學校、醫療機構）')
        parse_yb_bygroup(y, '附表1', scope_app1, '年底實有人數；全國依政府別')
    parse_app5()
    parse_app6()
    parse_local_overview()
    parse_mocs_t10()
    parse_mocs_t1()
    parse_mocs_99()
    parse_datagov_68029()
    manual_dgpa_pdf()
    manual_websearch()
    # 其他下載但未解析進 csv 的檔案也登錄
    extra = [
        ('mocs_年報114_一_全國公務人員概況.ods', '銓敘部 114年銓敘統計年報 一、公務人員概況統計(表1-17)', 'https://www.mocs.gov.tw/FileUpload/2137-15330/Documents//9.(一)全國公務人員概況.ods', 'https://www.mocs.gov.tw/pages/detail.aspx?Node=2137&Page=15330&Index=1', '105-114', '未解析（表1 數值與概況統計 PDF 一致）'),
        ('mocs_年報114_二_行政機關公務人員概況.ods', '銓敘部 114年銓敘統計年報 二、行政機關公務人員概況(表18-26)', 'https://www.mocs.gov.tw/FileUpload/2137-15330/Documents//10.(二)行政機關公務人員概況.ods', 'https://www.mocs.gov.tw/pages/detail.aspx?Node=2137&Page=15330&Index=1', '114', '未解析'),
        ('mocs_年報114_提要分析.pdf', '銓敘部 114年銓敘統計年報 提要分析', 'https://www.mocs.gov.tw/FileUpload/2133-15323/Documents//6.114年報提要分析.pdf', 'https://www.mocs.gov.tw/pages/detail.aspx?Node=2133&Page=15323&Index=1', '114', '未解析'),
        ('mocs_年報99_表15-23_行政機關公務人員概況.ods', '銓敘部 99年銓敘統計年報 二、行政機關公務人員概況', 'https://www.mocs.gov.tw/FileUpload/937-2856/Documents//表15～表23.ods', 'https://www.mocs.gov.tw/pages/detail.aspx?Node=937&Page=2856&Index=1', '99', '未解析'),
        ('mocs_概況統計_表2歷年全國公務人員人數按人員類別分.pdf', '銓敘部 概況統計 表2 歷年全國公務人員人數按人員類別分', 'https://www.mocs.gov.tw/FileUpload/1090-4043/Documents//表2歷年全國公務人員人數按人員類別分.pdf', 'https://www.mocs.gov.tw/pages/list.aspx?Node=1090&Type=1&Index=1', '95-114', '未解析（官等別）'),
        ('mocs_概況統計_表7歷年全國公務人員人數按銓敘狀況分.pdf', '銓敘部 概況統計 表7 歷年全國公務人員人數按銓敘狀況分', 'https://www.mocs.gov.tw/FileUpload/1090-4043/Documents//表7歷年全國公務人員人數按銓敘狀況分.pdf', 'https://www.mocs.gov.tw/pages/list.aspx?Node=1090&Type=1&Index=1', '95-114', '未解析'),
        ('mocs_datagov152191_全國公務人員人數按年別分.csv', 'data.gov.tw 152191 全國公務人員人數按年別分(銓敘部)', 'https://www.mocs.gov.tw/FileUpload/1835-9801/Documents//1全國公務人員人數按年別分(CSV檔).csv', 'https://data.gov.tw/dataset/152191', '104-113', '未解析（與概況統計 PDF 相同數列）'),
        ('dgpa_統計提要114_2_公務統計方案_公教人員數_資訊處114.xlsx', '人事總處 114年人事業務統計提要 2.公教人員數', 'https://www.dgpa.gov.tw/mp/info?mid=328&uid=902&pid=12898', 'https://www.dgpa.gov.tw/mp/info?mid=328&uid=902&pid=12898', '114', '未解析（含事業機構之公教人員數）'),
        ('dgpa_統計提要114_1_公務統計方案_機關數_資訊處114.xlsx', '人事總處 114年人事業務統計提要 1.機關數', 'https://www.dgpa.gov.tw/mp/info?mid=328&uid=902&pid=12899', 'https://www.dgpa.gov.tw/mp/info?mid=328&uid=902&pid=12899', '114', '未解析'),
        ('dgpa_統計提要114_8-09_人事統計提要_人事人員與公教人員人數統計比較_綜規處114修正.xls', '人事總處 114年人事業務統計提要 8-09', 'https://www.dgpa.gov.tw/mp/info?mid=328&uid=902&pid=12892', 'https://www.dgpa.gov.tw/mp/info?mid=328&uid=902&pid=12892', '歷年', '未解析'),
        ('dgpa_聘僱人員管理作業手冊_111.11編印版.pdf', '人事總處 聘僱人員管理作業參考手冊(111.11)', 'https://www.dgpa.gov.tw/information?uid=94&pid=11201', 'https://www.dgpa.gov.tw/information?uid=94&pid=11201', '-', '制度文件，未解析'),
        ('dgpa_公務人力發展學院113年員額評鑑情形報告.pdf', '人事總處 所屬機關員額評鑑專區 113年員額評鑑情形報告', 'https://www.dgpa.gov.tw/uploads/dgpa/files/202408/b4459d37-98a2-41ae-b22a-c528c35b9548.pdf', 'https://www.dgpa.gov.tw/informationlist?uid=782', '113', '僅單一機關之評鑑報告，未解析'),
        ('datagov_相關資料集清單.json', 'data.gov.tw 全站資料集清單中與員額/人數相關之 147 筆', 'https://data.gov.tw/api/front/dataset/export?format=csv', 'https://data.gov.tw/datasets/search', '-', '以關鍵字自全站清單篩選'),
    ]
    for local, name, url, page, years, method in extra:
        if os.path.exists(os.path.join(RAW, local)):
            reg_source(local, name, url, page, years, method)
    for y in sorted(DGPA_YB_PID):
        p = find_file(f'dgpa_年報{y}_') and [f for f in os.listdir(RAW) if f.startswith(f'dgpa_年報{y}_') and '彙整表' in f]
        if p:
            reg_source(p[0], f'人事總處 {y}年公教人力統計年報(彙整表)', yb_url(y), yb_url(y), '近十年', '未直接解析（各表另有單檔）')
        q = [f for f in os.listdir(RAW) if f.startswith(f'dgpa_年報{y}_') and '名詞定義' in f]
        if q:
            reg_source(q[0], f'人事總處 {y}年公教人力統計年報 名詞定義', yb_url(y), yb_url(y), str(y), 'docx XML 文字（供定義比對）')
    for f in os.listdir(RAW):
        if f.startswith('dgpa_概況'):
            m = re.search(r'概況(\d+)_第(\d)季', f)
            y, q = int(m.group(1)), m.group(2)
            pid = {115: 12967, 114: 12441, 113: 11942, 112: 11390, 111: 11004, 110: 10651, 109: 10157, 108: 9761, 107: 8111, 106: 7400}[y]
            u = f'https://www.dgpa.gov.tw/mp/info?mid=328&uid=330&pid={pid}'
            reg_source(f, f'人事總處 {y}年行政院所屬各機關公教人力概況 第{q}季', u, u, str(y), '未解析（公教人員依官等/機關類型，不含聘僱臨時）')

    os.makedirs(DATA, exist_ok=True)
    rows.sort(key=lambda r: (r['scope'], r['agency_group'], r['category'], r['measure'], r['year'], r['source_name'], r['note']))
    with open(os.path.join(DATA, 'headcount.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(DATA, 'headcount_sources.json'), 'w', encoding='utf-8') as f:
        json.dump(sorted(sources.values(), key=lambda s: s['local_path']), f, ensure_ascii=False, indent=1)
    print('rows', len(rows), 'sources', len(sources))
    if inc1 or inc9:
        print('年報間數值不一致（以最新年報為準）:')
        for yr, cat, lst in inc1 + inc9:
            print(' ', yr, cat, [(x[0], int(x[1])) for x in lst])


if __name__ == '__main__':
    main()

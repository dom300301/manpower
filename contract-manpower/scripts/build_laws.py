#!/usr/bin/env python3
"""
build_laws.py — 由全國法規資料庫開放資料（ChLaw.json / ChOrder.json）及已下載之行政規則文字檔，
建立 contract-manpower/data/laws.json。

用法（請以 python3 -I 執行，避免載入下載目錄內的任何模組）：
    python3 -I scripts/build_laws.py [--root contract-manpower]

輸入：
    raw/laws/api/ChLaw.json、ChOrder.json      全國法規資料庫 API（https://law.moj.gov.tw/api/Ch/Law/json、/Order/json）解壓後
    raw/laws/txt/*.txt                          行政規則（人事總處 PDF 轉文字、約僱人員報酬標準表 ODT 轉文字）
    raw/laws/exam/FL000605_職務代理注意事項.html  考試院主管法規共用系統頁面
輸出：
    data/laws.json
    data/laws_table.md（法規清冊表格，供 research/01 引用）
"""
import argparse, html, json, os, re, sys, datetime as dt

# ---------------------------------------------------------------- 中文數字 / 民國日期
CN = {'○': 0, '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '百': 100}

def cn2int(s):
    s = s.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    total, cur = 0, 0
    for ch in s:
        v = CN.get(ch)
        if v is None:
            return None
        if v >= 10:
            cur = (cur or 1) * v
            total += cur
            cur = 0
        else:
            cur = v
    return total + cur

def roc_date(text):
    """從『中華民國五十八年四月二十八日』或『中華民國 113 年 1 月 30 日』取出 ISO 日期。"""
    m = re.search(r'中華民國\s*([〇○零一二三四五六七八九十百\d]+)\s*年\s*([〇○零一二三四五六七八九十\d]+)\s*月\s*([〇○零一二三四五六七八九十\d]+)\s*日', text)
    if not m:
        return None
    y, mo, d = (cn2int(m.group(i)) for i in (1, 2, 3))
    if None in (y, mo, d):
        return None
    try:
        return dt.date(y + 1911, mo, d).isoformat()
    except ValueError:
        return None

def ymd(s):
    return f'{s[:4]}-{s[4:6]}-{s[6:]}' if s and len(s) == 8 else s

# ---------------------------------------------------------------- 沿革解析
def parse_history(raw):
    """全國法規資料庫 LawHistories 欄位：以『1.』『2.』起頭之條目，續行以空白縮排。"""
    entries, cur = [], None
    for line in raw.replace('\r\n', '\n').split('\n'):
        if re.match(r'^\d+\.', line):
            if cur:
                entries.append(cur)
            cur = re.sub(r'^\d+\.', '', line).strip()
        elif cur is not None:
            cur += line.strip()
        else:
            cur = line.strip()
    if cur:
        entries.append(cur)
    out = []
    for e in entries:
        e = re.sub(r'\s+', ' ', e)
        out.append({'date': roc_date(e), 'summary': e})
    return out

def parse_point_history(lines):
    """行政規則抬頭之沿革：每一條以『行政院 97 年 1 月 10 日…』或『中華民國…』起頭。"""
    text = ' '.join(l.strip() for l in lines)
    parts = re.split(r'(?=行政院\s*\d+\s*年\s*\d+\s*月\s*\d+\s*日|中華民國\s*\d+\s*年)', text)
    out = []
    for p in parts:
        p = re.sub(r'\s+', ' ', p).strip()
        if not p:
            continue
        m = re.search(r'(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日', p)
        d = dt.date(int(m.group(1)) + 1911, int(m.group(2)), int(m.group(3))).isoformat() if m else None
        out.append({'date': d, 'summary': p})
    return out

# ---------------------------------------------------------------- 條文解析
def api_articles(L, keep=None):
    """ArticleType A=條文，C=章節名稱。keep=(lo,hi) 僅保留條號介於範圍之條文（含該範圍前的章節標題）。"""
    arts, title = [], None
    for a in L['LawArticles']:
        if a['ArticleType'] != 'A':
            title = re.sub(r'\s+', ' ', a['ArticleContent']).strip()
            continue
        no = a['ArticleNo'].replace(' ', '')
        if keep:
            m = re.match(r'第(\d+)(?:-(\d+))?條', no)
            n = int(m.group(1)) if m else -1
            if not (keep[0] <= n <= keep[1]):
                continue
        rec = {'no': no, 'text': a['ArticleContent'].replace('\r\n', '\n').strip()}
        if title:
            rec['title'] = title
        arts.append(rec)
    return arts

PT = '一二三四五六七八九十'
POINT_RE = re.compile(r'^\s*([一二三四五六七八九十]{1,3})、\s*(.*)$')

def point_articles(lines):
    """將『一、…』『二、…』格式之行政規則切成點；續行併入前一點。"""
    arts, cur = [], None
    for line in lines:
        if not line.strip() or re.match(r'^\s*\d+\s*$', line):   # 空行、頁碼
            continue
        m = POINT_RE.match(line)
        if m and cn2int(m.group(1)) == len(arts) + (2 if cur else 1):
            if cur:
                arts.append(cur)
            cur = {'no': f'第{cn2int(m.group(1))}點', 'text': m.group(2).strip()}
        elif cur is not None:
            cur['text'] += '\n' + line.strip()
    if cur:
        arts.append(cur)
    for a in arts:
        a['text'] = re.sub(r'\n(?=[^（(１-９0-9一-十])', '', a['text'])   # 純換行接續的句子合併
    return arts

def html_text(path):
    x = open(path, encoding='utf-8', errors='replace').read()
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', x, flags=re.S)
    t = re.sub(r'<br\s*/?>|</p>|</div>|</tr>|</li>', '\n', t)
    t = re.sub(r'<[^>]+>', '', t)
    return html.unescape(t)

# ---------------------------------------------------------------- 目標清單
# (id, pcode, tags, note, keep_range)
TARGETS = [
    # A. 契約人力本體法規
    ('A01', 'S0020014', ['聘用', '契約人力', '本體法規'], '聘用人員之母法；依公務人員任用法第 36 條（原第 21 條）制定。', None),
    ('A02', 'S0020015', ['聘用', '契約人力', '本體法規'], '', None),
    ('A03', 'S0110014', ['約僱', '契約人力', '本體法規'], '原名「行政院暨所屬機關約僱人員僱用辦法」（61.12.27 訂定），108.10.1 修正名稱及全文。附件「約僱人員報酬標準表」已另存 raw/laws/dgpa/S0110014_附件_約僱人員報酬標準表.odt。', None),
    ('A05', 'S0110027', ['聘用', '約僱', '離職給與', '契約人力'], '原名「各機關學校聘僱人員離職儲金給與辦法」（84.2.10 訂定），107.8.28 修正名稱為「離職給與辦法」。', None),
    ('A07', 'S0110038', ['員額', '聘僱', '契約人力', '公務人員'], '99.4.1 施行；第 3 條定義第一至五類員額（聘僱人員、工友屬第二類），第 4 條定各類員額最高限。', None),
    ('A08', 'S0110040', ['員額', '聘僱', '契約人力'], '依總員額法第 10 條（授權）訂定之員額管理規範；總員額法無「施行細則」，此辦法即其子法。', None),
    ('A11', 'A0030128', ['聘用', '約僱', '契約人力', '給假'], '聘僱人員給假之行政院法規命令（補充蒐集）。', None),
    ('A12', 'S0110028', ['工友', '技工', '勞動', '契約人力'], '工友（含技工、駕駛）退職補償金；工友適用勞基法後之過渡給與（補充蒐集）。', None),
    ('A13', 'H0070038', ['約用', '契約進用', '教保員', '契約人力'], '公立幼兒園契約進用人員（教保員等）之進用、考核及待遇——教育體系「契約進用人員」範例（補充蒐集）。', None),
    # B. 公務人員對照法規
    ('B01', 'S0020001', ['公務人員', '任用'], '第 36 條：各機關以契約定期聘用之專業或技術人員，其聘用另以法律定之（聘用條例之授權依據）；第 26 條之 1、第 28 條於約聘僱人員準用。', None),
    ('B02', 'S0120001', ['公務人員', '救濟', '復審', '申訴'], '第 102 條列舉準用本法之人員（含各機關依法聘用、僱用人員）；114.7.9 修正增訂職場霸凌申訴之準用。', None),
    ('B03', 'S0020038', ['公務人員', '服務'], '111.6.22 全文修正後，適用範圍改列於第 2 條（受有俸給之文武職公務員及公營事業機構純勞工以外之人員；原第 24 條）；第 26 條：公營事業非決策人員及兼任行政職務教師不適用第 14、15 條。聘僱人員依職務代理注意事項第 7 點須遵守本法。', None),
    ('B04', 'S0040001', ['公務人員', '考績'], '', None),
    ('B05', 'S0030001', ['公務人員', '俸給'], '聘用、約僱人員薪點比照公務人員俸點（報酬標準表）之對照基礎。', None),
    ('B06', 'S0080034', ['公務人員', '退休', '撫卹'], '', None),
    ('B07', 'S0070001', ['公務人員', '保險', '公保'], '第 2 條、第 6 條被保險人範圍：法定機關編制內有給專任人員；聘用人員得參加公保，約僱人員自 103 年起改投勞保（依本法及相關規定）。', None),
    ('B08', 'S0010008', ['公務人員', '協會', '結社'], '', None),
    ('B09', 'S0110036', ['公務人員', '行政中立'], '第 17 條：各機關依法聘用、僱用人員準用本法。', None),
    # C. 勞動法規
    ('C01', 'N0030001', ['勞動', '勞基法', '約用', '臨時人員', '工友'], '第 3 條適用範圍；第 84 條：公務員兼具勞工身分者，其任（派）免、薪資、獎懲、退休、撫卹及保險事項，應適用公務員法令。公部門臨時人員自 97.1.1 起、技工工友自 87.7.1 起經勞動部（勞委會）公告適用。', None),
    ('C02', 'N0050001', ['勞動', '勞保'], '第 6 條、第 8 條被保險人範圍。', None),
    ('C03', 'N0030020', ['勞動', '勞退'], '第 7 條適用對象；公務機構臨時人員自 95.1.1 起提繳。', None),
    ('C04', 'A0030057', ['採購', '承攬', '勞務'], '第 2 條、第 7 條（勞務採購定義）、第 22 條等；勞務採購／勞動派遣與契約人力之交界。', None),
    ('C05', 'B0000001', ['民法', '僱傭', '承攬'], '僅收錄第二編第二章第七節「僱傭」（第 482–489 條）及第八節「承攬」（第 490–514 條）。', (482, 514)),
    ('C06', 'A0030055', ['行政程序', '行政契約'], '第三章行政契約（第 135–149 條）：聘用、約僱契約實務上被認定為公法（行政）契約。', None),
    ('C07', 'N0090001', ['勞動', '就業服務', '派遣'], '第 5 條就業歧視、第 46 條以下外國人聘僱；派遣相關規範主要在勞基法第 2 條、第 17 條之 1。', None),
    # D. 救濟程序
    ('D01', 'A0030020', ['救濟', '訴願'], '第 1 條、第 3 條適用範圍；聘僱契約爭議是否得提訴願，實務上多認屬公法契約應循行政訴訟。', None),
    ('D02', 'A0030154', ['救濟', '行政訴訟'], '第 2 條公法上爭議、第 8 條一般給付訴訟（公法契約爭議之救濟途徑）。', None),
    ('D03', 'N0020007', ['救濟', '勞動', '勞資爭議'], '約用（臨時）人員、技工工友等適用勞基法者之爭議處理途徑。', None),
]

# 法規清冊表格用之「關鍵條文摘要」
KEY_ARTICLES = {
    'A01': '§2 各機關應業務需要定期聘用；§3 聘用人員＝以契約定期聘用之專業或技術人員，職稱員額期限報酬應列預算並送銓敘部登記備查；§6 聘用人員不適用俸給、退休、撫卹法規（原文：不得兼任有職等之職務）；§7 不得擔任主管、兼任職位分類職務。',
    'A02': '§2 以所任工作係現有人員所不能擔任者為限（並列舉得聘用之科技、經濟等業務）；§3 聘用期限最長一年、得續聘；§4 聘用契約應載事項。',
    'A03': '§2 約僱人員＝所任工作相當分類職位公務人員第五職等以下之臨時性、特殊性工作；§3 僱用以年度計畫為限、期滿解僱；§4 不得僱用之情形（準用任用法§28）；§8 報酬依附件「約僱人員報酬標準表」；§8-1 參加勞保、勞退。',
    'A05': '§2 適用對象：依聘用條例聘用及依約僱辦法僱用人員；§3 離職儲金提撥（機關與個人各 50%）；§8-1 107.7.1 後新進人員改適用勞退條例。',
    'A07': '§2 適用一級機關及所屬各級機關；§3 五類員額（第二類＝依法令進用之聘僱人員、駐衛警察及工友）；§4 總數上限 160,900 人及各類最高限；§6 各機關年度員額之擬定；§10 員額管理辦法授權。',
    'A08': '§2 名詞定義；§6-§9 預算員額之編列、審核；§12 聘僱人員及工友員額之配置原則；§23 地方政府準用。',
    'A11': '§2 適用對象（聘用及約僱人員）；§3 各類假別及日數（比照公務人員請假規則）。',
    'A12': '§2 工友退職補償金給與對象；§3-§5 計算基準。',
    'A13': '§2 契約進用人員定義；§3-§6 進用程序、資格；§13 薪資基準（附表）；§18 考核；§20 契約終止。',
    'B01': '§5 官等職等；§9 任用資格；§26-1 機關首長卸任前不得任用（約聘僱準用）；§28 消極資格；§36 聘用人員另以法律定之。',
    'B02': '§2-§3 適用對象（法定機關依法任用之有給專任人員）；§25 復審；§77 申訴、再申訴；§102 準用：教育人員任用條例公布前之學校職員、公營事業依法任用人員、各機關依法派用聘用聘任僱用或留用人員等。',
    'B03': '§2 適用範圍（受有俸給之文武職公務員及公營事業機構純勞工以外之人員；111 年修正前為 §24）；§14 經營商業之禁止；§15 兼職限制；§16 離職後旋轉門；§26 公營事業非決策人員等不適用 §14、§15。',
    'B04': '§2-§3 考績種類；§6-§7 考績等第及獎懲；§9 平時考核。聘僱人員不適用（另依契約／機關考核規定）。',
    'B05': '§2 俸給種類；§4 俸級俸點表；§23 俸點折算俸額。聘僱人員薪點比照此俸點表。',
    'B06': '§2 適用對象（依公務人員任用法律任用、並經銓敘審定之人員）；聘僱人員不適用，改依離職儲金／勞退。',
    'B07': '§2 被保險人：法定機關（構）編制內有給專任人員、公立學校教職員、私校教職員等；§6 要保機關。',
    'B08': '§2 公務人員定義（各級政府機關、公立學校依法任用之有給專任人員）；§3 協會組織；聘僱人員非當然會員。',
    'B09': '§2 公務人員定義；§17 準用：各機關依法聘用、僱用人員等；§18 憲法或法律規定須超出黨派以外人員準用。',
    'C01': '§2 勞工、雇主、派遣等定義；§3 適用行業及中央主管機關指定；§9 定期契約；§17-1 派遣；§84 公務員兼具勞工身分者之適用；§84-2 工作年資。',
    'C02': '§6 強制加保對象（受僱於僱用五人以上事業單位之勞工等）；§8 自願加保；§9 相關規定。',
    'C03': '§7 適用對象（適用勞基法之本國籍勞工；其他經雇主同意提繳者）；§6 制度；§14 提繳率。',
    'C04': '§2 採購定義（含勞務之委任或僱傭）；§7 勞務＝專業服務、技術服務、資訊服務、研究發展、營運管理、維修、訓練、勞力及其他；§22 限制性招標；§63 契約。',
    'C05': '§482 僱傭定義；§483 報酬；§487 受僱人服勞務之報酬請求；§488-§489 終止；§490 承攬定義；§492-§495 瑕疵擔保；§505 報酬給付；§511 定作人終止契約。',
    'C06': '§135 行政契約之容許性；§136 和解契約；§137 雙務契約；§139 書面；§145-§148 情事變更、調整、強制執行；§149 準用民法。',
    'C07': '§2 名詞定義；§5 就業歧視禁止；§42-§62 外國人聘僱（含第 46 條工作類別）。',
    'D01': '§1 行政處分之訴願；§3 行政處分定義；§4 管轄；§14 期間；§77 不受理（非行政處分者）。',
    'D02': '§2 公法上爭議得提起行政訴訟；§4 撤銷訴訟；§5 課予義務訴訟；§8 給付訴訟（公法上契約）；§106 期間。',
    'D03': '§2 適用範圍；§4 調解；§5 權利事項與調整事項；§6 管轄；§23 仲裁；§39 裁決。',
}

# ---------------------------------------------------------------- 行政規則（不在法規資料庫）
def build_admin_rules(root):
    txt = os.path.join(root, 'raw', 'laws', 'txt')
    recs = []

    # A04 聘用人員注意事項（含附表二報酬標準表）——人事總處《聘僱人員管理作業參考手冊》111.11 收錄之 97.1.21 版
    hb = open(os.path.join(txt, '聘僱人員管理作業參考手冊_111.11.txt'), encoding='utf-8').read().split('\n')
    s = next(i for i, l in enumerate(hb) if l.strip() == '行政院暨所屬各級機關聘用人員注意事項')
    e = next(i for i, l in enumerate(hb) if i > s and '聘僱人員管理作業手冊' in l)
    hist_lines = [l for l in hb[s + 1:s + 12] if '中華民國' in l or '號' in l]
    hist = parse_point_history([re.sub(r'\s+', '', l) for l in hist_lines])
    arts = point_articles(hb[s + 12:e])
    recs.append({
        'id': 'A04a', 'name': '行政院暨所屬各級機關聘用人員注意事項', 'pcode': '', 'level': '行政規則',
        'authority': '行政院（行政院人事行政總處）', 'category': '行政＞行政院人事行政總處＞組編人力',
        'modified_date': '2008-01-21', 'history': hist,
        'url': 'https://www.dgpa.gov.tw/FileConversion?filename=dgpa%2Ffiles%2F202211%2Fed1435f4-811c-46c3-9725-570f089a145b.pdf&name=x.pdf',
        'articles': arts, 'tags': ['聘用', '契約人力', '行政規則', '報酬'],
        'note': '不在全國法規資料庫。全文取自行政院人事行政總處《聘僱人員管理作業參考手冊》（111 年 11 月編印版）第 27–32 頁，'
                '本機下載檔 raw/laws/dgpa/聘僱人員管理作業參考手冊_111.11.pdf。第 5 點附表（二）即「聘用人員比照分類職位公務人員俸點支給報酬標準表」，另建 A04b。',
    })
    recs.append({
        'id': 'A04b', 'name': '聘用人員比照分類職位公務人員俸點支給報酬標準表', 'pcode': '', 'level': '行政規則（附表）',
        'authority': '行政院（行政院人事行政總處）', 'category': '行政＞行政院人事行政總處＞組編人力',
        'modified_date': '2008-01-21', 'history': [{'date': '2008-01-21', 'summary': '行政院 97.1.21 院授人力字第 0970000936 號函修正「行政院暨所屬各級機關聘用人員注意事項」附表（手冊沿革記為附表一；手冊內文列為附表二）'}],
        'url': 'https://www.dgpa.gov.tw/FileConversion?filename=dgpa%2Ffiles%2F202211%2Fed1435f4-811c-46c3-9725-570f089a145b.pdf&name=x.pdf',
        'articles': [
            {'no': '附表', 'title': '聘用人員比照分類職位公務人員俸點支給報酬標準表（薪點區間摘錄）',
             'text': '相當第十三職等：報酬薪點 670–790（790、760、730、700、670）\n相當第十二職等：604–714\n相當第十一職等：538–648\n'
                     '相當第十職等：472–582\n相當第九職等：424–520\n相當第八職等：376–472\n相當第七職等：328–424\n相當第六職等：280–376\n'
                     '（相當第五職等以下另依約僱人員報酬標準表）\n附註：1. 聘用人員應具有本表所列相當職等之專門知能條件之一。'
                     '2. 依本表支給報酬，其比照支給報酬之薪點最高不得超過本機關副首長職位之薪點。本表薪點折合率另以命令規定，情形特殊者專案報院核定。'},
        ],
        'tags': ['聘用', '報酬', '薪點', '行政規則'],
        'note': '表格版面為多欄（職等／俸點／職責程度／所具專門知能條件／報酬薪點），PDF 轉文字後欄位交錯，此處僅摘錄各職等薪點區間；'
                '完整表格請見 raw/laws/dgpa/聘僱人員管理作業參考手冊_111.11.pdf 第 29–32 頁。薪點折合率隨軍公教待遇調整由行政院另函頒（目前聘僱人員每薪點折合率與公務人員俸點相同標準）。',
    })

    # A06a 臨時人員進用及運用要點（108.11.15 版，人事總處網站 doc 轉 pdf）
    t = open(os.path.join(txt, '臨時人員進用及運用要點_108.11.15.txt'), encoding='utf-8').read().split('\n')
    s = next(i for i, l in enumerate(t) if POINT_RE.match(l) and l.strip().startswith('一、'))
    hist = parse_point_history(t[1:s])
    recs.append({
        'id': 'A06a', 'name': '行政院及所屬各機關學校臨時人員進用及運用要點', 'pcode': '', 'level': '行政規則',
        'authority': '行政院（行政院人事行政總處）', 'category': '行政＞行政院人事行政總處＞組編人力',
        'modified_date': '2019-11-15', 'history': hist,
        'url': 'https://www.dgpa.gov.tw/FileConversion?filename=dgpa%2Ffiles%2F202104%2Fd3a48621-a8eb-4dbd-bd83-fe0c15e3c0ec.doc&nfix=pdf&name=x.pdf',
        'articles': point_articles(t[s:]), 'tags': ['臨時人員', '約用', '勞動', '勞基法', '行政規則', '契約人力'],
        'note': '不在全國法規資料庫（行政院函頒之行政規則）。全文取自人事總處網站（108.11.15 修正版，本機檔 raw/laws/dgpa/臨時人員進用及運用要點_108.11.15.pdf）。'
                '113.1.30 修正名稱為「約用人員進用及運用要點」（另建 A06b）。原「行政院與所屬中央及地方各機關學校臨時人員進用及運用要點」之正式名稱為「行政院及所屬各機關學校臨時人員進用及運用要點」。',
    })

    # A06b 約用人員進用及運用要點（113.1.30 版）
    t = open(os.path.join(txt, '約用人員進用及運用要點_1130130.txt'), encoding='utf-8').read().split('\n')
    s = next(i for i, l in enumerate(t) if POINT_RE.match(l) and l.strip().startswith('一、'))
    hist2 = list(hist) + [{'date': '2024-01-30', 'summary': '行政院 113 年 1 月 30 日院授人組字第 11320000341 號函修正名稱（臨時人員→約用人員）及全文，並自即日生效'},
                          {'date': None, 'summary': '（據各機關轉知公文）行政院再修正第 3、4、6 點，自 115 年 1 月 1 日生效（新增勞動契約應載明遵守臺灣地區與大陸地區人民關係條例等）；原始公文來源網域受限未能取得，待補。'}]
    recs.append({
        'id': 'A06b', 'name': '行政院及所屬各機關學校約用人員進用及運用要點', 'pcode': '', 'level': '行政規則',
        'authority': '行政院（行政院人事行政總處）', 'category': '行政＞行政院人事行政總處＞組編人力',
        'modified_date': '2024-01-30', 'history': hist2,
        'url': 'https://www.dgpa.gov.tw/FileConversion?filename=dgpa%2Ffiles%2F202402%2F6fe2dab8-4b2c-4275-9112-b5dde436166c.pdf&nfix=&name=x.pdf',
        'articles': point_articles(t[s:]), 'tags': ['約用', '臨時人員', '勞動', '勞基法', '行政規則', '契約人力'],
        'note': '不在全國法規資料庫。全文取自人事總處網站公告（113.1.30 修正版，本機檔 raw/laws/dgpa/約用人員進用及運用要點_1130130.pdf；公告頁 https://www.dgpa.gov.tw/information?uid=2&pid=11786）。'
                '115.1.1 生效之再修正版未能自可連網域取得。',
    })

    # A09 聘僱人員進用及管理：中央並無單一「行政院及所屬機關（構）聘僱人員進用及管理」法規
    recs.append({
        'id': 'A09', 'name': '行政院及所屬機關（構）聘僱人員進用及管理（相關規範彙整）', 'pcode': '', 'level': '行政規則／參考手冊',
        'authority': '行政院人事行政總處', 'category': '行政＞行政院人事行政總處＞組編人力',
        'modified_date': '2022-11-01', 'history': [{'date': '2022-11-01', 'summary': '行政院人事行政總處 111 年 11 月編印《聘僱人員管理作業參考手冊》（彙整聘用條例、約僱辦法、聘用人員注意事項、職務代理注意事項及釋例）'}],
        'url': 'https://www.dgpa.gov.tw/FileConversion?filename=dgpa%2Ffiles%2F202211%2Fed1435f4-811c-46c3-9725-570f089a145b.pdf&name=x.pdf',
        'articles': [], 'tags': ['聘用', '約僱', '聘僱', '契約人力', '參考資料'],
        'note': '查全國法規資料庫及人事總處網站，中央並無以此為名之單一法規；聘僱人員之進用及管理分別規定於聘用條例及施行細則、約僱辦法、聘用人員注意事項、職務代理注意事項、離職給與辦法、給假辦法，'
                '人事總處以《聘僱人員管理作業參考手冊》（111.11）彙整，各地方政府則另訂「○○政府及所屬各機關學校聘僱人員進用及管理要點」（如臺北市 FL101961，來源網域受限）。'
                '本機檔 raw/laws/dgpa/聘僱人員管理作業參考手冊_111.11.pdf。',
    })

    # A10 各機關職務代理應行注意事項（考試院主管法規共用系統 FL000605，114.7.3 修正）
    t = html_text(os.path.join(root, 'raw', 'laws', 'exam', 'FL000605_職務代理注意事項.html'))
    t = re.sub(r'\n\s*\n+', '\n', t)
    body = t[t.find('一、為規範各機關職務代理'):t.find('隱私權保護宣告')].replace(':::', '')
    lines = [re.sub(r'^\s{2,}', '', l) if not POINT_RE.match(l) else l for l in body.split('\n')]
    arts = point_articles(lines)
    recs.append({
        'id': 'A10', 'name': '各機關職務代理應行注意事項', 'pcode': 'FL000605', 'level': '行政規則',
        'authority': '銓敘部', 'category': '考試＞銓敘部＞銓敘部行政規則',
        'modified_date': '2025-07-03',
        'history': [{'date': '1987-11-06', 'summary': '銓敘部 76.11.6 訂定發布'},
                    {'date': '1995-04-25', 'summary': '84.4.25 修正（考試院法規系統歷史版本 hid=1926）'},
                    {'date': None, 'summary': '94 年、96 年修正（放寬以約聘僱人員辦理所遺業務之授權，見人事總處手冊釋例）'},
                    {'date': '2015-05-29', 'summary': '銓敘部 104.5.29 部銓三字第 10439723581 號令修正發布'},
                    {'date': '2025-07-03', 'summary': '銓敘部 114.7.3 部銓三字第 11458440041 號令修正發布（第 5 點等）'}],
        'url': 'https://law.exam.gov.tw/LawContent.aspx?id=FL000605',
        'articles': arts, 'tags': ['職務代理', '聘用', '約僱', '公務人員', '行政規則', '契約人力'],
        'note': '不在全國法規資料庫；全文取自考試院主管法規共用系統（law.exam.gov.tw，本機檔 raw/laws/exam/FL000605_職務代理注意事項.html）。pcode 欄為該系統之法規代碼，非全國法規資料庫 PCode。'
                '第 5 點：薦任以下非主管職務出缺或請假達一個月以上等情形，得依聘用條例或約僱辦法約聘僱人員辦理所遺業務；第 9 點：原因消失應即解聘僱。',
    })

    # C08 勞動部（勞委會）公告：公部門適用勞基法之範圍
    recs.append({
        'id': 'C08', 'name': '勞動部（行政院勞工委員會）指定公部門人員適用勞動基準法之公告', 'pcode': '', 'level': '公告（勞基法第 3 條第 3 項指定）',
        'authority': '勞動部', 'category': '行政＞勞動部＞勞動條件及就業平等',
        'modified_date': '2007-11-30',
        'history': [{'date': '1998-07-01', 'summary': '勞委會公告公務機構之技工、駕駛人、工友及清潔隊員等自 87.7.1 起適用勞基法（同批尚含醫療保健服務業〈醫師除外〉、國會助理等）'},
                    {'date': '2007-11-30', 'summary': '勞委會 96.11.30 勞動 1 字第 0960130914 號公告：公部門各業（公務機構、公立教育訓練服務業、公立社會福利機構、公立學術研究服務業、公立藝文業等）非依公務人員法制進用之臨時人員，自 97.1.1 起適用勞基法；但依聘用人員聘用條例、約僱人員僱用辦法進用者，及已另案指定適用之技工、駕駛、工友、清潔隊員、國會助理不在此列'}],
        'url': 'https://www.mol.gov.tw/topic/3066/5834/22675/',
        'articles': [], 'tags': ['勞動', '勞基法', '臨時人員', '約用', '工友', '技工', '公告'],
        'note': '來源：勞動部網站「勞動基準法適用行業」專區及常見問答（www.mol.gov.tw 非本環境可連網域，內容依 WebSearch 摘要記錄；公告字號引自新竹市政府轉載文件）。'
                '另勞保局說明各公務機構自 95.1.1 起應為非依公務人員法制進用之臨時人員提繳勞退。',
    })
    return recs

# ---------------------------------------------------------------- 主程式
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    api_dir = os.path.join(root, 'raw', 'laws', 'api')
    idx, update = {}, {}
    for n in ('ChLaw', 'ChOrder'):
        j = json.loads(open(os.path.join(api_dir, n + '.json'), 'rb').read().decode('utf-8-sig'))
        update[n] = j['UpdateDate']
        for L in j['Laws']:
            idx[re.search(r'pcode=([A-Z]\d{7})', L['LawURL']).group(1)] = L
    print('API 清單：', {k: len([1 for L in idx.values()]) for k in update}, update)

    laws = []
    for lid, pc, tags, note, keep in TARGETS:
        L = idx.get(pc)
        if L is None:
            print('!! API 清單找不到', lid, pc); continue
        cat = [c.strip() for c in L['LawCategory'].split('＞')]
        authority = cat[1] if len(cat) > 1 else cat[0]
        if authority == '院本部':
            authority = cat[0] + '（院本部）'
        hist = parse_history(L['LawHistories'])
        rec = {
            'id': lid, 'name': L['LawName'], 'pcode': pc, 'level': L['LawLevel'],
            'authority': authority, 'category': '＞'.join(cat),
            'modified_date': ymd(L['LawModifiedDate']),
            'history': hist, 'url': L['LawURL'],
            'articles': api_articles(L, keep),
            'tags': tags, 'note': note,
        }
        if L['LawAttachements']:
            rec['attachments'] = L['LawAttachements']
        if L['LawAbandonNote']:
            rec['note'] += ' 【已廢止：' + L['LawAbandonNote'] + '】'
        laws.append(rec)
    laws += build_admin_rules(root)
    laws.sort(key=lambda r: r['id'])

    meta = {'generated': dt.datetime.now().isoformat(timespec='seconds'),
            'source': {'ChLaw': 'https://law.moj.gov.tw/api/Ch/Law/json', 'ChOrder': 'https://law.moj.gov.tw/api/Ch/Order/json'},
            'api_update_date': update, 'count': len(laws)}
    out = os.path.join(root, 'data', 'laws.json')
    json.dump({'meta': meta, 'laws': laws}, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('寫出', out, len(laws), '筆')

    # 清冊表格
    rows = ['| 編號 | 法規名稱 | 位階 | 主管機關 | 制定（訂定）日 | 最近修正日 | 沿革重點 | 對契約人力的關鍵條文摘要 |', '|---|---|---|---|---|---|---|---|']
    for r in laws:
        h = r['history']
        first = next((x['date'] for x in h if x['date']), '')
        n_amend = max(len(h) - 1, 0)
        last = h[-1]['summary'][:60] + ('…' if len(h[-1]['summary']) > 60 else '') if h else ''
        brief = f'制定後修正 {n_amend} 次；最近：{last}' if h else '（見備註）'
        name = f'[{r["name"]}]({r["url"]})' if r['url'] else r['name']
        rows.append(f'| {r["id"]} | {name} | {r["level"]} | {r["authority"]} | {first} | {r["modified_date"]} | {brief} | {KEY_ARTICLES.get(r["id"], r["note"][:120])} |'.replace('\n', ' '))
    open(os.path.join(root, 'data', 'laws_table.md'), 'w', encoding='utf-8').write('\n'.join(rows) + '\n')

if __name__ == '__main__':
    main()

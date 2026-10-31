# -*- coding: utf-8 -*-
# 用途：掃描 raw/fetched/local/<縣市>/ 下已取得之全文（rootlaw_*.txt、glrs_*.txt、tc_*.txt、chcg_*.txt、ntpc_*_all.txt、臺北 tp_FL*.html），
#       解析點次／條次為 points:[{no,text,chapter?}]，輸出 catalog.json（含縣市、名稱、版本日期、來源網址、local_path、點數）。
# 執行：python3 -I build_catalog.py <raw/fetched/local 絕對路徑> <輸出 catalog.json>
# 需要網域：無（純離線解析）。
"""掃描 raw/fetched/local/<縣市>/ 下已取得之全文（rootlaw_*.txt、glrs_*.txt、tc_*.txt、chcg_*.txt、ntpc_*_all.txt、臺北 html），
解析為 points:[{no,text}]，輸出 catalog.json（供後續寫入 local_gov.json）。
用法：python3 -I build_catalog.py <raw/fetched/local 絕對路徑> <輸出 catalog.json>
"""
import re, sys, os, json, html, glob

BASE = sys.argv[1]
OUT = sys.argv[2]
CN = '一二三四五六七八九十'
PT = re.compile(r'^\s*(?:(第?[一二三四五六七八九十]{1,4}條?)[、．.]|(第\s*[一二三四五六七八九十]{1,4}\s*條)(?:\s+|$|(?=[（(]))|([一二三四五六七八九十]{1,4})\s*$)\s*')  # 點次／條次
CH = re.compile(r'^\s*(第\s*[一二三四五六七八九十]+\s*章.*|[壹貳參肆伍陸柒捌玖拾]\s+\S.*)$')  # 章節


def cn2int(s):
    s = s.replace('第', '').replace('條', '')
    if s == '十':
        return 10
    if '十' in s:
        a, b = s.split('十')
        return (CN.index(a) + 1 if a else 1) * 10 + (CN.index(b) + 1 if b else 0)
    return CN.index(s) + 1


def parse_points(body):
    lines = [l.rstrip() for l in body.split('\n')]
    points, cur, chapter = [], None, ''
    for l in lines:
        if not l.strip():
            continue
        m = CH.match(l)
        if m and len(l.strip()) < 30 and not PT.match(l):
            chapter = l.strip()
            continue
        m = PT.match(l)
        if m:
            try:
                n = cn2int((m.group(1) or m.group(2) or m.group(3)).replace(' ', ''))
            except ValueError:
                n = None
            if n is not None and (cur is None or n == cur['no'] + 1):
                if cur:
                    points.append(cur)
                cur = {'no': n, 'text': l[m.end():].strip()}
                if chapter:
                    cur['chapter'] = chapter
                    chapter = ''
                continue
        if cur:
            cur['text'] += ('' if cur['text'].endswith(('，', '、', '（', '(')) else '') + l.strip()
    if cur:
        points.append(cur)
    # 合併單行空白，清理全形空白
    for p in points:
        p['text'] = re.sub(r'[ 　]+', '', p['text']) if re.search(r'[一-鿿]', p['text']) else p['text']
    return points


def h2t(s):
    s = re.sub(r'<(script|style).*?</\1>', ' ', s, flags=re.S)
    s = re.sub(r'<br\s*/?>|</p>|</div>|</tr>|</li>|</h\d>', '\n', s)
    t = html.unescape(re.sub('<[^>]+>', ' ', s))
    t = re.sub(r'[ \t　]+', ' ', t)
    return re.sub(r'\n\s*\n+', '\n', t)


docs = []

def add(county, title, date, source, path, body, system, note=''):
    pts = parse_points(body)
    docs.append({'county': county, 'title': title.strip(), 'date': date.strip(), 'source': source, 'local_path': os.path.relpath(path, os.path.dirname(os.path.dirname(os.path.dirname(BASE)))),
                 'system': system, 'n_points': len(pts), 'chars': len(body), 'points': pts, 'note': note})

for county in sorted(os.listdir(BASE)):
    d = os.path.join(BASE, county)
    if not os.path.isdir(d) or county == 'rootlaw':
        continue
    # rootlaw
    for f in sorted(glob.glob(os.path.join(d, 'rootlaw_*.txt'))):
        t = open(f, encoding='utf-8').read()
        name = re.search(r'法規名稱：(.+)', t).group(1)
        date = re.search(r'版本時間：(.+)', t).group(1)
        src = re.search(r'來源：(.+)', t).group(1)
        body = t.split('【條文】', 1)[1] if '【條文】' in t else ''
        hist = t.split('【沿革】', 1)[1].split('【條文】')[0] if '【沿革】' in t else ''
        add(county, name, date, src, f, body, 'rootlaw', note=re.sub(r'\s+', ' ', hist.split('歷史沿革')[0]).strip()[:300])
    # GLRS（新竹市、嘉義市、金門縣、臺中市、彰化縣）
    for f in sorted(glob.glob(os.path.join(d, 'glrs_*.txt')) + glob.glob(os.path.join(d, 'tc_*.txt')) + glob.glob(os.path.join(d, 'chcg_*.txt'))):
        t = open(f, encoding='utf-8').read()
        if '法規名稱' not in t:
            continue
        name = re.search(r'法規名稱：\s*\n?\s*(.+)', t).group(1)
        pub = re.search(r'公發布日：\s*\n?\s*(.+)', t)
        amd = re.search(r'修正日期：\s*\n?\s*(.+)', t)
        no = re.search(r'發文字號：\s*\n?\s*(.+)', t)
        date = (amd.group(1) if amd else (pub.group(1) if pub else '?')).strip()
        if no:
            date += ' ' + no.group(1).strip()
        sid = re.search(r'glrs_([A-Z]+\d+)|tc_([A-Z]+\d+)|chcg_([A-Z]+\d+)', os.path.basename(f))
        sid = next(g for g in sid.groups() if g)
        host = {'新竹市': 'https://law.hccg.gov.tw', '嘉義市': 'https://law.chiayi.gov.tw', '金門縣': 'https://law.kinmen.gov.tw', '臺中市': 'https://law.taichung.gov.tw',
                '彰化縣': 'https://lawsearch.chcg.gov.tw/GLRSNEWSOUT', '苗栗縣': 'https://law.miaoli.gov.tw/glrsnewsout'}[county]
        # 條文起點：法規功能按鈕區之後
        i = t.find('歷史法規')
        body = t[i + 4:] if i > 0 else t
        body = body.split(county + '政府：')[0]
        add(county, name, date, f'{host}/LawContent.aspx?id={sid}', f, body, 'glrs')
    # 新北市法規系統
    for f in sorted(glob.glob(os.path.join(d, 'ntpc_*_all.txt'))):
        t = open(f, encoding='utf-8').read()
        name = re.search(r'法規名稱：\s*(.+?)\s*\(', t).group(1)
        date = re.search(r'\((民國[^)]+)\)', t).group(1)
        i = t.find(date) + len(date) + 1
        body = re.sub(r'\s+\d{1,2}\s+(?=[一二三四五六七八九十]+、)', '\n', t[i:])  # 去掉條次序號
        body = re.sub(r'(?<![\n一二三四五六七八九十第])((?:第?[一二三四五六七八九十]{1,3})、)', r'\n\1', body)
        hist_f = f.replace('_all.txt', '_hist.txt')
        hist = ''
        if os.path.exists(hist_f):
            h = open(hist_f, encoding='utf-8').read()
            hist = re.sub(r'\s+', ' ', h.split('系統時間')[-1].split(':::')[0]).strip()[:600]
        lncode = re.search(r'ntpc_(\w+)_all', os.path.basename(f)).group(1)
        add(county, name, date, f'https://web.law.ntpc.gov.tw/Scripts/FLAWDAT01.aspx?lncode={lncode}', f, body, 'ntpc', note=hist)
    # 臺北市法規系統
    for f in sorted(glob.glob(os.path.join(d, 'tp_FL*.html'))):
        if '_info' in f or '_attach' in f or '_hist' in f:
            continue
        t = h2t(open(f, encoding='utf-8', errors='replace').read())
        name = re.search(r'名 稱\s*\n\s*(.+)', t).group(1)
        date = re.search(r'修正日期\s*\n\s*(.+)', t).group(1)
        hist = re.search(r'沿 革\s*\n\s*(.+)', t).group(1)
        i = t.rfind('條號查詢')
        body = t[i + 4:].split(':::')[0]
        fl = re.search(r'tp_(FL\d+)', os.path.basename(f)).group(1)
        add(county, name, date, f'https://laws.gov.taipei/Law/LawSearch/LawArticleContent/{fl}', f, body, 'taipei', note=hist.strip())

json.dump(docs, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for x in docs:
    print(f"{x['county']}\t{x['system']}\t{x['n_points']:3d}點\t{x['chars']:6d}字\t{x['date'][:22]}\t{x['title']}")
print(len(docs), 'docs')

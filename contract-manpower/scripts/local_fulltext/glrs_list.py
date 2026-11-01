# -*- coding: utf-8 -*-
# 用途：列出 GLRS 型地方法規系統（臺中 law.taichung.gov.tw、彰化 lawsearch.chcg.gov.tw/GLRSNEWSOUT、新竹市 law.hccg.gov.tw、
#       嘉義市 law.chiayi.gov.tw、金門 law.kinmen.gov.tw、苗栗 law.miaoli.gov.tw/glrsnewsout）指定類別下之全部法規，印出含臨時／約用／約聘僱等關鍵字者之 id 與名稱。
# 執行：python3 -I glrs_list.py <系統根網址> <輸出目錄> [類別名稱正則，預設「人事|行政|秘書|通用|組織」，用 "." 掃全部]
#       取得 id 後以 <根網址>/LawContent.aspx?id=<id>（條文）及 LawHistory.aspx?id=<id>（沿革）下載。
# 需要網域：上述各 GLRS 法規系統（curl --cacert /root/.ccr/ca-bundle.crt）。
# usage: python3 -I glrs_list.py <base_url> <outdir> ; lists categories, then all laws in categories matching 人事|行政|秘書|通用, prints relevant ones
import re,sys,subprocess,html,os
CA='/root/.ccr/ca-bundle.crt'; base,outdir=sys.argv[1].rstrip('/'),sys.argv[2]; os.makedirs(outdir,exist_ok=True)
def get(url,f):
    subprocess.run(['curl','-sS','-m','60','--cacert',CA,'-o',f,url]); return open(f,encoding='utf-8',errors='replace').read() if os.path.exists(f) else ''
s=get(base+'/LawCategoryMain.aspx?type=M',f'{outdir}/cat.html')
cats=re.findall(r'CategoryID=(\d+)"[^>]*>([^<]*)',s)
print('CATS',[(c,n) for c,n in cats][:40])
pat=sys.argv[3] if len(sys.argv)>3 else '人事|行政|秘書|通用|組織'
todo=[(c,n) for c,n in cats if re.search(pat,n)]
# expand one level if subcategories exist
seen={}
for c,n in todo:
    sub=get(base+f'/LawCategoryMain.aspx?type=M&CategoryID={c}',f'{outdir}/cat_{c}.html')
    subs=re.findall(r'CategoryID=(\d+)"[^>]*>([^<]*)',sub)
    subs=[(sc,sn) for sc,sn in subs if sc.startswith(c) and sc!=c and sn.strip()]
    targets=[c]+[sc for sc,sn in subs]
    for t in targets:
        for p in range(1,30):
            h=get(base+f'/LawCategoryContentList.aspx?CategoryID={t}&page={p}',f'{outdir}/list_{t}_p{p}.html')
            items=re.findall(r'LawContent\.aspx\?id=([A-Z]+\d+)"[^>]*>(.*?)</a>',h,flags=re.S)
            items=[(i,html.unescape(re.sub('<[^>]+>','',x)).strip()) for i,x in items]
            items=[(i,x) for i,x in items if x]
            if not items: break
            for i,x in items: seen.setdefault(i,(x,n))
print('TOTAL',len(seen))
for i,(x,n) in seen.items():
    if re.search('臨時|約用|約聘|聘僱|契約|甄選|助理|非編制|報酬|員額|進用|僱用',x): print(i,x,'|',n)

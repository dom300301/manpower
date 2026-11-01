# -*- coding: utf-8 -*-
# 用途：依 LawID 清單自植根法律網（www.rootlaw.com.tw）下載地方法規現行條文（LawArticle.aspx）與沿革（LawContent.aspx），
#       依 LawID 前 3 碼（B01 臺北…B26 金門）分存至 <輸出目錄>/<縣市>/rootlaw_<LawID>.txt，並產生 rootlaw_index.json。
# 執行：python3 -I rootlaw_fetch.py <LawID清單檔（每行一個 LawID）> <輸出目錄，例 raw/fetched/local>
# 需要網域：www.rootlaw.com.tw（curl --cacert /root/.ccr/ca-bundle.crt）。LawID 可由 LawList.aspx?KWD1=<關鍵字>&ckbLawName=True 檢索取得。
# usage: python3 -I rootlaw_fetch.py <listfile> <baseoutdir>; listfile lines: LawID
import re,sys,html,subprocess,os,json
CA='/root/.ccr/ca-bundle.crt'
CM={'B01':'臺北市','B02':'新北市','B03':'基隆市','B04':'宜蘭縣','B05':'新竹市','B06':'新竹縣','B07':'桃園市','B08':'苗栗縣','B09':'臺中市','B11':'彰化縣','B12':'南投縣','B13':'嘉義市','B14':'嘉義縣','B15':'雲林縣','B16':'臺南市','B18':'高雄市','B20':'澎湖縣','B21':'屏東縣','B22':'臺東縣','B23':'花蓮縣','B26':'金門縣','B27':'連江縣'}
def h2t(s):
    s=re.sub(r'<(script|style).*?</\1>',' ',s,flags=re.S)
    s=re.sub(r'<br\s*/?>|</p>|</div>|</tr>|</li>|</h\d>','\n',s)
    t=html.unescape(re.sub('<[^>]+>',' ',s))
    t=re.sub(r'[ \t　]+',' ',t); t=re.sub(r'\n\s*\n+','\n',t); return t
base=sys.argv[2]; index=[]
for line in open(sys.argv[1],encoding='utf-8'):
    lid=line.strip().split()[0] if line.strip() else ''
    if not lid or lid.startswith('#'): continue
    county=CM.get(lid[:3],'other'); d=os.path.join(base,county); os.makedirs(d,exist_ok=True)
    fa=os.path.join(d,f'rootlaw_{lid}_article.html'); fc=os.path.join(d,f'rootlaw_{lid}_content.html')
    if not os.path.exists(fa) or os.path.getsize(fa)<5000:
        subprocess.run(['curl','-sS','--cacert',CA,'-o',fa,f'https://www.rootlaw.com.tw/LawArticle.aspx?LawID={lid}'])
    if not os.path.exists(fc) or os.path.getsize(fc)<5000:
        subprocess.run(['curl','-sS','--cacert',CA,'-o',fc,f'https://www.rootlaw.com.tw/LawContent.aspx?LawID={lid}'])
    ta=h2t(open(fa,encoding='utf-8',errors='replace').read()); tc=h2t(open(fc,encoding='utf-8',errors='replace').read())
    name=re.search(r'法規名稱：\s*\n?\s*(.+)',ta); name=name.group(1).strip() if name else '?'
    date=re.search(r'時間：\s*\n?\s*(中華民國[^\n]+)',ta); date=date.group(1).strip() if date else '?'
    i=ta.find('所有條文'); j=ta.find('植根公司首頁'); body=ta[i+4:j].strip() if i>0 else ''
    k=tc.find('立法沿革'); l=tc.find('法規異動'); hist=tc[k:l].strip() if k>0 else ''
    out=os.path.join(d,f'rootlaw_{lid}.txt')
    open(out,'w',encoding='utf-8').write(f'法規名稱：{name}\n版本時間：{date}\n來源：https://www.rootlaw.com.tw/LawArticle.aspx?LawID={lid}\n\n【沿革】\n{hist}\n\n【條文】\n{body}\n')
    index.append({'lawid':lid,'county':county,'name':name,'date':date,'chars':len(body),'path':out})
    print(county,lid,name,date,len(body))
json.dump(index,open(os.path.join(base,'rootlaw_index.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=1)

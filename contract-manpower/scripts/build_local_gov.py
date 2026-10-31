# -*- coding: utf-8 -*-
"""產生 contract-manpower/data/local_gov.json（22 直轄市、縣市契約人力樣態）。
資料來源：2026-10-31 WebSearch 摘要；因網路限制，各地方政府法規系統全文皆無法直接抓取。
accessible 欄位意義：
  "yes"      ：本環境可直接下載全文（law.moj.gov.tw / dgpa.gov.tw）
  "blocked"  ：搜尋到網址，但本環境被擋，無法取得全文（僅憑搜尋摘要）
  "listing"  ：僅在法規目錄（植根法律網等）看到名稱與日期，未見內容
"""
import json, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "contract-manpower/data/local_gov.json"

CENTRAL_NOTE = ("中央母法：行政院及所屬各機關學校約用人員進用及運用要點（113.1.30 更名，114.12.19 修正第3、4、6點並自115.1.1生效）"
                "第14點規定地方自治團體得準用；受中央補助經費進用者應依該要點辦理。")

def reg(title, year, url, accessible, summary):
    return {"title": title, "year": year, "url": url, "accessible": accessible, "summary": summary}

def hc(year, category, value, source):
    return {"year": year, "category": category, "value": value, "source": source}

data = []

# ---------------- 直轄市 ----------------
data.append({
  "name": "臺北市", "type": "直轄市",
  "regulations": [
    reg("臺北市政府各機關學校約用人員進用及運用要點（原「臨時人員進用及運用要點」）", "115.10.15 修正名稱及全文12點",
        "https://laws.gov.taipei/law/LawSearch/LawArticleContent/FL045489", "blocked",
        "約用人員＝非依公務人員法規且以人事費（或基金用人費）以外經費自行進用者，排除聘用、約僱、技工駕駛工友清潔隊員等；進用須符合5款條件之一（業務特殊現有人力無法負荷、配合重大政策、受委託或補助辦理特定業務、重大災害防疫等）；公開甄選並於網路公告至少7日；人數除新增業務外原則不得超過前一年度核定人數；辦理以不涉及公權力行使之業務為原則；首長及各級主管配偶與三親等親屬迴避；人事處得會同主計處訪查。"),
    reg("臺北市各機關學校臨時人員職稱及報酬參考表", "不明（衛生局薪點表引用）",
        "https://laws.gov.taipei/Law/File/0000211075", "blocked",
        "跨機關之職稱與報酬參照表；各機關（如衛生局專案約用人員薪點表、聯合醫院約用人員薪資結構表）另訂薪點表，薪點折合率比照當年度約聘僱人員，新進人員一律以最低本薪起敘，連續2年甲等晉一級。"),
    reg("臺北市政府推動業務委託民間辦理補充規定", "101 訂定，近年修正",
        "https://www.bjjh.tp.edu.tw/wp-content/uploads/doc/bjjh507/臺北市政府推動業務委託民間辦理補充規定及附表修正總說明及對照表.pdf", "blocked",
        "修正新增「機關應定期對勞務承攬案件進行檢討」之規定，為地方政府少數就勞務承攬訂有定期檢討機制者。"),
    reg("臺北市政府各機關年度聘僱用計畫人數（開放資料集）", "114", "https://data.taipei/dataset/detail?id=a8faace1-81f1-4944-a094-62ad734ce3bc", "blocked",
        "欄位含機關名稱、聘用、約僱、合計；摘要未顯示數字。"),
  ],
  "contract_types": ["約用人員（原臨時人員；含各局處專案約用人員）", "聘用人員", "約僱人員", "技工、駕駛、工友、清潔隊員（排除於約用要點）", "勞務承攬派駐人力", "委託民間辦理"],
  "political_appointee_clause": {"status": "無", "content": "搜尋摘要（含2009、2021、2026三版對照）均未見市長指定或隨首長進退條款；僅有親屬迴避與訪查規定。"},
  "salary_scheme": "各機關依「臨時人員職稱及報酬參考表」及自訂薪點表（薪點折合率比照約聘僱）；最低本薪起敘，考核晉級。",
  "labor_standards_act": "是",
  "caps_or_limits": "人數原則不得超過前一年度核定人數（新增業務除外）；年度聘僱用計畫人數另由人事處核定列管。",
  "core_noncore_rule": "約用人員辦理以不涉及公權力行使之業務為原則（2021年版說明：輔助機關執行非屬行使公權力之業務）。",
  "headcount": [
    hc("2018", "約聘僱人員", "約1,700餘人（市府員工近6.8萬人）", "關鍵評論網 https://www.thenewslens.com/article/105673（引人事處）"),
    hc("2018", "勞動派遣", "5人", "公視 https://news.pts.org.tw/article/400279"),
  ],
  "notable_practices": ["115.10.15 全文翻修並更名「約用人員」，為六都中最晚更名者之一但修正最完整（12點）", "明定人數不得逾前一年度核定人數之『凍結式』總量管制", "訂有勞務承攬案件定期檢討規定（業務委託民間辦理補充規定）", "開放資料平臺公開各機關聘僱人數"],
  "sources": ["https://laws.gov.taipei/law/LawSearch/LawExport/FL045489?type=2", "https://laws.gov.taipei/law/LawSearch/LawArticleContent/FL045489?date=20210708", "https://www.thenewslens.com/article/105673", "https://news.pts.org.tw/article/400279", "https://data.taipei/dataset/detail?id=a8faace1-81f1-4944-a094-62ad734ce3bc"],
})

data.append({
  "name": "新北市", "type": "直轄市",
  "regulations": [
    reg("新北市政府所屬機關學校非編制人員管理要點", "113.6.19 修正",
        "https://web.law.ntpc.gov.tw/Scripts/FLAWDAT01.aspx?lncode=1C0100010", "blocked",
        "新北市對「約用人員」之總括性規範（新北市未採「約用人員」名稱，稱「非編制人員」，含雇工、臨時雇工、暫僱人員）；附件一定期契約書、附件二暫僱人員支給報酬標準表；明訂迴避進用規範。全文無法取得，無法核對是否有市長指定／隨同進退條款。"),
    reg("新北市政府及所屬機關學校約聘僱與非編制人員服務評量要點", "100.4.12 訂定；109.3.26 修正",
        "https://www.personnel.ntpc.gov.tw/uploaddowndoc?dis=downloaddata&file=downloaddata%2F202405101528040.pdf", "blocked",
        "適用約僱、聘用及依勞基法進用之非編制人員（雇工、臨時雇工、暫僱人員）；各機關設評量委員會（副首長、首長指定人員、單位主管，首長指定一人為主席）；列舉應立即終止契約情形；不續聘或終止契約應書面通知並得申訴。"),
    reg("新北市政府所屬各機關學校辦理約聘僱與非編制人員公開甄選作業規定（原「自行遴補非編制人員公開甄選作業規定」）", "不明（更名修正）",
        "https://www.wsjh.ntpc.edu.tw/news/修正「新北市政府所屬各機關學校自行遴補非編制人員/", "blocked",
        "公開甄選程序規定；非編制人員管理要點已明訂迴避進用規範。"),
    reg("新北市政府非編制人員給假要點", "104.12.18", "http://www.rootlaw.com.tw/LawContent.aspx?LawID=B020110001005700-1041218", "listing", "非編制人員給假規定。"),
    reg("新北市政府環境保護局空氣污染防制基金約用人員約用要點／毒物及化學物質約用人員約用要點", "107.8.28／107.8.21",
        "https://www.rootlaw.com.tw/LawArticle.aspx?LawID=B020220001011300-1070828", "blocked",
        "基金進用之約用人員：契約自簽約日至當年12月31日、最長一年；薪點依學歷；年終考核決定升等、維持或終止；機關精簡整併組織變更得預告終止；適用勞基法及行政院臨時人員要點。"),
    reg("新北市政府聘用社會工作員及社會工作督導管理要點", "107.7.3", "https://www.rootlaw.com.tw/LawArticle.aspx?LawID=B020070001009600-1070703", "listing", "社工類契約人力之專法。"),
    reg("新北市政府人事處108年度自行研究報告「我國聘僱人員人事法制之研究」", "108",
        "https://www.rde.ntpc.gov.tw/userfiles/1160700/files/16我國聘僱人員人事法制之研究.pdf", "blocked",
        "指出現行制度分聘用、派用、機要、聘任、約僱五類，進用程序不夠嚴謹致首長濫用私人、聘僱酬庸化；引述契約人員人事條例草案：組織法律規定「隨同長官異動而更易」之契約人員得免公開甄選、首長於限制期間不得進用但續聘者得聘至原首長離職時止。"),
  ],
  "contract_types": ["聘用人員", "約僱人員（含職務代理人）", "其他非編制人員：雇工、臨時雇工、暫僱人員（適用勞基法）", "基金約用人員（環保局等）", "聘用社工員／社工督導", "勞動派遣（2018年尚有上百人）", "勞務承攬"],
  "political_appointee_clause": {"status": "不明", "content": "使用者所述「約用人員保留10～15%類似機要、隨市長進退」條款：以「隨同進退／隨市長進退／市長指定／百分之十／機要約用」等關鍵字多輪搜尋，均未在新北市任何法規摘要或新聞中找到；唯一相近文字為人事處108年研究報告引述之中央「契約人員人事條例草案」（隨同長官異動而更易之契約人員得免公開甄選）。非編制人員管理要點（113.6.19）全文被擋，無法排除；需開放 web.law.ntpc.gov.tw 核對。"},
  "salary_scheme": "暫僱人員支給報酬標準表（非編制人員管理要點附件二）；個案公告顯示臨時雇工月薪29,090元（2025新莊戶政）、暫僱人員比照勞動部勞發署臨時人員業務輔導員給薪標準第1階35,235元（2025原民局）；基金約用人員採薪點依學歷。",
  "labor_standards_act": "是",
  "caps_or_limits": "摘要未見明文總量比例；非編制人員須循年度計畫核定；工友另有員額管理作業要點。",
  "core_noncore_rule": "摘要未見明文；基金約用要點準用行政院臨時人員要點（非公權力）。",
  "headcount": [
    hc("2018", "勞動派遣", "上百人（六都中最多）", "公視 https://news.pts.org.tw/article/400279"),
  ],
  "notable_practices": ["不採「約用人員」名稱而以「非編制人員」統稱，並與約聘僱共用服務評量、公開甄選規定", "評量委員會由首長指定人員參與並指定主席", "區公所臨時人員過勞猝死遭監察院糾正（2021 金山區公所）", "人事處研究報告自承聘僱進用程序不嚴謹、有酬庸化情形"],
  "sources": ["https://web.law.ntpc.gov.tw/Scripts/FLAWDAT01.aspx?lncode=1C0100010", "https://www.personnel.ntpc.gov.tw/uploaddowndoc?dis=downloaddata&file=downloaddata%2F202405101528040.pdf", "https://www.rootlaw.com.tw/LawArticle.aspx?LawID=B020110001002300-1090326", "https://www.rde.ntpc.gov.tw/userfiles/1160700/files/16我國聘僱人員人事法制之研究.pdf", "https://www.rootlaw.com.tw/LawArticle.aspx?LawID=B020220001011300-1070828", "https://newtalk.tw/news/view/2021-09-02/630246", "https://news.pts.org.tw/article/400279"],
})

data.append({
  "name": "桃園市", "type": "直轄市",
  "regulations": [
    reg("桃園市政府及所屬各機關學校約用人員進用及管理要點（原「臨時人員進用及管理要點」）", "112.9.27 修正（部分自113.1.1施行）；113.3.20 修正更名",
        "https://law.tycg.gov.tw/LawContent.aspx?id=GL000770", "blocked",
        "約用人員＝非依公務人員法規、以人事費以外經費自行進用者，排除聘用、約僱、工友管理要點人員、測量助理、清潔隊員等；公開甄選並於人事總處事求人及市府徵才網公告3日以上；工資依勞動基準法；首長於任用法第26條之1期間不得新進用；親屬迴避。學校轉載 PDF：https://www.whjhs.tyc.edu.tw/wp-content/uploads/doc/wh710/桃園市政府及所屬各機關學校約用人員進用及管理要點.pdf"),
    reg("桃園市政府及所屬各機關學校約聘僱人員進用及考核要點", "109.7.14", "https://www.rootlaw.com.tw/LawContent.aspx?LawID=B070130001000600-1090714", "listing", "約聘僱報酬以核定計畫等別最低薪點起支；首長親屬迴避。"),
    reg("桃園市政府所屬各機關學校聘僱用及臨時人員職稱一覽表", "105.8.4 府人考字第1050192915號",
        "https://www.sdes.tyc.edu.tw/uploads/neilmfdcms/types1/7file/file/206_2_376735100e_1120076280_attach2.pdf", "blocked", "統一聘僱用及臨時人員職稱。"),
    reg("桃園市政府勞動局臨時人員工作規則", "105.3.3", "https://www.rootlaw.com.tw/LawArticle.aspx?LawID=B070100000003800-1050303", "listing", "機關別工作規則（勞基法第70條）。"),
  ],
  "contract_types": ["約用人員（原臨時人員）", "聘用人員", "約僱人員（含職務代理人、一年一僱之不定期契約約僱助理）", "專案督導（臨時人員，比照聘用十等進用；文化局）", "清潔隊員（另軌；張善政任內增額276人）", "勞務承攬／委外"],
  "political_appointee_clause": {"status": "無", "content": "未見「機要約用」或首長幕僚約用規定；僅有首長任用法第26條之1期間不得新進用之限制。"},
  "salary_scheme": "工資依勞基法；實務上部分職缺「比照聘用○等」敘薪（如文化局專案督導比照聘用十等）；2017年臨時人員加薪跟進中央。",
  "labor_standards_act": "是",
  "caps_or_limits": "摘要未見明文比例；須經市府核定計畫。",
  "core_noncore_rule": "更名總說明引行政院：臨時人員協助機關辦理未涉及公權力行使之常態性業務。",
  "headcount": [
    hc("2018", "勞動派遣", "0（已改委外、承攬）", "公視 https://news.pts.org.tw/article/400279"),
    hc("2024-2025", "清潔隊員增額", "276人（張善政任內）", "公視 https://news.pts.org.tw/article/823083"),
  ],
  "notable_practices": ["113年配合中央更名，為最早跟進之直轄市之一", "職稱一覽表統一聘僱用及臨時人員職稱", "個案以『臨時人員比照聘用十等』方式進用高階專案人力", "勞檢處擬以約用人員分擔庶務（勞動局）"],
  "sources": ["https://law.tycg.gov.tw/LawContent.aspx?id=GL000770", "https://www.whjhs.tyc.edu.tw/wp-content/uploads/doc/wh710/桃園市政府及所屬各機關學校約用人員進用及管理要點.pdf", "https://www.rootlaw.com.tw/LawContent.aspx?LawID=B070130001005600-1090714", "https://culture.tycg.gov.tw/home.jsp?dataserno=202302080007&id=95&mcustomize=job_view.jsp", "https://www.chinatimes.com/realtimenews/20170918000355-260503", "https://udn.com/news/story/7324/9406774"],
})

data.append({
  "name": "臺中市", "type": "直轄市",
  "regulations": [
    reg("臺中市政府及所屬機關學校約用人員及業務助理管理要點（原「暨所屬機關學校約用人員及業務助理僱用及管理要點」）", "112.10.30 修正更名生效",
        "https://www.personnel.taichung.gov.tw/media/994005/112年10月新增修訂人事法規釋例彙整表.pdf", "blocked",
        "約用人員係依計畫經費或基金僱用；112.10 修正名稱並修正「約用人員及業務助理支給報酬標準表」（刪除160、190薪點，因已無進用可能）。"),
    reg("臺中市政府及所屬各機關學校行政助理進用及管理要點", "108.5.30 修正",
        "https://www.dbas.taichung.gov.tw/media/529376/13-1臺中市政府及所屬各機關學校行政助理進用及管理要點-108530修正.pdf", "blocked",
        "行政助理＝非依公務人員法規以人事費以外經費進用之臨時人員（排除依約用及業務助理要點進用者）；業務以非行使公權力之臨時性、短期性、季節性及特定性具定期契約性質工作為限（含輔助性公權力例外）；進用前先檢討現有人力；親屬迴避。"),
    reg("臺中市政府暨所屬各機關學校約聘僱人員聘僱計畫及員額管控原則", "108.4.22",
        "https://www.personnel.taichung.gov.tw/media/431495/臺中市政府暨所屬各機關學校約聘僱人員聘僱計畫及員額管控原則-1080422發布.pdf", "blocked",
        "以公務預算約聘（僱）人數以一級機關為單位，分別不得超過機關預算總人數5%。"),
    reg("臺中市政府暨所屬機關學校約聘（僱、用）權益差異表", "不明", "https://www.tc.edu.tw/cms-file/61d6812a968ba346b821b70d.pdf", "blocked", "區分約聘（專門性業務）、約僱、約用（依計畫經費或基金僱用）三類之性質與權益。"),
  ],
  "contract_types": ["約用人員（計畫經費／基金）", "業務助理", "行政助理（臨時人員）", "聘用人員", "約僱人員"],
  "political_appointee_clause": {"status": "不明", "content": "搜尋未見「首長幕僚約用」或隨首長進退條款；約用要點全文被擋。"},
  "salary_scheme": "約用人員及業務助理支給報酬標準表（薪點制，114年行政助理案例280薪點＝37,800元；較早案例學士31,520／碩士36,050）。",
  "labor_standards_act": "是",
  "caps_or_limits": "約聘僱：一級機關公務預算約聘僱人數≤機關預算總人數5%；約用／行政助理：須先檢討現有人力，摘要未見比例。",
  "core_noncore_rule": "行政助理要點：以非行使公權力之臨時性、短期性、季節性及特定性工作為限。",
  "headcount": [],
  "notable_practices": ["約用人員／業務助理／行政助理三軌並列，是分類最細的直轄市", "約聘僱5%員額管控原則明文化（108年）", "112年修正報酬表刪除低薪點等級，反映起薪隨基本工資上移"],
  "sources": ["https://www.personnel.taichung.gov.tw/media/994005/112年10月新增修訂人事法規釋例彙整表.pdf", "https://www.dbas.taichung.gov.tw/media/529376/13-1臺中市政府及所屬各機關學校行政助理進用及管理要點-108530修正.pdf", "https://www.personnel.taichung.gov.tw/media/431495/臺中市政府暨所屬各機關學校約聘僱人員聘僱計畫及員額管控原則-1080422發布.pdf", "https://www.tc.edu.tw/cms-file/61d6812a968ba346b821b70d.pdf", "https://www.tc.edu.tw/news-file/67c00f00a49a1202e054145b.cab"],
})

data.append({
  "name": "臺南市", "type": "直轄市",
  "regulations": [
    reg("臺南市政府及所屬機關學校約用人員工作規則", "不明",
        "https://culture.tainan.gov.tw/df_ufiles/282/臺南市政府及所屬機關學校約用人員工作規則.pdf", "blocked",
        "適用對象：非依工友管理要點、聘用條例、約僱辦法進用，與機關簽訂勞動契約並適用勞基法之約用人員；得試用3個月；首長及各級主管配偶與三親等親屬迴避。"),
    reg("臺南市政府及所屬各機關臨時人員僱用及管理考核要點", "107.3.22 版",
        "https://w3fs.tainan.gov.tw/001/Upload/32/attachment/8923/4278/1070322-1.pdf", "blocked",
        "臨時人員＝不依公務人員法規以人事費以外經費進用者（不含約用人員、工友駕駛）；得辦理業務以非行使公權力之定期或不定期契約性質工作為限；僱用須於會計年度開始前簽准；第8點：機關首長於公務人員任用法第26條之1第1項期間內不得新僱用臨時人員。"),
    reg("臺南市政府及所屬機關學校約聘僱人員進用管理考核要點（原「約聘僱人員考核要點」）", "更名修正（年不明）",
        "https://culture.tainan.gov.tw/df_ufiles/033/臺南市政府及所屬機關學校約聘僱人員進用管理考核要點.pdf", "blocked", "修正後納入進用與終止契約等管理規範。"),
    reg("臺南市政府及所屬機關學校約用人員支給報酬標準表", "修正對照表（年不明）",
        "https://schoolweb.tn.edu.tw/~wyes_www/uploads/tadnews/file/nsn_14125_5_shS.pdf", "blocked",
        "約用人員依「等別」分級並以報酬薪點計算（二等起薪點190、級距200～240；三等起點220…），對應職責程度與所具知能條件（學歷）；薪點折算未達基本工資者依勞基法給付。"),
    reg("臺南市政府113年甄試職缺一覽表", "113", "https://job.tainan.gov.tw/wp-content/uploads/dj_page_uploads/d20240403090426_235.pdf", "blocked", "列各機關約用、約聘及臨時技術工職缺。"),
  ],
  "contract_types": ["約用人員（分等：約用二等～六等等）", "臨時人員", "臨時技術工", "聘用人員", "約僱人員"],
  "political_appointee_clause": {"status": "無", "content": "未見隨首長進退條款；僅有首長於任用法第26條之1期間不得新僱用臨時人員之限制（107年版第8點）。"},
  "salary_scheme": "約用人員支給報酬標準表：依等別（職責程度＋學歷）訂薪點，薪點制；108年勞工局約用五等案例月薪約34,000元。",
  "labor_standards_act": "是",
  "caps_or_limits": "摘要未見比例；僱用須會計年度前簽准並經審核。",
  "core_noncore_rule": "臨時人員以非行使公權力之定期或不定期契約性質工作為限。",
  "headcount": [hc("2018", "勞動派遣", "0", "公視 https://news.pts.org.tw/article/400279")],
  "notable_practices": ["約用人員採『等別＋薪點』分級，形同契約人力職等制", "約用人員與臨時人員分軌（工作規則 vs. 僱用管理考核要點）", "明文首長任期末期不得新僱臨時人員"],
  "sources": ["https://culture.tainan.gov.tw/df_ufiles/282/臺南市政府及所屬機關學校約用人員工作規則.pdf", "https://w3fs.tainan.gov.tw/001/Upload/32/attachment/8923/4278/1070322-1.pdf", "https://culture.tainan.gov.tw/df_ufiles/033/臺南市政府及所屬機關學校約聘僱人員進用管理考核要點.pdf", "https://schoolweb.tn.edu.tw/~wyes_www/uploads/tadnews/file/nsn_14125_5_shS.pdf", "https://job.tainan.gov.tw/wp-content/uploads/2019/10/108-3-12-1.pdf"],
})

data.append({
  "name": "高雄市", "type": "直轄市",
  "regulations": [
    reg("高雄市政府所屬各機關學校臨時人員進用及運用要點", "101 訂定；111.1.7 高市府行國職字第11130018600號函修正（搜尋未見113年後更名）",
        "https://orgws.kcg.gov.tw/001/KcgOrgUploadFiles/261/relfile/15627/65864/fb0b2e4d-e05a-4cec-8569-fdfe347af138.pdf", "blocked",
        "臨時人員＝以人事費以外經費自行進用之非公務人員（排除聘用、約僱、技工駕駛工友清潔隊員測量助理、教保員等）；業務以非公權力工作為限、先檢討現有人力；進用須經審核小組審議（代收代付或自負盈虧基金進用者由一級機關審核後報府備查）；以市府經費進用之人數不得超過各一級機關及所屬100年度實際進用人數，111年後新設機關以設立後第二年實際人數為準。"),
    reg("高雄市政府一級機關(含所屬)及區公所進用臨時人員控管上限數表", "106.1.1 基準",
        "https://orgws.kcg.gov.tw/001/KcgOrgUploadFiles/422/relfile/75883/380559/bcfae321-01b5-44d7-b917-9ba41672d377.pdf", "blocked",
        "逐機關訂臨時人員上限：環保局1,216、交通局625、教育局及所屬學校338、社會局348、衛生局313（表格被截斷，無法加總）。"),
    reg("高雄市立醫院醫務契約人員管理要點", "不明", "https://orgws.kcg.gov.tw/001/KcgOrgUploadFiles/478/relfile/79084/407734/8b2fcf08-e9da-4701-a6d8-85b7d6f84b93.pdf", "blocked", "契約人員公開甄選、先簽3個月試用契約。"),
  ],
  "contract_types": ["臨時人員（市府經費／基金／代收代付）", "聘用人員", "約僱人員", "醫務契約人員（市立醫院）", "技工駕駛工友清潔隊員測量助理（另軌）"],
  "political_appointee_clause": {"status": "無", "content": "未見條款。2026.8 陳其邁卸任前4局處首長改「代理」之爭議屬機要／政務職層次，與臨時人員無關。"},
  "salary_scheme": "各機關比照中央（如文化部）臨時人員酬金標準，依學歷敘薪點（108年都發局：學士261薪點32,547元、碩士289薪點36,038元）；114年衛生局長照中心案例月薪33,300元、每年最高13.5個月。",
  "labor_standards_act": "是",
  "caps_or_limits": "以100年度實際進用人數為上限（凍結式），並逐一級機關訂定控管上限數表。",
  "core_noncore_rule": "業務以非公權力工作為限；進用前須檢討現有人力。",
  "headcount": [
    hc("2017(106.1.1基準)", "臨時人員控管上限（部分機關）", "環保局1,216；交通局625；教育局及所屬338；社會局348；衛生局313", "高雄市政府控管上限數表 https://orgws.kcg.gov.tw/001/KcgOrgUploadFiles/422/relfile/75883/380559/bcfae321-01b5-44d7-b917-9ba41672d377.pdf"),
    hc("2021-2022", "警察局約聘僱", "110年底55人、111年底57人", "高雄市警察局員工統計表（orgws.kcg.gov.tw）"),
    hc("2018", "勞動派遣", "0", "公視 https://news.pts.org.tw/article/400279"),
  ],
  "notable_practices": ["逐機關『臨時人員控管上限數表』，是六都中最明確的機關別總量管制", "以100年度實際人數為基準凍結，與中央以96年度為基準同構", "尚未配合中央更名為約用人員（截至搜尋結果111年版）"],
  "sources": ["https://orgws.kcg.gov.tw/001/KcgOrgUploadFiles/261/relfile/15627/65864/fb0b2e4d-e05a-4cec-8569-fdfe347af138.pdf", "https://orgws.kcg.gov.tw/001/KcgOrgUploadFiles/422/relfile/75883/380559/bcfae321-01b5-44d7-b917-9ba41672d377.pdf", "https://urban-web.kcg.gov.tw/KDA/web_upload/KDA05/KDA0504/20200409143038-7.pdf", "https://www.chinatimes.com/realtimenews/20260818003513-260407", "https://news.pts.org.tw/article/400279"],
})

# ---------------- 市 ----------------
data.append({
  "name": "基隆市", "type": "市",
  "regulations": [
    reg("基隆市政府及所屬機關學校約用人員進用及管理要點", "113（配合中央更名）",
        "https://exlaw.klcg.gov.tw/LawContent.aspx?id=GL000073", "blocked",
        "約用人員＝非依公務人員法規、以人事費以外經費自行進用之人員；全文被擋。"),
    reg("基隆市政府及所屬機關學校約聘僱人員及約用人員公開甄選要點（修正對照表）", "113",
        "https://chps.kl.edu.tw/news/file/1862/修正對照表.pdf", "blocked",
        "配合行政院113.1.30更名，將「臨時人員」改為「約用人員」；經市府核定年度聘（僱）用計畫列管之約聘、約僱及約用人員出缺時應公開甄選，列有例外。"),
    reg("基隆市政府及所屬機關學校臨時人員僱用管理要點（舊）", "102.12.19", "https://www.rootlaw.com.tw/LawList.aspx?lcode=693", "listing", "舊名稱。"),
    reg("基隆市政府約聘社會工作人員管理要點", "114.4.22 修正", "https://syjh.kl.edu.tw/news/file/6134/1140422-基隆市政府約聘社會工作人員管理要點修正.docx", "blocked", "社工類專法。"),
  ],
  "contract_types": ["約用人員（原臨時人員）", "約聘人員", "約僱人員", "約聘社會工作人員", "技工工友"],
  "political_appointee_clause": {"status": "不明", "content": "全文被擋；摘要未見。"},
  "salary_scheme": "不明（全文被擋）。",
  "labor_standards_act": "不明（推定是，準用中央要點）",
  "caps_or_limits": "約用人員納入市府核定之年度聘（僱）用計畫列管。",
  "core_noncore_rule": "不明（全文被擋）。",
  "headcount": [],
  "notable_practices": ["約用人員與約聘僱人員共用一套公開甄選要點並同列年度聘僱用計畫列管", "113年即完成更名"],
  "sources": ["https://exlaw.klcg.gov.tw/LawContent.aspx?id=GL000073", "https://chps.kl.edu.tw/news/file/1862/修正對照表.pdf", "https://www.rootlaw.com.tw/LawList.aspx?lcode=693", "https://syps.kl.edu.tw/images/files/kledu31302/基隆市政府115年度公務人力培訓實施計畫.pdf"],
})

data.append({
  "name": "新竹市", "type": "市",
  "regulations": [
    reg("新竹市政府及所屬機關學校約用人員考核及輔導作業要點", "104.6.16 核定；113.5.10 修正名稱及附表；114.10.8 修正第4、6點",
        "https://www.pijh.hc.edu.tw/uploads/176362845086523lHkrNk.docx", "blocked",
        "平時考核每年6月、年終考核12月；甲等80分以上、乙等70～80、丙等未滿70；年終考核連續二年甲等或三年內一甲二乙者調增薪資一級（自次年1月）；丙等或連續多年乙等經輔導仍不能勝任者，依勞基法預告終止勞動契約；任職未滿一年不計入調薪累計。"),
    reg("新竹市政府約用人員工作規則", "不明", "https://www.hsps.hc.edu.tw/uploads/1788509592313W1B2CpN9.pdf", "blocked", "各校約用人員甄選簡章之依據（每日8小時等）。"),
    reg("監察院調查報告（新竹市政府104年不續聘63位約聘僱及95位臨時人員案）", "104-105", "https://cybsbox.cy.gov.tw/CYBSBoxSSL/edoc/download/45482", "blocked",
        "市府於104年2月底通知不續聘，未告知原因亦未予陳述意見機會，不續聘標準未公開透明，其中不乏考核連續多年甲等者，監察院認有不當。"),
  ],
  "contract_types": ["約用人員", "約僱人員", "約聘人員", "工友"],
  "political_appointee_clause": {"status": "無", "content": "未見條款；但104年市長換屆後大規模不續聘約聘僱與臨時人員遭監察院調查，顯示實務上存在『換屆汰換』現象。"},
  "salary_scheme": "115年起市庫自籌之約僱、約用人員及工友起薪32,450元（最低工資1.1倍）；考核連續甲等調增一級。",
  "labor_standards_act": "是",
  "caps_or_limits": "摘要未見。",
  "core_noncore_rule": "摘要未見。",
  "headcount": [hc("2015", "不續聘人數", "約聘僱63人、臨時人員95人", "監察院調查報告 https://cybsbox.cy.gov.tw/CYBSBoxSSL/edoc/download/45482")],
  "notable_practices": ["考核結果直接連動調薪一級及預告終止契約，為縣市中少見之明確『考核—薪級—退場』機制", "115年率先以最低工資1.1倍訂約用人員起薪", "104年換屆大規模不續聘案遭監察院調查"],
  "sources": ["https://www.pijh.hc.edu.tw/uploads/176362845086523lHkrNk.docx", "https://www.pijh.hc.edu.tw/uploads/1763628450872l8PgQOnS.pdf", "https://udn.com/news/story/7324/9519774", "https://cybsbox.cy.gov.tw/CYBSBoxSSL/edoc/download/45482"],
})

data.append({
  "name": "嘉義市", "type": "市",
  "regulations": [
    reg("嘉義市政府環境保護局土污基金約用人員約用要點", "99.12.6", "https://www.rootlaw.com.tw/LawList.aspx?lcode=937", "listing", "單一機關基金約用要點；市府通案約用／臨時人員要點搜尋未得。"),
    reg("嘉義市政府衛生局112年第1次約聘人員甄選簡章", "112", "https://dweb.cjcu.edu.tw/ShepherdFiles/C0206/News/20230116160900437.pdf", "blocked", "依聘用條例辦理，屬約聘而非約用。"),
    reg("嘉義市環保局擴編30名約用清潔人力（新聞）", "115.7", "https://www.1111.com.tw/news/166846/amp/", "blocked", "設籍嘉義市滿3個月、普通重型機車駕照；顯示以『約用』名義進用清潔人力。"),
  ],
  "contract_types": ["約用人員（基金／清潔人力）", "約聘人員", "公立幼兒園契約進用人員（廚工）"],
  "political_appointee_clause": {"status": "不明", "content": "未找到通案要點。"},
  "salary_scheme": "不明；清潔隊員招募月薪32K（115年）。",
  "labor_standards_act": "不明（推定是）",
  "caps_or_limits": "不明。",
  "core_noncore_rule": "不明。",
  "headcount": [hc("2026(115)", "約用清潔人力擴編", "30人", "1111 新聞 https://www.1111.com.tw/news/166846/amp/")],
  "notable_practices": ["僅見機關別（環保局基金）約用要點，通案規範未見於公開搜尋"],
  "sources": ["https://www.rootlaw.com.tw/LawList.aspx?lcode=937", "https://www.1111.com.tw/news/166846/amp/", "https://dweb.cjcu.edu.tw/ShepherdFiles/C0206/News/20230116160900437.pdf"],
})

# ---------------- 縣 ----------------
data.append({
  "name": "新竹縣", "type": "縣",
  "regulations": [
    reg("新竹縣政府及所屬機關學校約聘僱人員考核要點", "108.1.31 修正", "https://www.rootlaw.com.tw/LawList.aspx?lcode=765", "listing", "考核類規定。"),
    reg("新竹縣政府及所屬各機關學校臨時人員考核委員會設置要點", "108.9.19 訂定", "https://www.rootlaw.com.tw/LawList.aspx?lcode=766", "listing", "臨時人員設考核委員會。"),
    reg("新竹縣政府所屬各機關、學校新進醫事人員甄選作業要點", "不明", "https://www.rootlaw.com.tw/Attach/L-Doc/B060140001000800-0990715-5000-001.doc", "listing", "醫事人員甄選。"),
  ],
  "contract_types": ["臨時人員", "約聘僱人員", "新進醫事人員"],
  "political_appointee_clause": {"status": "不明", "content": "未找到進用要點。"},
  "salary_scheme": "不明。", "labor_standards_act": "不明", "caps_or_limits": "不明。", "core_noncore_rule": "不明。",
  "headcount": [],
  "notable_practices": ["臨時人員另設考核委員會（108年）", "進用要點未見於公開搜尋"],
  "sources": ["https://www.rootlaw.com.tw/LawList.aspx?lcode=765", "https://www.rootlaw.com.tw/LawList.aspx?lcode=766"],
})

data.append({
  "name": "苗栗縣", "type": "縣",
  "regulations": [
    reg("苗栗縣政府約用輔導人員／專業輔導人員甄選公告（教育處）", "113-114", "https://careercenter.ncu.edu.tw/storage/files/2024-12-27T11:22:22+08:00/來文3-附件1.pdf", "blocked",
        "依證照與學歷訂月薪（碩士＋心理師或社工師證照47,363元）；報名須簽迴避任用切結書（援引任用法第26條）。通案約用要點未得。"),
    reg("審計部對苗栗縣約聘僱及臨時人員之意見（新聞）", "2016", "https://ec.ltn.com.tw/article/breakingnews/1631381", "blocked",
        "審計部官員：約聘及約僱人員占正式員額比率不得超過5%；技工、工友、駕駛、助理工程師及臨時人員等並無員額限制。"),
    reg("苗栗縣約聘僱及臨時人員膨脹爭議（新聞）", "2014", "https://www.thenewslens.com/article/26746", "blocked", "中央認苗栗進用約聘僱、臨時人員太多，要求依法定比率精簡；中央款聘任之臨時約用人員已不補助、縣府表示留任。"),
  ],
  "contract_types": ["約用人員（輔導人員等計畫型）", "臨時人員", "約聘僱人員", "技工工友駕駛"],
  "political_appointee_clause": {"status": "不明", "content": "未找到要點。"},
  "salary_scheme": "計畫型約用依學歷與證照分級（教育處案例）。", "labor_standards_act": "不明（推定是）",
  "caps_or_limits": "約聘僱受5%比率限制（審計部說法）；臨時人員無員額限制。", "core_noncore_rule": "不明。",
  "headcount": [hc("2014", "約聘僱及臨時人員", "2005～2014年明顯增加（無確切數）", "關鍵評論網 https://www.thenewslens.com/article/26746")],
  "notable_practices": ["財政危機縣市，約聘僱與臨時人員膨脹受中央、審計關注之典型案例"],
  "sources": ["https://www.thenewslens.com/article/26746", "https://ec.ltn.com.tw/article/breakingnews/1631381", "https://careercenter.ncu.edu.tw/storage/files/2024-12-27T11:22:22+08:00/來文3-附件1.pdf"],
})

data.append({
  "name": "彰化縣", "type": "縣",
  "regulations": [
    reg("彰化縣政府暨所屬機關學校約用人員進用要點", "113（113-4875-1）",
        "https://lawsearch.chcg.gov.tw/GLRSNEWSOUT/LawContent.aspx?id=FL028110", "blocked",
        "目的在杜絕酬庸用人、建立公平公正公開用人制度；約用人員＝非依公務人員法制、以人事費以外經費進用者（排除聘用、技工駕駛工友清潔隊員、依臨時約聘僱人員進用要點進用者）；業務以非行使公權力為限；以公開甄選為原則，例外：中央補助且訂有程序、聘僱未達6個月、兩次甄選無人報名或無適當人選。學校轉載：https://www.hyjhes.chc.edu.tw/storage/074541/posts/463/files/113-4875-1彰化縣政府暨所屬機關學校約用人員進用要點.pdf"),
    reg("彰化縣政府暨所屬機關學校臨時人員進用要點", "不明", "https://town.chcg.gov.tw/files/進用要點107.7.19修正_50_1070724_50_1090601.pdf", "blocked", "各機關甄選簡章引用，臨時人員另有獨立規範。"),
    reg("彰化縣政府約用人員僱用契約書", "114.1.1", "https://files.chcg.gov.tw/files/12_20241206114434788_1140101約用人員僱用契約書.odt", "blocked", "親屬迴避、勞基法、請假與特休等。"),
    reg("彰化縣政府暨所屬機關學校約聘僱計畫審核要點", "不明", "https://www.gyes.chc.edu.tw/storage/074647/posts/2152/files/376470000A_1120114497_ATTACH3.pdf", "blocked", "第6點：聘、僱人數超過預算員額5%，應檢討計畫存廢。"),
    reg("彰化縣政府所屬各級學校約用護理人員進用要點", "114", "https://hyjhes.chc.edu.tw/storage/074541/posts/1792/files/114-4985-2彰化縣政府所屬各級學校約用護理人員進用要點.pdf", "blocked", "職類別約用要點。"),
  ],
  "contract_types": ["約用人員", "臨時人員", "臨時約聘僱人員", "約用護理人員", "身心障礙約用人員（學校）", "清潔隊員技工工友"],
  "political_appointee_clause": {"status": "無", "content": "要點以『杜絕酬庸用人』為立法目的，與隨首長進退之設計相反。"},
  "salary_scheme": "公告載明月支報酬；詳細分級不明。", "labor_standards_act": "是",
  "caps_or_limits": "約聘僱逾預算員額5%應檢討計畫存廢；約用人員比例未見。",
  "core_noncore_rule": "約用人員辦理之業務以非行使公權力為限。",
  "headcount": [],
  "notable_practices": ["要點開宗明義『杜絕酬庸用人』", "約用、臨時、臨時約聘僱三套進用要點並行", "職類別（護理）約用要點"],
  "sources": ["https://lawsearch.chcg.gov.tw/GLRSNEWSOUT/LawContent.aspx?id=FL028110", "https://www.hyjhes.chc.edu.tw/storage/074541/posts/463/files/113-4875-1彰化縣政府暨所屬機關學校約用人員進用要點.pdf", "https://files.chcg.gov.tw/files/12_20241206114434788_1140101約用人員僱用契約書.odt", "https://www.gyes.chc.edu.tw/storage/074647/posts/2152/files/376470000A_1120114497_ATTACH3.pdf"],
})

data.append({
  "name": "南投縣", "type": "縣",
  "regulations": [
    reg("南投縣政府暨所屬機關學校約聘(僱)人員管理要點", "97.2.29", "https://www.rootlaw.com.tw/LawList.aspx?lcode=908", "listing", "目錄僅見名稱。"),
    reg("南投縣政府臨時人員工作規則", "103.10.22", "https://www.rootlaw.com.tw/LawList.aspx?lcode=908", "listing", "勞基法第70條工作規則。"),
    reg("南投縣政府暨所屬機關短期進用人員管理要點", "97.1.1（已停止適用）", "https://www.rootlaw.com.tw/LawList.aspx?lcode=908", "listing", "已停止適用。"),
  ],
  "contract_types": ["臨時人員", "約聘(僱)人員"],
  "political_appointee_clause": {"status": "不明", "content": "未找到約用進用要點。"},
  "salary_scheme": "不明。", "labor_standards_act": "是（訂有臨時人員工作規則）", "caps_or_limits": "不明。", "core_noncore_rule": "不明。",
  "headcount": [],
  "notable_practices": ["以『臨時人員工作規則』為主要規範形式，未見113年後更名"],
  "sources": ["https://www.rootlaw.com.tw/LawList.aspx?lcode=908"],
})

data.append({
  "name": "雲林縣", "type": "縣",
  "regulations": [
    reg("雲林縣政府及所屬機關臨時人員工作要點", "不明（社會處徵才公告引用）", "https://ms.kmu.edu.tw/attachments/article/1154/徵才公告-臨時約用社工.pdf", "blocked",
        "臨時約用人員待遇與給假依本要點及縣府請假須知；112年臨時約用社工員月薪34,916元；任用至當年12月31日。"),
    reg("雲林縣政府社會處115年約用社會工作員／生活服務員需求計畫", "115", "https://yleni.mohw.gov.tw/files/115年約用社會工作員需求計畫_第1次.pdf", "blocked", "社政類約用人力計畫；約聘僱改以薪點計（312薪點×139.1＝43,399元）。"),
  ],
  "contract_types": ["臨時約用人員（社工、生活服務員、職管員等）", "約聘（僱）人員", "聘用人員（比照分類職位公務人員俸點）"],
  "political_appointee_clause": {"status": "不明", "content": "未找到要點全文。"},
  "salary_scheme": "臨時約用採固定月薪（公告）；約聘僱採薪點。", "labor_standards_act": "是（臨時人員工作要點／勞基法）",
  "caps_or_limits": "不明。", "core_noncore_rule": "不明。",
  "headcount": [],
  "notable_practices": ["以『臨時約用』混用名稱，社政人力大量以計畫型約用進用，契約以年度為限"],
  "sources": ["https://ms.kmu.edu.tw/attachments/article/1154/徵才公告-臨時約用社工.pdf", "https://yleni.mohw.gov.tw/files/115年約用社會工作員需求計畫_第1次.pdf", "https://socialwork.npust.edu.tw/wp-content/uploads/2025/02/1140218雲林縣政府附件.pdf"],
})

data.append({
  "name": "嘉義縣", "type": "縣",
  "regulations": [
    reg("嘉義縣政府臨時人員工作規則", "99.1.6", "https://www.rootlaw.com.tw/LawList.aspx?lcode=954", "listing", "目錄僅見名稱。"),
    reg("嘉義縣114學年度國中增置學務人力甄選（新聞／簡章）", "114", "https://www.1111.com.tw/news/jobns/162805", "blocked", "16名額、月薪逾36K、適用勞基法。"),
  ],
  "contract_types": ["臨時人員", "計畫型契約進用人員（學務人力等）"],
  "political_appointee_clause": {"status": "不明", "content": "未找到要點。"},
  "salary_scheme": "不明。", "labor_standards_act": "是（臨時人員工作規則）", "caps_or_limits": "不明。", "core_noncore_rule": "不明。",
  "headcount": [],
  "notable_practices": ["規範形式仍為99年之臨時人員工作規則"],
  "sources": ["https://www.rootlaw.com.tw/LawList.aspx?lcode=954", "https://www.1111.com.tw/news/jobns/162805"],
})

data.append({
  "name": "屏東縣", "type": "縣",
  "regulations": [
    reg("屏東縣政府及所屬機關學校約聘僱人員進用管理要點", "104.1.27 訂定；108.12.6、112.5.18 修正",
        "https://www.dtjh.ptc.edu.tw/uploads/1684724277395XCOGhWjZ.pdf", "blocked",
        "依經費來源區分聘用人員、約僱人員、約聘僱職務代理人等；報酬依聘用／約僱報酬標準表；僱用原因消失應解僱。各校『約用』行政助理、專案助理甄選簡章均以本要點及公開甄選作業要點為依據，顯示屏東縣將約用人力納入約聘僱要點管理。"),
    reg("屏東縣政府及所屬機關學校約聘僱人員公開甄選作業要點", "不明", "https://www.kcjh.ptc.edu.tw/uploads/1759216433935O0jyWMtT.pdf", "blocked", "公開甄選程序。"),
    reg("監察院糾正案（屏東縣政府清潔機構進用清潔隊員、駕駛、技工未落實公開甄選）", "不明", "https://cybsbox.cy.gov.tw/CYBSBoxSSL/edoc/download/49897", "blocked", "職缺淪為推薦或任用私人。"),
  ],
  "contract_types": ["聘用人員", "約僱人員", "約聘僱職務代理人", "約用行政助理／專案助理（計畫型）", "清潔隊員駕駛技工"],
  "political_appointee_clause": {"status": "無", "content": "未見條款；監察院曾糾正清潔機構用人未公開甄選。"},
  "salary_scheme": "依聘用／約僱報酬標準表（薪點）。", "labor_standards_act": "不明（約用計畫人員推定適用）",
  "caps_or_limits": "不明。", "core_noncore_rule": "不明。",
  "headcount": [],
  "notable_practices": ["未另訂約用要點，而以約聘僱要點涵蓋計畫型約用人力", "清潔機構用人遭監察院糾正"],
  "sources": ["https://www.dtjh.ptc.edu.tw/uploads/1684724277395XCOGhWjZ.pdf", "https://www.kcjh.ptc.edu.tw/uploads/1759216433935O0jyWMtT.pdf", "https://cybsbox.cy.gov.tw/CYBSBoxSSL/edoc/download/49897", "https://www.rootlaw.com.tw/LawList.aspx?lcode=1082"],
})

data.append({
  "name": "宜蘭縣", "type": "縣",
  "regulations": [
    reg("宜蘭縣政府暨所屬機關臨時人員進用作業注意事項", "86.3.13", "https://www.rootlaw.com.tw/LawList.aspx?lcode=718", "listing", "目錄僅見名稱；另有宜蘭縣政府臨時人員給假規定。"),
    reg("自由時報：宜蘭縣府約聘僱與臨時人員合約到期、傳裁倒數20%", "年份未標（約換屆年）", "https://news.ltn.com.tw/news/Yilan/breakingnews/2728251", "blocked",
        "府內約聘118人、約僱120人、臨時人員409人，府內外合計1,406人；縣府否認砍20%，稱依各局處考績排序調整，續約依考績優劣，產假受保障。"),
  ],
  "contract_types": ["臨時人員", "約聘人員", "約僱人員"],
  "political_appointee_clause": {"status": "無", "content": "無條款；但新聞顯示換屆時以考績排序決定續約，實務上具汰換空間。"},
  "salary_scheme": "不明。", "labor_standards_act": "不明（推定是）", "caps_or_limits": "不明。", "core_noncore_rule": "不明。",
  "headcount": [hc("不明（新聞未標年）", "府內約聘／約僱／臨時人員", "118／120／409；府內外合計1,406", "自由時報 https://news.ltn.com.tw/news/Yilan/breakingnews/2728251")],
  "notable_practices": ["規範形式老舊（86年注意事項）", "換屆期間『考績倒數20%不續約』傳聞"],
  "sources": ["https://www.rootlaw.com.tw/LawList.aspx?lcode=718", "https://news.ltn.com.tw/news/Yilan/breakingnews/2728251"],
})

data.append({
  "name": "花蓮縣", "type": "縣",
  "regulations": [
    reg("花蓮縣政府及所屬機關學校約用人員進用及管理要點（原「約聘僱人員進用及管理要點」112.8.1 府人任字第1120152671號函訂定）", "114.6.13 修訂新增「約用技術人員」",
        "https://www.1111.com.tw/news/163688/amp/", "blocked",
        "涵蓋人員類別、審查小組組成、年度考核作為續聘與調薪依據；114.6.13 新增約用技術人員類別；115年起擴大約用技術人員薪點制，最高薪資由45,903元提高至61,204元（調薪留才）。"),
    reg("花蓮縣政府臨時人員差假勤惰管理要點", "已停止適用", "https://www.rootlaw.com.tw/LawList.aspx?lcode=1123", "listing", "法規彙編標示停止適用。"),
  ],
  "contract_types": ["約用人員", "約用技術人員（114年新增）", "約聘僱人員", "契約進用加置照顧服務人員（學校）"],
  "political_appointee_clause": {"status": "不明", "content": "全文被擋；摘要未見。"},
  "salary_scheme": "薪點制；約用技術人員最高61,204元（115年起）。", "labor_standards_act": "不明（推定是）",
  "caps_or_limits": "設審查小組審查進用。", "core_noncore_rule": "不明。",
  "headcount": [],
  "notable_practices": ["114年新增『約用技術人員』類別並大幅提高薪資上限，為留才型分類之特例", "約聘僱與約用共用一套進用管理要點"],
  "sources": ["https://www.1111.com.tw/news/163688/amp/", "https://xc.hlc.edu.tw/~sfps_www/uploads/tadnews/file/nsn_2196_1.pdf", "https://www.rootlaw.com.tw/LawList.aspx?lcode=1123"],
})

data.append({
  "name": "臺東縣", "type": "縣",
  "regulations": [
    reg("國立臺東專科學校約用人員工作規則（臺東縣政府115.5.6 府社勞字第1150096309號函核備）", "115", "https://personnel.ntc.edu.tw/var/file/7/1007/img/448/814192711.pdf", "blocked",
        "顯示縣府以勞工主管機關身分核備轄內約用人員工作規則；縣府本身之約用要點搜尋未得。"),
    reg("臺東縣政府移工諮詢服務臨時人員甄選公告", "114", "https://cd.nccu.edu.tw/uploads/media/c3f5b9b514c8c14478e07b68726b206e.docx", "blocked", "引用勞動部臨時人員僱用資格條件一覽表。"),
  ],
  "contract_types": ["臨時人員（勞動部補助計畫）", "約用人員（學校）"],
  "political_appointee_clause": {"status": "不明", "content": "未找到要點。"},
  "salary_scheme": "不明。", "labor_standards_act": "不明（推定是）", "caps_or_limits": "不明。", "core_noncore_rule": "不明。",
  "headcount": [],
  "notable_practices": ["縣府通案約用規範未見於公開搜尋，僅見計畫型臨時人員公告"],
  "sources": ["https://personnel.ntc.edu.tw/var/file/7/1007/img/448/814192711.pdf", "https://cd.nccu.edu.tw/uploads/media/c3f5b9b514c8c14478e07b68726b206e.docx", "https://www.rootlaw.com.tw/LawList.aspx?lcode=1093"],
})

data.append({
  "name": "澎湖縣", "type": "縣",
  "regulations": [
    reg("澎湖縣政府及所屬各機關學校臨時人員進用及運用要點", "105.8.10 修正", "https://www.rootlaw.com.tw/LawList.aspx?lcode=1060", "listing", "目錄僅見名稱；未見113年後更名。"),
    reg("澎湖縣政府暨所屬機關、學校專業臨時人員管理要點", "89.8.16", "https://www.rootlaw.com.tw/LawList.aspx?lcode=1056", "listing", "『專業臨時人員』類別。"),
    reg("澎湖縣政府臨時人員工作規則", "105.10.24 修正", "https://www.rootlaw.com.tw/LawList.aspx?lcode=1053", "listing", "勞基法工作規則。"),
    reg("澎湖縣政府及所屬機關學校約聘僱人員公開甄選作業要點", "104.4.16", "https://www.rootlaw.com.tw/LawList.aspx?lcode=1052", "listing", "約聘僱公開甄選。"),
  ],
  "contract_types": ["臨時人員", "專業臨時人員", "約聘僱人員"],
  "political_appointee_clause": {"status": "不明", "content": "未見條文內容。"},
  "salary_scheme": "不明。", "labor_standards_act": "是（訂有臨時人員工作規則）", "caps_or_limits": "不明。", "core_noncore_rule": "不明。",
  "headcount": [],
  "notable_practices": ["另設『專業臨時人員』類別（89年）"],
  "sources": ["https://www.rootlaw.com.tw/LawList.aspx?lcode=1060", "https://www.rootlaw.com.tw/LawList.aspx?lcode=1056", "https://www.rootlaw.com.tw/LawList.aspx?lcode=1053", "https://www.rootlaw.com.tw/LawList.aspx?lcode=1052"],
})

data.append({
  "name": "金門縣", "type": "縣",
  "regulations": [
    reg("金門縣政府暨所屬機關約(聘)僱人員暨臨時人員考核輪調(任)要點", "91.11.18 訂定", "https://www.rootlaw.com.tw/LawList.aspx?lcode=1151", "listing", "臨時人員與約聘僱共同之考核及『輪調（任）』機制。"),
    reg("金門縣政府暨所屬機關學校約僱人員晉級作業要點／聘用人員晉階作業要點", "100.9.27 修正", "https://www.rootlaw.com.tw/LawList.aspx?lcode=1148", "listing", "約聘僱晉級。"),
    reg("金門縣選舉委員會臨時人員甄試公告", "不明", "https://post.cec.gov.tw/old_upload/21/1021/attach/94/pta_24651_6182714_61822.pdf", "blocked", "臨時人員招募樣態。"),
  ],
  "contract_types": ["臨時人員", "約聘僱人員"],
  "political_appointee_clause": {"status": "不明", "content": "未見內容。"},
  "salary_scheme": "不明。", "labor_standards_act": "不明", "caps_or_limits": "不明。", "core_noncore_rule": "不明。",
  "headcount": [],
  "notable_practices": ["臨時人員與約聘僱人員納入同一考核及輪調（任）要點，為少見之『輪調』設計"],
  "sources": ["https://www.rootlaw.com.tw/LawList.aspx?lcode=1151", "https://www.rootlaw.com.tw/LawList.aspx?lcode=1148"],
})

data.append({
  "name": "連江縣", "type": "縣",
  "regulations": [
    reg("連江縣衛生局所屬醫療機構約用人員進用及管理要點", "不明（113學年度公告引用）", "https://www.matsu-news.gov.tw/media/50728569/1130410-1.pdf", "blocked",
        "學校約用護理師依本要點支薪；經費不足時不再續聘。縣府通案約用要點搜尋未得。"),
    reg("連江縣政府文化處辦事員約僱職務代理人甄選", "不明", "https://www.matsucc.gov.tw/wp-content/uploads/2020/08/33-1001094213.docx", "blocked", "筆試60%、口試40%。"),
  ],
  "contract_types": ["約用人員（衛生局醫療機構、學校護理師）", "約僱職務代理人", "環境部補助地方環保機關人力"],
  "political_appointee_clause": {"status": "不明", "content": "未找到要點。"},
  "salary_scheme": "不明。", "labor_standards_act": "不明", "caps_or_limits": "不明。", "core_noncore_rule": "不明。",
  "headcount": [],
  "notable_practices": ["僅見機關別（衛生局）約用要點"],
  "sources": ["https://www.matsu-news.gov.tw/media/50728569/1130410-1.pdf", "https://www.matsucc.gov.tw/wp-content/uploads/2020/08/33-1001094213.docx"],
})

assert len(data) == 22, len(data)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"meta": {"generated": "2026-10-31", "method": "WebSearch 摘要（各地方政府網站被擋，無法抓全文）；中央法規自 law.moj.gov.tw / dgpa.gov.tw 下載", "central_note": CENTRAL_NOTE, "accessible_legend": {"yes": "本環境可直接下載全文", "blocked": "找到網址但被擋，僅憑搜尋摘要", "listing": "僅於法規目錄見名稱與日期"}}, "local_governments": data}, f, ensure_ascii=False, indent=2)
print("wrote", OUT, len(data))

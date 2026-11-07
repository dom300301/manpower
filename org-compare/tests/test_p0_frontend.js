// P0 前端驗收（headless Chromium）
const { chromium } = require('playwright');
const out = [];
const check = (c, m) => out.push((c ? 'PASS ' : 'FAIL ') + m);
(async () => {
  const b = await chromium.launch(); const pg = await b.newPage({ viewport: { width: 1400, height: 900 } });
  const errs = []; pg.on('pageerror', e => errs.push(String(e))); pg.on('console', m => { if (m.type() === 'error' && !/blob:x/.test(m.text())) errs.push(m.text()); }); // blob:x 為測試攔截 CSV 下載所致，非頁面錯誤
  const dialogs = []; pg.on('dialog', async d => { dialogs.push(d.message()); await d.dismiss(); });
  await pg.goto('file://' + (process.env.INDEX_HTML || (__dirname + '/../output/index.html'))); await pg.waitForSelector('#alist .card', { timeout: 30000 });
  // 駐外機構查詢
  await pg.fill('#q', '駐外機構'); await pg.waitForTimeout(300);
  const card = await pg.$eval('#alist .card', e => e.textContent);
  check(/員額 不適用（依審查指示排除）/.test(card) && !/員額 0/.test(card), `駐外機構卡片：${card.replace(/\s+/g, ' ').slice(0, 80)}`);
  await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const kp = await pg.$$eval('.kpi', els => els.map(e => e.textContent.replace(/\s+/g, ' ')));
  check(kp[0].includes('不適用') && !/^0編制/.test(kp[0]), `駐外機構 KPI 員額：${kp[0]}`);
  check(kp.every(k => !/^0/.test(k) || /兼/.test(k)), '駐外機構 KPI 無 0 值');
  // 以駐外機構為目標：±50%
  await pg.click('#toCompare'); await pg.waitForTimeout(400);
  check(/員額 不適用/.test(await pg.textContent('#ctarget')), '目標列顯示員額未取得');
  await pg.click('#nearBtn'); await pg.waitForTimeout(300);
  check(dialogs.length === 1 && (await pg.inputValue('#nmin')) === '' && (await pg.inputValue('#nmax')) === '', `±50% 被擋下並提示（nmin='${await pg.inputValue('#nmin')}', nmax='${await pg.inputValue('#nmax')}'）`);
  // 取消排除後，未知值不進平均／中位
  const chips = await pg.$$('#cExcl .chip'); for (const c of chips) { if ((await c.textContent()).includes('不可比較')) await c.click(); }
  await pg.waitForTimeout(300);
  const stat = await pg.$$eval('#ctable tr.stat td', tds => tds.map(t => t.textContent));
  const rowsAll = await pg.$$eval('#ctable tbody tr', trs => trs.map(t => t.children[0].textContent));
  check(rowsAll.some(r => r.includes('駐外機構')) && /n＝/.test(stat[0]), `取消排除後駐外機構在表內；統計列顯示樣本數：${stat[0]}`);
  const hcIdx = await pg.$$eval('#ctable thead th', ths => ths.findIndex(t => t.textContent.startsWith('員額合計')));
  const medianCell = stat[hcIdx]; const nCount = Number((stat[0].match(/n＝(\d+)/) || [])[1]);
  const numericRows = await pg.$$eval('#ctable tbody tr:not(.stat)', (trs, i) => trs.map(t => t.children[i].textContent).filter(v => /^\d+$/.test(v)).length, hcIdx);
  check(nCount === numericRows && medianCell !== '0', `中位數有效樣本 n=${nCount} 等於數值列數 ${numericRows}，中位數=${medianCell}`);
  // 匯出 CSV 內容：駐外機構員額空白
  const csvRows = await pg.evaluate(() => { const a = document.createElement('a'); let s = ''; const orig = URL.createObjectURL; URL.createObjectURL = (blob) => { blob.text().then(t => window.__csv = t); return 'blob:x'; }; document.getElementById('csvBtn').click(); URL.createObjectURL = orig; return new Promise(r => setTimeout(() => r(window.__csv), 300)); });
  const fin = (csvRows || '').split(/\r?\n/).find(l => l.startsWith('"駐外機構"'));
  check(fin && fin.split(',')[1 + (await pg.$$eval('#colPick label.on', ls => ls.map(l => l.textContent))).indexOf('員額合計') + 0] !== '"0"' && !/,"0",/.test(fin.slice(0, 40)), `CSV 駐外機構列：${(fin || '').slice(0, 60)}`);
  // 恢復預設排除後：農業部預設群組不含教育部
  for (const c of await pg.$$('#cExcl .chip')) { if ((await c.textContent()).includes('不可比較')) await c.click(); }
  await pg.fill('#cq', '農業部'); await pg.press('#cq', 'Enter'); await pg.waitForTimeout(400);
  const grp = await pg.$$eval('#ctable tbody tr:not(.stat)', trs => trs.map(t => t.children[0].textContent));
  check(grp.some(g => g.startsWith('教育部')) && grp.some(g => g.startsWith('財政部')), `農業部預設群組（${grp.length} 列）含教育部（Codex 已釐清）、財政部（已人工補登）`);
  // B1 回歸：範圍篩選 null 安全（取消排除後；以國家發展委員會為目標，工程會為 null 機關）
  await pg.fill('#cq', '國家發展委員會'); await pg.press('#cq', 'Enter'); await pg.waitForTimeout(400);
  for (const c of await pg.$$('#cExcl .chip')) { if ((await c.textContent()).includes('不可比較')) await c.click(); }
  await pg.waitForTimeout(200);
  const names = async () => pg.$$eval('#ctable tbody tr:not(.stat)', trs => trs.map(t => t.children[0].textContent.replace(/\s*不可比較$/, '')));
  const noLimit = await names();
  check(noLimit.includes('行政院公共工程委員會'), `B1-4 無上下限、取消排除：null 機關可留在列表（工程會在列，顯示未取得）`);
  const statN = Number(((await pg.$eval('#ctable tr.stat td', t => t.textContent)).match(/n＝(\d+)/) || [])[1]);
  const numericN = await pg.$$eval('#ctable tbody tr:not(.stat):not(.target)', trs => trs.filter(t => /^\d+$/.test(t.children[3].textContent)).length);  // 群組統計不含目標列
  check(statN === numericN, `B1-4 統計列 n＝${statN} 等於數值列數 ${numericN}（不含 null）`);
  await pg.fill('#nmax', '100'); await pg.waitForTimeout(300); const upper = await names();
  check(!upper.includes('行政院公共工程委員會') && upper.every(n => n !== '行政院公共工程委員會'), `B1-1 上限 100、下限空：null 機關不在清單（${upper.length} 列）`);
  await pg.fill('#nmin', '0'); await pg.waitForTimeout(300); const both = await names();
  check(!both.includes('行政院公共工程委員會'), `B1-2 範圍 0–100：null 機關不在清單（${both.length} 列）`);
  await pg.fill('#nmin', ''); await pg.fill('#nmax', ''); await pg.waitForTimeout(200);
  dialogs.length = 0; await pg.fill('#cq', '行政院公共工程委員會'); await pg.press('#cq', 'Enter'); await pg.waitForTimeout(300); await pg.click('#nearBtn'); await pg.waitForTimeout(300);
  check(dialogs.length === 1 && (await pg.inputValue('#nmin')) === '' && (await pg.inputValue('#nmax')) === '', 'B1-3 工程會為目標按 ±50% 仍被阻擋，不形成 [0,0]');
  for (const c of await pg.$$('#cExcl .chip')) { if ((await c.textContent()).includes('不可比較')) await c.click(); }
  await pg.waitForTimeout(200);
  // 狀態頁
  await pg.click('.tabs button[data-tab=info]'); await pg.waitForTimeout(300);
  const flaggedTxt = await pg.textContent('#flagged');
  const flagRows = await pg.$$eval('#flagged tbody tr', trs => trs.map(t => t.children[0].textContent));
  const expected = JSON.parse(require('fs').readFileSync(process.env.AGENCIES_JSON || (__dirname + '/../output/agencies_snapshot.json'), 'utf8')).agencies.filter(a => !a.可比較).length;
  check(new RegExp(`共 ${expected} 個`).test(flaggedTxt) && flagRows.length === expected && !flagRows.includes('教育部') && !flagRows.includes('衛生福利部臺中醫院') && !flagRows.includes('衛生福利部恆春旅遊醫院'), `狀態頁不可比較 ${flagRows.length} 個（與資料推導 ${expected} 一致），不含教育部（Codex 已釐清）、臺中醫院（已對源）、恆春（已校正）`);
  // 藥試所明細與臺中醫院顯示
  await pg.click('.tabs button[data-tab=search]'); await pg.fill('#q', '農業藥物試驗所'); await pg.waitForTimeout(300); await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const det = await pg.$eval('#adetail', e => e.textContent);
  const noteCells = await pg.$$eval('#adetail tbody tr', trs => trs.map(t => t.children[7].textContent));
  const fixBadges = await pg.$$eval('#adetail .badge.ok', bs => bs.filter(b => b.textContent === '人工修正').length);
  check(/表列合計 79/.test(det) && fixBadges === 6 && !noteCells.some(n => /卷/.test(n)), `藥試所詳情：表列合計 79、人工修正標示 ${fixBadges} 列、備註欄無頁眉文字`);
  await pg.fill('#q', '臺中醫院'); await pg.waitForTimeout(300); await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const det2 = await pg.$eval('#adetail', e => e.textContent);
  check(/已對源（官方附件 FileId 0000427371/.test(det2) && /控制列/.test(det2) && /217/.test(det2) && !/434/.test(det2), '臺中醫院詳情：已對源（官方附件 0000427371）、控制列說明、217 而非 434');
  // 無編制表機關：依據「無」須明示；「有」須給條號與未加總說明
  await pg.fill('#q', '駐外機構'); await pg.waitForTimeout(300);
  const cardsZ = await pg.$$('#alist .card'); for (const c of cardsZ) { if ((await c.textContent()).startsWith('駐外機構') && !(await c.textContent()).includes('監獄')) { await c.click(); break; } } await pg.waitForTimeout(300);
  const det3 = await pg.$eval('#adetail', e => e.textContent);
  check(/法定員額依據：尚未完成結構化（待確認）（/.test(det3) && /尚未完成其員額規定之結構化/.test(det3) && !/法定員額依據：無/.test(det3) && !/，條文）/.test(det3) && /不適用（依審查指示排除）/.test(det3) && /依審查指示排除/.test(det3), '駐外機構詳情：主文案「尚未完成結構化（待確認）」，括號內有說明與法規連結，無粗體「無」、無「，條文）」');
  await pg.fill('#q', '玉里分院'); await pg.waitForTimeout(300); await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const det5 = await pg.$eval('#adetail', e => e.textContent);
  check(/465/.test(det5) && /人工修正/.test(det5) && !/待審（員額不完整）/.test(det5), '玉里分院：改列後顯示 465 與人工修正標記，不再顯示待審');
  // 法定員額（條文區間）：工程會
  await pg.click('.tabs button[data-tab=search]'); await pg.fill('#q', '行政院公共工程委員會'); await pg.waitForTimeout(300); await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const detS = await pg.$eval('#adetail', e => e.textContent);
  check(/149–199（法定條文區間）/.test(detS) && /專任 149–199/.test(detS) && /聘用約僱 35–40/.test(detS) && /組織法規明定聘用／約僱人數/.test(detS) && /第14條/.test(detS), '工程會詳情：法定條文區間 149–199、聘用專業人員 35–40 另列、第14條原句');
  await pg.fill('#q', '臺灣警察專科學校'); await pg.waitForTimeout(300); await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const detW = await pg.$eval('#adetail', e => e.textContent);
  check(/警備隊 44–60（獨立參考，不計入）/.test(detW) && /警察官/.test(detW), '警專詳情：警備隊 44–60 獨立參考、列標警察官／文官類別');
  await pg.fill('#q', '數位發展部'); await pg.waitForTimeout(300); const cD = await pg.$$('#alist .card'); for (const c of cD) { if ((await c.textContent()).startsWith('數位發展部2級')) { await c.click(); break; } } await pg.waitForTimeout(300);
  const detD = await pg.$eval('#adetail', e => e.textContent);
  check(/聘用／約僱人數（特例）/.test(detD) && /不得超過一百人/.test(detD), '數位發展部詳情：組織法第7條聘用上限 100 列為特例');
  // 三項修正：軍事／國防排除、法規來源 anchor、臺中 PDF 按鈕
  await pg.click('.tabs button[data-tab=search]'); await pg.fill('#q', '臺中醫院'); await pg.waitForTimeout(300); await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const lawA = await pg.$$eval('#adetail .muted a', as => as.map(a => [a.getAttribute('href'), a.textContent]));
  check(lawA.every(([h]) => h && !h.includes('；') && (h.match(/https?:\/\//g) || []).length === 1), `臺中醫院詳情每個 anchor 僅一個 URL（${lawA.length} 個）`);
  check(lawA.filter(([h, t]) => /pcode=L0000053|pcode=D0000155/.test(h)).length === 2, '臺中醫院：兩部共用準則各自獨立 href');
  const pdfA = lawA.find(([h, t]) => t === '編制表 PDF'); const detT = await pg.$eval('#adetail', e => e.textContent);
  check(pdfA && /FileId=0000427371$/.test(pdfA[0]) && /115 年 10 月 30 日/.test(detT) && /0000368769/.test(detT) && !lawA.some(([h]) => /0000368769/.test(h)), '臺中醫院：PDF 按鈕指向新附件 0000427371、文字含 115-10-30；舊 0000368769 僅文字、無按鈕');
  await pg.fill('#q', '國防部'); await pg.waitForTimeout(300); const cN = await pg.$$('#alist .card'); for (const c of cN) { if ((await c.textContent()).startsWith('國防部2級')) { await c.click(); break; } } await pg.waitForTimeout(300);
  const lawN = await pg.$$eval('#adetail .muted a', as => as.map(a => a.getAttribute('href'))); check(lawN.filter(h => /pcode=F0000001$/.test(h)).length === 1, '國防部（單法）：組織法 anchor 一個、URL 單一');
  await pg.fill('#q', '行政院公共工程委員會'); await pg.waitForTimeout(300); await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const lawG = await pg.$$eval('#adetail .muted a', as => as.map(a => a.getAttribute('href'))); check(lawG.every(h => !h.includes('；')) && lawG.some(h => /pcode=A0010037$/.test(h)), '工程會（條文解析）：法規 anchor URL 單一');
  await pg.click('#toCompare'); await pg.waitForTimeout(300); await pg.fill('#cq', '農業部'); await pg.press('#cq', 'Enter'); await pg.waitForTimeout(400);
  const milChip = await pg.$$eval('#cExcl .chip', cs => cs.filter(c => c.textContent.includes('軍事／國防')).map(c => c.className));
  const grpOff = await pg.$$eval('#ctable tbody tr:not(.stat)', trs => trs.map(t => t.children[0].textContent));
  check(milChip.length === 1 && !/\bon\b/.test(milChip[0]) && grpOff.some(g => g.startsWith('國防部')), `農業部群組（軍事／國防排除預設關閉，比較定義未改）：含國防部本部（${grpOff.length} 列）`);
  for (const c of await pg.$$('#cExcl .chip')) { if ((await c.textContent()).includes('軍事／國防')) await c.click(); } await pg.waitForTimeout(300);
  const grpOn = await pg.$$eval('#ctable tbody tr:not(.stat)', trs => trs.map(t => t.children[0].textContent));
  check(!grpOn.some(g => g.startsWith('國防部')) && grpOn.length === grpOff.length - 1, '開啟軍事／國防排除後國防部本部移出群組（依部會欄，僅 −1）');
  await pg.fill('#cq', '國軍退除役官兵輔導委員會臺北市榮民服務處'); await pg.press('#cq', 'Enter'); await pg.waitForTimeout(400);
  const grpV = await pg.$$eval('#ctable tbody tr:not(.stat)', trs => trs.map(t => t.children[0].textContent));
  check(grpV.some(g => g.includes('新北市榮民服務處')) && grpV.some(g => g.includes('高雄市榮民服務處')), `退輔會榮民服務處群組在軍事／國防排除開啟下仍完整（${grpV.length} 列，退輔會不因名稱含「軍」被排除）`);
  for (const c of await pg.$$('#cExcl .chip')) { if ((await c.textContent()).includes('軍事／國防')) await c.click(); } await pg.waitForTimeout(200);
  await pg.click('.tabs button[data-tab=search]'); await pg.waitForTimeout(200);
  // 更新作業面板（只提示與複製指令，不執行更新）
  await pg.click('.tabs button[data-tab=info]'); await pg.waitForTimeout(300);
  const updTxt = await pg.$eval('#updPrompt', e => e.value); const updBtn = await pg.$('#copyUpd'); const verTxt = await pg.textContent('#version');
  check(updBtn && /update_dryrun\.py/.test(updTxt) && /不合併、不部署/.test(updTxt) && /manifest：/.test(verTxt) && /dryrun\.yml/.test(await pg.$eval('#version', e => e.innerHTML)), '狀態頁「資料更新作業」面板：顯示 manifest 摘要、可複製標準指令、連到 dry-run 工作流程');
  await pg.click('.tabs button[data-tab=search]'); await pg.waitForTimeout(200);
  const bi = await pg.textContent('#buildinfo'); check(/來源提交 [0-9a-f]{7}/.test(bi), `建檔資訊含來源提交：${bi}`);
  // P1：行政院區間
  await pg.fill('#q', '行政院'); await pg.waitForTimeout(300); const c0 = await pg.$$('#alist .card'); for (const c of c0) { if ((await c.textContent()).startsWith('行政院1級')) { await c.click(); break; } } await pg.waitForTimeout(300);
  const detE = await pg.$eval('#adetail', e => e.textContent);
  check(/635–637（區間）/.test(detE) && /不以下限充當定額/.test(detE), '行政院詳情：員額合計以區間 635–637 呈現');
  await pg.click('#toCompare'); await pg.waitForTimeout(400);
  dialogs.length = 0; await pg.click('#nearBtn'); await pg.waitForTimeout(300);
  check(dialogs.length === 1 && /區間/.test(dialogs[0]), `區間目標未勾選取下限時 ±50% 阻擋：${dialogs[0]}`);
  await pg.check('#rangeLower'); await pg.waitForTimeout(300);
  const st2 = await pg.$eval('#ctable tr.stat td', t => t.textContent); check(/口徑：區間取下限/.test(st2), `勾選後統計列標示口徑：${st2}`);
  await pg.uncheck('#rangeLower'); await pg.waitForTimeout(200);
  // P1：括號語意顯示
  await pg.click('.tabs button[data-tab=search]'); await pg.fill('#q', '海洋委員會海巡署'); await pg.waitForTimeout(300); const c1 = await pg.$$('#alist .card'); for (const c of c1) { if ((await c.textContent()).startsWith('海洋委員會海巡署3級')) { await c.click(); break; } } await pg.waitForTimeout(300);
  const detH = await pg.$eval('#adetail tbody tr', e => e.textContent);
  check(/兼任/.test(detH) && /1/.test(detH), `海巡署署長列顯示括號語意兼任：${detH.slice(0, 60)}`);
  await pg.fill('#q', '公共工程委員會'); await pg.waitForTimeout(300); await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const det4 = await pg.$eval('#adetail', e => e.textContent);
  check(/法定員額依據：行政院公共工程委員會組織條例第8條/.test(det4) && /未加總/.test(det4), '工程會詳情：法定員額依據條號與「未加總」說明');
  check(errs.length === 0, `無 console/page 錯誤（${errs.length}）${errs.slice(0, 2).join(' | ')}`);
  await b.close(); console.log(out.join('\n')); console.log(`\n結果：PASS ${out.filter(o => o.startsWith('PASS')).length}、FAIL ${out.filter(o => o.startsWith('FAIL')).length}`);
  process.exit(out.some(o => o.startsWith('FAIL')) ? 1 : 0);
})();

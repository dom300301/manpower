// P0 前端驗收（headless Chromium）
const { chromium } = require('playwright');
const out = [];
const check = (c, m) => out.push((c ? 'PASS ' : 'FAIL ') + m);
(async () => {
  const b = await chromium.launch(); const pg = await b.newPage({ viewport: { width: 1400, height: 900 } });
  const errs = []; pg.on('pageerror', e => errs.push(String(e))); pg.on('console', m => { if (m.type() === 'error' && !/blob:x/.test(m.text())) errs.push(m.text()); }); // blob:x 為測試攔截 CSV 下載所致，非頁面錯誤
  const dialogs = []; pg.on('dialog', async d => { dialogs.push(d.message()); await d.dismiss(); });
  await pg.goto('file:///home/user/manpower/org-compare/output/index.html'); await pg.waitForSelector('#alist .card', { timeout: 30000 });
  // 財政部查詢
  await pg.fill('#q', '財政部'); await pg.waitForTimeout(300);
  const card = await pg.$eval('#alist .card', e => e.textContent);
  check(/員額 未取得（需人工輸入）/.test(card) && !/員額 0/.test(card), `財政部卡片：${card.replace(/\s+/g, ' ').slice(0, 80)}`);
  await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const kp = await pg.$$eval('.kpi', els => els.map(e => e.textContent.replace(/\s+/g, ' ')));
  check(kp[0].includes('未取得') && !/^0編制/.test(kp[0]), `財政部 KPI 員額：${kp[0]}`);
  check(kp.every(k => !/^0/.test(k) || /兼/.test(k)), '財政部 KPI 無 0 值');
  // 以財政部為目標：±50%
  await pg.click('#toCompare'); await pg.waitForTimeout(400);
  check(/員額 未取得/.test(await pg.textContent('#ctarget')), '目標列顯示員額未取得');
  await pg.click('#nearBtn'); await pg.waitForTimeout(300);
  check(dialogs.length === 1 && (await pg.inputValue('#nmin')) === '' && (await pg.inputValue('#nmax')) === '', `±50% 被擋下並提示（nmin='${await pg.inputValue('#nmin')}', nmax='${await pg.inputValue('#nmax')}'）`);
  // 取消排除後，未知值不進平均／中位
  const chips = await pg.$$('#cExcl .chip'); for (const c of chips) { if ((await c.textContent()).includes('不可比較')) await c.click(); }
  await pg.waitForTimeout(300);
  const stat = await pg.$$eval('#ctable tr.stat td', tds => tds.map(t => t.textContent));
  const rowsAll = await pg.$$eval('#ctable tbody tr', trs => trs.map(t => t.children[0].textContent));
  check(rowsAll.some(r => r.includes('財政部')) && /n＝/.test(stat[0]), `取消排除後財政部在表內；統計列顯示樣本數：${stat[0]}`);
  const hcIdx = await pg.$$eval('#ctable thead th', ths => ths.findIndex(t => t.textContent.startsWith('員額合計')));
  const medianCell = stat[hcIdx]; const nCount = Number((stat[0].match(/n＝(\d+)/) || [])[1]);
  const numericRows = await pg.$$eval('#ctable tbody tr:not(.stat)', (trs, i) => trs.map(t => t.children[i].textContent).filter(v => /^\d+$/.test(v)).length, hcIdx);
  check(nCount === numericRows && medianCell !== '0', `中位數有效樣本 n=${nCount} 等於數值列數 ${numericRows}，中位數=${medianCell}`);
  // 匯出 CSV 內容：財政部員額空白
  const csvRows = await pg.evaluate(() => { const a = document.createElement('a'); let s = ''; const orig = URL.createObjectURL; URL.createObjectURL = (blob) => { blob.text().then(t => window.__csv = t); return 'blob:x'; }; document.getElementById('csvBtn').click(); URL.createObjectURL = orig; return new Promise(r => setTimeout(() => r(window.__csv), 300)); });
  const fin = (csvRows || '').split(/\r?\n/).find(l => l.startsWith('"財政部"'));
  check(fin && fin.split(',')[1 + (await pg.$$eval('#colPick label.on', ls => ls.map(l => l.textContent))).indexOf('員額合計') + 0] !== '"0"' && !/,"0",/.test(fin.slice(0, 40)), `CSV 財政部列：${(fin || '').slice(0, 60)}`);
  // 恢復預設排除後：農業部預設群組不含教育部
  for (const c of await pg.$$('#cExcl .chip')) { if ((await c.textContent()).includes('不可比較')) await c.click(); }
  await pg.fill('#cq', '農業部'); await pg.press('#cq', 'Enter'); await pg.waitForTimeout(400);
  const grp = await pg.$$eval('#ctable tbody tr:not(.stat)', trs => trs.map(t => t.children[0].textContent));
  check(!grp.some(g => g.startsWith('教育部')) && !grp.some(g => g.startsWith('財政部')), `農業部預設群組（${grp.length} 列）不含教育部、財政部`);
  // 狀態頁
  await pg.click('.tabs button[data-tab=info]'); await pg.waitForTimeout(300);
  const flaggedTxt = await pg.textContent('#flagged');
  const flagRows = await pg.$$eval('#flagged tbody tr', trs => trs.map(t => t.children[0].textContent));
  check(/共 41 個/.test(flaggedTxt) && flagRows.includes('教育部') && flagRows.includes('衛生福利部臺中醫院') && !flagRows.includes('衛生福利部恆春旅遊醫院'), `狀態頁不可比較 ${flagRows.length} 個，含教育部、臺中醫院，不含恆春`);
  // 藥試所明細與臺中醫院顯示
  await pg.click('.tabs button[data-tab=search]'); await pg.fill('#q', '農業藥物試驗所'); await pg.waitForTimeout(300); await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const det = await pg.$eval('#adetail', e => e.textContent);
  const noteCells = await pg.$$eval('#adetail tbody tr', trs => trs.map(t => t.children[7].textContent));
  const fixBadges = await pg.$$eval('#adetail .badge.ok', bs => bs.filter(b => b.textContent === '人工修正').length);
  check(/表列合計 79/.test(det) && fixBadges === 6 && !noteCells.some(n => /卷/.test(n)), `藥試所詳情：表列合計 79、人工修正標示 ${fixBadges} 列、備註欄無頁眉文字`);
  await pg.fill('#q', '臺中醫院'); await pg.waitForTimeout(300); await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const det2 = await pg.$eval('#adetail', e => e.textContent);
  check(/官方合計待核/.test(det2) && /控制列/.test(det2) && /217/.test(det2) && !/434/.test(det2), '臺中醫院詳情：官方合計待核、控制列說明、217 而非 434');
  check(errs.length === 0, `無 console/page 錯誤（${errs.length}）${errs.slice(0, 2).join(' | ')}`);
  await b.close(); console.log(out.join('\n')); console.log(`\n結果：PASS ${out.filter(o => o.startsWith('PASS')).length}、FAIL ${out.filter(o => o.startsWith('FAIL')).length}`);
  process.exit(out.some(o => o.startsWith('FAIL')) ? 1 : 0);
})();

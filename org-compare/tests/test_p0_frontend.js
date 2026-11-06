// P0 前端驗收（headless Chromium）
const { chromium } = require('playwright');
const out = [];
const check = (c, m) => out.push((c ? 'PASS ' : 'FAIL ') + m);
(async () => {
  const b = await chromium.launch(); const pg = await b.newPage({ viewport: { width: 1400, height: 900 } });
  const errs = []; pg.on('pageerror', e => errs.push(String(e))); pg.on('console', m => { if (m.type() === 'error' && !/blob:x/.test(m.text())) errs.push(m.text()); }); // blob:x 為測試攔截 CSV 下載所致，非頁面錯誤
  const dialogs = []; pg.on('dialog', async d => { dialogs.push(d.message()); await d.dismiss(); });
  await pg.goto('file://' + (process.env.INDEX_HTML || (__dirname + '/../output/index.html'))); await pg.waitForSelector('#alist .card', { timeout: 30000 });
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
  // B1 回歸：範圍篩選 null 安全（取消排除後）
  for (const c of await pg.$$('#cExcl .chip')) { if ((await c.textContent()).includes('不可比較')) await c.click(); }
  await pg.waitForTimeout(200);
  const names = async () => pg.$$eval('#ctable tbody tr:not(.stat)', trs => trs.map(t => t.children[0].textContent.replace(/\s*不可比較$/, '')));
  const noLimit = await names();
  check(noLimit.includes('財政部'), `B1-4 無上下限、取消排除：null 機關可留在列表（財政部在列，顯示未取得）`);
  const statN = Number(((await pg.$eval('#ctable tr.stat td', t => t.textContent)).match(/n＝(\d+)/) || [])[1]);
  const numericN = await pg.$$eval('#ctable tbody tr:not(.stat):not(.target)', trs => trs.filter(t => /^\d+$/.test(t.children[3].textContent)).length);  // 群組統計不含目標列
  check(statN === numericN, `B1-4 統計列 n＝${statN} 等於數值列數 ${numericN}（不含 null）`);
  await pg.fill('#nmax', '100'); await pg.waitForTimeout(300); const upper = await names();
  check(!upper.includes('財政部') && upper.every(n => n !== '財政部'), `B1-1 上限 100、下限空：null 機關不在清單（${upper.length} 列）`);
  await pg.fill('#nmin', '0'); await pg.waitForTimeout(300); const both = await names();
  check(!both.includes('財政部'), `B1-2 範圍 0–100：null 機關不在清單（${both.length} 列）`);
  await pg.fill('#nmin', ''); await pg.fill('#nmax', ''); await pg.waitForTimeout(200);
  dialogs.length = 0; await pg.fill('#cq', '財政部'); await pg.press('#cq', 'Enter'); await pg.waitForTimeout(300); await pg.click('#nearBtn'); await pg.waitForTimeout(300);
  check(dialogs.length === 1 && (await pg.inputValue('#nmin')) === '' && (await pg.inputValue('#nmax')) === '', 'B1-3 財政部為目標按 ±50% 仍被阻擋，不形成 [0,0]');
  for (const c of await pg.$$('#cExcl .chip')) { if ((await c.textContent()).includes('不可比較')) await c.click(); }
  await pg.waitForTimeout(200);
  // 狀態頁
  await pg.click('.tabs button[data-tab=info]'); await pg.waitForTimeout(300);
  const flaggedTxt = await pg.textContent('#flagged');
  const flagRows = await pg.$$eval('#flagged tbody tr', trs => trs.map(t => t.children[0].textContent));
  const expected = JSON.parse(require('fs').readFileSync(process.env.AGENCIES_JSON || (__dirname + '/../output/agencies_snapshot.json'), 'utf8')).agencies.filter(a => !a.可比較).length;
  check(new RegExp(`共 ${expected} 個`).test(flaggedTxt) && flagRows.length === expected && flagRows.includes('教育部') && flagRows.includes('衛生福利部臺中醫院') && !flagRows.includes('衛生福利部恆春旅遊醫院'), `狀態頁不可比較 ${flagRows.length} 個（與資料推導 ${expected} 一致），含教育部、臺中醫院，不含恆春（已校正）`);
  // 藥試所明細與臺中醫院顯示
  await pg.click('.tabs button[data-tab=search]'); await pg.fill('#q', '農業藥物試驗所'); await pg.waitForTimeout(300); await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const det = await pg.$eval('#adetail', e => e.textContent);
  const noteCells = await pg.$$eval('#adetail tbody tr', trs => trs.map(t => t.children[7].textContent));
  const fixBadges = await pg.$$eval('#adetail .badge.ok', bs => bs.filter(b => b.textContent === '人工修正').length);
  check(/表列合計 79/.test(det) && fixBadges === 6 && !noteCells.some(n => /卷/.test(n)), `藥試所詳情：表列合計 79、人工修正標示 ${fixBadges} 列、備註欄無頁眉文字`);
  await pg.fill('#q', '臺中醫院'); await pg.waitForTimeout(300); await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const det2 = await pg.$eval('#adetail', e => e.textContent);
  check(/官方合計待核/.test(det2) && /控制列/.test(det2) && /217/.test(det2) && !/434/.test(det2), '臺中醫院詳情：官方合計待核、控制列說明、217 而非 434');
  // 無編制表機關：依據「無」須明示；「有」須給條號與未加總說明
  await pg.fill('#q', '法務部矯正署'); await pg.waitForTimeout(300);
  const cardsZ = await pg.$$('#alist .card'); for (const c of cardsZ) { if ((await c.textContent()).startsWith('法務部矯正署') && !(await c.textContent()).includes('監獄')) { await c.click(); break; } } await pg.waitForTimeout(300);
  const det3 = await pg.$eval('#adetail', e => e.textContent);
  check(/法定員額依據：尚未完成結構化（待確認）（/.test(det3) && /尚未完成員額結構化/.test(det3) && !/法定員額依據：無/.test(det3) && !/，條文）/.test(det3) && /未取得（無編制表）/.test(det3), '矯正署詳情：主文案「尚未完成結構化（待確認）」，括號內有說明與法規連結，無粗體「無」、無「，條文）」');
  await pg.fill('#q', '玉里分院'); await pg.waitForTimeout(300); await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const det5 = await pg.$eval('#adetail', e => e.textContent);
  check(/待審（員額不完整）/.test(det5) && /已知列小計 462/.test(det5) && /不是完整總額/.test(det5) && !/^462/.test(det5), '玉里分院：顯示待審（員額不完整）、已知列小計 462 並標示不是完整總額');
  const bi = await pg.textContent('#buildinfo'); check(/來源提交 [0-9a-f]{7}/.test(bi), `建檔資訊含來源提交：${bi}`);
  await pg.fill('#q', '公共工程委員會'); await pg.waitForTimeout(300); await pg.click('#alist .card'); await pg.waitForTimeout(300);
  const det4 = await pg.$eval('#adetail', e => e.textContent);
  check(/法定員額依據：行政院公共工程委員會組織條例第8條/.test(det4) && /未加總/.test(det4), '工程會詳情：法定員額依據條號與「未加總」說明');
  check(errs.length === 0, `無 console/page 錯誤（${errs.length}）${errs.slice(0, 2).join(' | ')}`);
  await b.close(); console.log(out.join('\n')); console.log(`\n結果：PASS ${out.filter(o => o.startsWith('PASS')).length}、FAIL ${out.filter(o => o.startsWith('FAIL')).length}`);
  process.exit(out.some(o => o.startsWith('FAIL')) ? 1 : 0);
})();

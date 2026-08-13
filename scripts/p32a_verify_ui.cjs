const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

  let submitRequests = 0;
  page.on('request', (req) => {
    const url = req.url();
    if (url.includes('/submit') && req.method() === 'POST') {
      submitRequests += 1;
      console.error('UNEXPECTED SUBMIT REQUEST:', url);
    }
  });

  await page.goto('http://192.168.31.218:12823/target-design', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  const cards = await page.locator('text=/PepMLM|EvoBind2|DiffPepBuilder|PepFlow|PepHAR|PPFlow|PepGLAD|RFpeptides|PepPrCLIP/i').count();
  console.log('Model mentions found:', cards);

  const lockedCount = await page.locator('text=/Execution locked/i').count();
  console.log('Execution locked labels:', lockedCount);

  const notValidated = await page.locator('text=/NOT_EXPERIMENTALLY_VALIDATED/i').count();
  console.log('NOT_EXPERIMENTALLY_VALIDATED labels:', notValidated);

  const realRunLocked = await page.locator('button:has-text("Real Run Locked")').count();
  console.log('Real Run Locked buttons in detail drawer:', realRunLocked);

  // Open first model detail
  const detailButtons = await page.locator('button:has-text("Details")').all();
  if (detailButtons.length > 0) {
    await detailButtons[0].click();
    await page.waitForTimeout(500);
    const drawerLocked = await page.locator('button:disabled:has-text("Real Run Locked")').count();
    console.log('Detail drawer Real Run Locked disabled:', drawerLocked);
  }

  console.log('Unexpected submit requests:', submitRequests);
  await browser.close();
})();

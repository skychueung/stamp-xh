const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto('http://192.168.31.218:12823/target-design', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: '/home/xh/kxc/stampup/reports/p32a_screenshots/target_design_desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: '/home/xh/kxc/stampup/reports/p32a_screenshots/target_design_mobile.png', fullPage: true });
  await browser.close();
  console.log('Screenshots saved');
})();

// @ts-check
/**
 * STAMP P33P — PPFlow evidence / Real-Run gate / controlled download acceptance.
 *
 * Standalone Node ESM script. Uses the EXISTING `playwright` package directly
 * (NOT @playwright/test, which is not installed). Does not touch package.json.
 *
 * Run (apply phase, existing deps only, no npm install):
 *   P33P_E2E_BASE_URL=http://127.0.0.1:12823 node e2e/p33p-ppflow-evidence-accept.mjs
 *
 * Every API response is mocked with page.route(); the real backend is never hit.
 * PPFlow stays real_run_enabled=false / execution_locked=true in the success
 * fixture; the unlocked fixture is a synthetic governance probe only.
 * P33P does NOT implement submit — the Real Run button has no onClick handler.
 *
 * UI model (matches the live app):
 *   - ModelReadinessOverview is always rendered on /target-design.
 *   - Each model card has a "Details" button that opens a modal detail panel
 *     (div.fixed.inset-0.z-50). All detail assertions are scoped to that modal
 *     because the page also contains other "Real Run" buttons (CenterPage/P33L).
 *   - The model fixtures are COMPLETE ModelRegistryEntry objects (mirroring the
 *     live backend shape) so the detail panel renders without runtime errors
 *     (e.g. selectedModel.output_artifact_types.length must not throw).
 *
 * Coverage:
 *   - locked/unlocked API fixture -> Real Run button disabled/enabled + label
 *   - evidence load success -> stats + SHA + download buttons + NOT_EXPERIMENTALLY_VALIDATED
 *   - evidence load failure -> role="alert" error with HTTP status + detail
 *   - download success (200) -> exactly one download, no error alert
 *   - download 403 / 404 / 409 -> ZERO downloads, role="alert" error (no file saved)
 *   - unknown evidence id filtered out of rendered download buttons
 *   - state cleanup on close-detail and on model switch
 *   - zero submit / real-run / gate / checkpoint / probe / dry-run requests
 */

import { chromium } from 'playwright';

const BASE = process.env.P33P_E2E_BASE_URL || 'http://127.0.0.1:12823';

const MODELS_URL = '**/api/v1/models';
const MODEL_REGISTRY_URL = '**/api/v1/model-registry';
const EVIDENCE_URL = '**/api/v1/models/ppflow/evidence';
const downloadUrl = (id) => `**/api/v1/models/ppflow/evidence/${id}/download`;

const FORBIDDEN_PATH_PATTERNS = [
  /\/api\/v1\/models\/[^/]+\/submit/,
  /\/api\/v1\/models\/[^/]+\/dry-run/,
  /\/api\/v1\/models\/[^/]+\/probe/,
  /\/api\/v1\/models\/[^/]+\/real-run/,
  /\/api\/v1\/.*gate/,
  /\/api\/v1\/.*checkpoint/,
];

// Complete ModelRegistryEntry mirroring the live backend ppflow shape.
// Locked = real ppflow (real_run_enabled=false, execution_locked=true,
// supports_real_run=false) => canRealRun=false => "Real Run Locked".
const ppflowBase = {
  model_id: 'ppflow',
  display_name: 'PPFlow',
  category: 'flow_based_design',
  status: 'controlled_smoke_verified',
  status_reason: 'p33o_ppflow_path_repair_verified',
  description: 'PPFlow (controlled_smoke_verified): torsional flow-matching peptide design. NOT_EXPERIMENTALLY_VALIDATED.',
  supports_probe: true,
  supports_dry_run: true,
  supports_real_run: false,
  supports_structure_output: false,
  supports_sequence_output: true,
  supports_ranking: false,
  output_artifact_types: [],
  adapter_id: 'ppflow',
  safety_note: 'PPFlow outputs are computational predictions only. NOT_EXPERIMENTALLY_VALIDATED.',
  validation_policy: 'Disabled placeholder; NOT_EXPERIMENTALLY_VALIDATED.',
  real_run_enabled: false,
  stage: 'P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS',
  notes: 'P33O path-repair success; NOT_EXPERIMENTALLY_VALIDATED.',
  validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
  readiness_gate: 'P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS',
  readiness_level: 'controlled_smoke_verified',
  execution_locked: true,
  blocker_code: 'REAL_RUN_GATE_CLOSED',
  next_authorization: 'NEW_EXPLICIT_AUTH_REQUIRED_FOR_ANY_FUTURE_EXECUTION',
  last_verified_at: '2026-06-29T06:41:17+08:00',
  evidence_ref: 'STAMP_P33O_PPFLOW_PATH_REPAIR_SUCCESS_REPORT.md / p33o_ppflow_path_repair_20260629_063127/manifest.json',
  product_group: 'available_six',
  ui_selectable: true,
  ui_execution_state: 'probe_dry_run_available',
  activation_requirements: 'NEW_EXPLICIT_AUTH_REQUIRED_FOR_ANY_FUTURE_EXECUTION',
  delivery_status: 'delivered_for_probe_dry_run_ui',
};

// Complete PepMLM entry (peer model for the switch-cleanup test).
const pepmlmBase = {
  model_id: 'pepmlm',
  display_name: 'PepMLM',
  category: 'sequence_generation',
  status: 'smoke_rerun_verified',
  status_reason: 'p30b_smoke_rerun_verified_gate_closed',
  description: 'PepMLM masked-language-model peptide sequence generator. NOT_EXPERIMENTALLY_VALIDATED.',
  supports_probe: true,
  supports_dry_run: true,
  supports_real_run: true,
  supports_structure_output: false,
  supports_sequence_output: true,
  supports_ranking: false,
  output_artifact_types: ['sequence_csv', 'sequence_json', 'logs', 'manifest', 'input'],
  adapter_id: 'pepmlm',
  safety_note: 'PepMLM outputs are computational predictions only. NOT_EXPERIMENTALLY_VALIDATED.',
  validation_policy: 'All PepMLM outputs must be labelled NOT_EXPERIMENTALLY_VALIDATED.',
  real_run_enabled: false,
  stage: 'P30B_SMOKE_RERUN_GO',
  notes: 'P30B smoke rerun verified; gate CLOSED. NOT_EXPERIMENTALLY_VALIDATED.',
  validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
  readiness_gate: 'P30B_SMOKE_RERUN_GO',
  readiness_level: 'smoke_rerun_verified',
  execution_locked: true,
  blocker_code: 'REAL_RUN_GATE_CLOSED',
  next_authorization: 'explicit gate open required',
  last_verified_at: '2026-07-01T06:41:37+08:00',
  evidence_ref: 'STAMP_PEPMLM_SMOKE_RERUN_FIRST_REAL_MODEL_P30B_REPORT.md',
  product_group: 'available_six',
  ui_selectable: true,
  ui_execution_state: 'probe_dry_run_available',
  activation_requirements: 'NEW_EXPLICIT_AUTH_REQUIRED_FOR_ANY_FUTURE_EXECUTION',
  delivery_status: 'delivered_for_probe_dry_run_ui',
};

function lockedPpflow() {
  // Real ppflow lock state: canRealRun = supports_real_run && real_run_enabled && !execution_locked = false.
  return { ...ppflowBase, execution_locked: true, real_run_enabled: false };
}
function unlockedPpflow() {
  // SYNTHETIC governance probe only: all three flags allow Real Run, to verify
  // the canRealRun gate and that clicking the enabled button issues zero submit.
  return { ...ppflowBase, supports_real_run: true, execution_locked: false, real_run_enabled: true };
}

const evidenceData = {
  model_id: 'ppflow',
  stage: 'P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS',
  execution_locked: true,
  real_run_enabled: false,
  validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
  evidence: {
    success_report: 'reports/p33o_ppflow_repair/STAMP_P33O_PPFLOW_PATH_REPAIR_SUCCESS_REPORT.md',
    execution_manifest: 'reports/p33o_ppflow_repair/STAMP_P33O_PPFLOW_PATH_REPAIR_EXECUTION_MANIFEST.md',
    result_manifest: '/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33o_ppflow_path_repair_20260629_063127/manifest.json',
    status: '/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33o_ppflow_path_repair_20260629_063127/status.json',
    artifact_dir: '/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33o_ppflow_path_repair_20260629_063127/',
    sha256: {
      success_report: '8f6519e85ce6f7936794ed5d580fe2c7ef52dadff6c6643770d19c0eb873f293',
      execution_manifest: '1c3cfe85a35989f4deef44305186eb1683336c2900a9e5c43e24c8e0729ec307',
      result_manifest: '6d14f2f56f927d5130099d88e3993534a8662b88e43394cbc36de93a5a006a00',
      status: '3ffca90345575290cf9fccfbfb3997799631c7834e5f1a94c0e7f520c18628d8',
    },
    exit_code: 0,
    elapsed_seconds: 588.46,
    sample_dirs: 133,
    file_count: 404,
    artifact_bytes: 4408281,
    validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
  },
  downloadable_ids: ['success_report', 'execution_manifest', 'result_manifest', 'status'],
};

// ---- tiny assert harness ----
const results = [];
function check(name, cond, detail = '') {
  results.push({ name, ok: !!cond, detail });
  if (!cond) console.log(`  FAIL: ${name}${detail ? ' — ' + detail : ''}`);
  else console.log(`  ok:   ${name}`);
}

async function mockModelsList(page, models) {
  const fulfill = async (route) => {
    await route.fulfill({
      status: 200,
      json: { code: 200, message: 'ok', data: { models, scientific_boundary: 'computational prediction only' } },
    });
  };
  await page.route(MODELS_URL, fulfill);
  await page.route(MODEL_REGISTRY_URL, fulfill);
}

async function mockEvidence(page, status, body) {
  await page.route(EVIDENCE_URL, async (route) => {
    if (status === 200) {
      await route.fulfill({ status: 200, json: { code: 200, message: 'ok', data: body } });
    } else {
      await route.fulfill({ status, json: { detail: `evidence HTTP ${status}` } });
    }
  });
}

async function mockDownload(page, id, status, body) {
  await page.route(downloadUrl(id), async (route) => {
    if (status === 200) {
      await route.fulfill({ status: 200, contentType: 'text/plain', body });
    } else {
      await route.fulfill({ status, json: { detail: `download HTTP ${status}` } });
    }
  });
}

function trackForbidden(page) {
  const hits = [];
  page.on('request', (req) => {
    const u = req.url();
    if (FORBIDDEN_PATH_PATTERNS.some((re) => re.test(u))) {
      hits.push(`${req.method()} ${u}`);
    }
  });
  return hits;
}

/** The modal detail panel container (only present when a model is selected). */
function modalLocator(page) {
  return page.locator('div.fixed.inset-0.z-50').last();
}

/**
 * Open the detail modal for a model by clicking that card's "Details" button.
 * Returns the modal locator. Scoped so we never match other Real Run buttons.
 */
async function openDetailFor(page, displayName) {
  await page.goto('/target-design', { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  // The card is the innermost div that contains the display name AND a Details button.
  const card = page
    .locator('div', { hasText: displayName })
    .filter({ has: page.getByRole('button', { name: 'Details' }) })
    .last();
  await card.getByRole('button', { name: 'Details' }).click({ timeout: 5000 });
  const modal = modalLocator(page);
  // The modal is open once its "Run Probe" button is visible.
  await modal.getByRole('button', { name: /Run Probe/ }).waitFor({ state: 'visible', timeout: 5000 });
  return modal;
}

/** Close the modal via its X button (the only button with a lucide-x icon). */
async function closeModal(page) {
  const modal = modalLocator(page);
  await modal.locator('button:has(.lucide-x)').first().click({ timeout: 2000 }).catch(() => {});
  await page.waitForTimeout(300);
}

async function newContext(browser) {
  // baseURL on the context lets page.goto resolve relative URLs (e.g.
  // '/target-design') and keeps page.route globs anchored.
  const context = await browser.newContext({ acceptDownloads: true, baseURL: BASE });
  const page = await context.newPage();
  return { context, page };
}

async function run() {
  console.log(`\nSTAMP P33P PPFlow acceptance — base=${BASE}`);
  const browser = await chromium.launch({ headless: true });

  // 1. locked fixture
  {
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    await mockModelsList(page, [lockedPpflow()]);
    await mockEvidence(page, 200, evidenceData);
    const modal = await openDetailFor(page, 'PPFlow');
    const realRun = modal.getByRole('button', { name: /Real Run/ });
    check('locked: Real Run button visible', await realRun.isVisible().catch(() => false));
    check('locked: Real Run button disabled', await realRun.isDisabled().catch(() => false));
    check('locked: label is "Real Run Locked"', (await realRun.textContent().catch(() => '')).includes('Real Run Locked'));
    check('locked: zero forbidden requests', hits.length === 0, hits.join('; '));
    await context.close();
  }

  // 2. unlocked fixture (synthetic governance probe)
  {
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    await mockModelsList(page, [unlockedPpflow()]);
    await mockEvidence(page, 200, evidenceData);
    const modal = await openDetailFor(page, 'PPFlow');
    const realRun = modal.getByRole('button', { name: /^Real Run$/ });
    await realRun.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    check('unlocked: Real Run button enabled', await realRun.isEnabled().catch(() => false));
    check('unlocked: label is "Real Run" (no Locked)', (await realRun.textContent().catch(() => '')).trim() === 'Real Run');
    // P33P does not implement submit: clicking the enabled button must NOT issue any forbidden request.
    await realRun.click({ timeout: 2000 }).catch(() => {});
    await page.waitForTimeout(300);
    check('unlocked: clicking Real Run issues zero forbidden requests', hits.length === 0, hits.join('; '));
    await context.close();
  }

  // 3. evidence load success
  {
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    await mockModelsList(page, [lockedPpflow()]);
    await mockEvidence(page, 200, evidenceData);
    const modal = await openDetailFor(page, 'PPFlow');
    await modal.getByText('P33O evidence (computational only)').waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    check('evidence success: header visible', await modal.getByText('P33O evidence (computational only)').isVisible().catch(() => false));
    check('evidence success: Exit code 0', await modal.getByText('Exit code: 0').isVisible().catch(() => false));
    check('evidence success: Sample dirs 133', await modal.getByText('Sample dirs: 133').isVisible().catch(() => false));
    check('evidence success: Files 404', await modal.getByText('Files: 404').isVisible().catch(() => false));
    check('evidence success: success_report SHA visible', await modal.getByText(/success_report SHA: 8f6519/).isVisible().catch(() => false));
    check('evidence success: NOT_EXPERIMENTALLY_VALIDATED disclaimer visible', await modal.getByText(/NOT_EXPERIMENTALLY_VALIDATED\. Execution locked; Real Run remains disabled/).isVisible().catch(() => false));
    for (const id of evidenceData.downloadable_ids) {
      check(`evidence success: Download ${id} button visible`, await modal.getByRole('button', { name: `Download ${id}` }).isVisible().catch(() => false));
    }
    check('evidence success: zero forbidden requests', hits.length === 0, hits.join('; '));
    await context.close();
  }

  // 4. evidence load failure (500)
  {
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    await mockModelsList(page, [lockedPpflow()]);
    await mockEvidence(page, 500, { detail: 'evidence HTTP 500' });
    const modal = await openDetailFor(page, 'PPFlow');
    const alert = modal.getByRole('alert').filter({ hasText: 'Evidence load failed' });
    await alert.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    check('evidence fail: role=alert visible', await alert.isVisible().catch(() => false));
    check('evidence fail: alert contains HTTP 500', (await alert.textContent().catch(() => '')).includes('HTTP 500'));
    check('evidence fail: zero forbidden requests', hits.length === 0, hits.join('; '));
    await context.close();
  }

  // 5. download success (200) -> exactly one download, no error alert
  {
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    const downloads = [];
    page.on('download', (d) => downloads.push(d.suggestedFilename()));
    await mockModelsList(page, [lockedPpflow()]);
    await mockEvidence(page, 200, evidenceData);
    await mockDownload(page, 'success_report', 200, 'success report body');
    const modal = await openDetailFor(page, 'PPFlow');
    const btn = modal.getByRole('button', { name: 'Download success_report' });
    await btn.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    await btn.click({ timeout: 2000 }).catch(() => {});
    await page.waitForTimeout(500);
    check('download 200: exactly one download triggered', downloads.length === 1, `downloads=${downloads.length}`);
    check('download 200: no "Download failed" alert', (await modal.getByRole('alert').filter({ hasText: 'Download failed' }).count()) === 0);
    check('download 200: zero forbidden requests', hits.length === 0, hits.join('; '));
    await context.close();
  }

  // 6/7/8. download 403 / 404 / 409 -> zero downloads, role=alert error, no file saved
  for (const [id, status] of [['result_manifest', 403], ['status', 404], ['execution_manifest', 409]]) {
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    const downloads = [];
    page.on('download', (d) => downloads.push(d.suggestedFilename()));
    await mockModelsList(page, [lockedPpflow()]);
    await mockEvidence(page, 200, evidenceData);
    await mockDownload(page, id, status, '');
    const modal = await openDetailFor(page, 'PPFlow');
    const btn = modal.getByRole('button', { name: `Download ${id}` });
    await btn.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    await btn.click({ timeout: 2000 }).catch(() => {});
    await page.waitForTimeout(500);
    const alert = modal.getByRole('alert').filter({ hasText: 'Download failed' });
    await alert.waitFor({ state: 'visible', timeout: 3000 }).catch(() => {});
    check(`download ${status}: zero downloads (no file saved)`, downloads.length === 0, `downloads=${downloads.length}`);
    check(`download ${status}: role=alert "Download failed" visible`, await alert.isVisible().catch(() => false));
    check(`download ${status}: alert contains HTTP ${status}`, (await alert.textContent().catch(() => '')).includes(`HTTP ${status}`));
    check(`download ${status}: zero forbidden requests`, hits.length === 0, hits.join('; '));
    await context.close();
  }

  // 9. unknown evidence id filtered out of rendered buttons
  {
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    await mockModelsList(page, [lockedPpflow()]);
    const poisoned = {
      ...evidenceData,
      downloadable_ids: ['success_report', 'execution_manifest', 'result_manifest', 'status', 'evil_id', '../etc/passwd'],
    };
    await mockEvidence(page, 200, poisoned);
    const modal = await openDetailFor(page, 'PPFlow');
    await modal.getByText('P33O evidence (computational only)').waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    const knownButtons = 4;
    let visibleKnown = 0;
    for (const id of ['success_report', 'execution_manifest', 'result_manifest', 'status']) {
      if (await modal.getByRole('button', { name: `Download ${id}` }).isVisible().catch(() => false)) visibleKnown++;
    }
    check('unknown-id filter: all 4 known buttons visible', visibleKnown === knownButtons, `visibleKnown=${visibleKnown}`);
    check('unknown-id filter: evil_id button NOT rendered', (await modal.getByRole('button', { name: 'Download evil_id' }).count()) === 0);
    check('unknown-id filter: traversal id button NOT rendered', (await modal.getByRole('button', { name: /etc.passwd/ }).count()) === 0);
    check('unknown-id filter: zero forbidden requests', hits.length === 0, hits.join('; '));
    await context.close();
  }

  // 10. state cleanup on close-detail and on model switch
  {
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    await mockModelsList(page, [lockedPpflow(), pepmlmBase]);
    await mockEvidence(page, 200, evidenceData);
    const modal = await openDetailFor(page, 'PPFlow');
    const header = modal.getByText('P33O evidence (computational only)');
    await header.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    check('cleanup: evidence block visible after open', await header.isVisible().catch(() => false));
    // close detail -> evidence block must disappear
    await closeModal(page);
    check('cleanup: evidence block gone after close-detail', (await page.getByText('P33O evidence (computational only)').count()) === 0);
    // open PepMLM detail (selectedModel becomes non-ppflow) -> evidence must stay cleared
    const modal2 = await openDetailFor(page, 'PepMLM');
    await page.waitForTimeout(400);
    check('cleanup: evidence block gone after model switch to PepMLM', (await modal2.getByText('P33O evidence (computational only)').count()) === 0);
    check('cleanup: zero forbidden requests', hits.length === 0, hits.join('; '));
    await context.close();
  }

  await browser.close();

  const failed = results.filter((r) => !r.ok);
  console.log(`\n==== P33P acceptance: ${results.length - failed.length}/${results.length} passed, ${failed.length} failed ====`);
  if (failed.length) {
    console.log('FAILED:');
    for (const r of failed) console.log(`  - ${r.name}${r.detail ? ' — ' + r.detail : ''}`);
    process.exit(1);
  }
  process.exit(0);
}

run().catch((err) => {
  console.error('P33P acceptance script threw:', err);
  process.exit(2);
});

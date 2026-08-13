// @ts-check
/**
 * STAMP P33Q — six-model unified evidence & safe-download acceptance.
 *
 * Standalone Node ESM script. Uses the EXISTING `playwright` package directly
 * (NOT @playwright/test, which is not installed). Does not touch package.json.
 *
 * Run (existing deps only, no npm install):
 *   P33Q_E2E_BASE_URL=http://127.0.0.1:12823 node e2e/p33q-six-model-evidence-accept.mjs
 *
 * Every API response is mocked with page.route(); the real backend is never hit.
 * All six available_six models stay real_run_enabled=false / execution_locked=true.
 * P33Q does NOT implement submit — the Real Run button has no onClick handler.
 *
 * UI model (matches the live app after P33Q):
 *   - ModelReadinessOverview is always rendered on /target-design.
 *   - Each model card has a "Details" button opening a modal (div.fixed.inset-0.z-50).
 *   - The evidence center block renders for every selected model based on the
 *     unified /evidence response (availability / stats / artifacts / downloadable_ids).
 *
 * Coverage:
 *   - six models: evidence renders, stats, SHA, download buttons, disclaimer
 *   - placeholders + excluded: availability=unavailable, no download buttons
 *   - evidence load failure -> role="alert" with HTTP status + detail
 *   - download 200 (ppflow + pepmlm) -> exactly one download, no error
 *   - download 403 / 404 / 409 -> ZERO downloads, role=alert, no file saved
 *   - unknown evidence id filtered out of rendered buttons
 *   - state cleanup on close-detail and on model switch
 *   - zero submit / real-run / gate / checkpoint / probe / dry-run requests
 */

import { chromium } from 'playwright';

const BASE = process.env.P33Q_E2E_BASE_URL || 'http://127.0.0.1:12823';

const MODELS_URL = '**/api/v1/models';
const MODEL_REGISTRY_URL = '**/api/v1/model-registry';
const evidenceUrl = (mid) => `**/api/v1/models/${mid}/evidence`;
const downloadUrl = (mid, id) => `**/api/v1/models/${mid}/evidence/${id}/download`;

const FORBIDDEN_PATH_PATTERNS = [
  /\/api\/v1\/models\/[^/]+\/submit/,
  /\/api\/v1\/models\/[^/]+\/dry-run/,
  /\/api\/v1\/models\/[^/]+\/probe/,
  /\/api\/v1\/models\/[^/]+\/real-run/,
  /\/api\/v1\/.*gate/,
  /\/api\/v1\/.*checkpoint/,
];

// ---- complete ModelRegistryEntry builder (mirrors live backend shape) ----
function makeModel(o) {
  return {
    model_id: o.model_id,
    display_name: o.display_name,
    category: o.category || 'flow_based_design',
    status: o.status || 'controlled_smoke_verified',
    status_reason: o.status_reason || 'p33q_locked',
    description: o.description || 'P33Q model. NOT_EXPERIMENTALLY_VALIDATED.',
    supports_probe: true,
    supports_dry_run: true,
    supports_real_run: o.supports_real_run ?? false,
    supports_structure_output: false,
    supports_sequence_output: true,
    supports_ranking: false,
    output_artifact_types: o.output_artifact_types || [],
    adapter_id: o.model_id,
    safety_note: 'computational prediction only. NOT_EXPERIMENTALLY_VALIDATED.',
    validation_policy: 'Disabled placeholder; NOT_EXPERIMENTALLY_VALIDATED.',
    real_run_enabled: false,
    stage: o.stage || 'P33Q_LOCKED',
    notes: 'P33Q; NOT_EXPERIMENTALLY_VALIDATED.',
    validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
    readiness_gate: o.stage || 'P33Q_LOCKED',
    readiness_level: o.readiness_level || 'controlled_smoke_verified',
    execution_locked: true,
    blocker_code: 'REAL_RUN_GATE_CLOSED',
    next_authorization: 'NEW_EXPLICIT_AUTH_REQUIRED_FOR_ANY_FUTURE_EXECUTION',
    last_verified_at: '2026-07-01T00:00:00+00:00',
    evidence_ref: o.evidence_ref || '',
    product_group: o.product_group,
    ui_selectable: o.product_group === 'available_six',
    ui_execution_state:
      o.product_group === 'available_six'
        ? 'probe_dry_run_available'
        : o.product_group === 'reserved_placeholder'
        ? 'locked_placeholder'
        : 'excluded',
    activation_requirements: 'NEW_EXPLICIT_AUTH_REQUIRED_FOR_ANY_FUTURE_EXECUTION',
    delivery_status:
      o.product_group === 'available_six'
        ? 'delivered_for_probe_dry_run_ui'
        : 'out_of_scope_evidence_preserved',
  };
}

const SIX = [
  makeModel({ model_id: 'ppflow', display_name: 'PPFlow', category: 'flow_based_design', stage: 'P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS', product_group: 'available_six', output_artifact_types: [], evidence_ref: 'STAMP_P33O_PPFLOW_PATH_REPAIR_SUCCESS_REPORT.md / manifest.json' }),
  makeModel({ model_id: 'pepmlm', display_name: 'PepMLM', category: 'sequence_generation', stage: 'P30B_SMOKE_RERUN_GO', product_group: 'available_six', supports_real_run: true, output_artifact_types: ['sequence_csv', 'sequence_json', 'logs', 'manifest', 'input'], evidence_ref: 'STAMP_PEPMLM_SMOKE_RERUN_FIRST_REAL_MODEL_P30B_REPORT.md' }),
  makeModel({ model_id: 'evobind2', display_name: 'EvoBind2', category: 'structure_prediction / peptide_design', stage: 'P3B_CONTROLLED_SMOKE_OK', product_group: 'available_six', output_artifact_types: ['pdb', 'metrics_csv', 'logs', 'manifest', 'input'], evidence_ref: 'EVOBIND2_P3B... / P3C...' }),
  makeModel({ model_id: 'diffpepbuilder', display_name: 'DiffPepBuilder', category: 'diffusion_based_design', stage: 'P32B_CONTROLLED_SMOKE_OK', product_group: 'available_six', output_artifact_types: [], evidence_ref: 'STAMP_P32B_DELIVERY_MANIFEST.json' }),
  makeModel({ model_id: 'pepflow', display_name: 'PepFlow', category: 'flow_based_design', stage: 'P32B_CONTROLLED_SMOKE_OK', product_group: 'available_six', output_artifact_types: [], evidence_ref: 'STAMP_P32B_DELIVERY_MANIFEST.json' }),
  makeModel({ model_id: 'pephar', display_name: 'PepHAR', category: 'hierarchical_design', stage: 'P32B_CONTROLLED_SMOKE_OK', product_group: 'available_six', output_artifact_types: [], evidence_ref: 'STAMP_P32B_DELIVERY_MANIFEST.json' }),
];
const PLACEHOLDERS = [
  makeModel({ model_id: 'pepglad', display_name: 'PepGLAD', category: 'graph_conditioned_design', stage: 'P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED', product_group: 'reserved_placeholder', readiness_level: 'pending_probe', output_artifact_types: ['pdb', 'sequence_csv', 'scores_csv', 'logs', 'manifest', 'input'], evidence_ref: 'STAMP_P33J...json / P33I...md' }),
  makeModel({ model_id: 'rfpeptides', display_name: 'RFpeptides', category: 'structure_conditioned_design', stage: 'P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED', product_group: 'reserved_placeholder', readiness_level: 'pending_probe', output_artifact_types: [], evidence_ref: 'STAMP_P33J...json / P33I...md' }),
];
const EXCLUDED = [
  makeModel({ model_id: 'pepprclip', display_name: 'PepPrCLIP', category: 'ranking', stage: 'P0_8MODEL', product_group: 'excluded', readiness_level: 'pending_probe', supports_real_run: true, output_artifact_types: ['ranking_csv', 'scores_json', 'logs', 'manifest', 'input'], evidence_ref: 'STAMP_P31D1_REGISTRY_LIVE_STATE_SYNC_REPORT.md' }),
];

function artifact(id, sha, bytes) {
  return { id, filename: `${id}`, media_type: 'text/plain', sha256: sha, bytes };
}

const EVIDENCE = {
  ppflow: {
    model_id: 'ppflow', stage: 'P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS', validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
    execution_locked: true, real_run_enabled: false, supports_real_run: false,
    evidence_ref: 'STAMP_P33O_PPFLOW_PATH_REPAIR_SUCCESS_REPORT.md / manifest.json', availability: 'available',
    stats: { exit_code: 0, elapsed_seconds: 588.46, sample_dirs: 133, file_count: 404, artifact_bytes: 4408281 },
    downloadable_ids: ['success_report', 'execution_manifest', 'result_manifest', 'status'],
    artifacts: [
      artifact('success_report', '8f6519e85ce6f7936794ed5d580fe2c7ef52dadff6c6643770d19c0eb873f293', 7000),
      artifact('execution_manifest', '1c3cfe85a35989f4deef44305186eb1683336c2900a9e5c43e24c8e0729ec307', 5000),
      artifact('result_manifest', '6d14f2f56f927d5130099d88e3993534a8662b88e43394cbc36de93a5a006a00', 2000),
      artifact('status', '3ffca90345575290cf9fccfbfb3997799631c7834e5f1a94c0e7f520c18628d8', 1500),
    ],
  },
  pepmlm: {
    model_id: 'pepmlm', stage: 'P30B_SMOKE_RERUN_GO', validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
    execution_locked: true, real_run_enabled: false, supports_real_run: true,
    evidence_ref: 'STAMP_PEPMLM_SMOKE_RERUN_FIRST_REAL_MODEL_P30B_REPORT.md', availability: 'available',
    stats: { exit_code: 0, candidate_count: 3 },
    downloadable_ids: ['success_report', 'status', 'reasonix_review', 'artifacts_index'],
    artifacts: [
      artifact('success_report', '235cacd1e1dc2267177c446908bf81df6c22c29f23eae64f25aa90173060d96b', 6951),
      artifact('status', 'd334a3bf548c4b3d6fc23de04c2e858eef75c9b560c3eecb03eec7a3ad64f73f', 3575),
      artifact('reasonix_review', 'aa253e3c11516961102db35dbb89139d4749dd9db4522d715f23971bf063ef9f', 5229),
      artifact('artifacts_index', '57e8b6b92444449b1fe2c81d237d1bfb964458448a0661b10148e7ac30c2ed17', 2820),
    ],
  },
  evobind2: {
    model_id: 'evobind2', stage: 'P3B_CONTROLLED_SMOKE_OK', validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
    execution_locked: true, real_run_enabled: false, supports_real_run: false,
    evidence_ref: 'EVOBIND2_P3B... / P3C...', availability: 'partial', stats: null,
    downloadable_ids: ['p3b_report', 'p3c_report'],
    artifacts: [
      artifact('p3b_report', '01d5100ad74c0771314319a8a042fca9a62afd98e25a0556286376bf67d1d3e8', 16883),
      artifact('p3c_report', 'bb120103bca81069cdde25bd855e62c253c6fd7fc3c54e844e72b1f53bfa0390', 18366),
    ],
  },
  diffpepbuilder: {
    model_id: 'diffpepbuilder', stage: 'P32B_CONTROLLED_SMOKE_OK', validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
    execution_locked: true, real_run_enabled: false, supports_real_run: false,
    evidence_ref: 'STAMP_P32B_DELIVERY_MANIFEST.json', availability: 'partial', stats: null,
    downloadable_ids: ['delivery_manifest', 'result_manifest'],
    artifacts: [
      artifact('delivery_manifest', 'c755ff61980a8dbeccfec66a5f4cf06275542d59839892cab092fc56a00b2c0c', 3822),
      artifact('result_manifest', 'ccc6a3e0b601dbe69b8e2b8d5f808ade6bfd30f1c9fc42adb7d701f328202581', 2711),
    ],
  },
  pepflow: {
    model_id: 'pepflow', stage: 'P32B_CONTROLLED_SMOKE_OK', validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
    execution_locked: true, real_run_enabled: false, supports_real_run: false,
    evidence_ref: 'STAMP_P32B_DELIVERY_MANIFEST.json', availability: 'partial', stats: null,
    downloadable_ids: ['delivery_manifest', 'result_manifest'],
    artifacts: [
      artifact('delivery_manifest', 'c755ff61980a8dbeccfec66a5f4cf06275542d59839892cab092fc56a00b2c0c', 3822),
      artifact('result_manifest', 'fc76f5537d1cee88e3e446082d267ac690547861d5c207d0e2941341526708f6', 2286),
    ],
  },
  pephar: {
    model_id: 'pephar', stage: 'P32B_CONTROLLED_SMOKE_OK', validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
    execution_locked: true, real_run_enabled: false, supports_real_run: false,
    evidence_ref: 'STAMP_P32B_DELIVERY_MANIFEST.json', availability: 'partial', stats: null,
    downloadable_ids: ['delivery_manifest', 'result_manifest'],
    artifacts: [
      artifact('delivery_manifest', 'c755ff61980a8dbeccfec66a5f4cf06275542d59839892cab092fc56a00b2c0c', 3822),
      artifact('result_manifest', 'f6b25b80b023aa160241d0fb92d438ce2ffaf2bc5e97527fa5ff37e47ab98695', 2513),
    ],
  },
};
function unavailableEvidence(mid, stage, evidence_ref) {
  return {
    model_id: mid, stage, validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
    execution_locked: true, real_run_enabled: false, supports_real_run: false,
    evidence_ref, availability: 'unavailable', stats: null, downloadable_ids: [], artifacts: [],
  };
}

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

async function mockEvidence(page, mid, status, body) {
  await page.route(evidenceUrl(mid), async (route) => {
    if (status === 200) {
      await route.fulfill({ status: 200, json: { code: 200, message: 'ok', data: body } });
    } else {
      await route.fulfill({ status, json: { detail: `evidence HTTP ${status}` } });
    }
  });
}

async function mockDownload(page, mid, id, status, body) {
  await page.route(downloadUrl(mid, id), async (route) => {
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
    if (FORBIDDEN_PATH_PATTERNS.some((re) => re.test(u))) hits.push(`${req.method()} ${u}`);
  });
  return hits;
}

function modalLocator(page) {
  return page.locator('div.fixed.inset-0.z-50').last();
}

async function openDetailFor(page, displayName) {
  await page.goto('/target-design', { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  const card = page
    .locator('div', { hasText: displayName })
    .filter({ has: page.getByRole('button', { name: 'Details' }) })
    .last();
  await card.getByRole('button', { name: 'Details' }).click({ timeout: 5000 });
  const modal = modalLocator(page);
  await modal.getByRole('button', { name: /Run Probe/ }).waitFor({ state: 'visible', timeout: 5000 });
  return modal;
}

async function closeModal(page) {
  const modal = modalLocator(page);
  await modal.locator('button:has(.lucide-x)').first().click({ timeout: 2000 }).catch(() => {});
  await page.waitForTimeout(300);
}

async function newContext(browser) {
  const context = await browser.newContext({ acceptDownloads: true, baseURL: BASE });
  const page = await context.newPage();
  return { context, page };
}

async function run() {
  console.log(`\nSTAMP P33Q six-model acceptance — base=${BASE}`);
  const browser = await chromium.launch({ headless: true });

  // 1. Each of the six models: evidence renders with stats/SHA/buttons + disclaimer + forbidden=0
  for (const m of SIX) {
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    await mockModelsList(page, [m]);
    await mockEvidence(page, m.model_id, 200, EVIDENCE[m.model_id]);
    const modal = await openDetailFor(page, m.display_name);
    const header = modal.getByText('Evidence center (computational only)');
    await header.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    check(`${m.model_id}: evidence center header visible`, await header.isVisible().catch(() => false));
    check(`${m.model_id}: availability badge visible`, await modal.getByText(EVIDENCE[m.model_id].availability, { exact: false }).first().isVisible().catch(() => false));
    check(`${m.model_id}: NOT_EXPERIMENTALLY_VALIDATED disclaimer`, await modal.getByText(/NOT_EXPERIMENTALLY_VALIDATED\. Execution locked; Real Run remains disabled/).isVisible().catch(() => false));
    // stats rendering (if stats present)
    const ev = EVIDENCE[m.model_id];
    if (ev.stats) {
      for (const [k, v] of Object.entries(ev.stats)) {
        const repr = typeof v === 'number' ? v.toLocaleString() : String(v);
        check(`${m.model_id}: stat ${k} rendered`, await modal.getByText(`${k}: ${repr}`, { exact: false }).first().isVisible().catch(() => false));
      }
    }
    // download buttons for each known id
    for (const id of ev.downloadable_ids) {
      check(`${m.model_id}: Download ${id} button visible`, await modal.getByRole('button', { name: `Download ${id}` }).isVisible().catch(() => false));
    }
    // SHA list for each artifact
    for (const a of ev.artifacts) {
      check(`${m.model_id}: ${a.id} SHA visible`, await modal.getByText(`${a.id} SHA: ${a.sha256}`).isVisible().catch(() => false));
    }
    // Real Run locked (all six locked)
    const realRun = modal.getByRole('button', { name: /Real Run/ });
    check(`${m.model_id}: Real Run disabled (locked)`, await realRun.isDisabled().catch(() => false));
    check(`${m.model_id}: zero forbidden requests`, hits.length === 0, hits.join('; '));
    await context.close();
  }

  // 2. Placeholders + excluded: availability=unavailable, no download buttons
  for (const m of [...PLACEHOLDERS, ...EXCLUDED]) {
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    await mockModelsList(page, [m]);
    await mockEvidence(page, m.model_id, 200, unavailableEvidence(m.model_id, m.stage, m.evidence_ref));
    const modal = await openDetailFor(page, m.display_name);
    const header = modal.getByText('Evidence center (computational only)');
    await header.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    check(`${m.model_id}: evidence center header visible`, await header.isVisible().catch(() => false));
    check(`${m.model_id}: "no downloadable evidence" message`, await modal.getByText('No downloadable evidence bundle for this model in this phase.').isVisible().catch(() => false));
    check(`${m.model_id}: zero download buttons`, (await modal.getByRole('button', { name: /Download / }).count()) === 0);
    check(`${m.model_id}: zero forbidden requests`, hits.length === 0, hits.join('; '));
    await context.close();
  }

  // 3. evidence load failure (500) on pepmlm
  {
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    await mockModelsList(page, [SIX[1]]);
    await mockEvidence(page, 'pepmlm', 500, { detail: 'evidence HTTP 500' });
    const modal = await openDetailFor(page, 'PepMLM');
    const alert = modal.getByRole('alert').filter({ hasText: 'Evidence load failed' });
    await alert.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    check('evidence fail: role=alert visible', await alert.isVisible().catch(() => false));
    check('evidence fail: alert contains HTTP 500', (await alert.textContent().catch(() => '')).includes('HTTP 500'));
    check('evidence fail: zero forbidden requests', hits.length === 0, hits.join('; '));
    await context.close();
  }

  // 4. download success (200) on ppflow + pepmlm -> exactly one download, no error
  for (const [mid, id] of [['ppflow', 'success_report'], ['pepmlm', 'status']]) {
    const m = SIX.find((x) => x.model_id === mid);
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    const downloads = [];
    page.on('download', (d) => downloads.push(d.suggestedFilename()));
    await mockModelsList(page, [m]);
    await mockEvidence(page, mid, 200, EVIDENCE[mid]);
    await mockDownload(page, mid, id, 200, 'body');
    const modal = await openDetailFor(page, m.display_name);
    const btn = modal.getByRole('button', { name: `Download ${id}` });
    await btn.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    await btn.click({ timeout: 2000 }).catch(() => {});
    await page.waitForTimeout(500);
    check(`download 200 ${mid}/${id}: exactly one download`, downloads.length === 1, `downloads=${downloads.length}`);
    check(`download 200 ${mid}/${id}: no "Download failed" alert`, (await modal.getByRole('alert').filter({ hasText: 'Download failed' }).count()) === 0);
    check(`download 200 ${mid}/${id}: zero forbidden requests`, hits.length === 0, hits.join('; '));
    await context.close();
  }

  // 5. download 403 / 404 / 409 on pepmlm -> zero downloads, role=alert, no file saved
  for (const [id, st] of [['reasonix_review', 403], ['artifacts_index', 404], ['success_report', 409]]) {
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    const downloads = [];
    page.on('download', (d) => downloads.push(d.suggestedFilename()));
    await mockModelsList(page, [SIX[1]]);
    await mockEvidence(page, 'pepmlm', 200, EVIDENCE.pepmlm);
    await mockDownload(page, 'pepmlm', id, st, '');
    const modal = await openDetailFor(page, 'PepMLM');
    const btn = modal.getByRole('button', { name: `Download ${id}` });
    await btn.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    await btn.click({ timeout: 2000 }).catch(() => {});
    await page.waitForTimeout(500);
    const alert = modal.getByRole('alert').filter({ hasText: 'Download failed' });
    await alert.waitFor({ state: 'visible', timeout: 3000 }).catch(() => {});
    check(`download ${st} pepmlm/${id}: zero downloads`, downloads.length === 0, `downloads=${downloads.length}`);
    check(`download ${st} pepmlm/${id}: role=alert visible`, await alert.isVisible().catch(() => false));
    check(`download ${st} pepmlm/${id}: alert contains HTTP ${st}`, (await alert.textContent().catch(() => '')).includes(`HTTP ${st}`));
    check(`download ${st} pepmlm/${id}: zero forbidden requests`, hits.length === 0, hits.join('; '));
    await context.close();
  }

  // 6. unknown evidence id filtered out of rendered buttons (ppflow)
  {
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    await mockModelsList(page, [SIX[0]]);
    const poisoned = {
      ...EVIDENCE.ppflow,
      downloadable_ids: [...EVIDENCE.ppflow.downloadable_ids, 'evil_id', '../etc/passwd'],
      artifacts: [...EVIDENCE.ppflow.artifacts, artifact('evil_id', 'x'.repeat(64), 1)],
    };
    await mockEvidence(page, 'ppflow', 200, poisoned);
    const modal = await openDetailFor(page, 'PPFlow');
    await modal.getByText('Evidence center (computational only)').waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    let visibleKnown = 0;
    for (const id of EVIDENCE.ppflow.downloadable_ids) {
      if (await modal.getByRole('button', { name: `Download ${id}` }).isVisible().catch(() => false)) visibleKnown++;
    }
    check('unknown-id filter: all 4 known ppflow buttons visible', visibleKnown === 4, `visibleKnown=${visibleKnown}`);
    check('unknown-id filter: evil_id button NOT rendered', (await modal.getByRole('button', { name: 'Download evil_id' }).count()) === 0);
    check('unknown-id filter: traversal id button NOT rendered', (await modal.getByRole('button', { name: /etc.passwd/ }).count()) === 0);
    check('unknown-id filter: zero forbidden requests', hits.length === 0, hits.join('; '));
    await context.close();
  }

  // 7. state cleanup on close-detail and on model switch
  {
    const { context, page } = await newContext(browser);
    const hits = trackForbidden(page);
    await mockModelsList(page, [SIX[0], SIX[1]]);
    await mockEvidence(page, 'ppflow', 200, EVIDENCE.ppflow);
    await mockEvidence(page, 'pepmlm', 200, EVIDENCE.pepmlm);
    const modal = await openDetailFor(page, 'PPFlow');
    const header = modal.getByText('Evidence center (computational only)');
    await header.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    check('cleanup: evidence block visible after open', await header.isVisible().catch(() => false));
    await closeModal(page);
    check('cleanup: evidence block gone after close-detail', (await page.getByText('Evidence center (computational only)').count()) === 0);
    // open PepMLM detail -> ppflow evidence must be replaced by pepmlm evidence (no ppflow SHA leaking)
    const modal2 = await openDetailFor(page, 'PepMLM');
    await page.waitForTimeout(400);
    check('cleanup: ppflow success_report SHA gone after switch', (await modal2.getByText(/success_report SHA: 8f6519/).count()) === 0);
    check('cleanup: pepmlm success_report SHA visible after switch', await modal2.getByText(/success_report SHA: 235cacd1/).isVisible().catch(() => false));
    check('cleanup: zero forbidden requests', hits.length === 0, hits.join('; '));
    await context.close();
  }

  await browser.close();

  const failed = results.filter((r) => !r.ok);
  console.log(`\n==== P33Q acceptance: ${results.length - failed.length}/${results.length} passed, ${failed.length} failed ====`);
  if (failed.length) {
    console.log('FAILED:');
    for (const r of failed) console.log(`  - ${r.name}${r.detail ? ' — ' + r.detail : ''}`);
    process.exit(1);
  }
  process.exit(0);
}

run().catch((err) => {
  console.error('P33Q acceptance script threw:', err);
  process.exit(2);
});

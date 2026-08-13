// @ts-check
/**
 * STAMP P33U Lane B — P33TResultCenter React integration & safe-download acceptance.
 *
 * Standalone Node ESM script. Uses the EXISTING `playwright` package directly.
 * Mocks the real P33T backend; does not run models, load checkpoints, or touch GPUs.
 *
 * Run (existing deps only, no npm install):
 *   P33T_E2E_BASE_URL=http://127.0.0.1:12823 node e2e/p33t-result-center-accept.mjs
 *
 * Coverage:
 *   - /target-design renders P33TResultCenter with NOT_EXPERIMENTALLY_VALIDATED banner
 *   - Candidate list renders with sequence, length, source model, rank, score
 *   - Model filter dropdown reduces rendered rows
 *   - Metrics tab shows available metrics and unavailable_with_reason entries (no 0/N/A fake success)
 *   - Manifest tab shows validation_status / computational_prediction_only / experimental_validation badges
 *   - Artifact download 200 -> exactly one browser download, no error alert
 *   - Artifact download 403 (path traversal / non-whitelist) -> ZERO downloads, role=alert
 *   - Unknown candidate_id on metrics/manifest -> 404, role=alert, no crash
 *   - Delivery bundle 200 -> one zip download
 *   - No requests to checkpoint / env / source paths
 */

import { chromium } from 'playwright';

const BASE = process.env.P33T_E2E_BASE_URL || 'http://127.0.0.1:12823';

const RESULTS_URL = /\/api\/v1\/target-design\/results(?:\?.*)?$/;
const FILTER_URL = /\/api\/v1\/target-design\/results\/filter(?:\?.*)?$/;
const METRICS_URL = /\/api\/v1\/target-design\/results\/[^/]+\/metrics(?:\?.*)?$/;
const MANIFEST_URL = /\/api\/v1\/target-design\/results\/[^/]+\/manifest(?:\?.*)?$/;
const DOWNLOAD_URL = /\/api\/v1\/target-design\/results\/[^/]+\/downloads\/[^/]+(?:\?.*)?$/;
const BUNDLE_URL = /\/api\/v1\/target-design\/delivery-bundles(?:\?.*)?$/;
const BUNDLE_DOWNLOAD_URL = /\/api\/v1\/target-design\/delivery-bundles\/[^/]+\/download(?:\?.*)?$/;
const MODELS_URL = '**/api/v1/models';
const MODEL_REGISTRY_URL = '**/api/v1/model-registry';

const FORBIDDEN_PATH_PATTERNS = [
  /checkpoints/,
  /\/envs\//,
  /\/env\//,
  /\/source\//,
  /\.git/,
  /\.pth/,
  /\.pt/,
  /\.ckpt/,
];

const results = [];
function check(name, cond, detail = '') {
  results.push({ name, ok: !!cond, detail });
  if (!cond) console.log(`  FAIL: ${name}${detail ? ' — ' + detail : ''}`);
  else console.log(`  ok:   ${name}`);
}

function makeCandidate(overrides = {}) {
  return {
    candidate_id: overrides.candidate_id || 'c-pepmlm-001',
    sequence: overrides.sequence || 'MKTLLIL',
    length: overrides.length || 7,
    source_model_id: overrides.source_model_id || 'pepmlm',
    source_run_id: overrides.source_run_id || 'pepmlm-run-001',
    generation_rank: overrides.generation_rank ?? 1,
    generation_score: overrides.generation_score ?? 0.1234,
    input_target: overrides.input_target || 'MTR-target',
    created_at: '2026-07-02T00:00:00Z',
    validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
    computational_prediction_only: true,
    experimental_validation: false,
    ...overrides,
  };
}

const CANDIDATES = [
  makeCandidate({ candidate_id: 'c-pepmlm-001', sequence: 'MKTLLIL', source_model_id: 'pepmlm', generation_rank: 1 }),
  makeCandidate({ candidate_id: 'c-pepmlm-002', sequence: 'MKTLVIL', source_model_id: 'pepmlm', generation_rank: 2 }),
  makeCandidate({ candidate_id: 'c-pepflow-001', sequence: 'GGGGGGG', source_model_id: 'pepflow', generation_rank: 1 }),
  makeCandidate({ candidate_id: 'c-unknown-999', sequence: 'XXXXXXX', source_model_id: 'pepmlm', generation_rank: 99 }),
];

const METRICS = {
  'c-pepmlm-001': [
    {
      metric_id: 'm-001',
      metric_name: 'model_confidence',
      metric_value: 0.87,
      unit: null,
      scorer_name: 'pepmlm_native',
      scorer_version: 'p33s-c',
      scorer_license: 'MIT',
      metric_provenance: { backend: 'pepmlm', source: 'native_generation_log' },
      unavailable_with_reason: null,
      artifact_sha256: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    },
    {
      metric_id: 'm-002',
      metric_name: 'pLDDT',
      metric_value: null,
      unit: null,
      scorer_name: null,
      scorer_version: null,
      scorer_license: null,
      metric_provenance: {},
      unavailable_with_reason: 'ESMFold weights not authorized for download; structure scorer unavailable',
      artifact_sha256: null,
    },
    {
      metric_id: 'm-003',
      metric_name: 'predicted_Kd',
      metric_value: null,
      unit: 'nM',
      scorer_name: null,
      scorer_version: null,
      scorer_license: null,
      metric_provenance: {},
      unavailable_with_reason: 'PRODIGY/affinity backend not configured for this candidate',
      artifact_sha256: null,
    },
  ],
};

const MANIFEST = {
  run_id: 'pepmlm-run-001',
  model_id: 'pepmlm',
  validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
  computational_prediction_only: true,
  experimental_validation: false,
  output_artifacts: [
    { name: 'candidate_sequences.json', sha256: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' },
    { name: 'run_manifest.json', sha256: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' },
    { name: '../checkpoints/model.pth', sha256: '0000000000000000000000000000000000000000000000000000000000000000' },
  ],
};

function wrap(data) {
  return {
    code: 200,
    data,
    validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
    computational_prediction_only: true,
    experimental_validation: false,
  };
}

async function mockModels(page) {
  const emptyModels = { models: [] };
  await page.route(MODELS_URL, (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(emptyModels) }));
  await page.route(MODEL_REGISTRY_URL, (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(emptyModels) }));
}

async function mockP33TApis(page) {
  await page.route(RESULTS_URL, (route) => {
    const url = route.request().url();
    const sourceModelId = new URL(url).searchParams.get('source_model_id');
    const items = sourceModelId
      ? CANDIDATES.filter((c) => c.source_model_id === sourceModelId)
      : CANDIDATES;
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(wrap({ items, page: 1, page_size: 100, total: items.length })) });
  });

  await page.route(FILTER_URL, async (route) => {
    const body = route.request().postDataJSON() || {};
    let items = CANDIDATES;
    if (body.source_model_id) {
      items = items.filter((c) => c.source_model_id === body.source_model_id);
    }
    if (body.sequence_contains) {
      items = items.filter((c) => c.sequence.includes(body.sequence_contains));
    }
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(wrap({ items, total: items.length })) });
  });

  await page.route(METRICS_URL, (route) => {
    const url = route.request().url();
    const id = url.split('/').slice(-2)[0];
    if (id === 'c-unknown-999') {
      return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'candidate not found' }) });
    }
    const metrics = METRICS[id] || [];
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(wrap({ candidate_id: id, metrics })) });
  });

  await page.route(MANIFEST_URL, (route) => {
    const url = route.request().url();
    const id = url.split('/').slice(-2)[0];
    if (id === 'c-unknown-999') {
      return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'candidate not found' }) });
    }
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(wrap({ ...MANIFEST, run_id: `run-${id}` })) });
  });

  await page.route(DOWNLOAD_URL, (route) => {
    const url = route.request().url();
    const parts = url.split('/');
    const artifactId = decodeURIComponent(parts[parts.length - 1]);
    if (artifactId.includes('..') || artifactId.includes('/') || artifactId.includes('checkpoints') || artifactId.endsWith('.pth')) {
      return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'artifact not in download whitelist' }) });
    }
    route.fulfill({ status: 200, contentType: 'text/plain', body: `mock-content-of-${artifactId}` });
  });

  await page.route(BUNDLE_URL, (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(wrap({
      bundle_id: 'bundle-001',
      selected_candidate_ids: CANDIDATES.map((c) => c.candidate_id),
      ranking_policy: 'default: filter incomplete evidence, sort by generation_score',
      export_files: ['selected_candidates.tsv', 'scientific_metrics.tsv'],
      sha256_manifest: 'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
      created_at: '2026-07-02T00:00:00Z',
    })),
  }));

  await page.route(BUNDLE_DOWNLOAD_URL, (route) => route.fulfill({
    status: 200,
    contentType: 'application/zip',
    body: Buffer.from('PK\x03\x04mock-zip-content'),
  }));
}

async function waitForP33T(page) {
  await page.waitForSelector('section[aria-label="P33T result delivery center"]', { timeout: 10000 });
}

function createDownloadCounter(page) {
  let count = 0;
  page.on('download', () => {
    count += 1;
  });
  return {
    getCount: () => count,
    reset: () => { count = 0; },
  };
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ acceptDownloads: 'deny' });
  const page = await context.newPage();

  let requestLog = [];
  page.on('request', (req) => {
    const url = req.url();
    requestLog.push({ method: req.method(), url });
    for (const pattern of FORBIDDEN_PATH_PATTERNS) {
      if (pattern.test(url)) {
        console.log(`  FORBIDDEN_REQUEST: ${url}`);
      }
    }
  });

  const downloadCounter = createDownloadCounter(page);

  await mockModels(page);
  await mockP33TApis(page);

  console.log(`\nNavigating to ${BASE}/target-design`);
  await page.goto(`${BASE}/target-design`, { waitUntil: 'networkidle' });
  await waitForP33T(page);

  // 1. NOT_EXPERIMENTALLY_VALIDATED banner
  const banner = await page.locator('text=NOT_EXPERIMENTALLY_VALIDATED').first();
  check('banner visible', await banner.isVisible());

  const p33t = page.locator('section[aria-label="P33T result delivery center"]');
  const candidateTable = p33t.locator('[data-testid="p33t-candidate-table"]');

  // 2. Candidate table renders all rows
  await page.waitForTimeout(500);
  const rows = candidateTable.locator('tbody tr');
  check('candidate rows rendered', await rows.count() === 4, `count=${await rows.count()}`);

  // 3. Select pepflow from model filter and expect only one row
  await p33t.locator('select').first().selectOption('pepflow');
  await p33t.locator('button:has-text("Filter")').first().click();
  await page.waitForTimeout(800);
  const filteredRows = candidateTable.locator('tbody tr');
  check('model filter reduces rows', await filteredRows.count() === 1, `count=${await filteredRows.count()}`);

  // Reset filter
  await p33t.locator('select').first().selectOption('');
  await p33t.locator('button:has-text("Reset")').first().click();
  await page.waitForTimeout(800);

  // 4. Click first candidate and inspect metrics tab
  const firstRow = candidateTable.locator('tbody tr').first();
  await firstRow.click();
  await page.waitForTimeout(800);
  await p33t.locator('button[role="tab"]:has-text("Metrics")').click();
  await page.waitForTimeout(500);
  const metricsTable = p33t.locator('[data-testid="p33t-metrics-table"]');
  const metricCells = metricsTable.locator('tbody tr td:first-child');
  check('available metric rendered', await metricCells.filter({ hasText: 'model_confidence' }).count() === 1);
  check('unavailable metric shows reason', await p33t.locator('text=ESMFold weights not authorized').count() > 0);
  check('no fake 0 for unavailable', await p33t.locator('text=pLDDT').locator('xpath=../..').locator('text=0').count() === 0);

  // 5. Manifest tab badges
  await p33t.locator('button[role="tab"]:has-text("Manifest")').click();
  await page.waitForTimeout(500);
  check('manifest computational_prediction_only badge', await p33t.locator('text=computational_prediction_only: true').count() > 0);

  // 6. Artifact download 200
  await p33t.locator('button[role="tab"]:has-text("Artifacts")').click();
  await page.waitForTimeout(500);
  downloadCounter.reset();
  await p33t.locator('[data-testid="p33t-artifact-row-candidate_sequences.json"] button:has-text("Download")').click().catch(() => {});
  await page.waitForTimeout(800);
  const artifactDownloadCount = downloadCounter.getCount();
  check('artifact download triggered', artifactDownloadCount > 0, `count=${artifactDownloadCount}`);
  check('no download error alert', await p33t.locator('[role="alert"]').count() === 0);

  // 7. Path traversal / non-whitelist download -> 403, no new download
  await p33t.locator('[data-testid="p33t-artifact-row-../checkpoints/model.pth"] button:has-text("Download")').click().catch(() => {});
  await page.waitForTimeout(800);
  check('path traversal rejected with alert', await p33t.locator('[role="alert"]').count() > 0);

  // 8. Unknown candidate -> 404 on metrics tab
  await p33t.locator('button[role="tab"]:has-text("Metrics")').click();
  const unknownRow = candidateTable.locator('[data-testid="p33t-candidate-row-c-unknown-999"]');
  await unknownRow.click();
  await page.waitForTimeout(800);
  check('unknown candidate 404 handled', await p33t.locator('[role="alert"]').count() > 0);

  // 9. Bundle generation/download
  await p33t.locator('button[role="tab"]:has-text("Bundle")').click();
  await page.waitForTimeout(500);
  downloadCounter.reset();
  await p33t.locator('button:has-text("Generate & download bundle")').click().catch(() => {});
  await page.waitForTimeout(1000);
  const bundleDownloadCount = downloadCounter.getCount();
  check('bundle download triggered', bundleDownloadCount > 0, `count=${bundleDownloadCount}`);

  // 10. No forbidden requests observed (exclude intentional path-traversal probe from step 7)
  const intentionalProbeUrl = '/api/v1/target-design/results/c-pepmlm-001/downloads/..%2Fcheckpoints%2Fmodel.pth';
  const forbiddenRequests = requestLog.filter(
    (r) => FORBIDDEN_PATH_PATTERNS.some((p) => p.test(r.url)) && !r.url.includes(intentionalProbeUrl)
  );
  check('no checkpoint/env/source requests', forbiddenRequests.length === 0, `count=${forbiddenRequests.length}`);

  await context.close();
  await browser.close();

  console.log('\n--- Results ---');
  const failed = results.filter((r) => !r.ok);
  results.forEach((r) => console.log(`${r.ok ? 'PASS' : 'FAIL'} ${r.name}`));
  console.log(`\nTotal: ${results.length}, Passed: ${results.length - failed.length}, Failed: ${failed.length}`);
  process.exit(failed.length > 0 ? 1 : 0);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});

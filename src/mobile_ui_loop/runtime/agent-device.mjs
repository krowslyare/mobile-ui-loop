import { createAgentDeviceClient, normalizeAgentDeviceError } from 'agent-device';
import { realpath, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const METHODS = new Set(['open', 'inspect', 'press', 'scroll', 'back', 'capture', 'stop']);

function text(value, name) {
  if (typeof value !== 'string' || !value.trim() || value.length > 1000) throw new Error(`Invalid ${name}`);
  return value;
}

function normalizedSnapshot(snapshot) {
  const { fallbackScreenshotPath, ...safe } = snapshot;
  const labelled = (snapshot.nodes ?? []).filter((node) => Boolean(node.label || node.value) && node.visibleToUser !== false);
  return {
    ...safe,
    viewport: snapshot.viewport ? [snapshot.viewport.width, snapshot.viewport.height] : [],
    controls: (snapshot.nodes ?? []).map((node) => ({
      id: node.ref, type: node.kind ?? node.type, text: node.label ?? node.value ?? '',
      rect: node.rect, disabled: node.enabled === false,
    })),
    semantic_capture_available: (snapshot.nodes ?? []).length > 0,
    semantic_ui_detail: labelled.length ? 'labelled_content' : (snapshot.nodes ?? []).length ? 'structural_only' : 'unavailable',
    labelled_node_count: labelled.length,
  };
}

export async function runAdapter(request, factory = createAgentDeviceClient) {
  const { config, method, params = {} } = request ?? {};
  if (!config || !METHODS.has(method) || !['android', 'ios'].includes(config.platform)) throw new Error('Invalid runtime request');
  const target = text(config.target, 'device target');
  const session = text(config.session, 'session');
  const app = text(config.app, 'app');
  const root = await realpath(text(config.directory, 'session directory'));
  const selection = config.platform === 'android' ? { platform: 'android', serial: target } : { platform: 'ios', udid: target };
  const client = factory({ session, cwd: root, stateDir: path.join(root, 'upstream'), lockPolicy: 'reject', lockPlatform: config.platform });
  if (method === 'open') return client.apps.open({ ...selection, app });
  if (method === 'stop') return client.sessions.close();
  if (method === 'inspect') return normalizedSnapshot(await client.capture.snapshot({ ...selection, interactiveOnly: false }));
  if (method === 'press') {
    const choices = [params.ref !== undefined, params.selector !== undefined, params.x !== undefined || params.y !== undefined].filter(Boolean).length;
    if (choices !== 1) throw new Error('Choose one ref, selector, or coordinate point');
    const point = params.x !== undefined || params.y !== undefined;
    if (point && (![params.x, params.y].every(Number.isFinite) || params.x < 0 || params.y < 0)) throw new Error('Invalid coordinate point');
    const action = point ? { x: params.x, y: params.y } : params.ref !== undefined ? { ref: text(params.ref, 'ref') } : { selector: text(params.selector, 'selector') };
    return client.interactions.press({ ...selection, ...action });
  }
  if (method === 'scroll') {
    if (!['up', 'down', 'left', 'right'].includes(params.direction)) throw new Error('Invalid scroll direction');
    return client.interactions.scroll({ ...selection, direction: params.direction, amount: 0.5 });
  }
  if (method === 'back') return client.command.back(selection);
  const filename = params.filename;
  if (typeof filename !== 'string' || !/^[a-z0-9][a-z0-9_-]{0,100}\.png$/.test(filename)) throw new Error('Invalid capture filename');
  await mkdir(path.join(root, 'captures'), { recursive: true });
  const captureDirectory = await realpath(path.join(root, 'captures'));
  if (captureDirectory !== path.join(root, 'captures')) throw new Error('Capture directory must not be a symlink');
  const destination = path.join(captureDirectory, filename);
  // Capture promptly, including transient loaders. Semantic context is sampled
  // afterwards and is explicitly not an atomic image/tree observation.
  const screenshot = await client.capture.screenshot({ path: destination, scale: 1 });
  if (path.resolve(screenshot.path) !== destination) throw new Error('Runtime returned an unexpected image path');
  let snapshot;
  try {
    snapshot = normalizedSnapshot(await client.capture.snapshot({ ...selection, interactiveOnly: false }));
  } catch {
    snapshot = { nodes: [], controls: [], viewport: [], semantic_capture_available: false, semantic_error: 'Snapshot unavailable; use the screenshot as evidence.' };
  }
  return { file: 'captures/' + filename, snapshot: { ...snapshot, metadata_timing: 'semantic context sampled after screenshot' },
    runtime: { identifiers: screenshot.identifiers, displayRotation: screenshot.displayRotation } };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  try {
    let input = '';
    for await (const chunk of process.stdin) {
      input += chunk;
      if (input.length > 1024 * 1024) throw new Error('Runtime request exceeds 1 MiB');
    }
    const result = await runAdapter(JSON.parse(input));
    process.stdout.write(JSON.stringify({ ok: true, result }) + '\n');
  } catch (error) {
    const normalized = normalizeAgentDeviceError(error);
    process.stdout.write(JSON.stringify({ ok: false, error: normalized.message,
      code: normalized.code, dispatched: error?.details?.dispatched ?? 'unknown' }) + '\n');
    process.exitCode = 1;
  }
}

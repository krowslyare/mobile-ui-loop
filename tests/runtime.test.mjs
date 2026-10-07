import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, symlink, rm } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { runAdapter } from '../src/mobile_ui_loop/runtime/agent-device.mjs';

async function fixture(t) {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'ui-loop-test-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const calls = [];
  const snapshot = { nodes: [{ ref: 'e4', label: 'Next', kind: 'button' }], viewport: { width: 390, height: 844 }, identifiers: { serial: 'emulator-5560' }, fallbackScreenshotPath: '/private/runtime.png' };
  const client = {
    apps: { open: async (input) => { calls.push(['open', input]); return { ok: true }; } },
    sessions: { close: async () => { calls.push(['close']); return {}; } },
    capture: {
      snapshot: async (input) => { calls.push(['snapshot', input]); return snapshot; },
      screenshot: async (input) => { calls.push(['screenshot', input]); return { path: input.path, identifiers: snapshot.identifiers }; },
    },
    interactions: { press: async (input) => { calls.push(['press', input]); return {}; }, scroll: async (input) => { calls.push(['scroll', input]); return {}; } },
    command: { back: async (input) => { calls.push(['back', input]); return {}; } },
  };
  const config = { directory, platform: 'android', target: 'emulator-5560', app: 'dev.example.demo', session: 'pilot' };
  const factory = (options) => { calls.push(['factory', options]); return client; };
  return { directory, config, factory, client, calls };
}

test('selected app and explicit device stay scoped to one named session', async (t) => {
  const { config, factory, calls } = await fixture(t);
  await runAdapter({ config, method: 'open' }, factory);
  assert.equal(calls[0][1].session, 'pilot');
  assert.equal(calls[0][1].lockPolicy, 'reject');
  assert.deepEqual(calls[1][1], { platform: 'android', serial: 'emulator-5560', app: 'dev.example.demo' });
});

test('inspection preserves semantic uncertainty without leaking fallback paths', async (t) => {
  const { config, factory } = await fixture(t);
  const result = await runAdapter({ config, method: 'inspect' }, factory);
  assert.deepEqual(result.viewport, [390, 844]);
  assert.equal(result.controls[0].id, 'e4');
  assert.ok(!('fallbackScreenshotPath' in result));
});

test('capture happens before tree sampling and metadata declares its timing', async (t) => {
  const { config, factory, calls } = await fixture(t);
  const result = await runAdapter({ config, method: 'capture', params: { filename: '0001-home.png' } }, factory);
  assert.equal(result.file, 'captures/0001-home.png');
  assert.equal(calls[1][0], 'screenshot');
  assert.equal(calls[2][0], 'snapshot');
  assert.match(result.snapshot.metadata_timing, /after screenshot/);
});

test('a failed semantic snapshot does not turn an existing screenshot into an empty UI claim', async (t) => {
  const { config, factory, client } = await fixture(t);
  client.capture.snapshot = async () => { throw new Error('unsupported'); };
  const result = await runAdapter({ config, method: 'capture', params: { filename: '0001-loader.png' } }, factory);
  assert.equal(result.snapshot.semantic_capture_available, false);
  assert.match(result.snapshot.semantic_error, /use the screenshot/);
});

test('invalid actions cannot invoke arbitrary methods or ambiguous points', async (t) => {
  const { config, factory, calls } = await fixture(t);
  await assert.rejects(runAdapter({ config, method: 'exec' }, factory), /Invalid runtime/);
  await assert.rejects(runAdapter({ config, method: 'press', params: { ref: 'e4', x: 1, y: 2 } }, factory), /Choose one/);
  await assert.rejects(runAdapter({ config, method: 'press', params: { x: 1 } }, factory), /Invalid coordinate/);
  assert.equal(calls.filter(([kind]) => kind === 'press').length, 0);
});

test('path traversal and capture-directory symlinks never reach the SDK', async (t) => {
  const { directory, config, factory, calls } = await fixture(t);
  await assert.rejects(runAdapter({ config, method: 'capture', params: { filename: '../device.png' } }, factory), /Invalid capture filename/);
  await mkdir(path.join(directory, 'outside'));
  await symlink(path.join(directory, 'outside'), path.join(directory, 'captures'));
  await assert.rejects(runAdapter({ config, method: 'capture', params: { filename: '0001-home.png' } }, factory), /must not be a symlink/);
  assert.equal(calls.filter(([kind]) => kind === 'screenshot').length, 0);
});

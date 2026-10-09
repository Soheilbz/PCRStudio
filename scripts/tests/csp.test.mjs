import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { configureEdge, inlineScriptHashes } from '../../ops/prepare_caddy.mjs';

const BOOT_ONE_HASH = "'sha256-Y6ks+ziXz68Es9YXAxxkwDRBk0JY2cxIvZ+tSawA5c4='";
const BOOT_TWO_HASH = "'sha256-P/D1EC+OrqwuprMcFs1aClRk6awvKWNT/2R46TuQrAY='";

test('external assets remain subject to the self policy', () => {
  for (const html of [
    '<script type="module" src="/assets/app.js"></script>',
    '<ScRiPt data-note=">" SrC="/assets/app.js">window.boot = 1;</ScRiPt>',
    '<script src="">window.boot = 1;</script>',
    '<script SRC>window.boot = 1;</script>',
  ]) assert.equal(inlineScriptHashes(html), '');
});

test('permission changes when immutable inline script contents change', () => {
  const original = inlineScriptHashes('<script>window.boot = 1;</script>');
  assert.equal(original, BOOT_ONE_HASH);
  assert.equal(inlineScriptHashes('<script>window.boot = 2;</script>'), BOOT_TWO_HASH);
  assert.equal(original, inlineScriptHashes('<script>window.boot = 1;</script><script>window.boot = 1;</script>'));
});

test('quoted attributes and mixed-case HTML tags do not change inline permissions', () => {
  assert.equal(inlineScriptHashes('<ScRiPt data-note="src=/ignored.js >" TYPE="module">window.boot = 1;</sCrIpT>'), BOOT_ONE_HASH);
});

test('script markup in comments and inert HTML does not grant permission', () => {
  const html = '<!-- <script>window.boot = 2;</script> -->' +
    '<textarea><script>window.boot = 2;</script></textarea>' +
    '<noscript><script>window.boot = 2;</script></noscript>' +
    '<template><script>window.boot = 2;</script></template>' +
    '<script>window.boot = 1;</script>';
  assert.equal(inlineScriptHashes(html), BOOT_ONE_HASH);
});

test('hashes retain exact whitespace, Unicode, entity text and JavaScript tag text', () => {
  const content = '\n  window.boot = "é &amp; 🧬";\n  // <script> is JavaScript text\n';
  assert.equal(inlineScriptHashes(`<script>${content}</script>`), "'sha256-1xCp5bw7+lst938t8y2trujNe+qycO9Wu3OxvmNblMk='");
});

test('HTML script escape states determine the complete hash input', () => {
  const html = '<script><!--<script>window.boot = 1;</script>-->window.boot = 2;</script>';
  assert.equal(inlineScriptHashes(html), "'sha256-Ia3JpBcJ7GQ0R7gUBG1uWwTvye4mmGDvLOYFhDbjYho='");
});

test('configuration requires a marker and never enables arbitrary inline scripts', () => {
  assert.throws(() => configureEdge('<script>boot()</script>', 'script-src self'), /marker is missing/);
  const configured = configureEdge('<script>boot()</script>', "script-src 'self' @@SCRIPT_HASHES@@;");
  assert.equal(configured, "script-src 'self' 'sha256-MeZS89WlF0u+o0hCvHTBt4q1WHU+U+sJKgbdRUc36mY=';");
  assert.doesNotMatch(configured, /unsafe-inline|@@SCRIPT_HASHES@@/);
});

test('the CLI fills the actual Caddy header independently of the working directory', (context) => {
  const directory = mkdtempSync(join(tmpdir(), 'pcrstudio-csp-'));
  context.after(() => rmSync(directory, { recursive: true }));
  const html = join(directory, 'index.html');
  const output = join(directory, 'Caddyfile');
  writeFileSync(html, '<!-- <script>window.boot = 2;</script> --><script data-note=">">window.boot = 1;</script><script SRC="/assets/app.js"></script>');
  const result = spawnSync(process.execPath, [
    fileURLToPath(new URL('../../ops/prepare_caddy.mjs', import.meta.url)),
    html,
    fileURLToPath(new URL('../../ops/Caddyfile', import.meta.url)),
    output,
  ], { cwd: directory, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  const configured = readFileSync(output, 'utf8');
  assert.ok(configured.includes(`script-src 'self' ${BOOT_ONE_HASH}; style-src`));
  assert.doesNotMatch(configured, /@@SCRIPT_HASHES@@/);
});

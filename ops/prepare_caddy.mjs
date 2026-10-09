/** Bind CSP permission to the exact immutable React Router shell built into this image. */
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const { parse } = createRequire(new URL('../frontend/package.json', import.meta.url))('parse5');

export function inlineScriptHashes(html) {
  const hashes = new Set();
  function visit(node) {
    if (node.tagName === 'script' && !node.attrs.some((attribute) => attribute.name === 'src')) {
      const location = node.sourceCodeLocation;
      // Hash the immutable source, without serializing or normalizing the parser's text nodes.
      const content = html.slice(location.startTag.endOffset, location.endTag?.startOffset ?? location.endOffset);
      if (content.length > 0) hashes.add(`'sha256-${createHash('sha256').update(content).digest('base64')}'`);
    }
    for (const child of node.childNodes ?? []) visit(child);
  }
  visit(parse(html, { sourceCodeLocationInfo: true }));
  return [...hashes].join(' ');
}

export function configureEdge(html, template) {
  if (!template.includes('@@SCRIPT_HASHES@@')) throw new Error('CSP script hash marker is missing');
  return template.replace('@@SCRIPT_HASHES@@', inlineScriptHashes(html));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [html, template, output] = process.argv.slice(2);
  if (!html || !template || !output) throw new Error('Expected HTML, Caddy template and output paths');
  writeFileSync(output, configureEdge(readFileSync(html, 'utf8'), readFileSync(template, 'utf8')));
}

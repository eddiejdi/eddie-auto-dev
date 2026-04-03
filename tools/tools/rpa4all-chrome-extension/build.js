#!/usr/bin/env node
/**
 * build.js — Empacota a extensão em .zip para distribuição e gera update.xml.
 *
 * Uso:
 *   node build.js [--out <dir>] [--crx-url <url>] [--update-xml <path>]
 *
 * Saídas:
 *   dist/rpa4all-autofill-<version>.zip  — pacote pronto para carregar no Chrome (Load unpacked via zip)
 *   dist/rpa4all-autofill-<version>.crx  — CRX assinado (se --pem disponível)
 *   dist/update.xml                      — Omaha update manifest
 *   dist/latest.json                     — metadados para polling no background
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { createHash } = require('crypto');
const { promisify } = require('util');
const zlib = require('zlib');

const EXT_DIR = __dirname;
const MANIFEST_PATH = path.join(EXT_DIR, 'manifest.json');

const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
const VERSION = manifest.version;
const EXT_ID = 'ekpendnmipdiphpjeopgdlnaahjdbpdh';

// ----- CLI args -----
const args = process.argv.slice(2);
function getArg(name, fallback) {
  const idx = args.indexOf(name);
  return idx !== -1 && args[idx + 1] ? args[idx + 1] : fallback;
}

const OUT_DIR = path.resolve(getArg('--out', path.join(EXT_DIR, 'dist')));
const CRX_PUBLIC_URL = getArg(
  '--crx-url',
  `https://www.rpa4all.com/extension-updates/rpa4all-autofill-${VERSION}.zip`
);
const UPDATE_XML_PATH = path.join(OUT_DIR, 'update.xml');
const LATEST_JSON_PATH = path.join(OUT_DIR, 'latest.json');
const ZIP_PATH = path.join(OUT_DIR, `rpa4all-autofill-${VERSION}.zip`);

// Files to include in the package
const INCLUDE_FILES = [
  'autofill-core.js',
  'background.js',
  'content-script.js',
  'manifest.json',
  'options.css',
  'options.html',
  'options.js',
  'popup.css',
  'popup.html',
  'popup.js',
  'sample-masses.json',
  'README.md',
];

function sha256File(filePath) {
  const buf = fs.readFileSync(filePath);
  return createHash('sha256').update(buf).digest('hex');
}

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function buildZip() {
  ensureDir(OUT_DIR);

  // Remove old zip
  if (fs.existsSync(ZIP_PATH)) {
    fs.unlinkSync(ZIP_PATH);
  }

  const files = INCLUDE_FILES.filter((f) => fs.existsSync(path.join(EXT_DIR, f)));
  const fileList = files.map((f) => path.join(EXT_DIR, f));

  const relativeFiles = files.map((f) => `"${path.join(EXT_DIR, f)}"`).join(' ');

  // Use zip if available, otherwise write a note
  try {
    execSync(`cd "${EXT_DIR}" && zip -j "${ZIP_PATH}" ${files.join(' ')}`, { stdio: 'inherit' });
    console.log(`✓ ZIP: ${ZIP_PATH}`);
  } catch {
    console.error('zip command not available; install zip and retry.');
    process.exit(1);
  }

  return ZIP_PATH;
}

function buildUpdateXml(zipPath) {
  const sha256 = sha256File(zipPath);

  const xml = `<?xml version='1.0' encoding='UTF-8'?>
<!--
  Chrome/Firefox extension auto-update manifest (Omaha protocol).
  Gerado automaticamente por build.js — versionado junto com a extensão.
  Publicar em: https://www.rpa4all.com/extension-updates/rpa4all-autofill.xml
-->
<gupdate xmlns='http://www.google.com/update2/response' protocol='2.0'>
  <app appid='${EXT_ID}'>
    <updatecheck
      codebase='${CRX_PUBLIC_URL}'
      version='${VERSION}'
      hash_sha256='${sha256}'
    />
  </app>
</gupdate>
`;
  fs.writeFileSync(UPDATE_XML_PATH, xml, 'utf8');
  console.log(`✓ update.xml: ${UPDATE_XML_PATH}`);
  return { sha256, version: VERSION, url: CRX_PUBLIC_URL };
}

function buildLatestJson(sha256) {
  const latest = {
    version: VERSION,
    url: CRX_PUBLIC_URL,
    sha256,
    released_at: new Date().toISOString(),
    update_xml: 'https://www.rpa4all.com/extension-updates/rpa4all-autofill.xml',
  };
  fs.writeFileSync(LATEST_JSON_PATH, JSON.stringify(latest, null, 2), 'utf8');
  console.log(`✓ latest.json: ${LATEST_JSON_PATH}`);
}

function main() {
  console.log(`\n📦 Building RPA4ALL Autofill Extension v${VERSION}\n`);

  const zipPath = buildZip();
  const { sha256 } = buildUpdateXml(zipPath);
  buildLatestJson(sha256);

  console.log('\n✅ Build concluído.');
  console.log(`   ZIP:        ${ZIP_PATH}`);
  console.log(`   update.xml: ${UPDATE_XML_PATH}`);
  console.log(`   latest.json:${LATEST_JSON_PATH}`);
  console.log('\nPublique os 3 arquivos em https://www.rpa4all.com/extension-updates/\n');
}

main();

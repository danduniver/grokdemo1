// demo.js - Simple zero-dep demo script (ESM)
// Run via: npm run demo   or   node demo.js

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

console.log('=== grokdemo1 demo.js ===\n');

try {
  const pkg = JSON.parse(readFileSync(path.join(__dirname, 'package.json'), 'utf8'));
  console.log(`Project: ${pkg.name} v${pkg.version}`);
  console.log(`Description: ${pkg.description}`);
} catch (e) {
  console.log('package.json not readable in this context');
}

console.log('\nGrok demo script executed successfully.');
console.log('This project is ready for you to tell Grok what to build next!');
console.log('\nExamples:');
console.log('  "Add a real xAI API chat example in the browser"');
console.log('  "Implement a small REST API with Node http"');
console.log('  "Create a design doc for feature X using the design skill"');

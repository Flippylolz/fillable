import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

const catalogs = Object.fromEntries(['uk', 'en'].map(locale => [locale, JSON.parse(fs.readFileSync(`src/locales/${locale}.json`, 'utf8'))]));
const parameters = text => [...text.matchAll(/{{\s*([^} ]+)\s*}}/g)].map(match => match[1]).sort().join(',');
const logical = key => key.replace(/_(zero|one|two|few|many|other)$/, '');
const keys = catalog => [...new Set(Object.keys(catalog).map(logical))].sort().join('\n');
if (keys(catalogs.uk) !== keys(catalogs.en)) throw new Error('Catalog key mismatch');
for (const [locale, catalog] of Object.entries(catalogs)) {
  for (const [key, value] of Object.entries(catalog)) {
    if (typeof value !== 'string' || !value.trim()) throw new Error(`Empty translation: ${locale}/${key}`);
    const base = logical(key);
    const counterpart = catalogs.uk[key] ?? catalogs.uk[`${base}_other`];
    if (parameters(value) !== parameters(counterpart)) throw new Error(`Interpolation mismatch: ${key}`);
    if (base !== key) {
      for (const category of new Intl.PluralRules(locale).resolvedOptions().pluralCategories) {
        if (!catalog[`${base}_${category}`]) throw new Error(`Missing plural: ${locale}/${base}_${category}`);
      }
    }
  }
}
function scan(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) scan(file);
    else if (/\.tsx?$/.test(file)) {
      const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
      function visit(node) {
        if (ts.isJsxText(node) && node.text.trim()) throw new Error(`Hardcoded JSX text: ${file}`);
        if (ts.isJsxAttribute(node) && /^(title|placeholder|alt|aria-label)$/.test(node.name.getText(source)) && node.initializer && ts.isStringLiteral(node.initializer)) throw new Error(`Hardcoded accessible copy: ${file}`);
        ts.forEachChild(node, visit);
      }
      visit(source);
    }
  }
}
scan('src');
console.log('Ukrainian/English catalog and JSX copy checks passed');

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const logical = key => key.replace(/_(zero|one|two|few|many|other)$/, '');
const keys = catalog => [...new Set(Object.keys(catalog).map(logical))].sort().join('\n');
function parameters(text) {
  const pattern = /{{\s*([a-zA-Z_][a-zA-Z_0-9]*)\s*}}/g;
  if (text.replace(pattern, '').match(/{{|}}/)) throw new Error('Invalid interpolation');
  return [...text.matchAll(pattern)].map(match => match[1]).sort().join(',');
}

export function validateCatalogs(catalogs) {
  if (keys(catalogs.uk) !== keys(catalogs.en)) throw new Error('Catalog key mismatch');
  for (const [locale, catalog] of Object.entries(catalogs)) {
    for (const [key, value] of Object.entries(catalog)) {
      if (typeof value !== 'string' || !value.trim()) throw new Error(`Empty translation: ${locale}/${key}`);
      const base = logical(key);
      const reference = catalogs.uk[base] ?? catalogs.uk[`${base}_other`];
      if (typeof reference !== 'string' || parameters(value) !== parameters(reference)) throw new Error(`Interpolation mismatch: ${key}`);
      if (base !== key) {
        const categories = new Intl.PluralRules(locale).resolvedOptions().pluralCategories;
        if (!categories.includes(key.slice(base.length + 1))) throw new Error(`Invalid plural: ${locale}/${key}`);
        for (const category of categories) {
          if (!catalog[`${base}_${category}`]) throw new Error(`Missing plural: ${locale}/${base}_${category}`);
        }
      }
    }
  }
}

export function validateSource(text, file = 'component.tsx') {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
  const constants = new Map();
  function collect(node) {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) constants.set(node.name.text, node.initializer);
    ts.forEachChild(node, collect);
  }
  collect(source);
  function literal(node, seen = new Set()) {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return Boolean(node.text.trim());
    if (ts.isJsxExpression(node)) return node.expression && literal(node.expression, seen);
    if (ts.isConditionalExpression(node)) return literal(node.whenTrue, seen) || literal(node.whenFalse, seen);
    if (ts.isIdentifier(node) && constants.has(node.text) && !seen.has(node.text)) {
      seen.add(node.text);
      return literal(constants.get(node.text), seen);
    }
    return false;
  }
  function visit(node) {
    if (ts.isJsxText(node) && node.text.trim()) throw new Error(`Hardcoded JSX text: ${file}`);
    if (ts.isJsxExpression(node) && (ts.isJsxElement(node.parent) || ts.isJsxFragment(node.parent)) && literal(node)) throw new Error(`Hardcoded JSX expression: ${file}`);
    if (ts.isJsxAttribute(node) && /^(title|placeholder|alt|aria-label|label|description)$/.test(node.name.getText(source)) && node.initializer && literal(node.initializer)) throw new Error(`Hardcoded accessible copy: ${file}`);
    if (ts.isBinaryExpression(node) && node.left.getText(source) === 'document.title' && literal(node.right)) throw new Error(`Hardcoded page title: ${file}`);
    if (ts.isCallExpression(node) && /^(alert|confirm|prompt|window.alert|window.confirm|window.prompt)$/.test(node.expression.getText(source)) && node.arguments[0] && literal(node.arguments[0])) throw new Error(`Hardcoded dialog: ${file}`);
    ts.forEachChild(node, visit);
  }
  visit(source);
}

function scan(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) scan(file);
    else if (/\.tsx?$/.test(file)) validateSource(fs.readFileSync(file, 'utf8'), file);
  }
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  validateCatalogs(Object.fromEntries(['uk', 'en'].map(locale => [locale, JSON.parse(fs.readFileSync(`src/locales/${locale}.json`, 'utf8'))])));
  scan('src');
  console.log('Ukrainian/English catalog and application copy checks passed');
}

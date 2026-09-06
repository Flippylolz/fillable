import test from 'node:test';
import assert from 'node:assert/strict';
import { validateCatalogs, validateSource } from './check-i18n.mjs';

const valid = () => ({ uk: { title: 'Документи', count_one: '{{count}} документ', count_few: '{{count}} документи', count_many: '{{count}} документів', count_other: '{{count}} документа' }, en: { title: 'Documents', count_one: '{{count}} document', count_other: '{{count}} documents' } });

test('valid language-specific plurals and user data rendering pass', () => {
  validateCatalogs(valid());
  validateSource("const App = ({title}) => <main><h1>{t('app.title')}</h1><p>{title}</p><button aria-label={t('save.label')}>{t('save')}</button></main>");
});
for (const [name, mutate] of [
  ['missing English', c => delete c.en.title],
  ['empty translation', c => c.en.title = ' '],
  ['missing Ukrainian plural', c => delete c.uk.count_few],
  ['invalid English plural', c => c.en.count_few = '{{count}} documents'],
  ['interpolation mismatch', c => c.uk.count_one = '{{number}} документ'],
  ['malformed interpolation', c => c.en.count_one = '{{count} document'],
  ['wrong type', c => c.uk.title = 5],
]) test(name, () => { const catalog = valid(); mutate(catalog); assert.throws(() => validateCatalogs(catalog)); });

for (const source of [
  '<p>Hardcoded text</p>', '<p>{"Hardcoded"}</p>', '<p>{`Hardcoded`}</p>',
  '<input placeholder="Hardcoded" />', '<button aria-label={"Hardcoded"}/>',
  'const title = "Hardcoded"; const App = () => <h1>{title}</h1>',
  'const App = () => <p>{ready ? "Hardcoded" : data}</p>',
  'document.title = "Hardcoded"', 'window.alert("Hardcoded")',
]) test(`rejects ${source}`, () => assert.throws(() => validateSource(source)));

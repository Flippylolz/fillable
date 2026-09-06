import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';
import uk from './locales/uk.json';
import en from './locales/en.json';

export const i18n = i18next.createInstance();
void i18n.use(initReactI18next).init({
  resources: { uk: { translation: uk }, en: { translation: en } },
  lng: 'uk', fallbackLng: 'uk', supportedLngs: ['uk', 'en'],
  keySeparator: false, interpolation: { escapeValue: false },
  initAsync: false,
});

export function setLanguage(language: string) {
  return i18n.changeLanguage(language === 'en' ? 'en' : 'uk');
}

function locale() {
  return i18n.language === 'en' ? 'en' : 'uk-UA';
}

export function formatNumber(value: number, options?: Intl.NumberFormatOptions) {
  return new Intl.NumberFormat(locale(), options).format(value);
}

export function formatDate(value: Date, options?: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat(locale(), options).format(value);
}

export function formatBytes(value: number) {
  if (value < 1000) return i18n.t('profile.bytes', { count: value, value: formatNumber(value) });
  const units = ['kilobyte', 'megabyte', 'gigabyte', 'terabyte', 'petabyte'];
  const exponent = Math.min(Math.floor(Math.log10(value) / 3), units.length);
  return formatNumber(value / 1000 ** exponent, {
    style: 'unit', unit: units[exponent - 1], unitDisplay: 'short', maximumFractionDigits: 2,
  });
}

// Website language: English + all 22 scheduled Indian languages.
//  • the visitor's choice is remembered (localStorage) and can be set by link: ?lang=hi
//  • <html lang> and dir (Urdu, Sindhi and Kashmiri read right-to-left) follow the choice
//  • t('key', {vars}) → Designer override › built-in translation › English
import { Languages } from 'lucide-react';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useSite } from '../context/SiteContext';
import { readStore, writeStore } from '../utils/storage';
import { BUILT_IN } from './strings';

const STORE = 'site:lang';
const FALLBACK_LANGS = [{ code: 'en', name: 'English', native: 'English', dir: 'ltr' }];
const I18nContext = createContext(null);

function fill(text, vars) {
  return text.replace(/\{(\w+)\}/g, (m, k) => (vars[k] !== undefined && vars[k] !== null ? String(vars[k]) : m));
}

export function I18nProvider({ children }) {
  const { brand } = useSite();
  const cfg = brand?.i18n;
  const languages = cfg?.languages?.length ? cfg.languages : FALLBACK_LANGS;
  const [chosen, setChosen] = useState(() => {
    const fromUrl = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('lang') : null;
    return fromUrl || readStore(STORE, null);
  });
  const lang = languages.some((l) => l.code === chosen) ? chosen : (cfg?.default || 'en');
  const meta = languages.find((l) => l.code === lang) || FALLBACK_LANGS[0];
  const brandName = (brand?.name || '').trim();

  useEffect(() => {
    const el = document.documentElement;
    el.lang = lang === 'en' ? 'en-IN' : `${lang}-IN`;
    el.dir = meta.dir === 'rtl' ? 'rtl' : 'ltr';
  }, [lang, meta.dir]);

  const setLang = useCallback((code) => {
    setChosen(code);
    writeStore(STORE, code);
  }, []);

  const t = useCallback((key, vars = {}) => {
    const overrides = cfg?.overrides || {};
    const look = (k) => overrides[lang]?.[k] ?? BUILT_IN[lang]?.[k] ?? overrides.en?.[k] ?? BUILT_IN.en[k];
    const all = { brand: brandName, ...vars };
    let text = look(key);
    // No brand name set yet → use the wording that doesn't need one.
    if (text && text.includes('{brand}') && !brandName) text = look(`${key}.nobrand`) ?? text.replace('{brand}', '').trim();
    return text === undefined ? key : fill(text, all);
  }, [cfg, lang, brandName]);

  const value = useMemo(() => ({ lang, setLang, t, languages, dir: meta.dir, showPicker: cfg?.picker !== false && languages.length > 1 }),
    [lang, setLang, t, languages, meta.dir, cfg?.picker]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (ctx) return ctx;
  // Outside the provider (e.g. Studio): English, no picker.
  return { lang: 'en', setLang: () => {}, t: (k, v = {}) => fill(BUILT_IN.en[k] || k, v), languages: FALLBACK_LANGS, dir: 'ltr', showPicker: false };
}

export const useT = () => useI18n().t;

/** Compact language switch for the header: globe + language code, with the phone's own native picker on tap
 *  (an invisible <select> covers the button, so screen readers and keyboards get a real, labelled select). */
export function LanguagePicker({ className }) {
  const { lang, setLang, languages, t, showPicker } = useI18n();
  if (!showPicker) return null;
  return (
    <span className={className} style={{ position: 'relative', width: 'auto', minWidth: 44, paddingInline: 8, gap: 3, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
      <Languages size={17} strokeWidth={1.5} aria-hidden="true" />
      <span aria-hidden="true" className="pv-lang-code" style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.04em" }}>{lang.toUpperCase()}</span>
      <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label={t('lang.label')}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0, cursor: 'pointer', font: 'inherit' }}>
        {languages.map((l) => <option key={l.code} value={l.code} lang={l.code}>{l.native}{l.code !== 'en' ? ` · ${l.name}` : ''}</option>)}
      </select>
    </span>
  );
}

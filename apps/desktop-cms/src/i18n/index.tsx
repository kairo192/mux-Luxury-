// ============================================================================
// CMS i18n — React Context + hooks around translations.ts.
//
// Deliberately zero-dependency. react-i18next is bigger, pulls in i18next's
// loader machinery, and we don't need any of its advanced features: the
// dictionaries are hand-written in TypeScript, there are no namespaces or
// lazy loads, and we're never going to fetch remote translation files.
//
// Public API:
//   <I18nProvider>{children}</I18nProvider>
//   const t = useT();              →  (key, vars?) => string
//   const { lang, setLang } = useLang();
//   const { dir, isRtl } = useDir();
// ============================================================================
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  DICTS,
  LANG_LABELS,
  RTL_LANGS,
  SUPPORTED_LANGS,
  interpolate,
  translateRaw,
  type Lang,
} from "./translations";

const STORAGE_KEY = "luxe_cms_lang";

function loadLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && (SUPPORTED_LANGS as string[]).includes(stored)) return stored as Lang;
  } catch { /* localStorage unavailable (private browsing) — fall through */ }
  // Prefer the browser language only when it's one we support; otherwise
  // keep the shop's French default so first-launch isn't disorienting.
  try {
    const nav = (navigator.language || "fr").slice(0, 2).toLowerCase();
    if ((SUPPORTED_LANGS as string[]).includes(nav)) return nav as Lang;
  } catch { /* SSR */ }
  return "fr";
}

interface Ctx {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<Ctx | null>(null);

export const I18nProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Lang>(() => loadLang());

  useEffect(() => {
    // Keep the <html> element's lang + dir attributes in sync so Tailwind's
    // `rtl:` variant and any CSS that reads `:lang(ar)` work globally.
    if (typeof document === "undefined") return;
    document.documentElement.lang = lang;
    document.documentElement.dir = RTL_LANGS.has(lang) ? "rtl" : "ltr";
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try { localStorage.setItem(STORAGE_KEY, l); } catch { /* ignore */ }
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) =>
      interpolate(translateRaw(lang, key), vars),
    [lang],
  );

  const value = useMemo<Ctx>(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
};

export function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    // Callers outside the provider still get something usable — the raw
    // French strings — so an isolated component rendered in a test harness
    // without the provider does not crash the page.
    return {
      lang: "fr",
      setLang: () => { /* no-op */ },
      t: (key, vars) => interpolate(DICTS.fr?.[key] ?? key, vars),
    };
  }
  return ctx;
}

export function useT(): Ctx["t"] {
  return useI18n().t;
}

export function useLang(): { lang: Lang; setLang: (l: Lang) => void } {
  const { lang, setLang } = useI18n();
  return { lang, setLang };
}

export function useDir(): { dir: "ltr" | "rtl"; isRtl: boolean } {
  const { lang } = useI18n();
  const isRtl = RTL_LANGS.has(lang);
  return { dir: isRtl ? "rtl" : "ltr", isRtl };
}

// -------------------------------------------------- LanguageToggle UI --

export const LanguageToggle: React.FC<{ className?: string }> = ({ className }) => {
  const { lang, setLang } = useLang();
  return (
    <div
      role="group"
      aria-label="Language"
      className={
        "inline-flex items-stretch rounded-xl border border-[#D4AF62]/30 overflow-hidden text-xs font-bold " +
        (className ?? "")
      }
    >
      {SUPPORTED_LANGS.map((l) => (
        <button
          key={l}
          data-lang={l}
          type="button"
          onClick={() => setLang(l)}
          className={
            "px-2.5 h-8 flex items-center justify-center min-w-[2.5rem] active:scale-95 transition " +
            (lang === l
              ? "bg-[#D4AF62] text-[#02291F]"
              : "bg-transparent text-[#E8D4A5] hover:bg-white/10")
          }
          aria-pressed={lang === l}
          title={LANG_LABELS[l]}
        >
          {l === "ar" ? "عربي" : l.toUpperCase()}
        </button>
      ))}
    </div>
  );
};

// Re-export the Lang type so callers don't have to reach into translations.ts.
export type { Lang } from "./translations";

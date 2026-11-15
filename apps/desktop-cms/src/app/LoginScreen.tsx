import React from "react";
import { LanguageToggle } from "../i18n";
import { configureApiBaseUrl } from "../api/adminClient";

interface Props {
  overlays: React.ReactNode;
  successMsg: string;
  error: string;
  loginEmail: string;
  setLoginEmail: (v: string) => void;
  loginPassword: string;
  setLoginPassword: (v: string) => void;
  handleLogin: (e: React.FormEvent) => void;
  showServerConfig: boolean;
  setShowServerConfig: (v: boolean) => void;
  serverUrl: string;
  setServerUrl: (v: string) => void;
}

/** Staff login, with the API server choice (local / VPS / custom). */
export function LoginScreen({ overlays, successMsg, error, loginEmail, setLoginEmail, loginPassword, setLoginPassword, handleLogin, showServerConfig, setShowServerConfig, serverUrl, setServerUrl }: Props) {
  return (
    <div className="min-h-screen bg-[#02291F] text-white flex items-center justify-center p-6 relative">
      <div className="absolute top-5 right-5 z-20">
        <LanguageToggle />
      </div>
      {overlays}
      <div className="max-w-md w-full bg-[#063D2E] p-8 rounded-2xl border border-[#D4AF62]/40 space-y-4 shadow-2xl">
        <form onSubmit={handleLogin} className="space-y-4">
          <div className="text-center">
            <h1 className="text-2xl font-serif text-[#D4AF62] font-bold">Mus Luxury — Desktop CMS</h1>
            <p className="text-xs text-[#E8D4A5] mt-1">Connexion Administrateur Sécurisée — Maison Mus Luxury</p>
          </div>
          {successMsg && <div className="p-3 rounded bg-emerald-800 text-xs text-white">{successMsg}</div>}
          {error && <div className="p-3 rounded bg-red-900/90 text-xs text-red-100">{error}</div>}
          <div>
            <label htmlFor="login-email" className="block text-xs font-bold mb-1">Email / Identifiant</label>
            <input id="login-email" type="email" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} required placeholder="administrateur@mus-luxury.com" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-sm" />
          </div>
          <div>
            <label htmlFor="login-password" className="block text-xs font-bold mb-1">Mot de passe</label>
            <input id="login-password" type="password" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-sm" />
          </div>
          <button type="submit" className="w-full py-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-sm hover:brightness-105 transition shadow">
            Se connecter au CMS Desktop
          </button>
        </form>

        {/* Serveur Endpoint Selector */}
        <div className="pt-3 border-t border-[#D4AF62]/20">
          <button
            type="button"
            onClick={() => setShowServerConfig(!showServerConfig)}
            className="text-[11px] text-[#E8D4A5]/70 hover:text-[#D4AF62] transition flex items-center justify-between w-full"
          >
            <span>Serveur API : <code className="text-[#D4AF62]">{serverUrl}</code></span>
            <span>{showServerConfig ? "▲ Masquer" : "⚙ Modifier"}</span>
          </button>
          {showServerConfig && (
            <div className="mt-2.5 p-3 rounded-xl bg-[#02291F] border border-[#D4AF62]/30 space-y-2 text-xs">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    const u = "http://127.0.0.1:8000/api/v1";
                    configureApiBaseUrl(u);
                    setServerUrl(u);
                  }}
                  className={`px-2.5 py-1 rounded text-[11px] font-bold transition ${serverUrl.includes("127.0.0.1") || serverUrl.includes("localhost") ? "bg-[#D4AF62] text-[#02291F]" : "bg-white/10 text-white hover:bg-white/20"}`}
                >
                  Serveur Local (127.0.0.1:8000)
                </button>
                <button
                  type="button"
                  onClick={() => {
                    const u = "https://api.mus-luxury.com/api/v1";
                    configureApiBaseUrl(u);
                    setServerUrl(u);
                  }}
                  className={`px-2.5 py-1 rounded text-[11px] font-bold transition ${serverUrl.includes("mus-luxury.com") ? "bg-[#D4AF62] text-[#02291F]" : "bg-white/10 text-white hover:bg-white/20"}`}
                >
                  VPS Cloud (mus-luxury.com)
                </button>
              </div>
              <label htmlFor="cms-api-server-url" className="block text-[11px] font-bold text-[#E8D4A5]">
                Serveur API
              </label>
              <input
                id="cms-api-server-url"
                type="text"
                value={serverUrl}
                onChange={(e) => {
                  setServerUrl(e.target.value);
                  configureApiBaseUrl(e.target.value);
                }}
                className="w-full px-2.5 py-1.5 rounded bg-[#063D2E] border border-[#D4AF62]/40 text-xs font-mono text-white"
                placeholder="https://api.mus-luxury.com/api/v1"
              />
            </div>
          )}
        </div>

        <p className="pt-4 text-[11px] text-white/50 text-center">
          Mot de passe oublié ? La réinitialisation est une opération serveur
          effectuée par l'administrateur système sur le VPS.
        </p>
      </div>
    </div>
  );
}

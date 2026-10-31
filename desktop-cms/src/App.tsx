import React, { useState } from "react";
import { DesktopCmsApi, configureApiBaseUrl } from "./api/adminClient";

// Tauri 2 Desktop CMS Entry Point:
// Enforces mandatory Administrator Authentication before unlocking the CMS workspace.
export default function App() {
  const [user, setUser] = useState<{ email: string; full_name: string; role: string } | null>(null);
  const [serverUrl, setServerUrl] = useState("https://api.musluxury.dz/api/v1");
  const [email, setEmail] = useState("admin@musluxury.dz");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      configureApiBaseUrl(serverUrl);
      const res = await DesktopCmsApi.login(email, password);
      setUser(res.user);
    } catch (err: any) {
      setError(err.message || "Échec d'authentification");
    }
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-[#02291F] text-white flex items-center justify-center p-6">
        <form onSubmit={handleLogin} className="max-w-md w-full bg-[#063D2E] p-8 rounded-2xl border border-[#D4AF62]/40 space-y-4 shadow-2xl">
          <h1 className="text-2xl font-serif text-[#D4AF62] font-bold">Mus Luxury — Desktop CMS (Tauri 2)</h1>
          <p className="text-xs text-[#E8D4A5]">Authentification administrateur obligatoire. Contrôle distant sécurisé via HTTPS.</p>
          {error && <div className="p-3 rounded bg-red-800/80 text-xs">{error}</div>}
          <div>
            <label className="block text-xs font-bold mb-1">Serveur API Backend (HTTPS)</label>
            <input value={serverUrl} onChange={(e) => setServerUrl(e.target.value)} className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-xs font-mono" />
          </div>
          <div>
            <label className="block text-xs font-bold mb-1">Email Administrateur</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-bold mb-1">Mot de passe (Argon2id / PBKDF2)</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-sm" />
          </div>
          <button type="submit" className="w-full py-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-sm">
            Se connecter au CMS Desktop
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F8F6F0] text-[#202923]">
      <header className="bg-[#02291F] text-[#D4AF62] px-6 py-3 flex justify-between items-center">
        <span>Mus Luxury Desktop CMS — Connecté en tant que {user.full_name} ({user.role})</span>
        <button onClick={() => { DesktopCmsApi.logout(); setUser(null); }} className="text-xs underline">Verrouiller / Déconnexion</button>
      </header>
    </div>
  );
}

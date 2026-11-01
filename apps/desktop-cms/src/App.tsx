import React, { useEffect, useState } from "react";
import { DesktopCmsApi, configureApiBaseUrl } from "./api/adminClient";

// Tauri 2 Desktop CMS Entry Point:
// 1. Checks GET /api/v1/admin/auth/setup-status on startup.
// 2. If NOT initialized (first-time launch), shows the One-Time Owner Provisioning Wizard:
//    - Admin name, email, password, primary WhatsApp recovery number, and secondary emergency number.
//    - Submits to POST /api/v1/admin/auth/initialize-owner, saves in PostgreSQL, and permanently locks setup.
// 3. On all subsequent runs and on ANY other PC:
//    - The backend returns is_initialized = true.
//    - The CMS directly shows the Login & Forgot Password screen.
export default function App() {
  const [serverUrl, setServerUrl] = useState("https://api.musluxury.dz/api/v1");
  const [setupRequired, setSetupRequired] = useState<boolean | null>(null);
  const [user, setUser] = useState<{ email: string; full_name: string; role: string } | null>(null);

  // Setup form fields
  const [ownerName, setOwnerName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [ownerPassword, setOwnerPassword] = useState("");
  const [ownerConfirm, setOwnerConfirm] = useState("");
  const [whatsappPhone, setWhatsappPhone] = useState("+213");
  const [emergencyPhone, setEmergencyPhone] = useState("+213");

  // Login form fields
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    configureApiBaseUrl(serverUrl);
    DesktopCmsApi.getSetupStatus()
      .then((res: any) => {
        setSetupRequired(res.requires_owner_setup);
      })
      .catch(() => {
        // Fallback to login if server is unreachable
        setSetupRequired(false);
      });
  }, [serverUrl]);

  async function handleFirstTimeSetup(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (ownerPassword !== ownerConfirm) {
      setError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    try {
      const res = await DesktopCmsApi.initializeOwner({
        full_name: ownerName,
        email: ownerEmail,
        password: ownerPassword,
        whatsapp_phone: whatsappPhone,
        emergency_phone: emergencyPhone,
      });
      setUser(res.user);
      setSetupRequired(false);
      setSuccessMsg("Propriétaire configuré avec succès ! Cet écran ne s'affichera plus jamais.");
    } catch (err: any) {
      setError(err.message || "Échec de l'initialisation du propriétaire");
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await DesktopCmsApi.login(loginEmail, loginPassword);
      setUser(res.user);
    } catch (err: any) {
      setError(err.message || "Identifiants invalides");
    }
  }

  if (setupRequired === true && !user) {
    return (
      <div className="min-h-screen bg-[#02291F] text-white flex items-center justify-center p-6">
        <form onSubmit={handleFirstTimeSetup} className="max-w-lg w-full bg-[#063D2E] p-8 rounded-2xl border-2 border-[#D4AF62] space-y-4 shadow-2xl">
          <div className="text-center">
            <span className="px-3 py-1 rounded-full bg-[#D4AF62] text-[#02291F] text-[10px] font-extrabold uppercase">
              ★ Première Ouverture — Setup Unique ★
            </span>
            <h1 className="text-2xl font-serif text-white font-bold mt-2">Configuration Initiale du Propriétaire</h1>
            <p className="text-xs text-[#E8D4A5] mt-1">
              Configurez vos accès et vos 2 numéros de secours. Après enregistrement dans la base de données, <strong>cet écran ne s'affichera plus jamais, même depuis un autre PC</strong>.
            </p>
          </div>
          {error && <div className="p-3 rounded bg-red-900/90 text-xs text-red-100">{error}</div>}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block font-bold mb-1">Nom Complet</label>
              <input value={ownerName} onChange={(e) => setOwnerName(e.target.value)} required placeholder="Mustapha Harbit" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
            </div>
            <div>
              <label className="block font-bold mb-1">Email / Identifiant</label>
              <input type="email" value={ownerEmail} onChange={(e) => setOwnerEmail(e.target.value)} required placeholder="admin@musluxury.dz" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block font-bold mb-1">Mot de passe (≥ 10 car.)</label>
              <input type="password" value={ownerPassword} onChange={(e) => setOwnerPassword(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
            </div>
            <div>
              <label className="block font-bold mb-1">Confirmer mot de passe</label>
              <input type="password" value={ownerConfirm} onChange={(e) => setOwnerConfirm(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
            </div>
          </div>
          <div className="p-3 rounded-xl bg-[#02291F]/80 border border-[#D4AF62]/30 space-y-2 text-xs">
            <p className="font-bold text-[#D4AF62]">Récupération &amp; Urgence (WhatsApp) :</p>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[11px] mb-0.5">1. WhatsApp Récupération</label>
                <input value={whatsappPhone} onChange={(e) => setWhatsappPhone(e.target.value)} required placeholder="+213 550 00 00 01" className="w-full px-2.5 py-1.5 rounded bg-[#063D2E] border border-[#D4AF62]/40 font-mono text-xs" />
              </div>
              <div>
                <label className="block text-[11px] mb-0.5">2. Numéro Secours / Urgence</label>
                <input value={emergencyPhone} onChange={(e) => setEmergencyPhone(e.target.value)} required placeholder="+213 661 00 00 02" className="w-full px-2.5 py-1.5 rounded bg-[#063D2E] border border-[#D4AF62]/40 font-mono text-xs" />
              </div>
            </div>
          </div>
          <button type="submit" className="w-full py-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-sm shadow-xl">
            Enregistrer dans PostgreSQL &amp; Verrouiller le Setup
          </button>
        </form>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-[#02291F] text-white flex items-center justify-center p-6">
        <form onSubmit={handleLogin} className="max-w-md w-full bg-[#063D2E] p-8 rounded-2xl border border-[#D4AF62]/40 space-y-4 shadow-2xl">
          <div className="text-center">
            <h1 className="text-2xl font-serif text-[#D4AF62] font-bold">Mus Luxury — Desktop CMS</h1>
            <p className="text-xs text-[#E8D4A5] mt-1">Connexion Administrateur Sécurisée (Tauri 2)</p>
          </div>
          {successMsg && <div className="p-3 rounded bg-emerald-800 text-xs text-white">{successMsg}</div>}
          {error && <div className="p-3 rounded bg-red-900/90 text-xs text-red-100">{error}</div>}
          <div>
            <label className="block text-xs font-bold mb-1">Email / Identifiant</label>
            <input type="email" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} required placeholder="admin@musluxury.dz" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-bold mb-1">Mot de passe</label>
            <input type="password" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-sm" />
          </div>
          <div className="text-right">
            <button type="button" onClick={() => alert("Utilisez l'option Récupération WhatsApp sur votre téléphone")} className="text-xs text-[#D4AF62] underline">
              Mot de passe oublié ?
            </button>
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
        <span>Mus Luxury Desktop CMS — Connecté : {user.full_name} ({user.role})</span>
        <button onClick={() => { DesktopCmsApi.logout(); setUser(null); }} className="text-xs underline">
          Déconnexion
        </button>
      </header>
    </div>
  );
}

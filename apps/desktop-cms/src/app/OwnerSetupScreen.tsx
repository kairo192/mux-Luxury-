import React from "react";
import { Sparkles } from "lucide-react";

interface Props {
  overlays: React.ReactNode;
  error: string;
  ownerName: string;
  setOwnerName: (v: string) => void;
  ownerEmail: string;
  setOwnerEmail: (v: string) => void;
  ownerPassword: string;
  setOwnerPassword: (v: string) => void;
  ownerConfirm: string;
  setOwnerConfirm: (v: string) => void;
  emergencyPhone: string;
  setEmergencyPhone: (v: string) => void;
  handleFirstTimeSetup: (e: React.FormEvent) => void;
}

/** First start: create the owner account (shown once, before any login). */
export function OwnerSetupScreen({ overlays, error, ownerName, setOwnerName, ownerEmail, setOwnerEmail, ownerPassword, setOwnerPassword, ownerConfirm, setOwnerConfirm, emergencyPhone, setEmergencyPhone, handleFirstTimeSetup }: Props) {
  return (
    <div className="min-h-screen bg-[#02291F] text-white flex items-center justify-center p-6">
      {overlays}
      <form onSubmit={handleFirstTimeSetup} className="max-w-lg w-full bg-[#063D2E] p-8 rounded-2xl border-2 border-[#D4AF62] space-y-4 shadow-2xl">
        <div className="text-center">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#D4AF62] text-[#02291F] text-[10px] font-extrabold uppercase tracking-wide">
            <Sparkles className="w-3 h-3 text-[#02291F]" />
            <span>Première Ouverture — Configuration Initiale</span>
          </span>
          <h1 className="text-2xl font-serif text-white font-bold mt-2">Accès Propriétaire &amp; Direction</h1>
          <p className="text-xs text-[#E8D4A5] mt-1">
            Configurez vos accès et vos numéros de secours. Après enregistrement sécurisé, vos accès seront verrouillés.
          </p>
        </div>
        {error && <div className="p-3 rounded bg-red-900/90 text-xs text-red-100">{error}</div>}
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <label htmlFor="owner-name" className="block font-bold mb-1">Nom Complet</label>
            <input id="owner-name" value={ownerName} onChange={(e) => setOwnerName(e.target.value)} required placeholder="Nom et Prénom" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
          </div>
          <div>
            <label htmlFor="owner-email" className="block font-bold mb-1">Email / Identifiant</label>
            <input id="owner-email" type="email" value={ownerEmail} onChange={(e) => setOwnerEmail(e.target.value)} required placeholder="administrateur@domaine.dz" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <label htmlFor="owner-password" className="block font-bold mb-1">Mot de passe (≥ 10 car.)</label>
            <input id="owner-password" type="password" autoComplete="new-password" value={ownerPassword} onChange={(e) => setOwnerPassword(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
          </div>
          <div>
            <label htmlFor="owner-confirm" className="block font-bold mb-1">Confirmer mot de passe</label>
            <input id="owner-confirm" type="password" autoComplete="new-password" value={ownerConfirm} onChange={(e) => setOwnerConfirm(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
          </div>
        </div>
        <div className="p-3 rounded-xl bg-[#02291F]/80 border border-[#D4AF62]/30 space-y-1 text-xs">
          <p className="font-bold text-[#D4AF62]">Numéro de contact :</p>
          <label htmlFor="owner-phone" className="block text-[11px] mb-0.5">Téléphone propriétaire</label>
          <input id="owner-phone" value={emergencyPhone} onChange={(e) => setEmergencyPhone(e.target.value)} required placeholder="+213 5XX XX XX XX" className="w-full px-2.5 py-1.5 rounded bg-[#063D2E] border border-[#D4AF62]/40 font-mono text-xs" />
          <p className="text-[10px] text-white/50 pt-1">
            Mot de passe oublié ? Réinitialisation via la console serveur par l'administrateur système.
          </p>
        </div>
        <button type="submit" className="w-full py-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-sm shadow-xl hover:brightness-105 transition">
          Enregistrer et Sécuriser l'Accès Administrateur
        </button>
      </form>
    </div>
  );
}

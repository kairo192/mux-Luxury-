import React, { useEffect, useState, useCallback } from "react";
import {
  Users,
  Plus,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Pencil,
  KeyRound,
  ShieldCheck,
  X,
  UserCheck,
  UserX,
} from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";
import { useT } from "../i18n";
import { serverDate } from "../utils/serverDate";

interface Role {
  id: number;
  name: string;
  description: string;
  permissions: string[];
}
interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  phone?: string | null;
  is_active: number | boolean;
  last_login_at?: string | null;
  role_id: number;
  role_name: string;
}

const ROLE_LABEL: Record<string, string> = {
  super_admin: "Propriétaire / Super Admin",
  admin: "Administrateur",
  product_manager: "Gestion produits",
  order_manager: "Gestion commandes",
  inventory_manager: "Gestion stock",
  cashier: "Caissier",
  readonly: "Lecture seule",
};
const roleLabel = (n: string) => ROLE_LABEL[n] || n;

export const UsersRolesPage: React.FC = () => {
  const t = useT();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<any | null>(null);
  const [pwTarget, setPwTarget] = useState<AdminUser | null>(null);
  const [pwValue, setPwValue] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [u, r] = await Promise.all([DesktopCmsApi.listUsers(), DesktopCmsApi.listRoles()]);
      setUsers(u.items || []);
      setRoles(r.items || []);
      setError(null);
    } catch (e: any) {
      setError(e?.userMessage || "Chargement impossible");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const flash = (m: string) => {
    setSuccess(m);
    setError(null);
    setTimeout(() => setSuccess(null), 4000);
  };

  const openCreate = () =>
    setForm({ id: null, email: "", full_name: "", phone: "", role_id: roles.find((r) => r.name === "cashier")?.id || roles[0]?.id, password: "" });
  const openEdit = (u: AdminUser) =>
    setForm({ id: u.id, email: u.email, full_name: u.full_name, phone: u.phone || "", role_id: u.role_id, password: "" });

  const save = async () => {
    if (!form) return;
    setBusy(true);
    setError(null);
    try {
      if (form.id === null) {
        if (form.password.length < 10) {
          setBusy(false);
          return setError("Le mot de passe doit contenir au moins 10 caractères");
        }
        await DesktopCmsApi.createUser({
          email: form.email.trim(),
          full_name: form.full_name.trim(),
          phone: form.phone.trim() || null,
          role_id: Number(form.role_id),
          password: form.password,
        });
        flash(t("users_roles.flash_created"));
      } else {
        await DesktopCmsApi.updateUser(form.id, {
          full_name: form.full_name.trim(),
          phone: form.phone.trim() || null,
          role_id: Number(form.role_id),
        });
        flash(t("users_roles.flash_updated"));
      }
      setForm(null);
      load();
    } catch (e: any) {
      setError(e?.userMessage || "Enregistrement refusé");
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async (u: AdminUser) => {
    setBusy(true);
    try {
      await DesktopCmsApi.updateUser(u.id, { is_active: !(u.is_active === 1 || u.is_active === true) });
      flash(u.is_active ? "Compte désactivé" : "Compte réactivé");
      load();
    } catch (e: any) {
      setError(e?.userMessage || "Action refusée");
    } finally {
      setBusy(false);
    }
  };

  const resetPw = async () => {
    if (!pwTarget) return;
    if (pwValue.length < 10) return setError("Le mot de passe doit contenir au moins 10 caractères");
    setBusy(true);
    try {
      await DesktopCmsApi.resetUserPassword(pwTarget.id, pwValue);
      flash(t("users_roles.flash_password"));
      setPwTarget(null);
      setPwValue("");
    } catch (e: any) {
      setError(e?.userMessage || "Réinitialisation refusée");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4 text-sm">
      {error && (
        <div className="p-4 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" /> {error}
        </div>
      )}
      {success && (
        <div className="p-4 rounded-2xl bg-emerald-50 border-2 border-emerald-200 text-emerald-800 font-bold flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 shrink-0" /> {success}
        </div>
      )}

      <div className="bg-white p-5 rounded-3xl border border-[#D4AF62]/40 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
            <Users className="w-5 h-5" /> {t("users_roles.title")}
          </h3>
          <p className="text-gray-500 mt-1">Créez des comptes employés (caissier, gestionnaire…). Les permissions sont appliquées côté serveur.</p>
        </div>
        <div className="flex gap-2">
          <button aria-label="Actualiser" type="button" onClick={load} className="h-12 w-12 rounded-2xl border-2 border-gray-200 flex items-center justify-center text-gray-500 active:scale-95">
            <RefreshCw className="w-5 h-5" />
          </button>
          <button type="button" onClick={openCreate} className="h-12 px-5 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
            <Plus className="w-5 h-5" /> {t("users_roles.btn_new")}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin mr-2" /> {t("users_roles.loading")}
        </div>
      ) : users.length === 0 ? (
        <div className="bg-white p-10 rounded-3xl border border-gray-200 text-center text-gray-400">{t("users_roles.empty")}</div>
      ) : (
        <div className="bg-white rounded-3xl border border-gray-200 overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-[#063D2E] text-[#E8D4A5] text-xs uppercase">
              <tr>
                <th className="px-4 py-3">{t("users_roles.th_user")}</th>
                <th className="px-4 py-3">{t("users_roles.th_role")}</th>
                <th className="px-4 py-3">{t("users_roles.th_status")}</th>
                <th className="px-4 py-3 hidden md:table-cell">Dernière connexion</th>
                <th className="px-4 py-3 text-right">{t("users_roles.th_actions")}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const active = u.is_active === 1 || u.is_active === true;
                return (
                  <tr key={u.id} className="border-t border-gray-100">
                    <td className="px-4 py-3">
                      <div className="font-bold text-[#063D2E]">{u.full_name}</div>
                      <div className="text-gray-500 font-mono text-[11px]">{u.email}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 rounded-lg text-xs font-bold bg-[#D4AF62]/15 text-[#7a5c16]">{roleLabel(u.role_name)}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-lg text-xs font-bold ${active ? "bg-emerald-100 text-emerald-700" : "bg-gray-200 text-gray-500"}`}>
                        {active ? t("users_roles.active") : t("users_roles.inactive")}
                      </span>
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell text-gray-500 text-[11px]">
                      {u.last_login_at ? serverDate(u.last_login_at).toLocaleString("fr-FR") : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1.5">
                        <button type="button" onClick={() => openEdit(u)} title="Modifier" className="h-10 w-10 rounded-xl border-2 border-gray-200 flex items-center justify-center text-gray-500 active:scale-95">
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button type="button" onClick={() => setPwTarget(u)} title="Réinitialiser le mot de passe" className="h-10 w-10 rounded-xl border-2 border-gray-200 flex items-center justify-center text-gray-500 active:scale-95">
                          <KeyRound className="w-4 h-4" />
                        </button>
                        <button type="button" disabled={busy} onClick={() => toggleActive(u)} title={active ? "Désactiver" : "Réactiver"} className={`h-10 w-10 rounded-xl border-2 flex items-center justify-center active:scale-95 ${active ? "border-red-200 text-red-500" : "border-emerald-200 text-emerald-600"}`}>
                          {active ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ROLES REFERENCE */}
      <div className="bg-white p-4 rounded-3xl border border-gray-200">
        <h4 className="font-bold text-[#063D2E] mb-3 flex items-center gap-2">
          <ShieldCheck className="w-5 h-5" /> Rôles & permissions
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {roles.map((r) => (
            <div key={r.id} className="p-3 rounded-2xl border border-gray-100 bg-[#FCFBF8]">
              <div className="font-bold text-[#063D2E]">{roleLabel(r.name)}</div>
              <div className="text-gray-500 text-[11px] mb-1">{r.description}</div>
              <div className="flex flex-wrap gap-1">
                {r.permissions.length === 0 && <span className="text-gray-400 text-[11px]">—</span>}
                {r.permissions.map((p) => (
                  <span key={p} className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 font-mono text-[10px]">{p}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* CREATE/EDIT MODAL */}
      {form && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setForm(null)}>
          <div className="bg-white rounded-3xl w-full max-w-md max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <h3 className="font-serif font-bold text-[#063D2E] text-lg">{form.id === null ? t("users_roles.modal_new_title") : t("users_roles.modal_edit_title")}</h3>
              <button aria-label="Fermer" type="button" onClick={() => setForm(null)} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-5 space-y-3">
              <Field label={t("users_roles.lbl_fullname")}>
                <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] outline-none" />
              </Field>
              <Field label={t("users_roles.lbl_email")}>
                <input
                  value={form.email}
                  disabled={form.id !== null}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono disabled:opacity-60"
                  placeholder="caissier@mus-luxury.com"
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label={t("users_roles.lbl_phone")}>
                  <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono" placeholder="+213…" />
                </Field>
                <Field label={t("users_roles.lbl_role")}>
                  <select value={form.role_id} onChange={(e) => setForm({ ...form, role_id: e.target.value })} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 bg-white">
                    {roles.map((r) => (
                      <option key={r.id} value={r.id}>{roleLabel(r.name)}</option>
                    ))}
                  </select>
                </Field>
              </div>
              {form.id === null && (
                <Field label={t("users_roles.lbl_password")}>
                  <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200" />
                </Field>
              )}
              {error && (
                <div role="alert" className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm font-bold">{error}</div>
              )}
              <button type="button" disabled={busy} onClick={save} className="w-full h-14 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-base disabled:opacity-50 active:scale-[0.99]">
                {t("users_roles.btn_save")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RESET PASSWORD MODAL */}
      {pwTarget && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setPwTarget(null)}>
          <div className="bg-white rounded-3xl w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <h3 className="font-serif font-bold text-[#063D2E] text-lg">{t("users_roles.modal_pw_title")}</h3>
              <button aria-label="Fermer" type="button" onClick={() => setPwTarget(null)} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-5 space-y-3">
              <p className="text-gray-500">{pwTarget.full_name} — <span className="font-mono">{pwTarget.email}</span></p>
              <input type="password" value={pwValue} onChange={(e) => setPwValue(e.target.value)} placeholder="Nouveau mot de passe (min. 10)" className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200" />
              {error && (
                <div role="alert" className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm font-bold">{error}</div>
              )}
              <button type="button" disabled={busy} onClick={resetPw} className="w-full h-12 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold disabled:opacity-50 active:scale-95">
                {t("users_roles.modal_pw_title")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const Field: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <label className="block">
    <span className="block font-bold text-[#063D2E] mb-1 text-xs uppercase tracking-wide">{label}</span>
    {children}
  </label>
);

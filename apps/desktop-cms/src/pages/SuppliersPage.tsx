import React, { useEffect, useState, useCallback } from "react";
import {
  Truck,
  Plus,
  RefreshCw,
  Pencil,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  X,
  Phone,
  Mail,
  Package,
  Wallet,
  Archive,
} from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";
import { confirmClientAction } from "../utils/clientNotifier";
import { useT } from "../i18n";
import { serverDate } from "../utils/serverDate";
import { tr } from "../i18n/translations";

const fmt = (dzd: number) => `${Number(dzd || 0).toLocaleString("fr-DZ")} DA`;

interface Supplier {
  id: number;
  name: string;
  company_name?: string | null;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  tax_id?: string | null;
  notes?: string | null;
  is_active: number | boolean;
  purchase_orders_count?: number;
  total_purchased_dzd?: number;
  outstanding_dzd?: number;
}

export const SuppliersPage: React.FC = () => {
  const t = useT();
  const [items, setItems] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<any | null>(null);
  const [detail, setDetail] = useState<any | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await DesktopCmsApi.listSuppliers();
      setItems(d.items || []);
      setError(null);
    } catch (e: any) {
      setError(e?.userMessage || t("misc.load_failed"));
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
    setTimeout(() => setSuccess(null), 3500);
  };

  const openDetail = async (s: Supplier) => {
    try {
      setDetail(await DesktopCmsApi.getSupplier(s.id));
    } catch (e: any) {
      setError(e?.userMessage || t("misc.detail_failed"));
    }
  };

  const save = async () => {
    if (!form) return;
    if (!form.name.trim()) return setError(t("suppliers.name_required"));
    setBusy(true);
    setError(null);
    try {
      const payload = {
        name: form.name.trim(),
        company_name: form.company_name.trim() || null,
        contact_person: form.contact_person.trim() || null,
        phone: form.phone.trim() || null,
        email: form.email.trim() || null,
        address: form.address.trim() || null,
        tax_id: form.tax_id.trim() || null,
        notes: form.notes.trim() || null,
      };
      if (form.id === null) {
        await DesktopCmsApi.createSupplier(payload);
        flash(t("suppliers.created_flash"));
      } else {
        await DesktopCmsApi.updateSupplier(form.id, payload);
        flash(t("suppliers.updated_flash"));
      }
      setForm(null);
      load();
    } catch (e: any) {
      setError(e?.userMessage || t("misc.save_refused"));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (s: Supplier) => {
    const confirmed = await confirmClientAction({
      title: t("common.delete"),
      message: t("suppliers.delete_confirm", { name: s.name }),
      danger: true,
    });
    if (!confirmed) return;
    setBusy(true);
    try {
      await DesktopCmsApi.deleteSupplier(s.id);
      flash(t("suppliers.deleted_flash"));
      load();
    } catch (e: any) {
      setError(e?.userMessage || t("misc.delete_refused"));
    } finally {
      setBusy(false);
    }
  };

  const edit = (s: Supplier) =>
    setForm({
      id: s.id,
      name: s.name,
      company_name: s.company_name || "",
      contact_person: s.contact_person || "",
      phone: s.phone || "",
      email: s.email || "",
      address: s.address || "",
      tax_id: s.tax_id || "",
      notes: s.notes || "",
    });

  const openCreate = () =>
    setForm({ id: null, name: "", company_name: "", contact_person: "", phone: "", email: "", address: "", tax_id: "", notes: "" });

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
            <Truck className="w-5 h-5" /> {t("suppliers.title")}
          </h3>
          <p className="text-gray-500 mt-1">{t("suppliers.subtitle")}</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={load} className="h-12 w-12 rounded-2xl border-2 border-gray-200 flex items-center justify-center text-gray-500 active:scale-95" title={t("common.refresh")}>
            <RefreshCw className="w-5 h-5" />
          </button>
          <button type="button" onClick={openCreate} className="h-12 px-5 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
            <Plus className="w-5 h-5" /> {t("suppliers.new_supplier")}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin mr-2 rtl:mr-0 rtl:ml-2" /> {t("status.loading")}
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white p-10 rounded-3xl border border-gray-200 text-center text-gray-400">
          {t("suppliers.empty")}
        </div>
      ) : (
        <div className="bg-white rounded-3xl border border-gray-200 overflow-hidden">
          <table className="w-full text-start">
            <thead className="bg-[#063D2E] text-[#E8D4A5] text-xs uppercase">
              <tr>
                <th className="px-4 py-3 text-start">{t("suppliers.table_supplier")}</th>
                <th className="px-4 py-3 hidden md:table-cell text-start">{t("suppliers.table_contact")}</th>
                <th className="px-4 py-3 text-end">{t("suppliers.table_purchases")}</th>
                <th className="px-4 py-3 text-end">{t("suppliers.table_outstanding")}</th>
                <th className="px-4 py-3 text-end">{t("suppliers.table_actions")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => {
                const active = s.is_active === 1 || s.is_active === true;
                return (
                  <tr key={s.id} className={`border-t border-gray-100 hover:bg-[#FCFBF8] cursor-pointer ${!active ? "opacity-60" : ""}`} onClick={() => openDetail(s)}>
                    <td className="px-4 py-3 text-start">
                      <div className="font-bold text-[#063D2E] flex items-center gap-2">
                        {s.name}{(s.is_active === 0 || s.is_active === false) && <span className="ms-2 px-1.5 py-0.5 rounded bg-gray-200 text-gray-600 text-[10px] font-bold">{t("misc.archived")}</span>}
                        {!active && <span className="text-[10px] font-bold text-gray-500 bg-gray-200 px-1.5 py-0.5 rounded"><Archive className="w-3 h-3 inline mr-1 rtl:mr-0 rtl:ml-1" /> {t("suppliers.archived")}</span>}
                      </div>
                      {s.company_name && <div className="text-gray-500 text-[11px]">{s.company_name}</div>}
                      {s.tax_id && <div className="text-gray-400 font-mono text-[11px]">NIF: {s.tax_id}</div>}
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell text-start text-gray-500">
                      {s.contact_person && <div>{s.contact_person}</div>}
                      {s.phone && <div className="font-mono text-[11px]">{s.phone}</div>}
                    </td>
                    <td className="px-4 py-3 text-end">
                      <div className="font-mono font-bold">{fmt(s.total_purchased_dzd || 0)}</div>
                      <div className="text-[11px] text-gray-400">{t("suppliers.po_count", { count: s.purchase_orders_count || 0 })}</div>
                    </td>
                    <td className="px-4 py-3 text-end">
                      <span className={`font-mono font-bold ${(s.outstanding_dzd || 0) > 0 ? "text-amber-700" : "text-gray-400"}`}>
                        {(s.outstanding_dzd || 0) > 0 ? fmt(s.outstanding_dzd || 0) : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-end" onClick={(e) => e.stopPropagation()}>
                      <div className="flex gap-1.5 justify-end">
                        <button type="button" onClick={() => edit(s)} className="h-10 w-10 rounded-xl border-2 border-gray-200 inline-flex items-center justify-center text-gray-500 active:scale-95" title={t("common.edit")}>
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button type="button" onClick={() => remove(s)} className="h-10 w-10 rounded-xl border-2 border-red-200 inline-flex items-center justify-center text-red-500 active:scale-95" title={t("common.delete")}>
                          <Trash2 className="w-4 h-4" />
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

      {/* DETAIL MODAL */}
      {detail && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setDetail(null)}>
          <div className="bg-white rounded-3xl w-full max-w-lg max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <div>
                <h3 className="font-serif font-bold text-[#063D2E] text-lg">{detail.name}</h3>
                <div className="text-gray-500 text-[11px] flex items-center gap-3 flex-wrap">
                  {detail.contact_person && <span>{detail.contact_person}</span>}
                  {detail.phone && <span className="flex items-center gap-1 font-mono"><Phone className="w-3 h-3" /> {detail.phone}</span>}
                  {detail.email && <span className="flex items-center gap-1 font-mono"><Mail className="w-3 h-3" /> {detail.email}</span>}
                </div>
              </div>
              <button aria-label={tr("ui.close")} type="button" onClick={() => setDetail(null)} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <Kpi icon={Package} label={t("suppliers.kpi_orders")} value={String(detail.stats.purchase_orders_count)} sub={t("suppliers.kpi_orders_sub")} />
                <Kpi icon={Wallet} label={t("suppliers.kpi_purchased")} value={fmt(detail.stats.total_purchased_dzd)} sub={t("suppliers.kpi_purchased_sub")} />
                <Kpi icon={Wallet} label={t("suppliers.kpi_outstanding")} value={fmt(detail.stats.outstanding_dzd)} sub={t("suppliers.kpi_outstanding_sub")} accent={detail.stats.outstanding_dzd > 0} />
              </div>
              {detail.notes && <div className="p-3 rounded-2xl bg-[#F5F3EE] text-gray-600">{detail.notes}</div>}
              <div>
                <h4 className="font-bold text-[#063D2E] mb-2">{t("suppliers.recent_pos")}</h4>
                <div className="space-y-1 max-h-60 overflow-auto">
                  {detail.recent_purchase_orders.length === 0 && <div className="text-gray-400">{t("suppliers.no_pos")}</div>}
                  {detail.recent_purchase_orders.map((po: any) => {
                    const owed = (po.total_cost_dzd || 0) - (po.paid_amount_dzd || 0);
                    return (
                      <div key={po.id} className="flex items-center justify-between p-2 rounded-xl border border-gray-100">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold">{po.reference}</span>
                          <span className="text-[10px] font-bold text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">{po.status}</span>
                          <span className="text-[11px] text-gray-400">{serverDate(po.created_at).toLocaleDateString("fr-FR")}</span>
                        </div>
                        <div className="text-end">
                          <div className="font-mono font-bold">{fmt(po.total_cost_dzd)}</div>
                          {owed > 0 && <div className="text-[11px] text-amber-700 font-mono">{t("suppliers.due_amount", { amount: fmt(owed) })}</div>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CREATE/EDIT MODAL */}
      {form && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setForm(null)}>
          <div className="bg-white rounded-3xl w-full max-w-md max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <h3 className="font-serif font-bold text-[#063D2E] text-lg">{form.id === null ? t("suppliers.new_supplier") : t("suppliers.edit_supplier")}</h3>
              <button aria-label={tr("ui.close")} type="button" onClick={() => setForm(null)} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-5 space-y-3">
              <Input label={t("suppliers.field_name")} value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
              <div className="grid grid-cols-2 gap-3">
                <Input label={t("suppliers.field_company")} value={form.company_name} onChange={(v) => setForm({ ...form, company_name: v })} />
                <Input label={t("suppliers.field_contact_person")} value={form.contact_person} onChange={(v) => setForm({ ...form, contact_person: v })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Input label={t("suppliers.field_phone")} value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} mono />
                <Input label={t("suppliers.field_email")} value={form.email} onChange={(v) => setForm({ ...form, email: v })} mono />
              </div>
              <Input label={t("suppliers.field_address")} value={form.address} onChange={(v) => setForm({ ...form, address: v })} />
              <Input label={t("suppliers.field_tax_id")} value={form.tax_id} onChange={(v) => setForm({ ...form, tax_id: v })} mono />
              <label className="block">
                <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">{t("suppliers.field_notes")}</span>
                <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={2} className="w-full px-3 py-2 rounded-2xl border-2 border-gray-200" />
              </label>
              <button type="button" disabled={busy} onClick={save} className="w-full h-14 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-base disabled:opacity-50 active:scale-[0.99]">
                {form.id === null ? t("common.create") : t("common.save")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const Input: React.FC<{ label: string; value: string; onChange: (v: string) => void; mono?: boolean }> = ({ label, value, onChange, mono }) => (
  <label className="block">
    <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">{label}</span>
    <input value={value} onChange={(e) => onChange(e.target.value)} className={`w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] outline-none ${mono ? "font-mono" : ""}`} />
  </label>
);

const Kpi: React.FC<{ icon: any; label: string; value: string; sub: string; accent?: boolean }> = ({ icon: Icon, label, value, sub, accent }) => (
  <div className={`p-3 rounded-2xl border text-center ${accent ? "border-amber-300 bg-amber-50" : "border-gray-200"}`}>
    <div className="flex items-center justify-center gap-1 text-gray-500 text-[11px] font-bold uppercase"><Icon className="w-3.5 h-3.5" /> {label}</div>
    <div className={`text-base font-extrabold font-mono tabular-nums mt-0.5 ${accent ? "text-amber-700" : "text-[#063D2E]"}`}>{value}</div>
    <div className="text-[10px] text-gray-400">{sub}</div>
  </div>
);

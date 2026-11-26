import React, { useEffect, useState, useCallback } from "react";
import {
  Users,
  Search,
  Plus,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  X,
  Store,
  Globe,
  Phone,
  Mail,
  Pencil,
} from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";
import { useT } from "../i18n";
import { serverDate } from "../utils/serverDate";

const fmt = (dzd: number) => `${Number(dzd || 0).toLocaleString("fr-DZ")} DA`;

interface Customer {
  id: number;
  full_name: string;
  phone: string;
  email?: string | null;
  wilaya_code?: string;
  commune?: string;
  orders_count?: number;
  total_spent_dzd?: number;
  notes?: string | null;
}

export const CustomersPage: React.FC = () => {
  const t = useT();
  const [customers, setCustomers] = useState<Customer[]>([]);
  // Whole list = best customers first, 200 at a time; null while searching.
  const [totalCustomers, setTotalCustomers] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [detail, setDetail] = useState<any | null>(null);
  const [form, setForm] = useState<any | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await DesktopCmsApi.listCustomers();
      setCustomers(d.items || []);
      setTotalCustomers(typeof d.total === "number" ? d.total : null);
      setError(null);
    } catch (e: any) {
      setError(e?.userMessage || t("cust.load_failed"));
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

  const runSearch = async () => {
    if (!query.trim()) return load();
    setLoading(true);
    try {
      const d = await DesktopCmsApi.searchCustomers(query.trim());
      setCustomers(d.items || []);
      setTotalCustomers(null);
    } catch (e: any) {
      setError(e?.userMessage || t("cust.search_failed"));
    } finally {
      setLoading(false);
    }
  };

  const loadMore = async () => {
    setBusy(true);
    try {
      const d = await DesktopCmsApi.listCustomers(customers.length);
      setCustomers((prev) => [...prev, ...(d.items || [])]);
      if (typeof d.total === "number") setTotalCustomers(d.total);
    } catch (e: any) {
      setError(e?.userMessage || t("cust.load_failed"));
    } finally {
      setBusy(false);
    }
  };

  const openDetail = async (c: Customer) => {
    try {
      setDetail(await DesktopCmsApi.getCustomer(c.id));
    } catch (e: any) {
      setError(e?.userMessage || t("cust.detail_failed"));
    }
  };

  const save = async () => {
    if (!form) return;
    if (!form.full_name.trim() || (form.id === null && !form.phone.trim())) return setError(t("customers.form_name_required"));
    setBusy(true);
    setError(null);
    try {
      if (form.id === null) {
        await DesktopCmsApi.createCustomer({
          full_name: form.full_name.trim(),
          phone: form.phone.trim(),
          email: form.email.trim() || null,
          notes: form.notes.trim() || null,
        });
        flash(t("customers.flash_created"));
      } else {
        await DesktopCmsApi.updateCustomer(form.id, {
          full_name: form.full_name.trim(),
          email: form.email.trim() || null,
          notes: form.notes.trim() || null,
        });
        flash(t("customers.flash_updated"));
      }
      setForm(null);
      load();
    } catch (e: any) {
      setError(e?.userMessage || t("cust.save_refused"));
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
        <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
          <Users className="w-5 h-5" /> {t("customers.title")}
        </h3>
        <div className="flex gap-2 flex-1 md:flex-none">
          <div className="flex gap-2 flex-1">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runSearch()}
              placeholder={t("customers.search_placeholder")}
              className="flex-1 md:w-64 h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] outline-none"
            />
            <button aria-label="Rechercher" type="button" onClick={runSearch} className="h-12 px-4 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
              <Search className="w-5 h-5" />
            </button>
          </div>
          <button type="button" onClick={() => setForm({ id: null, full_name: "", phone: "", email: "", notes: "" })} className="h-12 px-4 rounded-2xl bg-[#D4AF62] text-[#02291F] font-bold flex items-center gap-2 active:scale-95">
            <Plus className="w-5 h-5" /> {t("customers.btn_new")}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin mr-2" /> {t("customers.loading")}
        </div>
      ) : customers.length === 0 ? (
        <div className="bg-white p-10 rounded-3xl border border-gray-200 text-center text-gray-400">{t("customers.empty")}</div>
      ) : (
        <div className="bg-white rounded-3xl border border-gray-200 overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-[#063D2E] text-[#E8D4A5] text-xs uppercase">
              <tr>
                <th className="px-4 py-3">{t("customers.th_customer")}</th>
                <th className="px-4 py-3 hidden md:table-cell">{t("customers.th_contact")}</th>
                <th className="px-4 py-3 text-right">{t("customers.th_spent")}</th>
                <th className="px-4 py-3 text-right">{t("customers.th_actions")}</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((c) => (
                <tr key={c.id} className="border-t border-gray-100 hover:bg-[#FCFBF8] cursor-pointer" onClick={() => openDetail(c)}>
                  <td className="px-4 py-3">
                    <div className="font-bold text-[#063D2E]">{c.full_name}</div>
                    <div className="text-gray-500 font-mono text-[11px]">{c.phone}</div>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell text-gray-500">
                    {c.email || "—"}
                    {c.commune ? <span className="text-[11px]"> · {c.commune}</span> : ""}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold">{fmt(c.total_spent_dzd || 0)}</td>
                  <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                    <button aria-label="Modifier" type="button" onClick={() => setForm({ id: c.id, full_name: c.full_name, phone: c.phone, email: c.email || "", notes: c.notes || "" })} className="h-10 w-10 rounded-xl border-2 border-gray-200 inline-flex items-center justify-center text-gray-500 active:scale-95">
                      <Pencil className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {totalCustomers !== null && totalCustomers > customers.length && (
            <div className="flex items-center justify-between gap-3 px-4 py-3 border-t border-gray-100 text-sm text-gray-500">
              <span>{t("customers.shown_of").replace("{shown}", String(customers.length)).replace("{total}", String(totalCustomers))}</span>
              <button type="button" disabled={busy} onClick={loadMore} className="h-10 px-4 rounded-xl border-2 border-[#063D2E] text-[#063D2E] font-bold active:scale-95 disabled:opacity-50">
                {t("customers.show_more")}
              </button>
            </div>
          )}
        </div>
      )}

      {/* DETAIL MODAL */}
      {detail && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setDetail(null)}>
          <div className="bg-white rounded-3xl w-full max-w-lg max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <div>
                <h3 className="font-serif font-bold text-[#063D2E] text-lg">{detail.full_name}</h3>
                <div className="text-gray-500 font-mono text-[11px] flex items-center gap-3">
                  <span className="flex items-center gap-1"><Phone className="w-3 h-3" /> {detail.phone}</span>
                  {detail.email && <span className="flex items-center gap-1"><Mail className="w-3 h-3" /> {detail.email}</span>}
                </div>
              </div>
              <button aria-label="Fermer" type="button" onClick={() => setDetail(null)} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <Kpi icon={Globe} label={t("cust.online")} value={fmt(detail.totals.online_spent_dzd)} sub={t("cust.orders_short", { n: detail.totals.online_orders })} />
                <Kpi icon={Store} label={t("cust.shop")} value={fmt(detail.totals.in_store_spent_dzd)} sub={t("cust.sales_n", { n: detail.totals.in_store_sales })} />
                <Kpi icon={Users} label={t("cust.total")} value={fmt(detail.totals.combined_spent_dzd)} sub={t("cust.cumulated")} accent />
              </div>
              {detail.notes && <div className="p-3 rounded-2xl bg-[#F5F3EE] text-gray-600">{detail.notes}</div>}
              <div>
                <h4 className="font-bold text-[#063D2E] mb-2">{t("cust.history")}</h4>
                <div className="space-y-1 max-h-72 overflow-auto">
                  {detail.history.length === 0 && <div className="text-gray-400">{t("cust.no_purchase")}</div>}
                  {detail.history.map((h: any, i: number) => (
                    <div key={i} className="flex items-center justify-between p-2 rounded-xl border border-gray-100">
                      <div className="flex items-center gap-2">
                        {h.channel === "online" ? <Globe className="w-4 h-4 text-sky-600" /> : <Store className="w-4 h-4 text-[#7a5c16]" />}
                        <span className="font-mono font-bold">{h.reference}</span>
                        <span className="text-[11px] text-gray-400">{serverDate(h.created_at).toLocaleDateString("fr-FR")}</span>
                        {h.sale_type === "refund" && <span className="text-[10px] text-red-600 font-bold">REMB.</span>}
                      </div>
                      <span className="font-mono font-bold">{fmt(h.total_dzd)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CREATE/EDIT MODAL */}
      {form && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setForm(null)}>
          <div className="bg-white rounded-3xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <h3 className="font-serif font-bold text-[#063D2E] text-lg">{form.id === null ? t("customers.modal_new_title") : t("customers.modal_edit_title")}</h3>
              <button aria-label="Fermer" type="button" onClick={() => setForm(null)} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-5 space-y-3">
              <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} placeholder={t("customers.lbl_fullname")} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] outline-none" />
              <input value={form.phone} disabled={form.id !== null} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder={t("customers.lbl_phone")} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono disabled:opacity-60" />
              <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder={t("customers.lbl_email")} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200" />
              <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder={t("customers.lbl_notes")} rows={3} className="w-full px-3 py-2 rounded-2xl border-2 border-gray-200" />
              <button type="button" disabled={busy} onClick={save} className="w-full h-14 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-base disabled:opacity-50 active:scale-[0.99]">
                {form.id === null ? t("customers.btn_save") : t("customers.btn_save")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const Kpi: React.FC<{ icon: any; label: string; value: string; sub: string; accent?: boolean }> = ({ icon: Icon, label, value, sub, accent }) => (
  <div className={`p-3 rounded-2xl border text-center ${accent ? "border-[#D4AF62]/50 bg-[#FCFBF8]" : "border-gray-200"}`}>
    <div className="flex items-center justify-center gap-1 text-gray-500 text-[11px] font-bold uppercase"><Icon className="w-3.5 h-3.5" /> {label}</div>
    <div className="text-base font-extrabold text-[#063D2E] font-mono tabular-nums mt-0.5">{value}</div>
    <div className="text-[10px] text-gray-400">{sub}</div>
  </div>
);

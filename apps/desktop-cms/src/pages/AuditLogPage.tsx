import React, { useEffect, useState, useCallback } from "react";
import { ClipboardCheck, RefreshCw, AlertTriangle, Search, Filter, X } from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";
import { useT } from "../i18n";

interface AuditLog {
  id: number;
  action: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, any>;
  admin_user_id: number | null;
  admin_email?: string | null;
  admin_name?: string | null;
  created_at: string;
}

export const AuditLogPage: React.FC = () => {
  const t = useT();
  const [items, setItems] = useState<AuditLog[]>([]);
  const [actions, setActions] = useState<Array<{ code: string; count: number }>>([]);
  const [entities, setEntities] = useState<Array<{ code: string; count: number }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<AuditLog | null>(null);

  const loadFacets = useCallback(async () => {
    try {
      const f = await DesktopCmsApi.getAuditLogFacets();
      setActions(f.actions || []);
      setEntities(f.entity_types || []);
    } catch {
      /* ignore */
    }
  }, []);

  const load = useCallback(
    async (filters?: { action: string; entityType: string; q: string }) => {
      const f = filters || { action, entityType, q };
      setLoading(true);
      try {
        const d = await DesktopCmsApi.listAuditLogs({
          limit: 100,
          action: f.action || undefined,
          entity_type: f.entityType || undefined,
          q: f.q.trim() || undefined,
        });
        setItems(d.items || []);
        setError(null);
      } catch (e: any) {
        setError(e?.userMessage || t("status.error"));
      } finally {
        setLoading(false);
      }
    },
    [action, entityType, q, t]
  );

  useEffect(() => {
    loadFacets();
    load({ action: "", entityType: "", q: "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const clear = () => {
    setAction("");
    setEntityType("");
    setQ("");
    load({ action: "", entityType: "", q: "" });
  };

  return (
    <div className="space-y-4 text-sm">
      {error && (
        <div className="p-4 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" /> {error}
        </div>
      )}

      <div className="bg-white p-5 rounded-3xl border border-[#D4AF62]/40">
        <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
          <ClipboardCheck className="w-5 h-5" /> {t("audit.title")}
        </h3>
        <p className="text-gray-500 mt-1">{t("audit.subtitle")}</p>
      </div>

      <div className="bg-white p-4 rounded-3xl border border-gray-200 flex flex-wrap items-end gap-3">
        <label className="block flex-1 min-w-[180px]">
          <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">{t("audit.lbl_action")}</span>
          <select value={action} onChange={(e) => setAction(e.target.value)} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 bg-white">
            <option value="">{t("audit.opt_all_actions")}</option>
            {actions.map((a) => (
              <option key={a.code} value={a.code}>{a.code} ({a.count})</option>
            ))}
          </select>
        </label>
        <label className="block flex-1 min-w-[180px]">
          <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">{t("audit.lbl_entity_type")}</span>
          <select value={entityType} onChange={(e) => setEntityType(e.target.value)} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 bg-white">
            <option value="">{t("audit.opt_all_entities")}</option>
            {entities.map((e) => (
              <option key={e.code} value={e.code}>{e.code} ({e.count})</option>
            ))}
          </select>
        </label>
        <label className="block flex-1 min-w-[180px]">
          <span className="block text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">{t("audit.lbl_search")}</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            placeholder={t("audit.search_placeholder")}
            className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200"
          />
        </label>
        <button type="button" onClick={() => load()} className="h-12 px-5 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
          <Search className="w-4 h-4" /> {t("audit.btn_filter")}
        </button>
        {(action || entityType || q) && (
          <button type="button" onClick={clear} className="h-12 px-4 rounded-2xl border-2 border-gray-200 font-bold text-gray-600 flex items-center gap-1.5 active:scale-95">
            <Filter className="w-4 h-4" /> {t("audit.btn_clear")}
          </button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin mr-2" /> {t("status.loading")}
        </div>
      ) : (
        <div className="bg-white rounded-3xl border border-gray-200 overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-[#063D2E] text-[#E8D4A5] text-xs uppercase">
              <tr>
                <th className="px-4 py-3">{t("audit.th_when")}</th>
                <th className="px-4 py-3">{t("audit.th_who")}</th>
                <th className="px-4 py-3">{t("audit.th_action")}</th>
                <th className="px-4 py-3">{t("audit.th_entity")}</th>
                <th className="px-4 py-3 hidden md:table-cell">{t("audit.th_details")}</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-gray-400">{t("audit.empty")}</td>
                </tr>
              )}
              {items.map((l) => (
                <tr key={l.id} className="border-t border-gray-100 hover:bg-[#FCFBF8] cursor-pointer" onClick={() => setOpen(l)}>
                  <td className="px-4 py-3 text-[11px] text-gray-500 font-mono whitespace-nowrap">{new Date(l.created_at).toLocaleString("fr-DZ")}</td>
                  <td className="px-4 py-3">
                    {l.admin_name ? <span className="font-bold text-[#063D2E]">{l.admin_name}</span> : <span className="text-gray-400">{t("audit.system_author")}</span>}
                    {l.admin_email && <div className="text-[11px] text-gray-400 font-mono">{l.admin_email}</div>}
                  </td>
                  <td className="px-4 py-3 font-mono text-[11px]">{l.action}</td>
                  <td className="px-4 py-3 font-mono text-[11px]">
                    {l.entity_type}
                    <span className="text-gray-400"> #{l.entity_id}</span>
                  </td>
                  <td className="px-4 py-3 text-[11px] text-gray-500 max-w-md truncate hidden md:table-cell">
                    {Object.keys(l.details || {}).length > 0
                      ? Object.entries(l.details).slice(0, 2).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(" · ")
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {open && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setOpen(null)}>
          <div className="bg-white rounded-3xl w-full max-w-lg max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <h3 className="font-serif font-bold text-[#063D2E] text-lg">{t("audit.modal_detail", { action: open.action })}</h3>
              <button type="button" onClick={() => setOpen(null)} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-5 space-y-2">
              <Row k={t("audit.row_date")} v={new Date(open.created_at).toLocaleString("fr-DZ")} />
              <Row k={t("audit.row_author")} v={open.admin_name ? `${open.admin_name} (${open.admin_email || "—"})` : t("audit.system_author")} />
              <Row k={t("audit.th_action")} v={open.action} mono />
              <Row k={t("audit.th_entity")} v={`${open.entity_type} #${open.entity_id}`} mono />
              <div>
                <div className="text-[11px] font-bold uppercase tracking-wide text-gray-500 mb-1">{t("audit.th_details")}</div>
                <pre className="p-3 rounded-2xl bg-[#F5F3EE] text-[11px] font-mono overflow-auto whitespace-pre-wrap break-all">
                  {JSON.stringify(open.details, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const Row: React.FC<{ k: string; v: string; mono?: boolean }> = ({ k, v, mono }) => (
  <div className="flex gap-3">
    <span className="w-20 shrink-0 text-[11px] font-bold uppercase tracking-wide text-gray-500">{k}</span>
    <span className={`flex-1 ${mono ? "font-mono text-[12px]" : ""}`}>{v}</span>
  </div>
);

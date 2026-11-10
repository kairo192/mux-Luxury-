import React, { useEffect, useState } from "react";
import { X, Printer, RefreshCw, AlertTriangle, Truck } from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";
import { useT } from "../i18n";

const fmt = (dzd: number) => `${Number(dzd || 0).toLocaleString("fr-DZ")} DA`;

export const DeliveryNoteModal: React.FC<{ orderId: number; onClose: () => void }> = ({ orderId, onClose }) => {
  const t = useT();
  const [data, setData] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    DesktopCmsApi.getOrderDeliveryNote(orderId)
      .then(setData)
      .catch((e) => setError(e?.userMessage || t("delivery_modal.load_error")));
  }, [orderId, t]);

  const b = data?.boutique_info || {};

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 print:p-0 print:bg-white" onClick={onClose}>
      <div className="bg-white rounded-3xl w-full max-w-2xl max-h-[95vh] overflow-auto print:rounded-none print:max-w-none print:max-h-none" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b print:hidden">
          <h3 className="font-serif font-bold text-[#063D2E] text-lg flex items-center gap-2">
            <Truck className="w-5 h-5" /> {t("delivery_modal.title", { ref: data?.order_reference || "…" })}
          </h3>
          <div className="flex gap-2">
            <button type="button" onClick={() => window.print()} disabled={!data} className="h-11 px-4 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95 disabled:opacity-50">
              <Printer className="w-4 h-4" /> {t("delivery_modal.btn_print")}
            </button>
            <button type="button" onClick={onClose} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {error ? (
          <div className="p-5"><div className="p-3 rounded-2xl bg-red-50 text-red-800 font-bold flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> {error}</div></div>
        ) : !data ? (
          <div className="flex items-center justify-center py-16 text-gray-500">
            <RefreshCw className="w-6 h-6 animate-spin mr-2" /> {t("delivery_modal.loading")}
          </div>
        ) : (
          <div id="delivery-note-sheet" className="p-10 text-[12px] text-gray-800 print:p-6">
            <div className="flex items-start justify-between mb-6 border-b border-gray-300 pb-4">
              <div>
                <div className="font-serif font-bold text-2xl text-[#063D2E]">{b.name || "Mus Luxury"}</div>
                {b.address && <div className="text-gray-500 text-[11px] mt-1">{b.address}</div>}
                {b.phone && <div className="text-gray-500 text-[11px]">Tél : {b.phone}</div>}
              </div>
              <div className="text-right">
                <div className="font-serif font-bold text-xl text-[#063D2E]">{t("delivery_modal.doc_heading")}</div>
                <div className="font-mono text-[11px] mt-1">{data.order_reference}</div>
                <div className="text-gray-500 text-[11px]">{new Date(data.created_at).toLocaleString("fr-DZ")}</div>
              </div>
            </div>

            {/* RECIPIENT */}
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="p-4 rounded-2xl border-2 border-[#063D2E] bg-[#FCFBF8]">
                <div className="text-[10px] uppercase tracking-wide text-gray-500 font-bold mb-1">{t("delivery_modal.recipient")}</div>
                <div className="font-bold text-base text-[#063D2E]">{data.customer_name}</div>
                <div className="text-gray-700 font-mono mt-1">{data.customer_phone}</div>
                <div className="text-gray-700 mt-2 leading-tight">
                  {data.delivery_address}
                  <br />
                  {data.commune} · {data.wilaya_name} ({data.wilaya_code})
                </div>
              </div>
              <div className="p-4 rounded-2xl border border-gray-200">
                <div className="text-[10px] uppercase tracking-wide text-gray-500 font-bold mb-1">{t("delivery_modal.delivery")}</div>
                <div className="font-bold">{data.delivery_method === "home" ? t("delivery_modal.home_delivery") : t("delivery_modal.relay_point")}</div>
                <div className="text-gray-500 text-[11px] mt-1">{t("delivery_modal.status")} <span className="font-bold text-[#063D2E]">{data.status}</span></div>
                {data.cod_amount_dzd > 0 && (
                  <div className="mt-3 p-2 rounded-xl bg-amber-50 border border-amber-200">
                    <div className="text-[10px] uppercase tracking-wide font-bold text-amber-700">{t("delivery_modal.cod_to_collect")}</div>
                    <div className="text-xl font-extrabold font-mono text-amber-800">{fmt(data.cod_amount_dzd)}</div>
                  </div>
                )}
              </div>
            </div>

            {/* ITEMS */}
            <div className="mb-4 text-[11px] uppercase tracking-wide text-gray-500 font-bold">
              {t("delivery_modal.package_content", { count: data.total_items })}
            </div>
            <table className="w-full mb-6 border border-gray-300">
              <thead className="bg-[#063D2E] text-[#E8D4A5] text-[11px] uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">{t("delivery_modal.th_product")}</th>
                  <th className="px-3 py-2 text-left w-40">{t("delivery_modal.th_variant")}</th>
                  <th className="px-3 py-2 text-left w-32">{t("delivery_modal.th_sku")}</th>
                  <th className="px-3 py-2 text-right w-16">{t("delivery_modal.th_qty")}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((it: any, idx: number) => (
                  <tr key={idx} className="border-t border-gray-200">
                    <td className="px-3 py-2 font-bold">{it.product_name}</td>
                    <td className="px-3 py-2">{it.variant_title}</td>
                    <td className="px-3 py-2 font-mono text-[11px]">{it.sku}</td>
                    <td className="px-3 py-2 text-right font-mono font-bold text-base">{it.quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {data.customer_notes && (
              <div className="mb-4 p-3 rounded-xl bg-[#FCFBF8] border border-gray-200 text-[11px]">
                <div className="text-gray-400 font-bold uppercase text-[10px] mb-1">{t("delivery_modal.customer_note")}</div>
                {data.customer_notes}
              </div>
            )}

            <div className="grid grid-cols-2 gap-4 mt-10">
              <div>
                <div className="border-b border-gray-400 mb-1" style={{ height: "40px" }} />
                <div className="text-[10px] text-gray-500 font-bold uppercase text-center">{t("delivery_modal.driver_sig")}</div>
              </div>
              <div>
                <div className="border-b border-gray-400 mb-1" style={{ height: "40px" }} />
                <div className="text-[10px] text-gray-500 font-bold uppercase text-center">{t("delivery_modal.customer_sig")}</div>
              </div>
            </div>
          </div>
        )}

        <style>{`
          @media print {
            @page { size: A4; margin: 12mm; }
            body * { visibility: hidden !important; }
            #delivery-note-sheet, #delivery-note-sheet * { visibility: visible !important; }
            #delivery-note-sheet { position: absolute; left: 0; top: 0; width: 100%; }
          }
        `}</style>
      </div>
    </div>
  );
};

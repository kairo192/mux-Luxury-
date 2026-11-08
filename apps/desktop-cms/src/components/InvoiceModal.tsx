import React, { useEffect, useState } from "react";
import { X, Printer, RefreshCw, AlertTriangle } from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";

const fmt = (dzd: number) => `${Number(dzd || 0).toLocaleString("fr-DZ")} DA`;

export const InvoiceModal: React.FC<{ saleId: number; onClose: () => void }> = ({ saleId, onClose }) => {
  const [data, setData] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    DesktopCmsApi.posGetSaleInvoice(saleId)
      .then(setData)
      .catch((e) => setError(e?.userMessage || "Chargement impossible"));
  }, [saleId]);

  const printIt = () => window.print();

  const b = data?.boutique_info || {};
  const c = data?.customer;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 print:p-0 print:bg-white" onClick={onClose}>
      <div
        className="bg-white rounded-3xl w-full max-w-3xl max-h-[95vh] overflow-auto print:rounded-none print:max-w-none print:max-h-none print:shadow-none"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b print:hidden">
          <h3 className="font-serif font-bold text-[#063D2E] text-lg">Facture · {data?.sale_reference || "…"}</h3>
          <div className="flex gap-2">
            <button type="button" onClick={printIt} disabled={!data} className="h-11 px-4 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95 disabled:opacity-50">
              <Printer className="w-4 h-4" /> Imprimer
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
            <RefreshCw className="w-6 h-6 animate-spin mr-2" /> Chargement…
          </div>
        ) : (
          <div id="invoice-sheet" className="p-10 text-[12px] text-gray-800 print:p-6">
            {/* HEADER */}
            <div className="flex items-start justify-between mb-6">
              <div>
                <div className="font-serif font-bold text-2xl text-[#063D2E]">{b.name || "Mus Luxury"}</div>
                {b.legal_name && b.legal_name !== b.name && <div className="text-gray-500">{b.legal_name}</div>}
                {b.address && <div className="text-gray-500 text-[11px] mt-1">{b.address}</div>}
                {b.phone && <div className="text-gray-500 text-[11px]">Tél : {b.phone}</div>}
              </div>
              <div className="text-right">
                <div className="font-serif font-bold text-xl text-[#063D2E]">{data.document_title}</div>
                <div className="font-mono text-[11px] mt-1">N° {data.sale_reference}</div>
                <div className="text-gray-500 text-[11px]">{new Date(data.created_at).toLocaleString("fr-DZ")}</div>
              </div>
            </div>

            {/* LEGAL IDENTIFIERS */}
            {(b.nif || b.nis || b.rc || b.article) && (
              <div className="grid grid-cols-4 gap-2 mb-6 p-3 rounded-2xl bg-[#FCFBF8] border border-gray-200 text-[11px]">
                {b.nif && <div><span className="text-gray-400 font-bold">NIF</span><div className="font-mono">{b.nif}</div></div>}
                {b.nis && <div><span className="text-gray-400 font-bold">NIS</span><div className="font-mono">{b.nis}</div></div>}
                {b.rc && <div><span className="text-gray-400 font-bold">RC</span><div className="font-mono">{b.rc}</div></div>}
                {b.article && <div><span className="text-gray-400 font-bold">ART. IMP.</span><div className="font-mono">{b.article}</div></div>}
              </div>
            )}

            {/* CUSTOMER */}
            <div className="mb-6 p-3 rounded-2xl border border-gray-200">
              <div className="text-[10px] uppercase tracking-wide text-gray-400 font-bold mb-1">Client</div>
              {c ? (
                <>
                  <div className="font-bold text-[#063D2E]">{c.full_name}</div>
                  <div className="text-gray-500 text-[11px] font-mono">{c.phone}</div>
                </>
              ) : (
                <div className="text-gray-500">Client de passage</div>
              )}
            </div>

            {/* ITEMS */}
            <table className="w-full mb-6 border border-gray-200">
              <thead className="bg-[#063D2E] text-[#E8D4A5] text-[11px] uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Désignation</th>
                  <th className="px-3 py-2 text-right w-20">Qté</th>
                  <th className="px-3 py-2 text-right w-32">P.U.</th>
                  <th className="px-3 py-2 text-right w-24">Remise</th>
                  <th className="px-3 py-2 text-right w-32">Total</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((it: any) => (
                  <tr key={it.id} className="border-t border-gray-200">
                    <td className="px-3 py-2">
                      <div className="font-bold">{it.product_name}</div>
                      <div className="text-gray-500 text-[11px]">{it.variant_title} · {it.sku}</div>
                    </td>
                    <td className="px-3 py-2 text-right font-mono">{it.quantity}</td>
                    <td className="px-3 py-2 text-right font-mono">{fmt(it.unit_price_dzd)}</td>
                    <td className="px-3 py-2 text-right font-mono">{it.line_discount_dzd ? `-${fmt(it.line_discount_dzd)}` : "—"}</td>
                    <td className="px-3 py-2 text-right font-mono font-bold">{fmt(it.line_total_dzd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* TOTALS */}
            <div className="flex justify-end mb-6">
              <div className="w-72 space-y-1">
                <div className="flex justify-between"><span className="text-gray-500">Sous-total HT</span><span className="font-mono">{fmt(data.subtotal_dzd)}</span></div>
                {data.discount_dzd > 0 && <div className="flex justify-between text-amber-700"><span>Remise</span><span className="font-mono">-{fmt(data.discount_dzd)}</span></div>}
                {data.tax_dzd > 0 && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">TVA ({data.tax_percent}%)</span>
                    <span className="font-mono">{fmt(data.tax_dzd)}</span>
                  </div>
                )}
                <div className="flex justify-between text-base font-bold border-t border-gray-300 pt-2">
                  <span>Total TTC</span>
                  <span className="font-mono">{fmt(data.total_dzd)}</span>
                </div>
              </div>
            </div>

            {/* PAYMENT */}
            <div className="mb-6 p-3 rounded-2xl bg-[#FCFBF8] border border-gray-200">
              <div className="text-[10px] uppercase tracking-wide text-gray-400 font-bold mb-1">Règlement</div>
              {data.payments.map((p: any) => (
                <div key={p.id} className="flex justify-between text-[11px]">
                  <span>{p.method === "cash" ? "Espèces" : p.method === "card" ? "Carte" : p.method === "transfer" ? "Virement" : p.method}</span>
                  <span className="font-mono">{fmt(p.amount_dzd)}</span>
                </div>
              ))}
            </div>

            {b.footer_line && <div className="text-center text-[11px] text-gray-500">{b.footer_line}</div>}
            {data.cashier_name && <div className="text-center text-[10px] text-gray-400 mt-2">Caissier : {data.cashier_name}</div>}
          </div>
        )}

        <style>{`
          @media print {
            @page { size: A4; margin: 12mm; }
            body * { visibility: hidden !important; }
            #invoice-sheet, #invoice-sheet * { visibility: visible !important; }
            #invoice-sheet { position: absolute; left: 0; top: 0; width: 100%; }
          }
        `}</style>
      </div>
    </div>
  );
};

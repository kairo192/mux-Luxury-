// Small building blocks of the till screen: amount format, keypad, figures, bottom sheet, receipt.
import React from "react";
import { Printer, X, Delete } from "lucide-react";
import { useEscapeToClose } from "../../utils/useEscapeToClose";
import { serverDate } from "../../utils/serverDate";

export function fmt(dzd: number): string {
  return `${Number(dzd || 0).toLocaleString("fr-DZ")} DA`;
}

// ---------------------------------------------------------------------------
// On-screen numeric keypad (touch). 64px keys, brand-consistent.
// ---------------------------------------------------------------------------
export const Keypad: React.FC<{
  value: string;
  onChange: (v: string) => void;
  quickAdds?: number[];
  onExact?: () => void;
}> = ({ value, onChange, quickAdds = [1000, 2000, 5000], onExact }) => {
  const press = (d: string) => {
    if (d === "del") {
      onChange(value.slice(0, -1));
    } else {
      const next = (value === "0" ? "" : value) + d;
      onChange(next.replace(/^0+(?=\d)/, "").slice(0, 9));
    }
  };
  const add = (n: number) => onChange(String((parseInt(value || "0", 10) || 0) + n));
  const keyCls =
    "h-16 rounded-2xl bg-white border-2 border-[#063D2E]/10 text-2xl font-bold text-[#063D2E] active:scale-95 active:bg-[#F5F3EE] transition-transform flex items-center justify-center select-none";
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        {quickAdds.map((n) => (
          <button key={n} type="button" onClick={() => add(n)} className="flex-1 h-12 rounded-xl bg-[#063D2E]/5 text-[#063D2E] font-bold text-sm active:scale-95">
            +{n.toLocaleString("fr-DZ")}
          </button>
        ))}
        {onExact && (
          <button type="button" onClick={onExact} className="flex-1 h-12 rounded-xl bg-[#D4AF62]/20 text-[#7a5c16] font-bold text-sm active:scale-95">
            Exact
          </button>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => (
          <button key={d} type="button" onClick={() => press(d)} className={keyCls}>
            {d}
          </button>
        ))}
        <button type="button" onClick={() => press("00")} className={keyCls}>
          00
        </button>
        <button type="button" onClick={() => press("0")} className={keyCls}>
          0
        </button>
        <button aria-label="Effacer le dernier chiffre" type="button" onClick={() => press("del")} className={`${keyCls} text-[#B91C1C]`}>
          <Delete className="w-7 h-7" />
        </button>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
export const Stat: React.FC<{ label: string; value: string; gold?: boolean }> = ({ label, value, gold }) => (
  <div>
    <div className="text-[11px] uppercase tracking-wide opacity-70">{label}</div>
    <div className={`font-bold font-mono tabular-nums ${gold ? "text-[#D4AF62]" : ""}`}>{value}</div>
  </div>
);

// Bottom sheet — large, touch-dismissable (modality.md: one task, obvious way out)
export const Sheet: React.FC<{ title: string; onClose: () => void; children: React.ReactNode }> = ({ title, onClose, children }) => {
  useEscapeToClose(onClose);
  return (
  <div className="fixed inset-0 bg-black/40 flex items-end sm:items-center justify-center z-50 p-0 sm:p-4" onClick={onClose}>
    <div
      className="bg-white rounded-t-3xl sm:rounded-3xl p-5 w-full sm:max-w-md max-h-[92vh] overflow-auto"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-serif font-bold text-[#063D2E] text-lg">{title}</h3>
        <button aria-label="Fermer" type="button" onClick={onClose} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:text-gray-700 hover:bg-gray-100 active:scale-95">
          <X className="w-6 h-6" />
        </button>
      </div>
      {children}
    </div>
  </div>
);
};

export const ReceiptModal: React.FC<{ sale: any; onClose: () => void; onPrint: () => void; onSystemPrint?: () => void }> = ({ sale, onClose, onPrint, onSystemPrint }) => {
  useEscapeToClose(onClose);
  const b = sale.boutique_info || {};
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-3xl w-full max-w-sm max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div id="pos-receipt" className="p-6 font-mono text-sm text-gray-800">
          <div className="text-center mb-2">
            <div className="font-bold text-base">{b.name || "Mus Luxury"}</div>
            {b.legal_name && b.legal_name !== b.name && <div className="text-xs">{b.legal_name}</div>}
            {b.address && <div className="text-xs">{b.address}</div>}
            {b.phone && <div className="text-xs">Tél: {b.phone}</div>}
            {(b.nif || b.nis || b.rc || b.article) && (
              <div className="text-xs mt-1">
                {b.nif && <div>NIF: {b.nif}</div>}
                {b.nis && <div>NIS: {b.nis}</div>}
                {b.rc && <div>RC: {b.rc}</div>}
                {b.article && <div>Art.: {b.article}</div>}
              </div>
            )}
          </div>
          <div className="border-t border-dashed my-2" />
          <div>Reçu: {sale.sale_reference}</div>
          <div>{serverDate(sale.created_at).toLocaleString("fr-FR")}</div>
          {sale.cashier_name && <div>Caissier: {sale.cashier_name}</div>}
          {sale.customer && <div>Client: {sale.customer.full_name}</div>}
          {sale.offline && <div className="font-bold text-amber-700">** HORS LIGNE — à synchroniser **</div>}
          {sale.sale_type === "refund" && <div className="font-bold text-red-700">** REMBOURSEMENT **</div>}
          <div className="border-t border-dashed my-2" />
          {(sale.items || []).map((it: any) => (
            <div key={it.id} className="flex justify-between">
              <span className="truncate pr-2">
                {it.quantity}× {it.product_name} ({it.variant_title})
              </span>
              <span>{fmt(it.line_total_dzd)}</span>
            </div>
          ))}
          <div className="border-t border-dashed my-2" />
          <div className="flex justify-between">
            <span>Sous-total</span>
            <span>{fmt(sale.subtotal_dzd)}</span>
          </div>
          {sale.discount_dzd > 0 && (
            <div className="flex justify-between">
              <span>Remise</span>
              <span>-{fmt(sale.discount_dzd)}</span>
            </div>
          )}
          {sale.tax_dzd > 0 && (
            <div className="flex justify-between">
              <span>Taxe</span>
              <span>{fmt(sale.tax_dzd)}</span>
            </div>
          )}
          <div className="flex justify-between font-bold text-base">
            <span>TOTAL</span>
            <span>{fmt(sale.total_dzd)}</span>
          </div>
          <div className="border-t border-dashed my-2" />
          {(sale.payments || []).map((p: any) => (
            <div key={p.id} className="flex justify-between">
              <span>{p.method === "cash" ? "Espèces" : p.method === "card" ? "Carte" : p.method === "transfer" ? "Virement" : p.method}</span>
              <span>{fmt(p.amount_dzd)}</span>
            </div>
          ))}
          {(sale.payments || []).some((p: any) => p.change_dzd > 0) && (
            <div className="flex justify-between">
              <span>Monnaie</span>
              <span>{fmt((sale.payments || []).reduce((s: number, p: any) => s + (p.change_dzd || 0), 0))}</span>
            </div>
          )}
          <div className="text-center mt-4 text-xs">{b.footer_line || `Merci de votre visite — ${b.name || "Mus Luxury"}`}</div>
        </div>
        <div className="p-4 border-t space-y-2 print:hidden">
          <div className="flex gap-2">
            <button type="button" onClick={onPrint} className="flex-1 h-14 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center justify-center gap-2 active:scale-95">
              <Printer className="w-5 h-5" /> Imprimer
            </button>
            <button type="button" onClick={onClose} className="flex-1 h-14 rounded-2xl bg-gray-100 font-bold active:scale-95">
              Fermer
            </button>
          </div>
          {onSystemPrint && (
            <button
              type="button"
              onClick={onSystemPrint}
              className="w-full h-11 rounded-2xl border-2 border-gray-200 text-gray-700 font-bold text-sm flex items-center justify-center gap-2 active:scale-95"
              title="Ouvrir l'aperçu système (toute imprimante Windows, ajuster la taille)"
            >
              <Printer className="w-4 h-4" /> Aperçu système (toute imprimante)
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

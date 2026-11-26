// The till's bottom sheets. PosPage decides when each is shown and owns the state they edit.
import { CheckCircle2, RotateCcw, Banknote, CreditCard, Wallet, UserPlus, UserCheck } from "lucide-react";
import type { PosQueueItem } from "../../utils/posOfflineQueue";
import { serverDate } from "../../utils/serverDate";
import type { LookupVariant, PaymentMethod, RegisterSession } from "./types";
import { Keypad, Sheet, fmt } from "./ui";
import { tr, localeFor } from "../../i18n/translations";

/** Choose the payment method, global discount and cash received; validates the sale. */
export function PaymentSheet({ total, payMethod, setPayMethod, orderDiscount, setOrderDiscount, tendered, setTendered, tenderedNum, receivedShown, change, busy, handleConfirmSale, setShowPay }: { total: number; payMethod: PaymentMethod; setPayMethod: (m: PaymentMethod) => void; orderDiscount: string; setOrderDiscount: (v: string) => void; tendered: string; setTendered: (v: string) => void; tenderedNum: number; receivedShown: number; change: number; busy: boolean; handleConfirmSale: () => void; setShowPay: (v: boolean) => void }) {
  return (
      <Sheet onClose={() => setShowPay(false)} title={tr("posx.pay_title", { total: fmt(total) })}>
        <div className="grid grid-cols-3 gap-2 mb-4">
          {([
            ["cash", tr("posx.m_cash"), Banknote],
            ["card", tr("posx.m_card"), CreditCard],
            ["transfer", tr("posx.m_transfer"), Wallet],
          ] as [PaymentMethod, string, any][]).map(([m, label, Icon]) => (
            <button
              key={m}
              type="button"
              onClick={() => setPayMethod(m)}
              className={`h-20 rounded-2xl border-2 font-bold flex flex-col items-center justify-center gap-1 active:scale-95 ${
                payMethod === m ? "bg-[#063D2E] text-[#D4AF62] border-[#063D2E]" : "border-gray-200 text-gray-600"
              }`}
            >
              <Icon className="w-6 h-6" /> {label}
            </button>
          ))}
        </div>

        <div className="flex items-center justify-between mb-3">
          <span className="text-gray-500 font-bold">{tr("posx.global_discount")}</span>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={0}
              value={orderDiscount}
              onChange={(e) => setOrderDiscount(e.target.value)}
              placeholder="0"
              className="w-28 h-11 px-3 rounded-xl border-2 border-gray-200 font-mono text-right text-base"
            />
            <span className="text-gray-400">DA</span>
          </div>
        </div>

        {payMethod === "cash" ? (
          <>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div className="p-3 rounded-2xl bg-[#F5F3EE] text-center">
                <div className="text-xs uppercase tracking-wide text-gray-500 font-bold">{tr("posx.received")}</div>
                <div className="text-2xl font-bold text-[#063D2E] font-mono tabular-nums">{fmt(receivedShown)}</div>
                {tenderedNum === 0 && <div className="text-[11px] text-gray-500">{tr("posx.exact_amount")}</div>}
              </div>
              <div className={`p-3 rounded-2xl text-center ${receivedShown >= total ? "bg-emerald-50" : "bg-red-50"}`}>
                <div className="text-xs uppercase tracking-wide text-gray-500 font-bold">{tr("posx.change")}</div>
                <div className={`text-2xl font-bold font-mono tabular-nums ${receivedShown >= total ? "text-emerald-700" : "text-red-600"}`}>
                  {receivedShown >= total ? fmt(change) : `-${fmt(total - receivedShown)}`}
                </div>
              </div>
            </div>
            <Keypad value={tendered} onChange={setTendered} quickAdds={[1000, 2000, 5000]} onExact={() => setTendered(String(total))} />
          </>
        ) : (
          <div className="p-4 rounded-2xl bg-[#F5F3EE] text-center mb-2">
            <div className="text-gray-500">{tr("posx.to_collect")}</div>
            <div className="text-3xl font-extrabold text-[#063D2E] font-mono tabular-nums">{fmt(total)}</div>
          </div>
        )}

        <button
          type="button"
          disabled={busy || (payMethod === "cash" && tenderedNum > 0 && tenderedNum < total)}
          onClick={handleConfirmSale}
          className="mt-4 w-full h-16 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-xl flex items-center justify-center gap-3 disabled:opacity-40 active:scale-[0.99]"
        >
          <CheckCircle2 className="w-6 h-6" /> Valider la vente
        </button>
      </Sheet>
  );
}

/** Pick the size / colour of a product found by name or barcode. */
export function VariantPickerSheet({ variantPicker, setVariantPicker, addVariantToCart }: { variantPicker: any; setVariantPicker: (v: any) => void; addVariantToCart: (v: LookupVariant) => void }) {
  return (
      <Sheet onClose={() => setVariantPicker(null)} title={variantPicker.name_fr}>
        <div className="grid grid-cols-2 gap-3">
          {(variantPicker.variants || []).map((v: any) => (
            <button
              key={v.variant_id}
              type="button"
              disabled={v.stock_qty < 1}
              onClick={() => addVariantToCart({ ...v, product_name: variantPicker.name_fr })}
              className="min-h-16 p-3 rounded-2xl border-2 border-[#063D2E]/15 font-bold text-left disabled:opacity-40 active:scale-95 hover:border-[#063D2E]"
            >
              <div className="text-base">{v.variant_title}</div>
              <div className="text-[#7a5c16] font-mono">{tr("posx.available", { price: fmt(v.unit_price_dzd), n: v.stock_qty })}</div>
            </button>
          ))}
        </div>
      </Sheet>
  );
}

/** End of day: count the cash and close the register. */
export function CloseRegisterSheet({ session, countedCash, setCountedCash, busy, handleCloseRegister, setShowClose }: { session: RegisterSession; countedCash: string; setCountedCash: (v: string) => void; busy: boolean; handleCloseRegister: () => void; setShowClose: (v: boolean) => void }) {
  return (
      <Sheet onClose={() => setShowClose(false)} title={tr("posx.close_title")}>
        <div className="p-3 rounded-2xl bg-[#F5F3EE] mb-3 text-center">
          <div className="text-xs uppercase tracking-wide text-gray-500 font-bold">{tr("posx.stat_expected")}</div>
          <div className="text-2xl font-bold text-[#063D2E] font-mono">{fmt(session.expected_cash_dzd || 0)}</div>
          <div className="text-xs text-gray-400 mt-1">Fond {fmt(session.opening_float_dzd)} + ventes espèces</div>
        </div>
        <div className="p-3 rounded-2xl bg-white border-2 border-gray-100 mb-3 text-center">
          <div className="text-xs uppercase tracking-wide text-gray-500 font-bold">{tr("posx.counted_cash")}</div>
          <div className="text-2xl font-bold text-[#063D2E] font-mono tabular-nums">{fmt(parseInt(countedCash || "0", 10) || 0)}</div>
        </div>
        <Keypad value={countedCash} onChange={setCountedCash} quickAdds={[1000, 5000, 10000]} onExact={() => setCountedCash(String(session.expected_cash_dzd || 0))} />
        <button
          type="button"
          disabled={busy}
          onClick={handleCloseRegister}
          className="mt-4 w-full h-16 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-lg disabled:opacity-50 active:scale-[0.99]"
        >
          {tr("posx.confirm_close")}
        </button>
      </Sheet>
  );
}

/** Full refund of a sale (stock is put back automatically). */
export function RefundSheet({ refundTarget, busy, handleFullRefund, setRefundTarget }: { refundTarget: any; busy: boolean; handleFullRefund: (sale: any) => void; setRefundTarget: (v: any) => void }) {
  return (
      <Sheet onClose={() => setRefundTarget(null)} title={tr("posx.refund_title", { ref: refundTarget.sale_reference })}>
        <p className="text-gray-600 mb-4 text-base">
          {tr("posx.refund_body", { total: fmt(refundTarget.total_dzd) })}
        </p>
        <button
          type="button"
          disabled={busy}
          onClick={() => handleFullRefund(refundTarget)}
          className="w-full h-16 rounded-2xl bg-red-600 text-white font-extrabold text-lg disabled:opacity-50 flex items-center justify-center gap-2 active:scale-[0.99]"
        >
          <RotateCcw className="w-6 h-6" /> {tr("posx.confirm_refund")}
        </button>
      </Sheet>
  );
}

/** Past and current register sessions with their totals and cash difference. */
export function SessionsHistorySheet({ sessionsHistory, setSessionsHistory }: { sessionsHistory: any[]; setSessionsHistory: (v: any[] | null) => void }) {
  return (
      <Sheet onClose={() => setSessionsHistory(null)} title={tr("posx.sessions_title")}>
        <div className="space-y-2 max-h-[60vh] overflow-auto">
          {sessionsHistory.length === 0 && <div className="text-gray-400 py-6 text-center">{tr("posx.no_session")}</div>}
          {sessionsHistory.map((s) => (
            <div key={s.id} className="p-3 rounded-2xl border border-gray-100 bg-[#FCFBF8]">
              <div className="flex items-center justify-between">
                <span className="font-bold text-[#063D2E]">#{s.id} · {s.register_name}</span>
                <span className={`px-2 py-0.5 rounded-lg text-xs font-bold ${s.status === "open" ? "bg-emerald-100 text-emerald-700" : "bg-gray-200 text-gray-600"}`}>
                  {s.status === "open" ? tr("posx.s_open") : tr("posx.s_closed")}
                </span>
              </div>
              <div className="text-gray-500 mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-[11px]">
                <span>{tr("posx.h_float", { v: fmt(s.opening_float_dzd) })}</span>
                <span>{tr("posx.h_sales", { v: fmt(s.total_sales_dzd || 0) })}</span>
                {(s.total_refunds_dzd || 0) > 0 && <span>{tr("posx.h_refunds", { v: fmt(s.total_refunds_dzd) })}</span>}
                {s.status === "open" && <span>{tr("posx.h_expected_open", { v: fmt(s.expected_cash_dzd || 0) })}</span>}
                {s.status === "closed" && <span>{tr("posx.h_expected", { v: fmt(s.expected_cash_dzd || 0) })}</span>}
                {s.status === "closed" && <span>{tr("posx.h_counted", { v: fmt(s.counted_cash_dzd || 0) })}</span>}
                {s.status === "closed" && (
                  <span className={`col-span-2 font-bold ${(s.variance_dzd || 0) === 0 ? "text-emerald-600" : "text-amber-700"}`}>
                    {tr("posx.h_variance", { v: `${(s.variance_dzd || 0) >= 0 ? "+" : ""}${fmt(s.variance_dzd || 0)}` })}
                  </span>
                )}
              </div>
              {s.opened_by_name && <div className="text-gray-400 text-[11px] mt-1">{tr("posx.h_opened_by", { name: s.opened_by_name })}{s.closed_by_name ? tr("posx.h_closed_by", { name: s.closed_by_name }) : ""}</div>}
            </div>
          ))}
        </div>
      </Sheet>
  );
}

/** Find or create the customer of the sale. */
export function CustomerSheet({ customer, setCustomer, custQuery, setCustQuery, searchCustomer, custResults, pickCustomer, custNewName, setCustNewName, custNewPhone, setCustNewPhone, createCustomer, setShowCustomer }: { customer: any; setCustomer: (c: any) => void; custQuery: string; setCustQuery: (v: string) => void; searchCustomer: () => void; custResults: any[]; pickCustomer: (c: any) => void; custNewName: string; setCustNewName: (v: string) => void; custNewPhone: string; setCustNewPhone: (v: string) => void; createCustomer: () => void; setShowCustomer: (v: boolean) => void }) {
  return (
      <Sheet onClose={() => setShowCustomer(false)} title={tr("posx.attach_title")}>
        {customer && (
          <div className="mb-3 p-3 rounded-2xl bg-emerald-50 border-2 border-emerald-200 flex items-center justify-between">
            <span className="font-bold text-emerald-800 flex items-center gap-2"><UserCheck className="w-4 h-4" /> {customer.full_name} · {customer.phone}</span>
            <button type="button" onClick={() => setCustomer(null)} className="text-emerald-700 font-bold text-sm underline">{tr("posx.remove")}</button>
          </div>
        )}
        <form onSubmit={(e) => { e.preventDefault(); searchCustomer(); }} className="flex gap-2 mb-2">
          <input
            value={custQuery}
            onChange={(e) => setCustQuery(e.target.value)}
            placeholder={tr("posx.customer_ph")}
            className="flex-1 h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] outline-none"
            autoFocus
          />
          <button type="submit" className="h-12 px-4 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold active:scale-95">{tr("posx.search")}</button>
        </form>
        <div className="space-y-1 max-h-48 overflow-auto mb-3">
          {custResults.map((c) => (
            <button key={c.id} type="button" onClick={() => pickCustomer(c)} className="w-full text-left p-2.5 rounded-xl border border-gray-100 hover:bg-[#FCFBF8] flex items-center justify-between active:scale-[0.99]">
              <span className="font-bold text-[#063D2E]">{c.full_name}</span>
              <span className="font-mono text-gray-500 text-[11px]">{c.phone}</span>
            </button>
          ))}
        </div>
        <div className="border-t pt-3">
          <div className="font-bold text-[#063D2E] mb-2 flex items-center gap-2"><UserPlus className="w-4 h-4" /> {tr("posx.new_customer")}</div>
          <div className="grid grid-cols-2 gap-2">
            <input value={custNewName} onChange={(e) => setCustNewName(e.target.value)} placeholder={tr("posx.full_name")} className="h-12 px-3 rounded-2xl border-2 border-gray-200" />
            <input value={custNewPhone} onChange={(e) => setCustNewPhone(e.target.value)} placeholder={tr("posx.phone")} className="h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono" />
          </div>
          <button type="button" onClick={createCustomer} className="mt-2 w-full h-12 rounded-2xl bg-[#D4AF62] text-[#02291F] font-bold active:scale-95">
            {tr("posx.create_attach")}
          </button>
        </div>
      </Sheet>
  );
}

/** Offline sales the server refused (kept, to be handled by hand). */
export function ConflictsSheet({ queue, setShowConflicts }: { queue: PosQueueItem[]; setShowConflicts: (v: boolean) => void }) {
  return (
      <Sheet onClose={() => setShowConflicts(false)} title={tr("posx.conflicts_title")}>
        <p className="text-gray-600 mb-3">
          {tr("posx.conflicts_body")}
        </p>
        <div className="space-y-2 max-h-[55vh] overflow-auto">
          {queue.filter((i) => i.status === "conflict").length === 0 && (
            <div className="text-gray-400 py-6 text-center">{tr("posx.no_conflict")}</div>
          )}
          {queue
            .filter((i) => i.status === "conflict")
            .map((i) => (
              <div key={i.client_txn_id} className="p-3 rounded-2xl border-2 border-red-100 bg-red-50/40">
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-[#063D2E]">{fmt(i.total_dzd)}</span>
                  <span className="text-xs text-gray-400">{serverDate(i.created_at).toLocaleString(localeFor())}</span>
                </div>
                <div className="text-red-600 text-[13px] mt-1">{i.error}</div>
                <div className="text-gray-500 text-[11px] mt-1">
                  {i.payload.items.map((it) => `${it.quantity}× #${it.variant_id}`).join(", ")}
                </div>
              </div>
            ))}
        </div>
      </Sheet>
  );
}

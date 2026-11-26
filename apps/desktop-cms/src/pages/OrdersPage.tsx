import { Ban, CheckCircle2, MessageCircle, Radio, Truck, X } from "lucide-react";
import { useT } from "../i18n";
import { notifyClientError } from "../utils/clientNotifier";
import { allowedOrderStatuses, orderStatusLabel, ORDER_STATUSES } from "../utils/orderStatus";
import { openExternalUrl } from "../utils/openExternal";
import { serverDate } from "../utils/serverDate";
import { localeFor, tr } from "../i18n/translations";

/** The COD history badge, from the figures (the server's own text is French). */
function codBadge(risk: any): string {
  const v = { reason: risk.blacklist_reason || "", ret: risk.returned_count ?? 0, deliv: risk.delivered_count ?? 0, canc: risk.cancelled_count ?? 0, rate: risk.return_rate_percent ?? 0 };
  const level = ["blacklisted", "high_risk", "medium_risk", "trusted", "normal"].includes(risk.risk_level) ? risk.risk_level : null;
  return level ? tr(`ord.badge_${level}`, v) : String(risk.warning_badge_fr || "");
}

type WhatsappTemplate = "confirmation_call" | "shipped_notice" | "no_answer_followup" | "delivery_arrived";

/** Everything the Orders screen shows and the actions it offers. The data and
 *  the actions live in App (shared with the sidebar badge, the new-order
 *  alerts and the automatic refresh); this file only draws the screen. */
export interface OrdersPageProps {
  orders: any[];
  statusFilter: string;
  onStatusFilterChange: (status: string) => void;
  searchInput: string;
  onSearchInputChange: (text: string) => void;
  onSearch: (text: string) => void;
  onStatusChange: (orderId: number, nextStatus: string) => void;
  onOpenInvoice: (orderId: number) => void;
  onOpenDeliveryNote: (orderId: number) => void;
  onExportCsv: () => void;
  onNotifyWhatsapp: (orderId: number, template?: WhatsappTemplate) => void;
  selectedInvoice: any | null;
  onCloseInvoice: () => void;
  waOutbox: any[];
  // Anti-retour (cash on delivery risk)
  codCheckPhone: string;
  onCodCheckPhoneChange: (phone: string) => void;
  codCheckResult: any | null;
  onCheckPhoneRisk: () => void;
  codBlacklist: any[];
  codBlacklistReason: string;
  onCodBlacklistReasonChange: (reason: string) => void;
  onBlockPhone: (phone: string, reason?: string) => void;
  onUnblockPhone: (phone: string) => void;
}

export function OrdersPage(props: OrdersPageProps) {
  const t = useT();
  const {
    orders,
    statusFilter: orderStatusFilter,
    onStatusFilterChange: setOrderStatusFilter,
    searchInput: orderSearchInput,
    onSearchInputChange: setOrderSearchInput,
    onSearch: setOrderSearch,
    onStatusChange: handleOrderStatusChange,
    onOpenInvoice: handleOpenInvoice,
    onOpenDeliveryNote: setDeliveryNoteOrderId,
    onExportCsv: handleExportOrdersCsv,
    onNotifyWhatsapp: handleNotifyOrderCustomerWhatsapp,
    selectedInvoice,
    onCloseInvoice,
    waOutbox,
    codCheckPhone,
    onCodCheckPhoneChange: setCodCheckPhone,
    codCheckResult,
    onCheckPhoneRisk: handleCheckPhoneCodRisk,
    codBlacklist,
    codBlacklistReason,
    onCodBlacklistReasonChange: setCodBlacklistReason,
    onBlockPhone: handleBlockCustomerPhone,
    onUnblockPhone: handleUnblockCustomerPhone,
  } = props;
  const setSelectedInvoice = (v: null) => { if (v === null) onCloseInvoice(); };

  return (
    <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-base font-serif font-bold text-[#063D2E]">{t("sidebar.orders")} ({orders.length})</h3>
        <div className="flex items-center gap-2">
          <form
            onSubmit={(e) => { e.preventDefault(); setOrderSearch(orderSearchInput.trim()); }}
            className="flex items-center gap-1"
          >
            <input
              type="search"
              aria-label={t("orders.search_placeholder")}
              value={orderSearchInput}
              onChange={(e) => { setOrderSearchInput(e.target.value); if (!e.target.value) setOrderSearch(""); }}
              placeholder={t("orders.search_placeholder")}
              className="w-56 px-3 py-1.5 border rounded-xl bg-[#F8F6F0]"
            />
          </form>
          <select
            value={orderStatusFilter}
            onChange={(e) => setOrderStatusFilter(e.target.value)}
            className="px-3 py-1.5 border rounded-xl bg-[#F8F6F0] font-semibold"
          >
            <option value="">{t("common.all")}</option>
            {ORDER_STATUSES.map((st) => (
              <option key={st} value={st}>{orderStatusLabel(st)}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleExportOrdersCsv}
            className="px-3.5 py-1.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold"
          >
            ⬇ CSV
          </button>
        </div>
      </div>
      <div className="space-y-3">
        {orders.map((o) => {
          const risk = o.cod_risk || {};
          const badgeClass =
            risk.risk_level === "blacklisted" || risk.risk_level === "high_risk"
              ? "bg-red-100 text-red-900 border-red-300"
              : risk.risk_level === "medium_risk"
              ? "bg-amber-100 text-amber-900 border-amber-300"
              : "bg-emerald-50 text-emerald-900 border-emerald-200";
          return (
            <div key={o.id} data-order-ref={o.order_reference} className="p-4 rounded-xl border border-gray-200 flex flex-wrap items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono font-extrabold text-[#063D2E]">#{o.order_reference} • {o.customer_name} ({o.customer_phone})</span>
                  {risk.warning_badge_fr && (
                    <span className={`px-2.5 py-0.5 rounded-full border text-[11px] font-extrabold ${badgeClass}`}>
                      {codBadge(risk)}
                    </span>
                  )}
                </div>
                <div className="text-gray-600">
                  {t("ord.delivery")} <strong>{o.wilaya_code} - {o.wilaya_name}</strong> ({o.commune}) •{" "}
                  <strong>{o.delivery_method === "stop_desk" ? t("ord.stop_desk") : t("ord.home")}</strong>
                  {o.delivery_address ? <> • {o.delivery_address}</> : null}
                </div>
                {Array.isArray(o.items) && o.items.length > 0 && (
                  <ul className="text-gray-800">
                    {o.items.map((it: any) => (
                      <li key={it.id}>
                        {it.quantity} × <strong>{it.product_name}</strong>
                        {it.variant_title ? ` (${it.variant_title})` : ""} <span className="text-gray-500 font-mono">{it.sku}</span>
                        {" — "}{Number(it.line_total_dzd || 0).toLocaleString("fr-FR")} DA
                      </li>
                    ))}
                  </ul>
                )}
                <div className="font-bold text-[#063D2E]">
                  {t("ord.items_total", { amount: Number(o.subtotal_dzd).toLocaleString("fr-FR") })}
                  {Number(o.subtotal_dzd) + Number(o.delivery_fee_dzd) !== Number(o.total_dzd) ? t("ord.discount", { amount: (Number(o.subtotal_dzd) + Number(o.delivery_fee_dzd) - Number(o.total_dzd)).toLocaleString("fr-FR") }) + (o.coupon_code ? t("ord.with_code", { code: o.coupon_code }) : "") : ""}
                  {" "}{t("ord.plus_delivery", { fee: Number(o.delivery_fee_dzd) === 0 ? t("ord.free") : `${Number(o.delivery_fee_dzd).toLocaleString("fr-FR")} DA` })}
                  {" "}{t("ord.to_collect", { amount: Number(o.total_dzd).toLocaleString("fr-FR") })}
                </div>
                {o.created_at && (
                  <div className="text-[11px] text-gray-500">
                    {t("ord.received_on", { date: serverDate(o.created_at).toLocaleString(localeFor()) })}
                    {o.customer_notes ? <>{t("ord.customer_note")}<em>{o.customer_notes}</em></> : null}
                  </div>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={o.status}
                  aria-label={t("ord.status_aria", { ref: o.order_reference })}
                  disabled={o.status === "cancelled" || o.status === "returned"}
                  onChange={(e) => handleOrderStatusChange(o.id, e.target.value)}
                  className="px-3 py-1.5 rounded-lg border font-bold bg-[#F8F6F0] disabled:opacity-60"
                >
                  {allowedOrderStatuses(o.status).map((st) => (
                    <option key={st} value={st}>{orderStatusLabel(st)}</option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => handleOpenInvoice(o.id)}
                  className="px-3 py-1.5 rounded-lg bg-[#063D2E] text-[#D4AF62] font-bold"
                >
                  {t("invoice_modal.title", { ref: "" }).replace("·", "").trim() || "Facture"}
                </button>
                <button
                  type="button"
                  onClick={() => setDeliveryNoteOrderId(o.id)}
                  className="px-3 py-1.5 rounded-lg bg-[#D4AF62] text-[#02291F] font-bold"
                  title={t("delivery_modal.doc_heading")}
                >
                  {t("delivery_modal.doc_heading")}
                </button>
                <button
                  type="button"
                  onClick={() => handleNotifyOrderCustomerWhatsapp(o.id, "confirmation_call")}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold"
                  title="WhatsApp"
                >
                  <MessageCircle className="w-3.5 h-3.5 text-white" />
                  <span>WhatsApp</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleNotifyOrderCustomerWhatsapp(o.id, "shipped_notice")}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#F8F6F0] border border-[#063D2E] text-[#063D2E] font-bold hover:bg-gray-100 transition"
                >
                  <Truck className="w-3.5 h-3.5 text-[#063D2E]" />
                  <span>{t("ord.shipment")}</span>
                </button>
                {risk.is_blacklisted ? (
                  <button
                    type="button"
                    onClick={() => handleUnblockCustomerPhone(o.customer_phone)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-700 text-white font-bold hover:bg-emerald-800 transition"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 text-white" />
                    <span>{t("ord.unblock")}</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => handleBlockCustomerPhone(o.customer_phone, t("ord.block_reason"))}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-50 text-red-800 border border-red-200 font-bold hover:bg-red-100 transition"
                  >
                    <Ban className="w-3.5 h-3.5 text-red-700" />
                    <span>{t("ord.block")}</span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Anti-Retour COD & Phone Blacklist Control Panel */}
      <div className="p-5 rounded-2xl bg-[#F8F6F0] border border-[#D4AF62]/40 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h4 className="font-serif font-bold text-base text-[#063D2E]">{t("ord.cod_title", { n: codBlacklist.length })}</h4>
            <p className="text-gray-500">{t("ord.cod_sub")}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={codCheckPhone}
            onChange={(e) => setCodCheckPhone(e.target.value)}
            placeholder={t("ord.phone_ph")}
            className="px-3 py-2 border rounded-xl bg-white font-mono w-56"
          />
          <input
            value={codBlacklistReason}
            onChange={(e) => setCodBlacklistReason(e.target.value)}
            placeholder={t("ord.reason_ph")}
            className="px-3 py-2 border rounded-xl bg-white flex-1"
          />
          <button
            type="button"
            onClick={handleCheckPhoneCodRisk}
            className="px-3.5 py-2 rounded-xl bg-[#063D2E] text-[#E8D4A5] font-bold"
          >
            {t("ord.check_score")}
          </button>
          <button
            type="button"
            onClick={() => handleBlockCustomerPhone(codCheckPhone, codBlacklistReason)}
            className="px-3.5 py-2 rounded-xl bg-red-700 text-white font-bold"
          >
            {t("ord.block_number")}
          </button>
        </div>
        {codCheckResult && (
          <div className="p-3 rounded-xl bg-white border flex flex-wrap items-center justify-between gap-2">
            <div>
              <strong className="font-mono text-[#063D2E]">{codCheckResult.phone_local} ({codCheckResult.phone_e164})</strong> — {codBadge(codCheckResult)}
            </div>
            <div className="font-mono">
              {t("ord.check_counts", { orders: codCheckResult.total_orders, deliv: codCheckResult.delivered_count, ret: codCheckResult.returned_count, rate: codCheckResult.return_rate_percent })}
            </div>
          </div>
        )}
        {codBlacklist.length > 0 && (
          <div className="space-y-1.5 pt-1">
            {codBlacklist.map((bl) => (
              <div key={bl.phone_e164} className="p-2.5 rounded-xl bg-red-50 border border-red-200 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Ban className="w-4 h-4 text-red-700 shrink-0" />
                  <span className="font-mono font-bold text-red-900">{bl.phone_local} ({bl.phone_e164})</span>
                  <span className="text-gray-400">•</span>
                  <span className="text-red-800">{bl.reason}</span>
                </div>
                <button
                  type="button"
                  onClick={() => handleUnblockCustomerPhone(bl.phone_e164)}
                  className="px-2.5 py-1 rounded bg-white text-emerald-900 border font-bold"
                >
                  {t("ord.unblock")}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {waOutbox.length > 0 && (
        <div className="bg-white p-5 rounded-2xl border border-[#D4AF62]/40 shadow-xs space-y-2 text-xs">
          <h4 className="font-serif font-bold text-[#063D2E] text-sm flex items-center gap-2">
            <Radio className="w-4 h-4 text-[#D4AF62]" />
            <span>{t("ord.wa_prepared", { n: waOutbox.length })}</span>
          </h4>
          <div className="space-y-1.5 max-h-40 overflow-y-auto">
            {waOutbox.slice(0, 6).map((m: any, idx: number) => (
              <div key={m.message_id || idx} className="p-2.5 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="font-mono font-bold text-[#063D2E] mr-2">{m.recipient_local || m.recipient_e164}</span>
                  <span className="px-2 py-0.5 rounded bg-[#063D2E] text-[#D4AF62] text-[10px] font-bold mr-2">
                    {m.template_type || m.channel || "OTP"}
                  </span>
                  <span className="text-gray-700">{m.message_text ? m.message_text.slice(0, 95) + "..." : t("ord.message_id", { id: m.message_id })}</span>
                </div>
                {m.wa_me_customer_url && (
                  <button
                    type="button"
                    onClick={() => openExternalUrl(m.wa_me_customer_url).catch((err) => notifyClientError(err, t("ord.wa_open_failed")))}
                    className="px-2.5 py-1 rounded-lg bg-emerald-700 text-white font-bold text-[10px]"
                  >
                    {t("ord.wa_reopen")}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {selectedInvoice && (
        <div className="p-5 rounded-2xl bg-[#F8F6F0] border-2 border-[#D4AF62] space-y-2">
          <div className="flex justify-between items-center">
            <h4 className="font-serif font-bold text-base text-[#063D2E]">
              {t("ord.invoice_title", { ref: selectedInvoice.order_reference, shop: selectedInvoice.boutique_info?.name || "" })}
            </h4>
            <button aria-label={t("ord.close")}
              type="button"
              onClick={() => setSelectedInvoice(null)}
              className="p-1 rounded-lg text-gray-500 hover:text-black transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <p><strong>{t("ord.inv_shop")}</strong> {selectedInvoice.boutique_info?.address} • {t("ord.inv_phone", { phone: selectedInvoice.boutique_info?.phone || "" })}</p>
          <p><strong>{t("ord.inv_customer")}</strong> {selectedInvoice.customer_name} ({selectedInvoice.customer_phone}) — {selectedInvoice.delivery_address}</p>
          <p className="font-extrabold text-sm text-[#063D2E]">{t("ord.inv_total", { amount: selectedInvoice.total_dzd })}</p>
        </div>
      )}
    </div>
  );
}

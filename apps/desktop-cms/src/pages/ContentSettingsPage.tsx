import React, { useCallback, useEffect, useRef, useState } from "react";
import { DesktopCmsApi } from "../api/adminClient";
import { HomepageContentPanel } from "../components/HomepageContentPanel";
import { notifyClientError, notifyClientSuccess, notifyClientWarning } from "../utils/clientNotifier";
import { useT } from "../i18n";

// The shop's hours as they were written in the page, shown until the owner
// saves their own (CMS → Paramètres boutique).
const DEFAULT_OPENING_HOURS = [
  "Samedi : 10h00 – 20h00", "Dimanche : 10h00 – 20h00", "Lundi : 10h00 – 20h00", "Mardi : 10h00 – 20h00",
  "Mercredi : 10h00 – 20h00", "Jeudi : 10h00 – 20h00", "Vendredi (prière du vendredi) : 15h00 – 21h00",
].join("\n");

/** The Contenu & Bannières screen: home-page blocks and banners, the shop's
 *  contact details / hours / free delivery, promo codes and information pages.
 *  It loads and saves its own data (nothing else in the CMS uses it). */
export interface ContentSettingsPageProps {
  /** The screen is visible: reload so it shows what is on the server. */
  active: boolean;
  /** The user may edit the shop content (content:write). */
  canEdit: boolean;
  categories: any[];
  products: any[];
}

export function ContentSettingsPage({ active, canEdit, categories, products }: ContentSettingsPageProps) {
  const t = useT();
  const [storePhoneInput, setStorePhoneInput] = useState("");
  const [storeWhatsappInput, setStoreWhatsappInput] = useState("");
  const [storeLocationInput, setStoreLocationInput] = useState("");
  const [mapsUrlInput, setMapsUrlInput] = useState("");
  const [openingHoursInput, setOpeningHoursInput] = useState(DEFAULT_OPENING_HOURS);
  const [freeThresholdInput, setFreeThresholdInput] = useState("");
  const [instagramInput, setInstagramInput] = useState("");
  const [tiktokInput, setTiktokInput] = useState("");
  // Set while the owner is typing: a background refresh (window focus,
  // auto-reload) must not wipe what has not been saved yet.
  const settingsDirtyRef = useRef(false);
  const pageDirtyRef = useRef(false);
  // Edit counters: a save only marks the form clean if nothing was typed while
  // it was being sent; otherwise the reload after it keeps the newer typing.
  const settingsRevRef = useRef(0);
  const pageRevRef = useRef(0);
  const [couponCode, setCouponCode] = useState("");
  const [couponType, setCouponType] = useState<"percentage" | "fixed_dzd">("percentage");
  const [couponValue, setCouponValue] = useState(10);
  const [couponMinOrder, setCouponMinOrder] = useState(5000);
  const [pageSlug, setPageSlug] = useState("about");
  const EMPTY_PAGE = { title_fr: "", title_ar: "", title_en: "", content_fr: "", content_ar: "", content_en: "" };
  const [pageDraft, setPageDraft] = useState<Record<string, string>>(EMPTY_PAGE);
  const [pageLang, setPageLang] = useState<"fr" | "ar" | "en">("fr");
  const pageDraftFrom = (pg: any) => ({
    title_fr: pg?.title_fr || "", title_ar: pg?.title_ar || "", title_en: pg?.title_en || "",
    content_fr: pg?.content_fr || "", content_ar: pg?.content_ar || "", content_en: pg?.content_en || "",
  });
  const [coupons, setCoupons] = useState<any[]>([]);
  const [staticPages, setStaticPages] = useState<any[]>([]);
  // Read by load() without making it re-run when another page is picked.
  const pageSlugRef = useRef(pageSlug);
  pageSlugRef.current = pageSlug;

  const load = useCallback(async () => {
    if (!canEdit) return;
    try {
      const [layData, pgData, cpnData] = await Promise.all([
        DesktopCmsApi.getStoreLayout().catch(() => ({ homepage_sections: [] })),
        DesktopCmsApi.listStaticPages().catch(() => ({ items: [] })),
        DesktopCmsApi.listCoupons().catch(() => ({ items: [] })),
      ]);
      setCoupons(cpnData.items || []);
    if (layData.settings && !settingsDirtyRef.current) {
      const s = layData.settings;
      setStorePhoneInput(String(s.store_phone || s.contact_phone || ""));
      setStoreWhatsappInput(String(s.whatsapp_contact_number || s.whatsapp_phone || ""));
      setStoreLocationInput(String(s.store_location || ""));
      setMapsUrlInput(String(s.store_maps_url || ""));
      setOpeningHoursInput(String(s.opening_hours || "").trim() || DEFAULT_OPENING_HOURS);
      setFreeThresholdInput(String(s.free_delivery_threshold_dzd ?? s.free_shipping_threshold_dzd ?? ""));
      setInstagramInput(String(s.instagram_url || ""));
      setTiktokInput(String(s.tiktok_url || ""));
    }
    const loadedPages = pgData.items || [];
    setStaticPages(loadedPages);
    if (!pageDirtyRef.current) {
      setPageDraft(pageDraftFrom(loadedPages.find((p: any) => p.slug === pageSlugRef.current)));
    }
    } catch (err: any) {
      notifyClientError(err, t("cs.load_failed"), false);
    }
  }, [canEdit]);

  useEffect(() => {
    if (active) void load();
  }, [active, load]);

  async function handleSaveStoreSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!storePhoneInput.trim() || !storeLocationInput.trim()) {
      notifyClientWarning(t("cs.incomplete_title"), t("cs.incomplete_body"));
      return;
    }
    const hourLines = openingHoursInput.split("\n").map((l) => l.trim()).filter(Boolean);
    if (hourLines.length > 14 || hourLines.some((l) => l.length > 80 || !l.includes(":"))) {
      notifyClientWarning(t("cs.hours_title"), t("cs.hours_body"));
      return;
    }
    const threshold = freeThresholdInput.replace(/\s/g, "");
    if (threshold && !/^\d+$/.test(threshold)) {
      notifyClientWarning(t("cs.threshold_title"), t("cs.threshold_body"));
      return;
    }
    const waDigits = storeWhatsappInput.replace(/[^\d]/g, "");
    if (storeWhatsappInput.trim() && (waDigits.length < 9 || waDigits.length > 15)) {
      notifyClientWarning(t("cs.wa_title"), t("cs.wa_body"));
      return;
    }
    for (const [label, url] of [["Instagram", instagramInput], ["TikTok", tiktokInput], ["Google Maps", mapsUrlInput]]) {
      if (url.trim() && !/^https:\/\/[^\s]+$/.test(url.trim())) {
        notifyClientWarning(t("cs.link_title", { label }), t("cs.link_body"));
        return;
      }
    }
    const savedRev = settingsRevRef.current;
    try {
      await DesktopCmsApi.updateStoreSettings({
        store_phone: storePhoneInput.trim(),
        whatsapp_contact_number: storeWhatsappInput.trim(),
        store_location: storeLocationInput.trim(),
        opening_hours: hourLines.join("\n"),
        store_maps_url: mapsUrlInput.trim(),
        free_delivery_threshold_dzd: threshold || "0",
        instagram_url: instagramInput.trim(),
        tiktok_url: tiktokInput.trim(),
      });
      if (settingsRevRef.current === savedRev) settingsDirtyRef.current = false;
      const okMsg = t("cs.saved_body");
      notifyClientSuccess(t("cs.saved_title"), okMsg);
      await load();
    } catch (err: any) {
      notifyClientError(err, t("cs.save_refused"));
    }
  }

  async function handleCreateCoupon(e: React.FormEvent) {
    e.preventDefault();
    const cleanCode = couponCode.trim().toUpperCase();
    if (cleanCode.length < 3 || Number(couponValue) <= 0) {
      notifyClientWarning(
        t("cs.coupon_bad_title"),
        t("cs.coupon_bad_body")
      );
      return;
    }
    try {
      await DesktopCmsApi.createCoupon({
        code: cleanCode,
        discount_type: couponType,
        discount_value: Number(couponValue),
        min_order_dzd: Math.max(0, Number(couponMinOrder) || 0),
      });
      const okMsg = t("cs.coupon_created", { code: cleanCode });
      notifyClientSuccess(t("cs.coupon_on_title"), okMsg);
      setCouponCode("");
      await load();
    } catch (err: any) {
      notifyClientError(err, t("cs.coupon_create_refused"));
    }
  }

  async function handleDeactivateCoupon(couponId: number, code: string) {
    try {
      await DesktopCmsApi.deactivateCoupon(couponId);
      const okMsg = t("cs.coupon_off", { code });
      notifyClientSuccess(t("cs.coupon_off_title"), okMsg);
      await load();
    } catch (err: any) {
      notifyClientError(err, t("cs.coupon_off_failed"));
    }
  }

  async function handleSaveStaticPage(e: React.FormEvent) {
    e.preventDefault();
    if (pageDraft.title_fr.trim().length < 2 || pageDraft.content_fr.trim().length < 5) {
      notifyClientWarning(
        t("cs.page_incomplete_title"),
        t("cs.page_incomplete_body")
      );
      return;
    }
    const savedRev = pageRevRef.current;
    try {
      await DesktopCmsApi.upsertStaticPage(pageSlug, {
        title_fr: pageDraft.title_fr.trim(),
        title_ar: pageDraft.title_ar.trim(),
        title_en: pageDraft.title_en.trim(),
        content_fr: pageDraft.content_fr.trim(),
        content_ar: pageDraft.content_ar.trim(),
        content_en: pageDraft.content_en.trim(),
        is_published: true,
      });
      if (pageRevRef.current === savedRev) pageDirtyRef.current = false;
      const okMsg = t("cs.page_published", { slug: pageSlug });
      notifyClientSuccess(t("cs.page_published_title"), okMsg);
      await load();
    } catch (err: any) {
      notifyClientError(err, t("cs.page_failed"));
    }
  }

  return (
    <div className="space-y-6 text-xs">
      {canEdit && <HomepageContentPanel categories={categories} products={products} />}

      <form onSubmit={handleSaveStoreSettings} onChange={() => { settingsDirtyRef.current = true; settingsRevRef.current += 1; }} className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4">
        <div>
          <h3 className="text-base font-serif font-bold text-[#063D2E]">{t("cs.contact_title")}</h3>
          <p className="text-gray-500">{t("cs.contact_sub")}</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="block font-bold mb-1">{t("cs.phone")}</label>
            <input value={storePhoneInput} onChange={(e) => setStorePhoneInput(e.target.value)} placeholder="0655 53 41 54" className="w-full px-3 py-2 border rounded-xl font-mono" />
          </div>
          <div>
            <label className="block font-bold mb-1">{t("cs.whatsapp")}</label>
            <input value={storeWhatsappInput} onChange={(e) => setStoreWhatsappInput(e.target.value)} placeholder="+213 655 53 41 54" className="w-full px-3 py-2 border rounded-xl font-mono" />
          </div>
          <div>
            <label className="block font-bold mb-1">{t("cs.address")}</label>
            <input value={storeLocationInput} onChange={(e) => setStoreLocationInput(e.target.value)} className="w-full px-3 py-2 border rounded-xl" />
          </div>
          <div>
            <label className="block font-bold mb-1">{t("cs.maps")}</label>
            <input value={mapsUrlInput} onChange={(e) => setMapsUrlInput(e.target.value)} placeholder="https://www.google.com/maps/…" className="w-full px-3 py-2 border rounded-xl font-mono" />
          </div>
          <div>
            <label className="block font-bold mb-1">{t("cs.instagram")}</label>
            <input value={instagramInput} onChange={(e) => setInstagramInput(e.target.value)} placeholder="https://www.instagram.com/…" className="w-full px-3 py-2 border rounded-xl font-mono" />
          </div>
          <div>
            <label className="block font-bold mb-1">{t("cs.tiktok")}</label>
            <input value={tiktokInput} onChange={(e) => setTiktokInput(e.target.value)} placeholder="https://www.tiktok.com/@…" className="w-full px-3 py-2 border rounded-xl font-mono" />
          </div>
          <div>
            <label className="block font-bold mb-1">{t("cs.free_from")}</label>
            <input inputMode="numeric" value={freeThresholdInput} onChange={(e) => setFreeThresholdInput(e.target.value)} placeholder={t("cs.free_ph")} className="w-full px-3 py-2 border rounded-xl font-bold" />
            <p className="text-[11px] text-gray-500 mt-1">
              {Number(freeThresholdInput.replace(/\s/g, "")) > 0
                ? t("cs.free_on", { amount: Number(freeThresholdInput.replace(/\s/g, "")).toLocaleString("fr-FR") })
                : t("cs.free_off")}
            </p>
          </div>
        </div>
        <div>
          <label htmlFor="store-opening-hours" className="block font-bold mb-1">{t("cs.hours")}</label>
          <textarea id="store-opening-hours" rows={7} value={openingHoursInput} onChange={(e) => setOpeningHoursInput(e.target.value)} className="w-full md:w-2/3 px-3 py-2 border rounded-xl font-mono text-xs" />
          <p className="text-[11px] text-gray-500 mt-1">{t("cs.hours_hint")}</p>
        </div>
        <button type="submit" className="px-5 py-2.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold">
          {t("cs.save_contact")}
        </button>
      </form>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <form onSubmit={handleCreateCoupon} className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
          <h3 className="text-base font-serif font-bold text-[#063D2E]">{t("cs.coupon_new")}</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-bold mb-1">{t("cs.coupon_code")}</label>
              <input value={couponCode} onChange={(e) => setCouponCode(e.target.value)} required placeholder="LUXE20" className="w-full px-3 py-2 border rounded-xl font-mono uppercase" />
            </div>
            <div>
              <label className="block font-bold mb-1">{t("cs.coupon_type")}</label>
              <select value={couponType} onChange={(e) => setCouponType(e.target.value as "percentage" | "fixed_dzd")} className="w-full px-3 py-2 border rounded-xl bg-white">
                <option value="percentage">{t("cs.coupon_pct")}</option>
                <option value="fixed_dzd">{t("cs.coupon_fixed")}</option>
              </select>
            </div>
            <div>
              <label className="block font-bold mb-1">Valeur</label>
              <input type="number" min={1} value={couponValue} onChange={(e) => setCouponValue(Number(e.target.value))} required className="w-full px-3 py-2 border rounded-xl font-bold" />
            </div>
            <div>
              <label className="block font-bold mb-1">{t("cs.coupon_min")}</label>
              <input type="number" min={0} value={couponMinOrder} onChange={(e) => setCouponMinOrder(Number(e.target.value))} required className="w-full px-3 py-2 border rounded-xl" />
            </div>
          </div>
          <button type="submit" className="px-5 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold">
            {t("cs.coupon_activate")}
          </button>
          {coupons.length > 0 && (
            <div className="pt-3 border-t space-y-1.5">
              <p className="font-bold text-[#063D2E]">{t("cs.coupons_saved", { n: coupons.length })}</p>
              {/* Every code stays reachable (active ones first), in a scrolling list. */}
              <div className="max-h-64 overflow-y-auto space-y-1.5 pr-1">
              {[...coupons].sort((a: any, b: any) => Number(b.is_active) - Number(a.is_active)).map((cpn: any) => (
                <div key={cpn.id} className="flex items-center justify-between bg-[#F8F6F0] px-3 py-1.5 rounded-lg border">
                  <span>
                    <strong className="font-mono text-[#063D2E]">{cpn.code}</strong> ({cpn.discount_value}{cpn.discount_type === "percentage" ? "%" : " DA"}) • {t("cs.coupon_uses", { n: `${cpn.usage_count}${cpn.usage_limit ? `/${cpn.usage_limit}` : ""}` })}{cpn.orders_count !== undefined ? t("cs.coupon_orders", { n: cpn.orders_count, amount: Number(cpn.discount_given_dzd || 0).toLocaleString("fr-FR") }) : ""}
                  </span>
                  {cpn.is_active ? (
                    <button type="button" onClick={() => handleDeactivateCoupon(cpn.id, cpn.code)} className="px-2 py-0.5 rounded bg-red-50 text-red-700 font-bold">
                      {t("cs.deactivate")}
                    </button>
                  ) : (
                    <span className="text-gray-400 font-bold">{t("cs.inactive")}</span>
                  )}
                </div>
              ))}
              </div>
            </div>
          )}
        </form>

        <form onSubmit={handleSaveStaticPage} onChange={() => { pageDirtyRef.current = true; pageRevRef.current += 1; }} className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
          <div>
            <h3 className="text-base font-serif font-bold text-[#063D2E]">{t("cs.pages_title")}</h3>
            <p className="text-gray-500">{t("cs.pages_sub")}</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-bold mb-1">{t("cs.page")}</label>
              <select value={pageSlug} onChange={(e) => {
                const nextSlug = e.target.value;
                if (pageDirtyRef.current && !window.confirm(t("cs.unsaved_confirm"))) return;
                setPageSlug(nextSlug);
                pageDirtyRef.current = false;
                setPageDraft(pageDraftFrom(staticPages.find((p: any) => p.slug === nextSlug)));
              }} className="w-full px-3 py-2 border rounded-xl bg-white">
                <option value="about">{t("cs.p_about")}</option>
                <option value="faq">{t("cs.p_faq")}</option>
                <option value="returns">{t("cs.p_returns")}</option>
                <option value="terms">{t("cs.p_terms")}</option>
              </select>
            </div>
            <div>
              <label className="block font-bold mb-1">{t("cs.language")}</label>
              <div className="flex gap-1">
                {(["fr", "ar", "en"] as const).map((l) => (
                  <button key={l} type="button" onClick={() => setPageLang(l)}
                    className={`flex-1 py-2 rounded-xl border font-bold ${pageLang === l ? "bg-[#063D2E] text-[#D4AF62] border-[#063D2E]" : "bg-white text-gray-600"}`}>
                    {l.toUpperCase()}{l === "fr" ? " *" : pageDraft[`content_${l}`] ? "" : t("cs.empty")}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div>
            <label className="block font-bold mb-1">{t("cs.title_l", { l: pageLang.toUpperCase() })}</label>
            <input dir={pageLang === "ar" ? "rtl" : "ltr"} value={pageDraft[`title_${pageLang}`] || ""} onChange={(e) => setPageDraft({ ...pageDraft, [`title_${pageLang}`]: e.target.value })} required={pageLang === "fr"} className="w-full px-3 py-2 border rounded-xl" />
          </div>
          <div>
            <label className="block font-bold mb-1">{t("cs.text_l", { l: pageLang.toUpperCase() })}</label>
            <textarea dir={pageLang === "ar" ? "rtl" : "ltr"} rows={9} value={pageDraft[`content_${pageLang}`] || ""} onChange={(e) => setPageDraft({ ...pageDraft, [`content_${pageLang}`]: e.target.value })} required={pageLang === "fr"} className="w-full px-3 py-2 border rounded-xl leading-relaxed" />
            <p className="text-[11px] text-gray-500">{t("cs.para_hint")}</p>
          </div>
          <button type="submit" className="px-5 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold">
            {t("cs.publish")}
          </button>
        </form>
      </div>
    </div>
  );
}

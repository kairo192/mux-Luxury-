import React, { useCallback, useEffect, useRef, useState } from "react";
import { DesktopCmsApi } from "../api/adminClient";
import { HomepageContentPanel } from "../components/HomepageContentPanel";
import { notifyClientError, notifyClientSuccess, notifyClientWarning } from "../utils/clientNotifier";

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
      notifyClientError(err, "Chargement du contenu de la boutique impossible", false);
    }
  }, [canEdit]);

  useEffect(() => {
    if (active) void load();
  }, [active, load]);

  async function handleSaveStoreSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!storePhoneInput.trim() || !storeLocationInput.trim()) {
      notifyClientWarning("Paramètres incomplets", "Veuillez renseigner le téléphone et l'adresse officielle de la boutique Mus Luxury.");
      return;
    }
    const hourLines = openingHoursInput.split("\n").map((l) => l.trim()).filter(Boolean);
    if (hourLines.length > 14 || hourLines.some((l) => l.length > 80 || !l.includes(":"))) {
      notifyClientWarning("Horaires invalides", "Une ligne par jour, sous la forme « Samedi : 10h00 – 20h00 » (14 lignes au plus).");
      return;
    }
    const threshold = freeThresholdInput.replace(/\s/g, "");
    if (threshold && !/^\d+$/.test(threshold)) {
      notifyClientWarning("Seuil invalide", "Le seuil de livraison gratuite est un montant en DA (chiffres seulement), ou 0 pour le désactiver.");
      return;
    }
    const waDigits = storeWhatsappInput.replace(/[^\d]/g, "");
    if (storeWhatsappInput.trim() && (waDigits.length < 9 || waDigits.length > 15)) {
      notifyClientWarning("Numéro WhatsApp invalide", "Exemple : +213 655 53 41 54");
      return;
    }
    for (const [label, url] of [["Instagram", instagramInput], ["TikTok", tiktokInput], ["Google Maps", mapsUrlInput]]) {
      if (url.trim() && !/^https:\/\/[^\s]+$/.test(url.trim())) {
        notifyClientWarning(`Lien ${label} invalide`, "Collez l'adresse complète de la page, commençant par https://");
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
      const okMsg = "Paramètres de la boutique Mus Luxury enregistrés et synchronisés.";
      notifyClientSuccess("Paramètres boutique enregistrés", okMsg);
      await load();
    } catch (err: any) {
      notifyClientError(err, "Enregistrement des paramètres refusé");
    }
  }

  async function handleCreateCoupon(e: React.FormEvent) {
    e.preventDefault();
    const cleanCode = couponCode.trim().toUpperCase();
    if (cleanCode.length < 3 || Number(couponValue) <= 0) {
      notifyClientWarning(
        "Code promo invalide",
        "Veuillez saisir un code promo d'au moins 3 caractères et une valeur de remise strictement positive."
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
      const okMsg = `Code promo "${cleanCode}" créé et activé sur la boutique.`;
      notifyClientSuccess("Code promotionnel activé", okMsg);
      setCouponCode("");
      await load();
    } catch (err: any) {
      notifyClientError(err, "Création du code promo refusée");
    }
  }

  async function handleDeactivateCoupon(couponId: number, code: string) {
    try {
      await DesktopCmsApi.deactivateCoupon(couponId);
      const okMsg = `Code promo "${code}" désactivé avec succès.`;
      notifyClientSuccess("Code promo désactivé", okMsg);
      await load();
    } catch (err: any) {
      notifyClientError(err, "Désactivation du code promo impossible");
    }
  }

  async function handleSaveStaticPage(e: React.FormEvent) {
    e.preventDefault();
    if (pageDraft.title_fr.trim().length < 2 || pageDraft.content_fr.trim().length < 5) {
      notifyClientWarning(
        "Contenu de page incomplet",
        "Veuillez saisir un titre et un texte complet avant de publier la page statique."
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
      const okMsg = `Page statique "/pages/${pageSlug}" enregistrée et publiée.`;
      notifyClientSuccess("Page statique publiée", okMsg);
      await load();
    } catch (err: any) {
      notifyClientError(err, "Enregistrement de la page statique impossible");
    }
  }

  return (
    <div className="space-y-6 text-xs">
      {canEdit && <HomepageContentPanel categories={categories} products={products} />}

      <form onSubmit={handleSaveStoreSettings} onChange={() => { settingsDirtyRef.current = true; settingsRevRef.current += 1; }} className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4">
        <div>
          <h3 className="text-base font-serif font-bold text-[#063D2E]">Coordonnées de la boutique</h3>
          <p className="text-gray-500">Affichées partout sur la boutique en ligne (en-tête, pied de page, boutons WhatsApp, page produit).</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="block font-bold mb-1">Téléphone affiché</label>
            <input value={storePhoneInput} onChange={(e) => setStorePhoneInput(e.target.value)} placeholder="0655 53 41 54" className="w-full px-3 py-2 border rounded-xl font-mono" />
          </div>
          <div>
            <label className="block font-bold mb-1">Numéro WhatsApp</label>
            <input value={storeWhatsappInput} onChange={(e) => setStoreWhatsappInput(e.target.value)} placeholder="+213 655 53 41 54" className="w-full px-3 py-2 border rounded-xl font-mono" />
          </div>
          <div>
            <label className="block font-bold mb-1">Adresse de la boutique</label>
            <input value={storeLocationInput} onChange={(e) => setStoreLocationInput(e.target.value)} className="w-full px-3 py-2 border rounded-xl" />
          </div>
          <div>
            <label className="block font-bold mb-1">Lien Google Maps de la boutique</label>
            <input value={mapsUrlInput} onChange={(e) => setMapsUrlInput(e.target.value)} placeholder="https://www.google.com/maps/…" className="w-full px-3 py-2 border rounded-xl font-mono" />
          </div>
          <div>
            <label className="block font-bold mb-1">Page Instagram (lien)</label>
            <input value={instagramInput} onChange={(e) => setInstagramInput(e.target.value)} placeholder="https://www.instagram.com/…" className="w-full px-3 py-2 border rounded-xl font-mono" />
          </div>
          <div>
            <label className="block font-bold mb-1">Page TikTok (lien)</label>
            <input value={tiktokInput} onChange={(e) => setTiktokInput(e.target.value)} placeholder="https://www.tiktok.com/@…" className="w-full px-3 py-2 border rounded-xl font-mono" />
          </div>
          <div>
            <label className="block font-bold mb-1">Livraison gratuite à partir de (DA)</label>
            <input inputMode="numeric" value={freeThresholdInput} onChange={(e) => setFreeThresholdInput(e.target.value)} placeholder="0 = pas de livraison gratuite" className="w-full px-3 py-2 border rounded-xl font-bold" />
            <p className="text-[11px] text-gray-500 mt-1">
              {Number(freeThresholdInput.replace(/\s/g, "")) > 0
                ? `Commandes de ${Number(freeThresholdInput.replace(/\s/g, "")).toLocaleString("fr-FR")} DA ou plus : livraison offerte (appliquée aussi par le serveur).`
                : "Désactivée : la livraison est toujours payante."}
            </p>
          </div>
        </div>
        <div>
          <label htmlFor="store-opening-hours" className="block font-bold mb-1">Horaires d'ouverture</label>
          <textarea id="store-opening-hours" rows={7} value={openingHoursInput} onChange={(e) => setOpeningHoursInput(e.target.value)} className="w-full md:w-2/3 px-3 py-2 border rounded-xl font-mono text-xs" />
          <p className="text-[11px] text-gray-500 mt-1">Une ligne par jour : « Jour : horaires » (ex. « Vendredi : Fermé »). Affichés sur la page Contact de la boutique.</p>
        </div>
        <button type="submit" className="px-5 py-2.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold">
          Enregistrer les coordonnées
        </button>
      </form>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <form onSubmit={handleCreateCoupon} className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
          <h3 className="text-base font-serif font-bold text-[#063D2E]">+ Créer un Code Promo Client</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-bold mb-1">Code (ex: RAMADAN15)</label>
              <input value={couponCode} onChange={(e) => setCouponCode(e.target.value)} required placeholder="LUXE20" className="w-full px-3 py-2 border rounded-xl font-mono uppercase" />
            </div>
            <div>
              <label className="block font-bold mb-1">Type de remise</label>
              <select value={couponType} onChange={(e) => setCouponType(e.target.value as "percentage" | "fixed_dzd")} className="w-full px-3 py-2 border rounded-xl bg-white">
                <option value="percentage">Pourcentage (%)</option>
                <option value="fixed_dzd">Montant fixe (DA)</option>
              </select>
            </div>
            <div>
              <label className="block font-bold mb-1">Valeur</label>
              <input type="number" min={1} value={couponValue} onChange={(e) => setCouponValue(Number(e.target.value))} required className="w-full px-3 py-2 border rounded-xl font-bold" />
            </div>
            <div>
              <label className="block font-bold mb-1">Minimum commande (DA)</label>
              <input type="number" min={0} value={couponMinOrder} onChange={(e) => setCouponMinOrder(Number(e.target.value))} required className="w-full px-3 py-2 border rounded-xl" />
            </div>
          </div>
          <button type="submit" className="px-5 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold">
            Activer le Code Promo
          </button>
          {coupons.length > 0 && (
            <div className="pt-3 border-t space-y-1.5">
              <p className="font-bold text-[#063D2E]">Codes Promo Enregistrés ({coupons.length})</p>
              {/* Every code stays reachable (active ones first), in a scrolling list. */}
              <div className="max-h-64 overflow-y-auto space-y-1.5 pr-1">
              {[...coupons].sort((a: any, b: any) => Number(b.is_active) - Number(a.is_active)).map((cpn: any) => (
                <div key={cpn.id} className="flex items-center justify-between bg-[#F8F6F0] px-3 py-1.5 rounded-lg border">
                  <span>
                    <strong className="font-mono text-[#063D2E]">{cpn.code}</strong> ({cpn.discount_value}{cpn.discount_type === "percentage" ? "%" : " DA"}) • Utilisations: {cpn.usage_count}{cpn.usage_limit ? `/${cpn.usage_limit}` : ""}{cpn.orders_count !== undefined ? ` • ${cpn.orders_count} commande(s) gardée(s), ${Number(cpn.discount_given_dzd || 0).toLocaleString("fr-FR")} DA de remise` : ""}
                  </span>
                  {cpn.is_active ? (
                    <button type="button" onClick={() => handleDeactivateCoupon(cpn.id, cpn.code)} className="px-2 py-0.5 rounded bg-red-50 text-red-700 font-bold">
                      Désactiver
                    </button>
                  ) : (
                    <span className="text-gray-400 font-bold">Inactif</span>
                  )}
                </div>
              ))}
              </div>
            </div>
          )}
        </form>

        <form onSubmit={handleSaveStaticPage} onChange={() => { pageDirtyRef.current = true; pageRevRef.current += 1; }} className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
          <div>
            <h3 className="text-base font-serif font-bold text-[#063D2E]">Pages d'information</h3>
            <p className="text-gray-500">Ouvertes depuis le pied de page de la boutique. Sans texte arabe / anglais, le texte français est affiché.</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-bold mb-1">Page</label>
              <select value={pageSlug} onChange={(e) => {
                const nextSlug = e.target.value;
                if (pageDirtyRef.current && !window.confirm("Les modifications non enregistrées de cette page seront perdues. Continuer ?")) return;
                setPageSlug(nextSlug);
                pageDirtyRef.current = false;
                setPageDraft(pageDraftFrom(staticPages.find((p: any) => p.slug === nextSlug)));
              }} className="w-full px-3 py-2 border rounded-xl bg-white">
                <option value="about">À propos</option>
                <option value="faq">Questions fréquentes</option>
                <option value="returns">Livraison &amp; retours</option>
                <option value="terms">Conditions générales</option>
              </select>
            </div>
            <div>
              <label className="block font-bold mb-1">Langue</label>
              <div className="flex gap-1">
                {(["fr", "ar", "en"] as const).map((l) => (
                  <button key={l} type="button" onClick={() => setPageLang(l)}
                    className={`flex-1 py-2 rounded-xl border font-bold ${pageLang === l ? "bg-[#063D2E] text-[#D4AF62] border-[#063D2E]" : "bg-white text-gray-600"}`}>
                    {l.toUpperCase()}{l === "fr" ? " *" : pageDraft[`content_${l}`] ? "" : " (vide)"}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div>
            <label className="block font-bold mb-1">Titre ({pageLang.toUpperCase()})</label>
            <input dir={pageLang === "ar" ? "rtl" : "ltr"} value={pageDraft[`title_${pageLang}`] || ""} onChange={(e) => setPageDraft({ ...pageDraft, [`title_${pageLang}`]: e.target.value })} required={pageLang === "fr"} className="w-full px-3 py-2 border rounded-xl" />
          </div>
          <div>
            <label className="block font-bold mb-1">Texte ({pageLang.toUpperCase()})</label>
            <textarea dir={pageLang === "ar" ? "rtl" : "ltr"} rows={9} value={pageDraft[`content_${pageLang}`] || ""} onChange={(e) => setPageDraft({ ...pageDraft, [`content_${pageLang}`]: e.target.value })} required={pageLang === "fr"} className="w-full px-3 py-2 border rounded-xl leading-relaxed" />
            <p className="text-[11px] text-gray-500">Un retour à la ligne = un nouveau paragraphe sur la boutique.</p>
          </div>
          <button type="submit" className="px-5 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold">
            Publier la page
          </button>
        </form>
      </div>
    </div>
  );
}

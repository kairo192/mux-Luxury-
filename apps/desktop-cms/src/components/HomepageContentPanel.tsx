// ============================================================================
// Page d'accueil de la boutique — what the home page shows, managed here.
//
//  * Blocks: switch each home block on/off (big banner, guarantees bar,
//    categories, featured products, promotion cards).
//  * Banners:
//      - "Bannière principale" (position hero): the big banner at the top.
//        Several = they rotate every 7 s.
//      - "Carte promo" (position promo_grid): the promotion cards.
//    Title / text in FR-AR-EN, button text, where the button leads (whole
//    shop, a category, a product or an https:// link), photo, on/off, order.
//
// Everything here is read by the shop from GET /api/v1/store/layout.
// ============================================================================

import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Eye, EyeOff, ImagePlus, Loader2, Megaphone, Pencil, Plus, Trash2, X } from "lucide-react";
import { DesktopCmsApi, mediaUrl, PLACEHOLDER_IMG } from "../api/adminClient";
import { confirmClientAction, notifyClientError, notifyClientSuccess, notifyClientWarning } from "../utils/clientNotifier";

type Banner = {
  id: number;
  position: "hero" | "promo_grid" | "seasonal";
  title_fr: string;
  title_ar?: string;
  title_en?: string;
  subtitle_fr?: string;
  subtitle_ar?: string;
  subtitle_en?: string;
  cta_text_fr?: string;
  cta_link?: string;
  image_url?: string;
  is_active: number | boolean;
  display_order: number;
};

type Section = { section_key: string; title_fr: string; is_active: boolean; display_order: number };

type Draft = Omit<Banner, "id" | "is_active"> & { id?: number; is_active: boolean };

const EMPTY: Draft = {
  position: "promo_grid",
  title_fr: "",
  title_ar: "",
  title_en: "",
  subtitle_fr: "",
  subtitle_ar: "",
  subtitle_en: "",
  cta_text_fr: "",
  cta_link: "#/boutique",
  image_url: "",
  is_active: true,
  display_order: 1,
};

const POSITIONS: Record<string, string> = {
  hero: "Bannière principale (haut de page)",
  promo_grid: "Carte promo (sous les produits)",
};

const SECTION_HELP: Record<string, string> = {
  hero_banner: "Grande bannière en haut de l'accueil",
  trust_bar: "Livraison 69 wilayas, paiement à la livraison, qualité, service client",
  categories_grid: "Vos catégories avec leur photo",
  featured_products: "Grille des produits sur l'accueil",
  promo_banners: "Cartes promo (visibles seulement s'il y en a)",
};

function linkLabel(link: string | undefined, categories: any[], products: any[]): string {
  const l = String(link || "");
  if (!l || l === "#/boutique") return "Toute la boutique";
  const c = l.match(/^\/categorie\/(.+)$/);
  if (c) return `Catégorie : ${categories.find((x) => x.slug === c[1])?.name_fr || c[1]}`;
  const p = l.match(/^\/produit\/(.+)$/);
  if (p) return `Produit : ${products.find((x) => x.slug === p[1])?.name_fr || p[1]}`;
  return l;
}

export function HomepageContentPanel({ categories: allCategories, products }: { categories: any[]; products: any[] }) {
  // Only what a customer can actually open on the shop.
  const categories = useMemo(
    () => allCategories.filter((c) => c.is_active !== 0 && c.is_active !== false && !c.deleted_at),
    [allCategories]
  );
  const [sections, setSections] = useState<Section[]>([]);
  const [banners, setBanners] = useState<Banner[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Draft | null>(null);
  const [uploading, setUploading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [sec, ban] = await Promise.all([DesktopCmsApi.listHomepageSections(), DesktopCmsApi.listBanners()]);
      setSections(sec?.items || []);
      setBanners((ban?.items || []).filter((b: Banner) => b.position !== "seasonal"));
    } catch (err) {
      notifyClientError(err, "Chargement de la page d'accueil impossible", false);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const byPosition = useMemo(() => {
    const out: Record<string, Banner[]> = { hero: [], promo_grid: [] };
    banners.forEach((b) => (out[b.position] || (out[b.position] = [])).push(b));
    Object.values(out).forEach((list) => list.sort((a, b) => a.display_order - b.display_order || a.id - b.id));
    return out;
  }, [banners]);

  async function toggleSection(sec: Section) {
    try {
      await DesktopCmsApi.updateHomepageSection(sec.section_key, { is_active: !sec.is_active, display_order: sec.display_order, config: {} });
      notifyClientSuccess(sec.is_active ? "Bloc masqué" : "Bloc affiché", `« ${sec.title_fr} » sur la page d'accueil.`);
      await load();
    } catch (err) {
      notifyClientError(err, "Modification du bloc impossible");
    }
  }

  function payloadOf(d: Draft) {
    return {
      position: d.position,
      title_fr: d.title_fr.trim(),
      title_ar: d.title_ar?.trim() || "",
      title_en: d.title_en?.trim() || "",
      subtitle_fr: d.subtitle_fr?.trim() || "",
      subtitle_ar: d.subtitle_ar?.trim() || "",
      subtitle_en: d.subtitle_en?.trim() || "",
      cta_text_fr: d.cta_text_fr?.trim() || "",
      cta_link: d.cta_link?.trim() || "#/boutique",
      image_url: d.image_url?.trim() || "",
      is_active: d.is_active,
      display_order: d.display_order,
    };
  }

  async function saveBanner() {
    if (!editing) return;
    if (!editing.title_fr.trim()) {
      notifyClientWarning("Titre requis", "Saisissez au moins le titre en français.");
      return;
    }
    const link = editing.cta_link?.trim() || "";
    if (link && !/^(#\/|\/categorie\/[a-z0-9-]+$|\/produit\/[a-z0-9-]+$|https:\/\/)/.test(link)) {
      notifyClientWarning("Lien invalide", "Choisissez une destination dans la liste, ou un lien commençant par https://");
      return;
    }
    setBusy(true);
    try {
      if (editing.id) {
        await DesktopCmsApi.updateBanner(editing.id, payloadOf(editing));
        notifyClientSuccess("Bannière enregistrée", "La boutique l'affiche dans la minute.");
      } else {
        await DesktopCmsApi.createBanner(payloadOf(editing));
        notifyClientSuccess("Bannière créée", editing.is_active ? "Elle apparaît sur la boutique dans la minute." : "Elle est enregistrée mais masquée.");
      }
      setEditing(null);
      await load();
    } catch (err) {
      notifyClientError(err, "Enregistrement de la bannière impossible");
    } finally {
      setBusy(false);
    }
  }

  async function quickUpdate(b: Banner, patch: Partial<Draft>) {
    try {
      await DesktopCmsApi.updateBanner(b.id, payloadOf({ ...(b as any), is_active: Boolean(b.is_active), ...patch }));
      await load();
    } catch (err) {
      notifyClientError(err, "Modification de la bannière impossible");
    }
  }

  async function move(b: Banner, dir: -1 | 1) {
    const list = byPosition[b.position] || [];
    const idx = list.findIndex((x) => x.id === b.id);
    const other = list[idx + dir];
    if (!other) return;
    try {
      await DesktopCmsApi.updateBanner(b.id, payloadOf({ ...(b as any), is_active: Boolean(b.is_active), display_order: other.display_order === b.display_order ? b.display_order + dir : other.display_order }));
      await DesktopCmsApi.updateBanner(other.id, payloadOf({ ...(other as any), is_active: Boolean(other.is_active), display_order: b.display_order }));
      await load();
    } catch (err) {
      notifyClientError(err, "Réorganisation impossible");
    }
  }

  async function remove(b: Banner) {
    const ok = await confirmClientAction({
      title: "Supprimer la bannière",
      message: `« ${b.title_fr} » disparaîtra de la boutique.`,
      confirmLabel: "Supprimer",
      danger: true,
    });
    if (!ok) return;
    try {
      await DesktopCmsApi.deleteBanner(b.id);
      notifyClientSuccess("Bannière supprimée", b.title_fr);
      await load();
    } catch (err) {
      notifyClientError(err, "Suppression impossible");
    }
  }

  async function uploadImage(file: File) {
    setUploading(true);
    try {
      const res: any = await DesktopCmsApi.uploadMediaFile(file);
      setEditing((d) => (d ? { ...d, image_url: res.url } : d));
    } catch (err) {
      notifyClientError(err, "Envoi de la photo impossible");
    } finally {
      setUploading(false);
    }
  }

  const linkMode = (l?: string) => {
    if (!l || l === "#/boutique") return "shop";
    if (l.startsWith("/categorie/")) return "category";
    if (l.startsWith("/produit/")) return "product";
    return "url";
  };

  return (
    <div className="space-y-5 text-xs">
      {/* ---------------- Home blocks ---------------- */}
      <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
        <h3 className="text-base font-serif font-bold text-[#063D2E]">Blocs de la page d'accueil</h3>
        <p className="text-gray-500">Affichez ou masquez chaque bloc de l'accueil de la boutique.</p>
        {loading ? (
          <Loader2 className="w-5 h-5 animate-spin text-[#063D2E]" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {sections.map((sec) => (
              <button
                key={sec.section_key}
                type="button"
                role="switch"
                aria-checked={sec.is_active}
                onClick={() => toggleSection(sec)}
                className={`text-start p-3.5 rounded-xl border flex items-start gap-3 transition ${
                  sec.is_active ? "bg-emerald-50 border-emerald-200" : "bg-gray-50 border-gray-200 opacity-80"
                }`}
              >
                <span className={`relative inline-flex h-5 w-9 shrink-0 rounded-full mt-0.5 ${sec.is_active ? "bg-[#063D2E]" : "bg-gray-300"}`}>
                  <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${sec.is_active ? "start-[18px]" : "start-0.5"}`} />
                </span>
                <span>
                  <span className="block font-bold text-[#063D2E]">{sec.title_fr}</span>
                  <span className="block text-[11px] text-gray-500">{SECTION_HELP[sec.section_key] || ""}</span>
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ---------------- Banners ---------------- */}
      <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-serif font-bold text-[#063D2E] flex items-center gap-2">
              <Megaphone className="w-4 h-4 text-[#D4AF62]" /> Bannières de la boutique
            </h3>
            <p className="text-gray-500">Sans bannière principale, l'accueil affiche le texte de la marque. Sans carte promo, ce bloc est masqué.</p>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => setEditing({ ...EMPTY, position: "hero", display_order: (byPosition.hero?.length || 0) + 1 })}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-[#063D2E] text-[#063D2E] font-bold hover:bg-[#063D2E]/5">
              <Plus className="w-4 h-4" /> Bannière principale
            </button>
            <button type="button" onClick={() => setEditing({ ...EMPTY, position: "promo_grid", display_order: (byPosition.promo_grid?.length || 0) + 1 })}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold">
              <Plus className="w-4 h-4" /> Carte promo
            </button>
          </div>
        </div>

        {(["hero", "promo_grid"] as const).map((pos) => (
          <div key={pos} className="space-y-2">
            <p className="font-bold text-[#063D2E]">{POSITIONS[pos]} ({byPosition[pos]?.length || 0})</p>
            {(byPosition[pos] || []).length === 0 ? (
              <p className="text-gray-400 italic px-1">Aucune.</p>
            ) : (
              (byPosition[pos] || []).map((b, i, list) => (
                <div key={b.id} className={`flex items-center gap-3 p-2.5 rounded-xl border ${b.is_active ? "border-gray-200" : "border-dashed border-gray-300 opacity-70"}`}>
                  <img src={b.image_url ? mediaUrl(b.image_url) : PLACEHOLDER_IMG} alt="" className="w-16 h-12 rounded-lg object-cover bg-[#F8F6F0]" />
                  <div className="min-w-0 flex-1">
                    <p className="font-bold text-[#202923] truncate">{b.title_fr}</p>
                    <p className="text-[11px] text-gray-500 truncate">
                      {b.subtitle_fr ? `${b.subtitle_fr} · ` : ""}→ {linkLabel(b.cta_link, categories, products)}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button type="button" title="Monter" disabled={i === 0} onClick={() => move(b, -1)} className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-30"><ArrowUp className="w-3.5 h-3.5" /></button>
                    <button type="button" title="Descendre" disabled={i === list.length - 1} onClick={() => move(b, 1)} className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-30"><ArrowDown className="w-3.5 h-3.5" /></button>
                    <button type="button" title={b.is_active ? "Masquer" : "Afficher"} onClick={() => quickUpdate(b, { is_active: !b.is_active })} className="p-1.5 rounded-lg hover:bg-gray-100">
                      {b.is_active ? <Eye className="w-3.5 h-3.5 text-emerald-700" /> : <EyeOff className="w-3.5 h-3.5 text-gray-400" />}
                    </button>
                    <button type="button" title="Modifier" onClick={() => setEditing({ ...(b as any), is_active: Boolean(b.is_active) })} className="p-1.5 rounded-lg hover:bg-gray-100"><Pencil className="w-3.5 h-3.5" /></button>
                    <button type="button" title="Supprimer" onClick={() => remove(b)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-600"><Trash2 className="w-3.5 h-3.5" /></button>
                  </div>
                </div>
              ))
            )}
          </div>
        ))}
      </div>

      {/* ---------------- Banner editor ---------------- */}
      {editing && (
        <div className="animate-backdrop fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div role="dialog" aria-modal="true" aria-labelledby="banner-editor-title" className="animate-modal bg-white rounded-2xl max-w-3xl w-full max-h-[92vh] overflow-y-auto shadow-2xl border-2 border-[#D4AF62]">
            <div className="px-5 py-3.5 flex items-center justify-between bg-gradient-to-r from-[#02291F] to-[#063D2E] text-white sticky top-0 z-10">
              <span id="banner-editor-title" className="font-extrabold text-sm text-[#E8D4A5]">
                {editing.id ? "Modifier la bannière" : "Nouvelle bannière"}
              </span>
              <button type="button" onClick={() => setEditing(null)} aria-label="Fermer" className="w-7 h-7 rounded-full bg-black/25 flex items-center justify-center"><X className="w-4 h-4" /></button>
            </div>
            <div className="p-5 grid grid-cols-1 md:grid-cols-5 gap-5 text-xs">
              <div className="md:col-span-3 space-y-3">
                <label className="block">
                  <span className="font-bold">Emplacement</span>
                  <select value={editing.position} onChange={(e) => setEditing({ ...editing, position: e.target.value as any })} className="mt-1 w-full px-3 py-2 border rounded-xl bg-white">
                    {Object.entries(POSITIONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </label>
                {(["fr", "ar", "en"] as const).map((l) => (
                  <div key={l} className="grid grid-cols-2 gap-2">
                    <label className="block">
                      <span className="font-bold">Titre ({l.toUpperCase()}){l === "fr" ? " *" : ""}</span>
                      <input dir={l === "ar" ? "rtl" : "ltr"} value={(editing as any)[`title_${l}`] || ""} onChange={(e) => setEditing({ ...editing, [`title_${l}`]: e.target.value } as Draft)} className="mt-1 w-full px-3 py-2 border rounded-xl" />
                    </label>
                    <label className="block">
                      <span className="font-bold">Texte ({l.toUpperCase()})</span>
                      <input dir={l === "ar" ? "rtl" : "ltr"} value={(editing as any)[`subtitle_${l}`] || ""} onChange={(e) => setEditing({ ...editing, [`subtitle_${l}`]: e.target.value } as Draft)} className="mt-1 w-full px-3 py-2 border rounded-xl" />
                    </label>
                  </div>
                ))}
                <div className="grid grid-cols-2 gap-2">
                  <label className="block">
                    <span className="font-bold">Texte du bouton (FR)</span>
                    <input value={editing.cta_text_fr || ""} onChange={(e) => setEditing({ ...editing, cta_text_fr: e.target.value })} placeholder="Voir la collection" className="mt-1 w-full px-3 py-2 border rounded-xl" />
                  </label>
                  <label className="block">
                    <span className="font-bold">Le bouton ouvre</span>
                    <select
                      value={linkMode(editing.cta_link)}
                      onChange={(e) => {
                        const m = e.target.value;
                        const next = m === "shop" ? "#/boutique"
                          : m === "category" ? `/categorie/${categories[0]?.slug || ""}`
                          : m === "product" ? `/produit/${products[0]?.slug || ""}`
                          : "https://";
                        setEditing({ ...editing, cta_link: next });
                      }}
                      className="mt-1 w-full px-3 py-2 border rounded-xl bg-white"
                    >
                      <option value="shop">Toute la boutique</option>
                      <option value="category" disabled={!categories.length}>Une catégorie</option>
                      <option value="product" disabled={!products.length}>Un produit</option>
                      <option value="url">Un lien externe (https://)</option>
                    </select>
                  </label>
                </div>
                {linkMode(editing.cta_link) === "category" && (
                  <select value={(editing.cta_link || "").replace("/categorie/", "")} onChange={(e) => setEditing({ ...editing, cta_link: `/categorie/${e.target.value}` })} className="w-full px-3 py-2 border rounded-xl bg-white">
                    {categories.map((c) => <option key={c.id} value={c.slug}>{c.name_fr}</option>)}
                  </select>
                )}
                {linkMode(editing.cta_link) === "product" && (
                  <select value={(editing.cta_link || "").replace("/produit/", "")} onChange={(e) => setEditing({ ...editing, cta_link: `/produit/${e.target.value}` })} className="w-full px-3 py-2 border rounded-xl bg-white">
                    {products.filter((p) => p.status === "published").map((p) => <option key={p.id} value={p.slug}>{p.name_fr}</option>)}
                  </select>
                )}
                {linkMode(editing.cta_link) === "url" && (
                  <input value={editing.cta_link || ""} onChange={(e) => setEditing({ ...editing, cta_link: e.target.value })} placeholder="https://…" className="w-full px-3 py-2 border rounded-xl font-mono" />
                )}
                <label className="flex items-center gap-2 font-bold pt-1">
                  <input type="checkbox" checked={editing.is_active} onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })} />
                  Visible sur la boutique
                </label>
              </div>

              {/* Photo + preview */}
              <div className="md:col-span-2 space-y-3">
                <span className="font-bold block">Photo</span>
                <div className="relative rounded-2xl overflow-hidden hero-luxury-bg bg-gradient-to-br from-[#02291F] to-[#063D2E] text-white p-4 min-h-[180px] flex flex-col justify-end">
                  {editing.image_url && <img src={mediaUrl(editing.image_url)} alt="" className="absolute inset-0 w-full h-full object-cover opacity-60" />}
                  <div className="relative space-y-1">
                    <p className="font-serif text-lg font-bold text-[#E8D4A5]">{editing.title_fr || "Titre de la bannière"}</p>
                    {editing.subtitle_fr && <p className="text-[11px] text-white/85">{editing.subtitle_fr}</p>}
                    <span className="inline-block mt-1 px-3 py-1 rounded-full bg-[#D4AF62] text-[#02291F] text-[10px] font-bold">{editing.cta_text_fr || "Voir la collection"}</span>
                  </div>
                </div>
                <label className="flex items-center justify-center gap-2 px-3 py-2 rounded-xl border border-[#D4AF62] text-[#063D2E] font-bold cursor-pointer hover:bg-[#D4AF62]/10">
                  {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ImagePlus className="w-4 h-4" />}
                  Téléverser une photo
                  <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => e.target.files?.[0] && uploadImage(e.target.files[0])} />
                </label>
                {editing.image_url && (
                  <button type="button" onClick={() => setEditing({ ...editing, image_url: "" })} className="w-full text-[11px] text-gray-500 underline">Retirer la photo</button>
                )}
              </div>
            </div>
            <div className="px-5 py-3.5 border-t flex justify-end gap-2 sticky bottom-0 bg-white">
              <button type="button" onClick={() => setEditing(null)} className="px-4 py-2 rounded-xl border border-gray-300 font-bold text-gray-700">Annuler</button>
              <button type="button" onClick={saveBanner} disabled={busy} className="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-extrabold disabled:opacity-50">
                {busy && <Loader2 className="w-4 h-4 animate-spin" />} Enregistrer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

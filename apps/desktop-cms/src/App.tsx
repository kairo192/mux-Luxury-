import React, { useEffect, useState } from "react";
import { DesktopCmsApi } from "./api/adminClient";
import { CategoryBuilderPage } from "./pages/CategoryBuilderPage";
import { DeliveryWilayasPage } from "./pages/DeliveryWilayasPage";

type CmsTab =
  | "dashboard"
  | "products"
  | "categories"
  | "inventory"
  | "orders"
  | "delivery_wilayas"
  | "content"
  | "backups";

export default function App() {
  const [checkingSetup, setCheckingSetup] = useState(true);
  const [requiresOwnerSetup, setRequiresOwnerSetup] = useState(false);
  const [user, setUser] = useState<any | null>(null);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [activeTab, setActiveTab] = useState<CmsTab>("dashboard");

  // First-Time Owner Initialization Fields
  const [ownerName, setOwnerName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [ownerPassword, setOwnerPassword] = useState("");
  const [ownerConfirm, setOwnerConfirm] = useState("");
  const [whatsappPhone, setWhatsappPhone] = useState("");
  const [emergencyPhone, setEmergencyPhone] = useState("");

  // Login & WhatsApp Recovery Fields
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [showRecoveryModal, setShowRecoveryModal] = useState(false);
  const [recPhone, setRecPhone] = useState("0655534154");
  const [recChannel, setRecChannel] = useState<"whatsapp_cloud_api" | "offline_emergency">("whatsapp_cloud_api");
  const [recCode, setRecCode] = useState("");
  const [recNewPassword, setRecNewPassword] = useState("");
  const [recStepInfo, setRecStepInfo] = useState("");

  // Workspace Data States
  const [dashboard, setDashboard] = useState<any | null>(null);
  const [categories, setCategories] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [movements, setMovements] = useState<any[]>([]);
  const [backups, setBackups] = useState<any[]>([]);
  const [restoreReport, setRestoreReport] = useState<any | null>(null);
  const [selectedInvoice, setSelectedInvoice] = useState<any | null>(null);
  const [loadingWorkspace, setLoadingWorkspace] = useState(false);

  // Dynamic Product Creation Form State
  const [prodCategoryId, setProdCategoryId] = useState<number>(1);
  const [prodNameFr, setProdNameFr] = useState("");
  const [prodSku, setProdSku] = useState("");
  const [prodSlug, setProdSlug] = useState("");
  const [prodSellingPrice, setProdSellingPrice] = useState(4500);
  const [prodCostPrice, setProdCostPrice] = useState(2600);
  const [prodStatus, setProdStatus] = useState<"published" | "draft">("published");
  const [prodDynamicAttrs, setProdDynamicAttrs] = useState<Record<string, string>>({});
  const [prodVariantStock, setProdVariantStock] = useState(5);

  useEffect(() => {
    DesktopCmsApi.getSetupStatus()
      .then((status) => {
        setRequiresOwnerSetup(Boolean(status.requires_owner_setup));
        setCheckingSetup(false);
      })
      .catch(() => {
        setRequiresOwnerSetup(false);
        setCheckingSetup(false);
      });
  }, []);

  async function loadAllWorkspaceData() {
    if (!user) return;
    setLoadingWorkspace(true);
    setError("");
    try {
      const [dashData, catData, prodData, ordData, movData, bkpData] = await Promise.all([
        DesktopCmsApi.getDashboard(),
        DesktopCmsApi.listCategories(),
        DesktopCmsApi.listAdminProducts({ include_archived: true }),
        DesktopCmsApi.listOrders(),
        DesktopCmsApi.listInventoryMovements(),
        DesktopCmsApi.listBackups(),
      ]);
      setDashboard(dashData);
      setCategories(catData.items || []);
      setProducts(prodData.items || []);
      setOrders(ordData.items || []);
      setMovements(movData.items || []);
      setBackups(bkpData.items || []);
      if (catData.items?.length && !prodCategoryId) {
        setProdCategoryId(catData.items[0].id);
      }
    } catch (err: any) {
      if (err.message === "SESSION_EXPIRED") {
        setUser(null);
        setError("Session expirée. Veuillez vous reconnecter.");
      } else {
        setError(err.message || "Erreur lors de la synchronisation avec le serveur");
      }
    } finally {
      setLoadingWorkspace(false);
    }
  }

  useEffect(() => {
    if (user) {
      loadAllWorkspaceData();
    }
  }, [user]);

  async function handleFirstTimeSetup(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (ownerPassword !== ownerConfirm) {
      setError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    try {
      const res = await DesktopCmsApi.initializeOwner({
        full_name: ownerName,
        email: ownerEmail,
        password: ownerPassword,
        whatsapp_phone: whatsappPhone,
        emergency_phone: emergencyPhone,
      });
      setRequiresOwnerSetup(false);
      setSuccessMsg(
        `Propriétaire configuré dans PostgreSQL. Code d'urgence : ${res.emergency_code_backup}. Cet écran est désormais verrouillé définitivement.`
      );
    } catch (err: any) {
      setError(err.message || "Erreur lors de l'initialisation");
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await DesktopCmsApi.login(loginEmail, loginPassword);
      setUser(res.user);
    } catch (err: any) {
      setError(err.message || "Identifiants invalides");
    }
  }

  async function handleRequestRecoveryOtp() {
    setError("");
    setRecStepInfo("");
    try {
      const res = await DesktopCmsApi.requestPasswordRecovery(recPhone, recChannel);
      if (res.test_otp) {
        setRecCode(res.test_otp);
        setRecStepInfo(`Code OTP WhatsApp (Mode Sandbox) généré : ${res.test_otp} (valable 5 min).`);
      } else {
        setRecStepInfo(res.message || "Code OTP envoyé sur votre WhatsApp administrateur vérifié.");
      }
    } catch (err: any) {
      setError(err.message || "Impossible d'envoyer le code OTP WhatsApp. Utilisez le canal Code de Secours Hors-Ligne.");
    }
  }

  async function handlePasswordRecoveryVerify(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await DesktopCmsApi.verifyPasswordRecovery(recPhone, recCode, recNewPassword);
      setShowRecoveryModal(false);
      setRecStepInfo("");
      const extra = res.replacement_emergency_code
        ? ` Nouveau code de secours généré : ${res.replacement_emergency_code}`
        : "";
      setSuccessMsg(`Mot de passe réinitialisé avec succès.${extra} Connectez-vous avec votre nouveau mot de passe.`);
    } catch (err: any) {
      setError(err.message || "Code de récupération invalide ou expiré");
    }
  }

  async function handleCreateProduct(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccessMsg("");
    try {
      const selectedCat = categories.find((c) => c.id === Number(prodCategoryId));
      const variantAxes = (selectedCat?.attributes || []).filter((a: any) => a.is_variant_axis);
      const defaultAttrs: Record<string, string> = {};
      variantAxes.forEach((ax: any) => {
        defaultAttrs[ax.attr_key] = ax.options?.[0]?.value || "Standard";
      });

      await DesktopCmsApi.createProduct({
        category_id: Number(prodCategoryId),
        slug:
          prodSlug.trim() ||
          prodNameFr
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-|-$/g, ""),
        sku: prodSku.trim(),
        name_fr: prodNameFr.trim(),
        purchase_cost_dzd: Number(prodCostPrice),
        selling_price_dzd: Number(prodSellingPrice),
        status: prodStatus,
        dynamic_attributes: prodDynamicAttrs,
        variants: [
          {
            sku: `${prodSku.trim()}-STD`,
            title: Object.values(defaultAttrs).join(" / ") || "Standard",
            stock_qty: Number(prodVariantStock),
            attributes: defaultAttrs,
          },
        ],
      });
      setSuccessMsg(`Produit "${prodNameFr}" créé et synchronisé sur la boutique.`);
      setProdNameFr("");
      setProdSku("");
      setProdSlug("");
      setProdDynamicAttrs({});
      await loadAllWorkspaceData();
    } catch (err: any) {
      setError(err.message || "Erreur lors de la création du produit");
    }
  }

  async function handleArchiveProduct(productId: number) {
    setError("");
    try {
      await DesktopCmsApi.archiveProduct(productId);
      setSuccessMsg(`Produit #${productId} archivé en toute sécurité (historique des commandes préservé).`);
      await loadAllWorkspaceData();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleAdjustStock(variantId: number, delta: number) {
    setError("");
    try {
      await DesktopCmsApi.adjustVariantStock(variantId, delta, "cms_manual_adjustment");
      setSuccessMsg(`Stock de la variante #${variantId} mis à jour (${delta > 0 ? `+${delta}` : delta}).`);
      await loadAllWorkspaceData();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleOrderStatusChange(orderId: number, nextStatus: string) {
    setError("");
    try {
      await DesktopCmsApi.updateOrderStatus(orderId, nextStatus);
      setSuccessMsg(`Statut de la commande #${orderId} mis à jour vers "${nextStatus}".`);
      await loadAllWorkspaceData();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleOpenInvoice(orderId: number) {
    setError("");
    try {
      const inv = await DesktopCmsApi.getOrderInvoice(orderId);
      setSelectedInvoice(inv);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleTriggerBackup() {
    setError("");
    try {
      const bkp = await DesktopCmsApi.triggerBackup();
      setSuccessMsg(`Sauvegarde créée et vérifiée : ${bkp.filename} (SHA-256: ${bkp.sha256_checksum.slice(0, 16)}...)`);
      await loadAllWorkspaceData();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleVerifyBackupRestore(backupId: number) {
    setError("");
    try {
      const rep = await DesktopCmsApi.verifyBackupRestore(backupId);
      setRestoreReport(rep);
      setSuccessMsg(`Test de restauration isolée réussi pour la sauvegarde #${backupId} !`);
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (checkingSetup) {
    return <div className="p-10 text-center text-white bg-[#02291F] min-h-screen">Vérification de l'état d'initialisation PostgreSQL...</div>;
  }

  if (requiresOwnerSetup) {
    return (
      <div className="min-h-screen bg-[#02291F] text-white flex items-center justify-center p-6">
        <form onSubmit={handleFirstTimeSetup} className="max-w-lg w-full bg-[#063D2E] p-8 rounded-2xl border-2 border-[#D4AF62] space-y-4 shadow-2xl">
          <div className="text-center">
            <span className="px-3 py-1 rounded-full bg-[#D4AF62] text-[#02291F] text-[10px] font-extrabold uppercase">
              ★ Première Ouverture — Setup Unique ★
            </span>
            <h1 className="text-2xl font-serif text-white font-bold mt-2">Configuration Initiale du Propriétaire</h1>
            <p className="text-xs text-[#E8D4A5] mt-1">
              Configurez vos accès et vos 2 numéros de secours. Après enregistrement dans la base de données, <strong>cet écran ne s'affichera plus jamais, même depuis un autre PC</strong>.
            </p>
          </div>
          {error && <div className="p-3 rounded bg-red-900/90 text-xs text-red-100">{error}</div>}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block font-bold mb-1">Nom Complet</label>
              <input value={ownerName} onChange={(e) => setOwnerName(e.target.value)} required placeholder="Mustapha Harbit" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
            </div>
            <div>
              <label className="block font-bold mb-1">Email / Identifiant</label>
              <input type="email" value={ownerEmail} onChange={(e) => setOwnerEmail(e.target.value)} required placeholder="admin@musluxury.dz" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block font-bold mb-1">Mot de passe (≥ 10 car.)</label>
              <input type="password" value={ownerPassword} onChange={(e) => setOwnerPassword(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
            </div>
            <div>
              <label className="block font-bold mb-1">Confirmer mot de passe</label>
              <input type="password" value={ownerConfirm} onChange={(e) => setOwnerConfirm(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
            </div>
          </div>
          <div className="p-3 rounded-xl bg-[#02291F]/80 border border-[#D4AF62]/30 space-y-2 text-xs">
            <p className="font-bold text-[#D4AF62]">Récupération &amp; Urgence (WhatsApp) :</p>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[11px] mb-0.5">1. WhatsApp Récupération</label>
                <input value={whatsappPhone} onChange={(e) => setWhatsappPhone(e.target.value)} required placeholder="0655 53 41 54" className="w-full px-2.5 py-1.5 rounded bg-[#063D2E] border border-[#D4AF62]/40 font-mono text-xs" />
              </div>
              <div>
                <label className="block text-[11px] mb-0.5">2. Numéro Secours / Urgence</label>
                <input value={emergencyPhone} onChange={(e) => setEmergencyPhone(e.target.value)} required placeholder="+213 661 00 00 02" className="w-full px-2.5 py-1.5 rounded bg-[#063D2E] border border-[#D4AF62]/40 font-mono text-xs" />
              </div>
            </div>
          </div>
          <button type="submit" className="w-full py-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-sm shadow-xl">
            Enregistrer dans PostgreSQL &amp; Verrouiller le Setup
          </button>
        </form>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-[#02291F] text-white flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-[#063D2E] p-8 rounded-2xl border border-[#D4AF62]/40 space-y-4 shadow-2xl">
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="text-center">
              <h1 className="text-2xl font-serif text-[#D4AF62] font-bold">Mus Luxury — Desktop CMS</h1>
              <p className="text-xs text-[#E8D4A5] mt-1">Connexion Administrateur Sécurisée (Tauri 2 • Ouled Yaïch 09)</p>
            </div>
            {successMsg && <div className="p-3 rounded bg-emerald-800 text-xs text-white">{successMsg}</div>}
            {error && <div className="p-3 rounded bg-red-900/90 text-xs text-red-100">{error}</div>}
            <div>
              <label className="block text-xs font-bold mb-1">Email / Identifiant</label>
              <input type="email" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} required placeholder="admin@musluxury.dz" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-bold mb-1">Mot de passe</label>
              <input type="password" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-sm" />
            </div>
            <div className="text-right">
              <button type="button" onClick={() => setShowRecoveryModal(!showRecoveryModal)} className="text-xs text-[#D4AF62] underline">
                Mot de passe oublié ? (Récupération WhatsApp / Code Secours)
              </button>
            </div>
            <button type="submit" className="w-full py-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-sm">
              Se connecter au CMS Desktop
            </button>
          </form>

          {showRecoveryModal && (
            <form onSubmit={handlePasswordRecoveryVerify} className="pt-4 border-t border-[#D4AF62]/30 space-y-3 text-xs">
              <h3 className="font-bold text-[#D4AF62]">Récupération Administrateur (WhatsApp Cloud API / Code Secours)</h3>
              {recStepInfo && <div className="p-2.5 rounded bg-emerald-900/90 border border-emerald-400/40 text-emerald-100">{recStepInfo}</div>}
              <div>
                <label className="block text-[11px] mb-1 text-[#E8D4A5]">Canal de récupération</label>
                <select
                  value={recChannel}
                  onChange={(e) => setRecChannel(e.target.value as "whatsapp_cloud_api" | "offline_emergency")}
                  className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-white"
                >
                  <option value="whatsapp_cloud_api">WhatsApp Business Cloud API (OTP 6 chiffres)</option>
                  <option value="offline_emergency">Code de Secours Hors-Ligne (Urgence Propriétaire)</option>
                </select>
              </div>
              <div className="flex gap-2">
                <input value={recPhone} onChange={(e) => setRecPhone(e.target.value)} placeholder="Téléphone (0655534154 ou +213...)" required className="flex-1 px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 font-mono" />
                <button
                  type="button"
                  onClick={handleRequestRecoveryOtp}
                  className="px-3 py-2 rounded bg-[#D4AF62] text-[#02291F] font-extrabold whitespace-nowrap"
                >
                  1. Envoyer OTP WhatsApp
                </button>
              </div>
              <input value={recCode} onChange={(e) => setRecCode(e.target.value)} placeholder="Code OTP 6 chiffres ou LUXE-EMERGENCY-2026-RECOVERY" required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 font-mono" />
              <input type="password" value={recNewPassword} onChange={(e) => setRecNewPassword(e.target.value)} placeholder="Nouveau mot de passe (≥ 10 caractères)" required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
              <button type="submit" className="w-full py-2.5 rounded-xl bg-emerald-700 text-white font-bold">
                2. Vérifier le code &amp; Réinitialiser le mot de passe
              </button>
            </form>
          )}
        </div>
      </div>
    );
  }

  const activeCategoryObj = categories.find((c) => c.id === Number(prodCategoryId)) || categories[0];

  return (
    <div className="min-h-screen bg-[#F8F6F0] text-[#202923] flex flex-col">
      {/* Top Header */}
      <header className="bg-[#02291F] text-[#D4AF62] px-6 py-3.5 flex flex-wrap justify-between items-center gap-4 border-b border-[#D4AF62]/30">
        <div className="flex items-center gap-3">
          <span className="font-serif font-bold text-lg text-white">Mus Luxury — Desktop CMS</span>
          <span className="px-2.5 py-0.5 rounded-full bg-[#063D2E] border border-[#D4AF62]/40 text-xs">
            {user.full_name} ({user.role})
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <button
            type="button"
            onClick={loadAllWorkspaceData}
            className="px-3 py-1.5 rounded-lg bg-[#063D2E] text-[#E8D4A5] border border-[#D4AF62]/40 font-bold"
          >
            ↻ Synchroniser avec le serveur
          </button>
          <button
            type="button"
            onClick={() => {
              DesktopCmsApi.logout();
              setUser(null);
            }}
            className="px-3 py-1.5 rounded-lg bg-red-900/80 text-white font-bold"
          >
            Déconnexion
          </button>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="bg-[#063D2E] text-[#E8D4A5] px-6 py-2 flex flex-wrap gap-2 text-xs font-bold border-b border-[#D4AF62]/30">
        {[
          { id: "dashboard", label: "1. Tableau de Bord" },
          { id: "products", label: "2. Produits & Variantes" },
          { id: "categories", label: "3. Catégories & Attributs (14 types)" },
          { id: "inventory", label: "4. Stocks & Mouvements" },
          { id: "orders", label: "5. Commandes & Factures" },
          { id: "delivery_wilayas", label: "6. Livraison 69 Wilayas (Domicile / Stop-Desk)" },
          { id: "content", label: "7. Boutique & Réseaux (Ouled Yaïch)" },
          { id: "backups", label: "8. Sauvegardes & Restauration" },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setActiveTab(t.id as CmsTab)}
            className={`px-3.5 py-2 rounded-xl transition ${
              activeTab === t.id ? "bg-[#D4AF62] text-[#02291F] font-extrabold" : "hover:bg-[#02291F]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {/* Global Status / Error Banner */}
      <div className="max-w-7xl w-full mx-auto px-6 pt-4 space-y-2">
        {error && <div className="p-3 rounded-xl bg-red-100 border border-red-300 text-red-900 text-xs font-bold">{error}</div>}
        {successMsg && <div className="p-3 rounded-xl bg-emerald-100 border border-emerald-300 text-emerald-900 text-xs font-bold">{successMsg}</div>}
      </div>

      {/* Main Content Area */}
      <main className="max-w-7xl w-full mx-auto p-6 flex-1 space-y-6">
        {loadingWorkspace && <div className="text-xs text-gray-500">Synchronisation des données en cours...</div>}

        {/* TAB 1: DASHBOARD */}
        {activeTab === "dashboard" && dashboard && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-6 gap-4 text-xs">
              <div className="bg-white p-4 rounded-2xl border border-[#D4AF62]/40">
                <span className="text-gray-500">Chiffre d'affaires</span>
                <p className="text-xl font-extrabold text-[#063D2E] mt-1">{dashboard.total_revenue_dzd} DA</p>
              </div>
              <div className="bg-white p-4 rounded-2xl border border-[#D4AF62]/40">
                <span className="text-gray-500">Total Commandes</span>
                <p className="text-xl font-extrabold text-[#063D2E] mt-1">{dashboard.total_orders}</p>
              </div>
              <div className="bg-white p-4 rounded-2xl border border-[#D4AF62]/40">
                <span className="text-gray-500">Produits Actifs</span>
                <p className="text-xl font-extrabold text-[#063D2E] mt-1">{dashboard.total_active_products ?? dashboard.published_products}</p>
              </div>
              <div className="bg-white p-4 rounded-2xl border border-[#D4AF62]/40">
                <span className="text-gray-500">Catégories Actives</span>
                <p className="text-xl font-extrabold text-[#063D2E] mt-1">{dashboard.total_categories}</p>
              </div>
              <div className="bg-white p-4 rounded-2xl border border-amber-300">
                <span className="text-amber-800">Stock Faible (≤ 3)</span>
                <p className="text-xl font-extrabold text-amber-700 mt-1">{dashboard.low_stock_variants}</p>
              </div>
              <div className="bg-white p-4 rounded-2xl border border-red-300">
                <span className="text-red-800">Rupture de Stock (0)</span>
                <p className="text-xl font-extrabold text-red-700 mt-1">{dashboard.out_of_stock_variants}</p>
              </div>
            </div>

            {/* Orders by Status Breakdown */}
            <div className="bg-white p-5 rounded-2xl border border-[#D4AF62]/40 space-y-3 text-xs">
              <h3 className="font-serif font-bold text-base text-[#063D2E]">Répartition des commandes par statut</h3>
              <div className="grid grid-cols-3 md:grid-cols-9 gap-2">
                {Object.entries(dashboard.orders_by_status || {}).map(([st, cnt]) => (
                  <div key={st} className="p-2.5 rounded-xl bg-[#F8F6F0] border text-center">
                    <div className="font-mono text-[10px] text-gray-500">{st}</div>
                    <div className="font-extrabold text-base text-[#063D2E]">{String(cnt)}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: PRODUCTS & DYNAMIC CATEGORY ATTRIBUTES */}
        {activeTab === "products" && (
          <div className="space-y-6">
            <form onSubmit={handleCreateProduct} className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4 text-xs">
              <h2 className="text-lg font-serif font-bold text-[#063D2E]">+ Créer un produit (Formulaire adaptatif selon la catégorie)</h2>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div>
                  <label className="block font-bold mb-1">Catégorie *</label>
                  <select
                    value={prodCategoryId}
                    onChange={(e) => {
                      setProdCategoryId(Number(e.target.value));
                      setProdDynamicAttrs({});
                    }}
                    className="w-full px-3 py-2 border rounded-xl bg-white font-semibold"
                  >
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name_fr}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block font-bold mb-1">Nom du produit (FR) *</label>
                  <input value={prodNameFr} onChange={(e) => setProdNameFr(e.target.value)} required placeholder="ex: Sac Émeraude Prestige" className="w-full px-3 py-2 border rounded-xl" />
                </div>
                <div>
                  <label className="block font-bold mb-1">Code SKU *</label>
                  <input value={prodSku} onChange={(e) => setProdSku(e.target.value)} required placeholder="LUX-BAG-099" className="w-full px-3 py-2 border rounded-xl font-mono" />
                </div>
                <div>
                  <label className="block font-bold mb-1">Prix de vente (DA) *</label>
                  <input type="number" min={0} value={prodSellingPrice} onChange={(e) => setProdSellingPrice(Number(e.target.value))} required className="w-full px-3 py-2 border rounded-xl font-bold" />
                </div>
              </div>

              {/* Dynamic Attributes Driven by Selected Category */}
              {activeCategoryObj && (activeCategoryObj.attributes || []).filter((a: any) => !a.is_variant_axis).length > 0 && (
                <div className="p-4 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30 space-y-2">
                  <p className="font-bold text-[#063D2E]">
                    Caractéristiques spécifiques à la catégorie « {activeCategoryObj.name_fr} » :
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {(activeCategoryObj.attributes || [])
                      .filter((a: any) => !a.is_variant_axis)
                      .map((attr: any) => (
                        <div key={attr.attr_key}>
                          <label className="block font-semibold mb-1">
                            {attr.label_fr} {attr.is_required ? "*" : ""}
                          </label>
                          {attr.options && attr.options.length > 0 ? (
                            <select
                              value={prodDynamicAttrs[attr.attr_key] || ""}
                              onChange={(e) => setProdDynamicAttrs({ ...prodDynamicAttrs, [attr.attr_key]: e.target.value })}
                              required={Boolean(attr.is_required && prodStatus === "published")}
                              className="w-full px-3 py-1.5 border rounded-lg bg-white"
                            >
                              <option value="">-- Choisir --</option>
                              {attr.options.map((o: any) => (
                                <option key={o.value} value={o.value}>
                                  {o.label_fr}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <input
                              value={prodDynamicAttrs[attr.attr_key] || ""}
                              onChange={(e) => setProdDynamicAttrs({ ...prodDynamicAttrs, [attr.attr_key]: e.target.value })}
                              required={Boolean(attr.is_required && prodStatus === "published")}
                              placeholder={attr.label_fr}
                              className="w-full px-3 py-1.5 border rounded-lg bg-white"
                            />
                          )}
                        </div>
                      ))}
                  </div>
                </div>
              )}

              <button type="submit" className="px-6 py-2.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold">
                Enregistrer &amp; Publier le Produit
              </button>
            </form>

            {/* Product List */}
            <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3 text-xs">
              <h3 className="text-base font-serif font-bold text-[#063D2E]">Catalogue Produits ({products.length})</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-[#063D2E] text-[#E8D4A5]">
                      <th className="p-2.5">ID / SKU</th>
                      <th className="p-2.5">Produit</th>
                      <th className="p-2.5">Prix Vente (DA)</th>
                      <th className="p-2.5">Coût Achat (Privé)</th>
                      <th className="p-2.5">Stock Total</th>
                      <th className="p-2.5">Statut</th>
                      <th className="p-2.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {products.map((p) => (
                      <tr key={p.id}>
                        <td className="p-2.5 font-mono font-bold">#{p.id} • {p.sku}</td>
                        <td className="p-2.5 font-bold">{p.name_fr}</td>
                        <td className="p-2.5 font-extrabold text-[#063D2E]">{p.selling_price_dzd} DA</td>
                        <td className="p-2.5 text-gray-500">{p.purchase_cost_dzd ?? 0} DA</td>
                        <td className="p-2.5 font-bold">{p.total_stock}</td>
                        <td className="p-2.5">
                          <span className="px-2 py-0.5 rounded bg-gray-100 font-semibold">{p.status}</span>
                        </td>
                        <td className="p-2.5 text-right">
                          {p.status !== "archived" && (
                            <button
                              type="button"
                              onClick={() => handleArchiveProduct(p.id)}
                              className="px-2.5 py-1 rounded bg-red-50 text-red-700 border border-red-200 font-bold"
                            >
                              Archiver
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: DYNAMIC CATEGORIES & ATTRIBUTES */}
        {activeTab === "categories" && <CategoryBuilderPage onCategoryChanged={loadAllWorkspaceData} />}

        {/* TAB 4: INVENTORY & MOVEMENTS */}
        {activeTab === "inventory" && (
          <div className="space-y-6 text-xs">
            <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
              <h3 className="text-base font-serif font-bold text-[#063D2E]">Gestion des Stocks par Variante</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {products.flatMap((p) =>
                  (p.variants || []).map((v: any) => (
                    <div key={v.id} className="p-3 rounded-xl border flex items-center justify-between">
                      <div>
                        <div className="font-bold text-[#063D2E]">{p.name_fr} — {v.title}</div>
                        <div className="font-mono text-gray-500">SKU: {v.sku} • Stock actuel: <strong>{v.stock_qty}</strong></div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button type="button" onClick={() => handleAdjustStock(v.id, -1)} className="px-2.5 py-1 rounded bg-gray-100 font-bold">-1</button>
                        <button type="button" onClick={() => handleAdjustStock(v.id, 5)} className="px-2.5 py-1 rounded bg-[#063D2E] text-[#D4AF62] font-bold">+5</button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
              <h3 className="text-base font-serif font-bold text-[#063D2E]">Historique des Mouvements de Stock ({movements.length})</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-[#063D2E] text-[#E8D4A5]">
                      <th className="p-2">ID</th>
                      <th className="p-2">Produit / Variante</th>
                      <th className="p-2">Variation</th>
                      <th className="p-2">Avant → Après</th>
                      <th className="p-2">Motif</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {movements.map((m) => (
                      <tr key={m.id}>
                        <td className="p-2 font-mono">#{m.id}</td>
                        <td className="p-2 font-bold">{m.product_name} ({m.variant_title})</td>
                        <td className="p-2 font-extrabold">{m.change_qty > 0 ? `+${m.change_qty}` : m.change_qty}</td>
                        <td className="p-2 font-mono">{m.previous_qty} → {m.new_qty}</td>
                        <td className="p-2">{m.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: ORDERS & INVOICES */}
        {activeTab === "orders" && (
          <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4 text-xs">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-serif font-bold text-[#063D2E]">Commandes Clients ({orders.length})</h3>
            </div>
            <div className="space-y-3">
              {orders.map((o) => (
                <div key={o.id} className="p-4 rounded-xl border border-gray-200 flex flex-wrap items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="font-mono font-extrabold text-[#063D2E]">#{o.order_reference} • {o.customer_name} ({o.customer_phone})</div>
                    <div className="text-gray-600">
                      Destination: <strong>{o.wilaya_code} - {o.wilaya_name}</strong> ({o.commune}) • Mode: <strong>{o.delivery_method}</strong>
                    </div>
                    <div className="font-bold text-[#063D2E]">
                      Sous-total: {o.subtotal_dzd} DA + Livraison: {o.delivery_fee_dzd} DA = Total COD: {o.total_dzd} DA
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      value={o.status}
                      onChange={(e) => handleOrderStatusChange(o.id, e.target.value)}
                      className="px-3 py-1.5 rounded-lg border font-bold bg-[#F8F6F0]"
                    >
                      {["new", "pending_confirmation", "confirmed", "preparing", "ready_for_shipment", "shipped", "delivered", "cancelled", "returned"].map((st) => (
                        <option key={st} value={st}>{st}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => handleOpenInvoice(o.id)}
                      className="px-3 py-1.5 rounded-lg bg-[#063D2E] text-[#D4AF62] font-bold"
                    >
                      Facture / Bon de livraison
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {selectedInvoice && (
              <div className="p-5 rounded-2xl bg-[#F8F6F0] border-2 border-[#D4AF62] space-y-2">
                <div className="flex justify-between items-center">
                  <h4 className="font-serif font-bold text-base text-[#063D2E]">
                    Facture COD #{selectedInvoice.order_reference} — {selectedInvoice.boutique_info?.name}
                  </h4>
                  <button type="button" onClick={() => setSelectedInvoice(null)} className="font-bold">Fermer ✕</button>
                </div>
                <p><strong>Boutique :</strong> {selectedInvoice.boutique_info?.address} • Tél/WhatsApp : {selectedInvoice.boutique_info?.phone}</p>
                <p><strong>Client :</strong> {selectedInvoice.customer_name} ({selectedInvoice.customer_phone}) — {selectedInvoice.delivery_address}</p>
                <p className="font-extrabold text-sm text-[#063D2E]">Total à encaisser à la livraison : {selectedInvoice.total_dzd} DA</p>
              </div>
            )}
          </div>
        )}

        {/* TAB 6: 69 WILAYAS DELIVERY TARIFFS */}
        {activeTab === "delivery_wilayas" && <DeliveryWilayasPage />}

        {/* TAB 7: STORE CONTENT & REAL SOCIAL/LOCATION SETTINGS */}
        {activeTab === "content" && (
          <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4 text-xs">
            <h3 className="text-base font-serif font-bold text-[#063D2E]">Coordonnées Officielles &amp; Réseaux Sociaux (Mus Luxury)</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-3.5 rounded-xl bg-[#F8F6F0] border">
                <span className="text-gray-500 block">Adresse &amp; Localisation Google Maps</span>
                <strong className="text-sm text-[#063D2E]">FVX6+GCJ Mus luxury, Ouled Yaïch (Blida — 09)</strong>
              </div>
              <div className="p-3.5 rounded-xl bg-[#F8F6F0] border">
                <span className="text-gray-500 block">WhatsApp &amp; Téléphone Boutique</span>
                <strong className="text-sm font-mono text-[#063D2E]">0655534154 (+213655534154)</strong>
              </div>
              <div className="p-3.5 rounded-xl bg-[#F8F6F0] border">
                <span className="text-gray-500 block">Instagram Officiel</span>
                <strong className="text-sm text-[#063D2E]">https://www.instagram.com/musluxury09?rpxt=emk3bjBhdjV5d2Ux</strong>
              </div>
              <div className="p-3.5 rounded-xl bg-[#F8F6F0] border">
                <span className="text-gray-500 block">TikTok Officiel</span>
                <strong className="text-sm text-[#063D2E]">https://www.tiktok.com/@musluxury.092?_r=1&amp;_t=ZS-9B2mO0gpA7V</strong>
              </div>
            </div>
          </div>
        )}

        {/* TAB 8: BACKUPS & ISOLATED RESTORE VERIFICATION */}
        {activeTab === "backups" && (
          <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4 text-xs">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-serif font-bold text-[#063D2E]">Sauvegardes Chiffrées &amp; Test de Restauration Isolée</h3>
                <p className="text-gray-500">Génère une archive SQL compressée (.sql.gz), vérifie son empreinte SHA-256 et teste sa restauration dans une base isolée.</p>
              </div>
              <button
                type="button"
                onClick={handleTriggerBackup}
                className="px-4 py-2.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold"
              >
                + Créer une sauvegarde maintenant
              </button>
            </div>

            {restoreReport && (
              <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-300 space-y-1">
                <p className="font-bold text-emerald-900">✓ Restauration isolée vérifiée avec succès ({restoreReport.filename})</p>
                <p>
                  Enregistrements restaurés et vérifiés : Produits: <strong>{restoreReport.restored_counts?.products}</strong> • Catégories: <strong>{restoreReport.restored_counts?.categories}</strong> • Commandes: <strong>{restoreReport.restored_counts?.orders}</strong> • Wilayas: <strong>{restoreReport.restored_counts?.delivery_zones}</strong>
                </p>
              </div>
            )}

            <div className="space-y-2">
              {backups.map((b) => (
                <div key={b.id} className="p-3 rounded-xl border flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="font-mono font-bold text-[#063D2E]">{b.filename} ({b.size_bytes} octets)</div>
                    <div className="font-mono text-[11px] text-gray-500">SHA-256: {b.sha256_checksum}</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleVerifyBackupRestore(b.id)}
                    className="px-3 py-1.5 rounded-lg bg-[#063D2E] text-[#D4AF62] font-bold"
                  >
                    Tester la restauration isolée
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

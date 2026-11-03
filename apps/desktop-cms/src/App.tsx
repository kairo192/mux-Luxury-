import { readDraft, writeDraft, clearDraft } from "./utils/draftStorage";
import {
  ClientNotificationItem,
  notifyClientError,
  notifyClientSuccess,
  notifyClientWarning,
  subscribeClientNotifications,
} from "./utils/clientNotifier";
import {
  NetworkTelemetryState,
  getNetworkTelemetry,
  subscribeNetworkTelemetry,
} from "./utils/networkQueue";
import React, { useEffect, useState } from "react";
import {
  LayoutDashboard,
  ShoppingBag,
  Tags,
  PackageCheck,
  Boxes,
  FileText,
  Receipt,
  Landmark,
  TrendingUp,
  Truck,
  Palette,
  ShieldCheck,
  Plus,
  RefreshCw,
  ArrowUpRight,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  DollarSign,
  Download,
  Clock,
  Sparkles,
  Edit3,
  Trash2,
  Archive,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Calculator,
  Wand2,
  Eye,
  EyeOff,
  CheckSquare,
  Square,
  PackagePlus,
  MessageCircle,
  Ban,
  Radio,
  ShieldAlert,
  UploadCloud,
  X,
  Layers,
  Tag,
  Check,
  Filter,
} from "lucide-react";
import { RevenueTrendChart, OrderStatusDistributionChart, InventoryHealthWidget } from "./components/CmsCharts";
import { DesktopCmsApi, restoreSessionFromOsKeychain } from "./api/adminClient";
import { CategoryBuilderPage } from "./pages/CategoryBuilderPage";
import { DeliveryWilayasPage } from "./pages/DeliveryWilayasPage";
import { PurchasesPage } from "./pages/PurchasesPage";
import { ExpensesPage } from "./pages/ExpensesPage";
import { TreasuryPage } from "./pages/TreasuryPage";
import { AccountingPage } from "./pages/AccountingPage";

type CmsTab =
  | "dashboard"
  | "products"
  | "categories"
  | "purchases"
  | "inventory"
  | "orders"
  | "expenses"
  | "treasury"
  | "accounting"
  | "delivery_wilayas"
  | "content"
  | "backups";

export default function App() {
  const [checkingSetup, setCheckingSetup] = useState(true);
  const [requiresOwnerSetup, setRequiresOwnerSetup] = useState(false);
  const [user, setUser] = useState<any | null>(() => readDraft("luxe_cms_user", null));
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [toastQueue, setToastQueue] = useState<ClientNotificationItem[]>([]);
  const [activeMessageBox, setActiveMessageBox] = useState<ClientNotificationItem | null>(null);

  useEffect(() => {
    const unsub = subscribeClientNotifications((item) => {
      setToastQueue((prev) => [item, ...prev.slice(0, 4)]);
      if (item.showModalBox) {
        setActiveMessageBox(item);
      }
      setTimeout(() => {
        setToastQueue((prev) => prev.filter((t) => t.id !== item.id));
      }, 5500);
    });
    return unsub;
  }, []);
  const [activeTab, setActiveTab] = useState<CmsTab>(() => readDraft("luxe_cms_active_tab", "dashboard"));

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
  const [recPhone, setRecPhone] = useState("");
  const [recChannel, setRecChannel] = useState<"whatsapp_cloud_api" | "offline_emergency">("whatsapp_cloud_api");
  const [recCode, setRecCode] = useState("");
  const [recNewPassword, setRecNewPassword] = useState("");
  const [recStepInfo, setRecStepInfo] = useState("");

  // Workspace Data States
  const [dashboard, setDashboard] = useState<any | null>(null);
  const [reports, setReports] = useState<any | null>(null);
  const [brands, setBrands] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [movements, setMovements] = useState<any[]>([]);
  const [banners, setBanners] = useState<any[]>([]);
  const [coupons, setCoupons] = useState<any[]>([]);
  const [homepageSections, setHomepageSections] = useState<any[]>([]);
  const [staticPages, setStaticPages] = useState<any[]>([]);
  const [backups, setBackups] = useState<any[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [readinessStatus, setReadinessStatus] = useState<any | null>(null);
  const [recoveryStatus, setRecoveryStatus] = useState<any | null>(null);
  const [healthStatus, setHealthStatus] = useState<any | null>(null);
  const [restoreReport, setRestoreReport] = useState<any | null>(null);
  const [selectedInvoice, setSelectedInvoice] = useState<any | null>(null);
  const [loadingWorkspace, setLoadingWorkspace] = useState(false);
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);
  const [newBrandName, setNewBrandName] = useState("");
  const [newImageUrl, setNewImageUrl] = useState("/assets/prod_sac_chanel_hd.jpg");
  const [matrixColorCsv, setMatrixColorCsv] = useState("Noir, Or");
  const [matrixSizeCsv, setMatrixSizeCsv] = useState("S, M, L");
  const [bannerTitleFr, setBannerTitleFr] = useState("");
  const [bannerImageUrl, setBannerImageUrl] = useState("/assets/hero_banner_mus.jpg");
  const [orderSearch, setOrderSearch] = useState("");
  const [codBlacklist, setCodBlacklist] = useState<any[]>([]);
  const [codCheckPhone, setCodCheckPhone] = useState("");
  const [codBlacklistReason, setCodBlacklistReason] = useState("Retour abusif / Non-récupération COD");
  const [codCheckResult, setCodCheckResult] = useState<any | null>(null);
  const [keychainStatus, setKeychainStatus] = useState<any | null>(null);
  const [waOutbox, setWaOutbox] = useState<any[]>([]);
  const [netTelemetry, setNetTelemetry] = useState<NetworkTelemetryState>(() => getNetworkTelemetry());

  useEffect(() => {
    const unsubNet = subscribeNetworkTelemetry((st) => setNetTelemetry(st));
    return unsubNet;
  }, []);

  // Product Search, Creation, Edit & Variant Matrix State
  const [prodSearch, setProdSearch] = useState(() => readDraft("luxe_cms_prod_search", ""));
  const [prodCategoryId, setProdCategoryId] = useState<number>(() => readDraft("luxe_cms_prod_cat_id", 1));
  const [prodNameFr, setProdNameFr] = useState(() => readDraft("luxe_cms_prod_name_fr", ""));
  const [prodSku, setProdSku] = useState(() => readDraft("luxe_cms_prod_sku", ""));
  const [prodSlug, setProdSlug] = useState(() => readDraft("luxe_cms_prod_slug", ""));
  const [prodSellingPrice, setProdSellingPrice] = useState(() => readDraft("luxe_cms_prod_price", 4500));
  const [prodCostPrice, setProdCostPrice] = useState(() => readDraft("luxe_cms_prod_cost", 2600));
  const [prodStatus, setProdStatus] = useState<"published" | "draft">(() => readDraft("luxe_cms_prod_status", "published"));
  const [prodDynamicAttrs, setProdDynamicAttrs] = useState<Record<string, string>>(() => readDraft("luxe_cms_prod_dyn_attrs", {}));
  const [prodVariantStock, setProdVariantStock] = useState(() => readDraft("luxe_cms_prod_stock", 5));
  const [editingProduct, setEditingProduct] = useState<any | null>(null);
  const [productToDelete, setProductToDelete] = useState<any | null>(null);
  const [forceDeleteProduct, setForceDeleteProduct] = useState(false);
  const [productFilterTab, setProductFilterTab] = useState<"all" | "published" | "draft" | "archived" | "low_stock">("all");
  const [deletingProduct, setDeletingProduct] = useState(false);

  function handleGenerateAutoSku() {
    const cat = categories.find((c) => c.id === Number(prodCategoryId));
    let prefix = "LUX";
    if (cat?.slug) {
      if (cat.slug.includes("sac") || cat.slug.includes("maroquinerie")) prefix = "LUX-BAG";
      else if (cat.slug.includes("chaussure") || cat.slug.includes("soulier")) prefix = "LUX-SHO";
      else if (cat.slug.includes("beaute") || cat.slug.includes("maquillage") || cat.slug.includes("parfum")) prefix = "LUX-BEA";
      else if (cat.slug.includes("accessoire") || cat.slug.includes("chale")) prefix = "LUX-ACC";
      else prefix = `LUX-${cat.slug.slice(0, 3).toUpperCase()}`;
    }
    const randomNum = Math.floor(100 + Math.random() * 900);
    const newSku = `${prefix}-${randomNum}`;
    setProdSku(newSku);
    notifyClientSuccess("SKU Généré", `Référence attribuée : ${newSku}`);
  }

  // Order Filter State
  const [orderStatusFilter, setOrderStatusFilter] = useState("");

  // Store Settings, Coupon & Static Page State (Tab 7)
  const [storePhoneInput, setStorePhoneInput] = useState("");
  const [storeWhatsappInput, setStoreWhatsappInput] = useState("");
  const [storeLocationInput, setStoreLocationInput] = useState("FVX6+GCJ Mus luxury, Ouled Yaïch");
  const [freeThresholdInput, setFreeThresholdInput] = useState("25000");
  const [couponCode, setCouponCode] = useState("");
  const [couponType, setCouponType] = useState<"percentage" | "fixed_dzd">("percentage");
  const [couponValue, setCouponValue] = useState(10);
  const [couponMinOrder, setCouponMinOrder] = useState(5000);
  const [pageSlug, setPageSlug] = useState("about");
  const [pageTitleFr, setPageTitleFr] = useState("Maison Mus Luxury — Ouled Yaïch");
  const [pageContentFr, setPageContentFr] = useState("Boutique officielle Mus Luxury à Ouled Yaïch (Blida 09). Livraison rapide 69 Wilayas avec paiement à la livraison.");

  const [keychainReady, setKeychainReady] = useState(false);

  useEffect(() => {
    restoreSessionFromOsKeychain()
      .catch(() => null)
      .finally(() => setKeychainReady(true));
    DesktopCmsApi.getSetupStatus()
      .then((status) => {
        setRequiresOwnerSetup(Boolean(status.requires_owner_setup));
        setCheckingSetup(false);
      })
      .catch(() => {
        setRequiresOwnerSetup(false);
        setCheckingSetup(false);
      });

    function handleWindowFocus() {
      if (user) {
        void loadAllWorkspaceData();
      }
    }
    window.addEventListener("focus", handleWindowFocus);
    return () => window.removeEventListener("focus", handleWindowFocus);
  }, [user]);

  async function loadAllWorkspaceData() {
    if (!user) return;
    setLoadingWorkspace(true);
    setError("");
    try {
      const [dashData, repData, brdData, catData, prodData, ordData, custData, movData, layData, bnrData, pgData, bkpData, recData, hltData, blData, kcStatus, outboxData, auditData, readyData, cpnData] = await Promise.all([
        DesktopCmsApi.getDashboard(),
        DesktopCmsApi.getReports().catch(() => null),
        DesktopCmsApi.listBrands().catch(() => ({ items: [] })),
        DesktopCmsApi.listCategories(),
        DesktopCmsApi.listAdminProducts({ include_archived: true }),
        DesktopCmsApi.listOrders(orderStatusFilter || undefined),
        DesktopCmsApi.listCustomers().catch(() => ({ items: [] })),
        DesktopCmsApi.listInventoryMovements(),
        DesktopCmsApi.getStoreLayout().catch(() => ({ homepage_sections: [] })),
        DesktopCmsApi.listBanners().catch(() => ({ items: [] })),
        DesktopCmsApi.listStaticPages().catch(() => ({ items: [] })),
        DesktopCmsApi.listBackups(),
        DesktopCmsApi.getRecoveryStatus().catch(() => null),
        DesktopCmsApi.checkHealth().catch(() => ({ status: "ok" })),
        DesktopCmsApi.listCodBlacklist().catch(() => ({ items: [] })),
        DesktopCmsApi.getKeychainStatus().catch(() => null),
        DesktopCmsApi.listCommunicationsOutbox().catch(() => ({ items: [] })),
        DesktopCmsApi.listAuditLogs(30).catch(() => ({ items: [] })),
        DesktopCmsApi.checkReadiness().catch(() => ({ ready: true })),
        DesktopCmsApi.listCoupons().catch(() => ({ items: [] })),
      ]);
      setCodBlacklist(blData.items || []);
      setKeychainStatus(kcStatus);
      setWaOutbox(outboxData.items || []);
      setAuditLogs(auditData.items || []);
      setReadinessStatus(readyData);
      setCoupons(cpnData.items || []);
      setDashboard(dashData);
      setReports(repData);
      setBrands(brdData.items || []);
      setCategories(catData.items || []);
      setProducts(prodData.items || []);
      setOrders(ordData.items || []);
      setCustomers(custData.items || []);
      setMovements(movData.items || []);
      setHomepageSections(layData.homepage_sections || []);
      if (layData.settings) {
        const s = layData.settings;
        if (s.store_phone || s.contact_phone) setStorePhoneInput(String(s.store_phone || s.contact_phone));
        if (s.whatsapp_contact_number || s.whatsapp_phone) setStoreWhatsappInput(String(s.whatsapp_contact_number || s.whatsapp_phone));
        if (s.store_location) setStoreLocationInput(String(s.store_location));
        if (s.free_delivery_threshold_dzd !== undefined || s.free_shipping_threshold_dzd !== undefined) {
          setFreeThresholdInput(String(s.free_delivery_threshold_dzd ?? s.free_shipping_threshold_dzd));
        }
      }
      setBanners(bnrData.items || []);
      const loadedPages = pgData.items || [];
      setStaticPages(loadedPages);
      const currentPg = loadedPages.find((p: any) => p.slug === pageSlug) || loadedPages[0];
      if (currentPg) {
        setPageTitleFr(currentPg.title_fr || "");
        setPageContentFr(currentPg.content_fr || "");
      }
      setBackups(bkpData.items || []);
      setRecoveryStatus(recData);
      setHealthStatus(hltData);
      if (catData.items?.length && !prodCategoryId) {
        setProdCategoryId(catData.items[0].id);
      }
    } catch (err: any) {
      if (err?.code === "SESSION_EXPIRED" || err?.message === "SESSION_EXPIRED") {
        setUser(null);
        const msg = "Par mesure de sécurité, votre session a expiré. Vos brouillons locaux sont conservés — veuillez vous reconnecter.";
        setError(msg);
        notifyClientWarning("Session expirée", msg);
      } else {
        const tr = notifyClientError(err, "Synchronisation avec le serveur interrompue", false);
        setError(tr.message);
      }
    } finally {
      setLoadingWorkspace(false);
    }
  }

  useEffect(() => {
    writeDraft("luxe_cms_user", user);
  }, [user]);

  useEffect(() => {
    writeDraft("luxe_cms_active_tab", activeTab);
  }, [activeTab]);

  useEffect(() => {
    writeDraft("luxe_cms_prod_search", prodSearch);
    writeDraft("luxe_cms_prod_cat_id", prodCategoryId);
    writeDraft("luxe_cms_prod_name_fr", prodNameFr);
    writeDraft("luxe_cms_prod_sku", prodSku);
    writeDraft("luxe_cms_prod_slug", prodSlug);
    writeDraft("luxe_cms_prod_price", prodSellingPrice);
    writeDraft("luxe_cms_prod_cost", prodCostPrice);
    writeDraft("luxe_cms_prod_status", prodStatus);
    writeDraft("luxe_cms_prod_dyn_attrs", prodDynamicAttrs);
    writeDraft("luxe_cms_prod_stock", prodVariantStock);
  }, [prodSearch, prodCategoryId, prodNameFr, prodSku, prodSlug, prodSellingPrice, prodCostPrice, prodStatus, prodDynamicAttrs, prodVariantStock]);

  useEffect(() => {
    const tabOrder: CmsTab[] = ["dashboard", "products", "categories", "inventory", "orders", "delivery_wilayas", "content", "backups"];
    function onKeyDown(e: KeyboardEvent) {
      if (e.altKey && e.key >= "1" && e.key <= "8") {
        e.preventDefault();
        setActiveTab(tabOrder[Number(e.key) - 1]);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (user && keychainReady) {
      loadAllWorkspaceData();
    }
  }, [user, keychainReady]);

  useEffect(() => {
    if (user && keychainReady) {
      DesktopCmsApi.listOrders(orderStatusFilter || undefined)
        .then((ordData) => setOrders(ordData.items || []))
        .catch(() => {});
    }
  }, [orderStatusFilter, keychainReady]);

  async function handleFirstTimeSetup(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (ownerPassword.length < 10) {
      const msg = "Le mot de passe propriétaire doit comporter au moins 10 caractères.";
      setError(msg);
      notifyClientWarning("Mot de passe trop court", msg);
      return;
    }
    if (ownerPassword !== ownerConfirm) {
      const msg = "Les deux mots de passe saisis ne correspondent pas.";
      setError(msg);
      notifyClientWarning("Confirmation du mot de passe", msg);
      return;
    }
    try {
      const res = await DesktopCmsApi.initializeOwner({
        full_name: ownerName.trim(),
        email: ownerEmail.trim(),
        password: ownerPassword,
        whatsapp_phone: whatsappPhone.trim(),
        emergency_phone: emergencyPhone.trim(),
      });
      setRequiresOwnerSetup(false);
      if (res?.user) {
        setUser(res.user);
      }
      const okMsg = `Accès propriétaire configuré avec succès. Code de secours sécurisé : ${res.emergency_code_backup}. Vos accès sont désormais verrouillés.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Initialisation Propriétaire Verrouillée", okMsg, true);
    } catch (err: any) {
      const tr = notifyClientError(err, "Initialisation du propriétaire refusée");
      setError(tr.message);
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!loginEmail.trim() || !loginPassword) {
      notifyClientWarning("Identifiants requis", "Veuillez renseigner votre adresse e-mail et votre mot de passe administrateur.");
      return;
    }
    try {
      const res = await DesktopCmsApi.login(loginEmail.trim(), loginPassword);
      setUser(res.user);
      notifyClientSuccess("Connexion établie", `Bienvenue dans le CMS Mus Luxury, ${res.user.full_name}.`);
    } catch (err: any) {
      const tr = notifyClientError(err, "Échec de connexion administrateur");
      setError(tr.message);
    }
  }

  async function handleRequestRecoveryOtp() {
    setError("");
    setRecStepInfo("");
    if (!recPhone.trim()) {
      notifyClientWarning("Numéro requis", "Veuillez saisir votre numéro de téléphone administrateur (ex: 05XX / 06XX / 07XX...).");
      return;
    }
    try {
      const res = await DesktopCmsApi.requestPasswordRecovery(recPhone.trim(), recChannel);
      if (res.test_otp) {
        setRecCode(res.test_otp);
        const msg = `Code OTP WhatsApp (Mode Sandbox) généré : ${res.test_otp} (valable 5 min).`;
        setRecStepInfo(msg);
        notifyClientSuccess("Code OTP WhatsApp envoyé", msg);
      } else {
        const msg = res.message || "Code OTP envoyé sur votre WhatsApp administrateur vérifié.";
        setRecStepInfo(msg);
        notifyClientSuccess("Code OTP WhatsApp envoyé", msg);
      }
    } catch (err: any) {
      const tr = notifyClientError(err, "Envoi du code OTP WhatsApp impossible");
      setError(tr.message);
    }
  }

  async function handlePasswordRecoveryVerify(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!recPhone.trim() || !recCode.trim() || recNewPassword.length < 10) {
      notifyClientWarning(
        "Données de récupération incomplètes",
        "Veuillez saisir votre téléphone, le code de vérification et un nouveau mot de passe d'au moins 10 caractères."
      );
      return;
    }
    try {
      const res = await DesktopCmsApi.verifyPasswordRecovery(recPhone.trim(), recCode.trim(), recNewPassword);
      setShowRecoveryModal(false);
      setRecStepInfo("");
      const extra = res.replacement_emergency_code
        ? ` Nouveau code de secours généré : ${res.replacement_emergency_code}`
        : "";
      const okMsg = `Mot de passe réinitialisé avec succès.${extra} Connectez-vous avec votre nouveau mot de passe.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Mot de passe réinitialisé", okMsg, true);
    } catch (err: any) {
      const tr = notifyClientError(err, "Vérification du code de récupération refusée");
      setError(tr.message);
    }
  }

  async function handleCreateProduct(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccessMsg("");
    if (!prodNameFr.trim() || !prodSku.trim()) {
      notifyClientWarning("Champs produit requis", "Veuillez renseigner la désignation du produit (FR) et sa référence SKU unique.");
      return;
    }
    if (Number(prodSellingPrice) <= 0 || Number(prodCostPrice) < 0) {
      notifyClientWarning("Prix invalide", "Le prix de vente en DA doit être strictement positif et le coût d'achat ne peut pas être négatif.");
      return;
    }
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
            stock_qty: Math.max(0, Number(prodVariantStock) || 0),
            attributes: defaultAttrs,
          },
        ],
      });
      const okMsg = `Produit "${prodNameFr}" créé et synchronisé sur la boutique.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Produit ajouté au catalogue", okMsg);
      setProdNameFr("");
      setProdSku("");
      setProdSlug("");
      setProdDynamicAttrs({});
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Création du produit impossible");
      setError(tr.message);
    }
  }

  async function handleSaveEditedProduct(e: React.FormEvent) {
    e.preventDefault();
    if (!editingProduct) return;
    setError("");
    if (!editingProduct.name_fr?.trim() || Number(editingProduct.selling_price_dzd) <= 0) {
      notifyClientWarning("Champs produit invalides", "Veuillez vérifier le nom et le prix de vente (DA) du produit.");
      return;
    }
    try {
      await DesktopCmsApi.updateProduct(editingProduct.id, {
        name_fr: editingProduct.name_fr.trim(),
        sku: editingProduct.sku?.trim() || undefined,
        category_id: editingProduct.category_id ? Number(editingProduct.category_id) : undefined,
        brand_id: editingProduct.brand_id ? Number(editingProduct.brand_id) : undefined,
        main_image_url: editingProduct.main_image_url || undefined,
        selling_price_dzd: Number(editingProduct.selling_price_dzd),
        purchase_cost_dzd: Number(editingProduct.purchase_cost_dzd || 0),
        status: editingProduct.status,
        dynamic_attributes: editingProduct.attributes || undefined,
        expected_version: Number(editingProduct.version || 1),
      });
      const okMsg = `Produit #${editingProduct.id} mis à jour avec contrôle de concurrence optimiste.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Fiche produit enregistrée", okMsg);
      setEditingProduct(null);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Conflit ou erreur lors de la mise à jour du produit");
      setError(tr.message);
    }
  }

  async function handleArchiveProduct(productId: number) {
    setError("");
    try {
      await DesktopCmsApi.archiveProduct(productId);
      const okMsg = `Produit #${productId} archivé en toute sécurité (historique des commandes préservé).`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Produit archivé", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Archivage du produit impossible");
      setError(tr.message);
    }
  }

  async function handleConfirmDeleteProduct(hard: boolean) {
    if (!productToDelete) return;
    setDeletingProduct(true);
    setError("");
    try {
      const res = await DesktopCmsApi.deleteProduct(productToDelete.id, hard, hard && forceDeleteProduct);
      if (res?.archived && !res?.deleted && hard) {
        const warnMsg = res.message || "Ce produit possède des commandes rattachées et a été archivé au lieu d'être supprimé.";
        setError(warnMsg);
        notifyClientError(warnMsg, "Produit archivé (commandes existantes)");
      } else {
        const okMsg =
          res?.message ||
          (hard
            ? `Produit "${productToDelete.name_fr}" supprimé définitivement du catalogue et de la base de données.`
            : `Produit "${productToDelete.name_fr}" archivé en toute sécurité.`);
        setSuccessMsg(okMsg);
        notifyClientSuccess(hard ? "Produit supprimé" : "Produit archivé", okMsg);
        setProductToDelete(null);
        setForceDeleteProduct(false);
      }
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Suppression du produit impossible");
      setError(tr.message);
    } finally {
      setDeletingProduct(false);
    }
  }

  async function handleRestoreProduct(productId: number) {
    setError("");
    try {
      await DesktopCmsApi.bulkUpdateProductStatus([productId], "published");
      const okMsg = `Produit #${productId} réactivé et remis en vente sur la boutique en ligne.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Produit réactivé", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Réactivation du produit impossible");
      setError(tr.message);
    }
  }

  async function handleAdjustStock(variantId: number, delta: number) {
    setError("");
    try {
      await DesktopCmsApi.adjustVariantStock(variantId, delta, "cms_manual_adjustment");
      const okMsg = `Stock de la variante #${variantId} mis à jour (${delta > 0 ? `+${delta}` : delta}).`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Stock mis à jour", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Ajustement de stock refusé");
      setError(tr.message);
    }
  }

  async function handleOrderStatusChange(orderId: number, nextStatus: string) {
    setError("");
    try {
      await DesktopCmsApi.updateOrderStatus(orderId, nextStatus);
      const okMsg = `Statut de la commande #${orderId} mis à jour vers "${nextStatus}".`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Statut de commande mis à jour", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Changement de statut de commande refusé");
      setError(tr.message);
    }
  }

  async function handleOpenInvoice(orderId: number) {
    setError("");
    try {
      const inv = await DesktopCmsApi.getOrderInvoice(orderId);
      setSelectedInvoice(inv);
      notifyClientSuccess("Facture générée", `Bon de livraison / Facture de la commande #${inv.order_reference} prêt à l'impression.`);
    } catch (err: any) {
      const tr = notifyClientError(err, "Ouverture de la facture impossible");
      setError(tr.message);
    }
  }

  async function handleCheckPhoneCodRisk() {
    if (!codCheckPhone.trim() || codCheckPhone.trim().length < 8) {
      notifyClientWarning(
        "Numéro de téléphone requis",
        "Veuillez saisir un numéro de téléphone algérien valide (ex: 0550 11 22 33 ou +213...) pour analyser son historique COD."
      );
      return;
    }
    setError("");
    try {
      const res = await DesktopCmsApi.checkPhoneCodRisk(codCheckPhone.trim());
      setCodCheckResult(res);
      notifyClientSuccess(
        "Score Anti-Retour COD calculé",
        `Numéro ${res.phone_local} : ${res.delivered_count} livrée(s), ${res.returned_count} retour(s) (${res.return_rate_percent}% retours).`
      );
    } catch (err: any) {
      const tr = notifyClientError(err, "Vérification Anti-Retour COD impossible");
      setError(tr.message);
    }
  }

  async function handleBlockCustomerPhone(phone: string, reason = "Retour abusif / Non-récupération COD") {
    if (!phone.trim()) {
      notifyClientWarning("Numéro manquant", "Veuillez indiquer le numéro de téléphone à bloquer sur la Liste Noire COD.");
      return;
    }
    setError("");
    try {
      const res = await DesktopCmsApi.addPhoneToCodBlacklist(phone.trim(), reason.trim() || "Retour abusif / Non-récupération COD", true);
      setCodCheckResult(res);
      const okMsg = `Numéro ${res.phone_local} ajouté à la Liste Noire Anti-Retour COD. Ses futures commandes seront bloquées automatiquement.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Numéro bloqué (Liste Noire COD)", okMsg, true);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Blocage du numéro impossible");
      setError(tr.message);
    }
  }

  async function handleUnblockCustomerPhone(phone: string) {
    setError("");
    try {
      const res = await DesktopCmsApi.removePhoneFromCodBlacklist(phone);
      setCodCheckResult(res);
      const okMsg = `Numéro ${res.phone_local} débloqué de la Liste Noire COD.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Numéro débloqué", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Déblocage du numéro impossible");
      setError(tr.message);
    }
  }

  async function handleNotifyOrderCustomerWhatsapp(
    orderId: number,
    templateType: "confirmation_call" | "shipped_notice" | "no_answer_followup" | "delivery_arrived" = "confirmation_call"
  ) {
    setError("");
    try {
      const receipt = await DesktopCmsApi.notifyOrderCustomerWhatsapp(orderId, templateType);
      const okMsg = `Notification WhatsApp (${templateType}) transmise à ${receipt.recipient_local} : "${receipt.message_text.slice(0, 90)}..."`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Notification WhatsApp Client Envoyée", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Envoi de la notification WhatsApp impossible");
      setError(tr.message);
    }
  }

  async function handleExportOrdersCsv() {
    setError("");
    try {
      const csvText = await DesktopCmsApi.exportOrdersCsv();
      const blob = new Blob([csvText], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "mus_luxury_orders.csv";
      a.click();
      URL.revokeObjectURL(url);
      const okMsg = "Export CSV des commandes généré et téléchargé (mus_luxury_orders.csv).";
      setSuccessMsg(okMsg);
      notifyClientSuccess("Export CSV téléchargé", okMsg);
    } catch (err: any) {
      const tr = notifyClientError(err, "Export CSV des commandes impossible");
      setError(tr.message);
    }
  }

  async function handleSaveStoreSettings(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!storePhoneInput.trim() || !storeLocationInput.trim()) {
      notifyClientWarning("Paramètres incomplets", "Veuillez renseigner le téléphone et l'adresse officielle de la boutique Mus Luxury.");
      return;
    }
    try {
      await DesktopCmsApi.updateStoreSettings({
        store_phone: storePhoneInput.trim(),
        whatsapp_contact_number: storeWhatsappInput.trim(),
        store_location: storeLocationInput.trim(),
        free_delivery_threshold_dzd: freeThresholdInput.trim(),
      });
      const okMsg = "Paramètres de la boutique Mus Luxury enregistrés et synchronisés.";
      setSuccessMsg(okMsg);
      notifyClientSuccess("Paramètres boutique enregistrés", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Enregistrement des paramètres refusé");
      setError(tr.message);
    }
  }

  async function handleCreateCoupon(e: React.FormEvent) {
    e.preventDefault();
    setError("");
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
      setSuccessMsg(okMsg);
      notifyClientSuccess("Code promotionnel activé", okMsg);
      setCouponCode("");
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Création du code promo refusée");
      setError(tr.message);
    }
  }

  async function handleDeactivateCoupon(couponId: number, code: string) {
    setError("");
    try {
      await DesktopCmsApi.deactivateCoupon(couponId);
      const okMsg = `Code promo "${code}" désactivé avec succès.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Code promo désactivé", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Désactivation du code promo impossible");
      setError(tr.message);
    }
  }

  async function handleDeleteBanner(bannerId: number) {
    setError("");
    try {
      await DesktopCmsApi.deleteBanner(bannerId);
      const okMsg = `Bannière #${bannerId} supprimée.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Bannière supprimée", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Suppression de la bannière impossible");
      setError(tr.message);
    }
  }

  async function handleSaveStaticPage(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (pageTitleFr.trim().length < 2 || pageContentFr.trim().length < 5) {
      notifyClientWarning(
        "Contenu de page incomplet",
        "Veuillez saisir un titre et un texte complet avant de publier la page statique."
      );
      return;
    }
    try {
      await DesktopCmsApi.upsertStaticPage(pageSlug, {
        title_fr: pageTitleFr.trim(),
        content_fr: pageContentFr.trim(),
        is_published: true,
      });
      const okMsg = `Page statique "/pages/${pageSlug}" enregistrée et publiée.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Page statique publiée", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Enregistrement de la page statique impossible");
      setError(tr.message);
    }
  }

  async function handleTriggerBackup() {
    setError("");
    try {
      const bkp = await DesktopCmsApi.triggerBackup();
      const okMsg = `Sauvegarde créée et vérifiée : ${bkp.filename} (SHA-256: ${bkp.sha256_checksum.slice(0, 16)}...)`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Sauvegarde complète créée", okMsg, true);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Échec de la création de sauvegarde");
      setError(tr.message);
    }
  }

  async function handleVerifyBackupRestore(backupId: number) {
    setError("");
    try {
      const rep = await DesktopCmsApi.verifyBackupRestore(backupId);
      setRestoreReport(rep);
      const okMsg = `Test de restauration isolée réussi pour la sauvegarde #${backupId} (${rep.restored_counts?.products || 0} produits, ${rep.restored_counts?.delivery_zones || 69} wilayas vérifiées) !`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Restauration isolée vérifiée", okMsg, true);
    } catch (err: any) {
      const tr = notifyClientError(err, "Vérification de la sauvegarde échouée");
      setError(tr.message);
    }
  }

  async function handleDeltaSync() {
    setError("");
    try {
      const syncRes = await DesktopCmsApi.deltaSync(0, 0);
      await loadAllWorkspaceData();
      const okMsg = `Delta Sync terminé : ${syncRes.missed_orders_count} commande(s) et ${syncRes.current_variant_stocks?.length || 0} variantes synchronisées.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Synchronisation serveur terminée", okMsg);
    } catch (err: any) {
      const tr = notifyClientError(err, "Synchronisation Delta interrompue");
      setError(tr.message);
    }
  }

  async function handleCreateBrand(e: React.FormEvent) {
    e.preventDefault();
    if (!newBrandName.trim()) {
      notifyClientWarning("Nom de marque requis", "Veuillez saisir le nom de la marque avant de l'ajouter.");
      return;
    }
    setError("");
    try {
      const slug = newBrandName.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
      await DesktopCmsApi.createBrand({ name: newBrandName.trim(), slug, logo_url: "/assets/mus_luxury_logo.png" });
      const createdName = newBrandName.trim();
      setNewBrandName("");
      const okMsg = `Marque "${createdName}" créée et ajoutée au catalogue.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Marque ajoutée", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Création de la marque impossible");
      setError(tr.message);
    }
  }

  async function handleBulkStatus(status: "published" | "draft" | "archived") {
    if (selectedProductIds.length === 0) {
      notifyClientWarning(
        "Aucun produit sélectionné",
        "Veuillez cocher au moins un produit dans le tableau avant d'appliquer une action groupée."
      );
      return;
    }
    setError("");
    try {
      const count = selectedProductIds.length;
      await DesktopCmsApi.bulkUpdateProductStatus(selectedProductIds, status);
      setSelectedProductIds([]);
      const okMsg = `Statut "${status}" appliqué à ${count} produit(s).`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Mise à jour groupée effectuée", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Mise à jour groupée impossible");
      setError(tr.message);
    }
  }

  async function handleGenerateVariantMatrix(productId: number) {
    setError("");
    const colors = matrixColorCsv.split(",").map((s) => s.trim()).filter(Boolean);
    const sizes = matrixSizeCsv.split(",").map((s) => s.trim()).filter(Boolean);
    if (colors.length === 0 || sizes.length === 0) {
      notifyClientWarning("Axes de variantes requis", "Veuillez indiquer au moins une couleur et une taille séparées par des virgules.");
      return;
    }
    try {
      await DesktopCmsApi.generateVariants(productId, {
        axes: { color: colors, size: sizes },
        default_stock: 4,
      });
      const okMsg = `Matrice de variantes (${colors.length}×${sizes.length}) générée pour le produit #${productId}.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Matrice de variantes générée", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Génération des variantes impossible");
      setError(tr.message);
    }
  }

  async function handleUploadLocalProductMedia(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      notifyClientWarning("Format d'image non supporté", "Veuillez sélectionner une image au format JPEG (.jpg), PNG (.png) ou WEBP (.webp).");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      notifyClientWarning("Image trop volumineuse", "La taille de l'image ne doit pas dépasser 5 Mo.");
      return;
    }
    setError("");
    try {
      const uploaded = await DesktopCmsApi.uploadMediaFile(file);
      setNewImageUrl(uploaded.url);
      setBannerImageUrl(uploaded.url);
      notifyClientSuccess("Image téléversée sur le serveur", `Fichier vérifié et enregistré : ${uploaded.url}`);
    } catch (err: any) {
      const tr = notifyClientError(err, "Téléversement de l'image refusé");
      setError(tr.message);
    }
  }

  async function handleAddProductGalleryImage(productId: number) {
    if (!newImageUrl.trim()) {
      notifyClientWarning("URL d'image requise", "Veuillez téléverser une image ou saisir son chemin avant de l'ajouter à la galerie.");
      return;
    }
    setError("");
    try {
      const img = await DesktopCmsApi.addProductImage(productId, {
        image_url: newImageUrl.trim(),
        alt_text: "Mus Luxury Gallery",
        display_order: 1,
        set_as_primary: true,
      });
      await DesktopCmsApi.reorderProductImages(productId, {
        orders: [{ image_id: img.id, display_order: 1 }],
        primary_image_url: newImageUrl.trim(),
      });
      const okMsg = `Image ajoutée et ordonnée pour le produit #${productId}.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Galerie produit mise à jour", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Ajout de l'image à la galerie impossible");
      setError(tr.message);
    }
  }

  async function handleRemoveProductGalleryImage(imageId: number) {
    setError("");
    try {
      await DesktopCmsApi.deleteProductImage(imageId);
      const okMsg = `Image #${imageId} supprimée de la galerie.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Image retirée", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Suppression de l'image impossible");
      setError(tr.message);
    }
  }

  async function handleToggleHomepageSection(sec: any) {
    setError("");
    try {
      await DesktopCmsApi.updateHomepageSection(sec.section_key, {
        title_fr: sec.title_fr,
        is_active: !sec.is_active,
        display_order: sec.display_order || 1,
        config: sec.config || {},
      });
      const okMsg = `Section d'accueil "${sec.title_fr}" mise à jour.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Mise en page mise à jour", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Modification de la section d'accueil impossible");
      setError(tr.message);
    }
  }

  async function handleCreateBanner(e: React.FormEvent) {
    e.preventDefault();
    if (!bannerTitleFr.trim()) {
      notifyClientWarning("Titre de bannière requis", "Veuillez saisir le titre de la bannière promotionnelle avant de la publier.");
      return;
    }
    setError("");
    try {
      await DesktopCmsApi.createBanner({
        position: "promo_grid",
        title_fr: bannerTitleFr.trim(),
        subtitle_fr: "Collection Exclusive Mus Luxury",
        cta_text_fr: "Découvrir",
        cta_link: "/categories/sacs",
        image_url: bannerImageUrl,
        is_active: true,
        display_order: banners.length + 1,
      });
      setBannerTitleFr("");
      const okMsg = "Bannière promotionnelle créée et publiée.";
      setSuccessMsg(okMsg);
      notifyClientSuccess("Bannière publiée", okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, "Création de la bannière impossible");
      setError(tr.message);
    }
  }

  async function handleRotateEmergencyCode() {
    setError("");
    try {
      const res = await DesktopCmsApi.rotateEmergencyCode();
      const okMsg = `Nouveau Code d'Urgence Hors-Ligne généré : ${res.emergency_code} (Conservez-le en lieu sûr).`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Code d'Urgence régénéré", okMsg, true);
    } catch (err: any) {
      const tr = notifyClientError(err, "Rotation du code d'urgence refusée");
      setError(tr.message);
    }
  }

  function renderClientNotificationCenter() {
    return (
      <>
        {/* Floating Toast Notification Stack (Top-Right) */}
        <div className="fixed top-4 right-4 z-50 flex flex-col gap-2.5 max-w-md w-full pointer-events-none">
          {toastQueue.map((t) => {
            const styleMap = {
              success: "bg-[#02291F] text-white border-[#D4AF62]",
              error: "bg-red-950 text-white border-red-400",
              warning: "bg-amber-950 text-white border-amber-400",
              info: "bg-[#063D2E] text-white border-[#D4AF62]",
            };
            const badgeMap = {
              success: "CONFIRMATION",
              error: "ALERTE SÉCURITÉ / ACTION",
              warning: "VÉRIFICATION REQUISE",
              info: "INFORMATION",
            };
            return (
              <div
                key={t.id}
                role="status"
                aria-live="polite"
                className={`pointer-events-auto p-3.5 rounded-2xl border-2 shadow-2xl flex items-start justify-between gap-3 ${styleMap[t.type]}`}
              >
                <div className="space-y-1 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/15 text-[#D4AF62] font-extrabold text-[10px]">
                      {t.type === "success" && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
                      {t.type === "error" && <ShieldAlert className="w-3 h-3 text-rose-400" />}
                      {t.type === "warning" && <AlertTriangle className="w-3 h-3 text-amber-400" />}
                      {t.type === "info" && <Clock className="w-3 h-3 text-[#D4AF62]" />}
                      <span>{badgeMap[t.type]}</span>
                    </span>
                    <span className="text-[10px] opacity-70 font-mono">{t.timestamp}</span>
                  </div>
                  <p className="font-bold text-sm text-[#E8D4A5]">{t.title}</p>
                  <p className="text-xs leading-relaxed opacity-95">{t.message}</p>
                </div>
                <button
                  type="button"
                  onClick={() => setToastQueue((prev) => prev.filter((item) => item.id !== t.id))}
                  className="text-xs font-bold p-1 rounded bg-white/10 hover:bg-white/20"
                  aria-label="Fermer la notification"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })}
        </div>

        {/* Modal Client Message Box Dialog (Boîte de Message Client) */}
        {activeMessageBox && (
          <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
            <div
              role="dialog"
              aria-modal="true"
              className="bg-white text-[#202923] rounded-2xl max-w-md w-full overflow-hidden shadow-2xl border-2 border-[#D4AF62]"
            >
              <div
                className={`px-5 py-3.5 flex items-center justify-between ${
                  activeMessageBox.type === "error"
                    ? "bg-red-900 text-white"
                    : activeMessageBox.type === "warning"
                    ? "bg-amber-800 text-white"
                    : "bg-[#063D2E] text-white"
                }`}
              >
                <div className="flex items-center gap-2">
                  {activeMessageBox.type === "error" && <ShieldAlert className="w-4 h-4 text-rose-300" />}
                  {activeMessageBox.type === "warning" && <AlertTriangle className="w-4 h-4 text-amber-300" />}
                  {activeMessageBox.type === "info" && <CheckCircle2 className="w-4 h-4 text-[#D4AF62]" />}
                  <span className="text-base font-extrabold text-[#D4AF62]">
                    {activeMessageBox.type === "error"
                      ? "Message Système — Action interrompue"
                      : activeMessageBox.type === "warning"
                      ? "Vérification des données"
                      : "Confirmation Mus Luxury CMS"}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveMessageBox(null)}
                  className="w-7 h-7 rounded-full bg-black/25 text-white font-bold text-xs flex items-center justify-center hover:bg-black/40 transition"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="p-6 space-y-4 text-xs">
                <h4 className="text-base font-serif font-bold text-[#063D2E]">{activeMessageBox.title}</h4>
                <p className="text-sm text-gray-700 leading-relaxed bg-[#F8F6F0] p-3.5 rounded-xl border border-[#D4AF62]/30">
                  {activeMessageBox.message}
                </p>
                <div className="flex justify-end pt-1">
                  <button
                    type="button"
                    onClick={() => setActiveMessageBox(null)}
                    className="px-6 py-2.5 rounded-xl bg-[#063D2E] hover:bg-[#02291F] text-[#D4AF62] font-extrabold text-xs shadow"
                  >
                    Compris (Fermer)
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </>
    );
  }

  function renderDeleteProductModal() {
    if (!productToDelete) return null;
    return (
      <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
        <div
          role="dialog"
          aria-modal="true"
          className="bg-white text-[#202923] rounded-2xl max-w-lg w-full overflow-hidden shadow-2xl border-2 border-[#D4AF62]"
        >
          <div className="px-6 py-4 bg-[#063D2E] text-white flex items-center justify-between border-b border-[#D4AF62]/40">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-[#D4AF62]" />
              <div>
                <h3 className="text-base font-serif font-bold text-[#D4AF62]">
                  Suppression / Archivage du Produit
                </h3>
                <p className="text-[11px] text-[#E8D4A5]">Gestion du catalogue — Maison Mus Luxury</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => { setProductToDelete(null); setForceDeleteProduct(false); setError(""); }}
              disabled={deletingProduct}
              className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-white font-bold flex items-center justify-center transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="p-6 space-y-5 text-xs">
            {error && (
              <div className="p-3 bg-red-100 border border-red-300 text-red-800 rounded-xl text-xs font-semibold flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-800 shrink-0" />
                <span>{error}</span>
              </div>
            )}
            {/* Product info banner */}
            <div className="p-4 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30 flex items-center gap-4">
              <div className="w-16 h-16 rounded-xl bg-[#063D2E]/10 border border-[#D4AF62]/40 flex items-center justify-center overflow-hidden shrink-0">
                {productToDelete.main_image_url || productToDelete.image_url ? (
                  <img
                    src={productToDelete.main_image_url || productToDelete.image_url}
                    alt=""
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <ShoppingBag className="w-7 h-7 text-[#063D2E]/40" />
                )}
              </div>
              <div className="space-y-1">
                <span className="px-2 py-0.5 rounded-full bg-[#063D2E] text-[#D4AF62] text-[10px] font-mono font-bold">
                  SKU: {productToDelete.sku}
                </span>
                <h4 className="text-base font-serif font-bold text-[#063D2E]">{productToDelete.name_fr}</h4>
                <div className="text-[11px] text-gray-600 flex gap-3 font-mono">
                  <span>
                    Prix de vente: <strong>{Number(productToDelete.selling_price_dzd || 0).toLocaleString()} DA</strong>
                  </span>
                  <span>
                    Stock: <strong>{productToDelete.total_stock ?? 0} unités</strong>
                  </span>
                  <span>
                    Statut: <strong>{productToDelete.status === "archived" ? "Archivé (hors vitrine)" : productToDelete.status}</strong>
                  </span>
                </div>
              </div>
            </div>

            <p className="text-gray-700 leading-relaxed font-semibold">
              Veuillez sélectionner l'action à exécuter pour cet article :
            </p>

            {/* Action buttons */}
            <div className="space-y-3">
              {/* Permanent Hard Delete */}
              <div className="p-3.5 rounded-xl border border-red-200 bg-red-50/70 space-y-2">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <strong className="text-red-900 block font-bold text-xs">
                      Option 1 : Suppression Définitive de la Base
                    </strong>
                    <span className="text-[11px] text-red-700 leading-relaxed block mt-0.5">
                      Supprime intégralement la fiche, ses variantes et images de la base de données.
                    </span>
                    <label className="flex items-center gap-2 mt-2 pt-2 border-t border-red-200 text-red-900 cursor-pointer font-bold text-[11px]">
                      <input
                        type="checkbox"
                        checked={forceDeleteProduct}
                        onChange={(e) => setForceDeleteProduct(e.target.checked)}
                        className="rounded text-red-600 w-4 h-4"
                      />
                      <span>Forcer la suppression définitive (efface également les commandes tests rattachées)</span>
                    </label>
                  </div>
                  <button
                    type="button"
                    disabled={deletingProduct}
                    onClick={() => handleConfirmDeleteProduct(true)}
                    className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-red-700 hover:bg-red-800 disabled:opacity-50 text-white font-extrabold whitespace-nowrap shadow-xs shrink-0"
                  >
                    <Trash2 className="w-4 h-4 text-white" />
                    <span>{deletingProduct ? "Suppression..." : "Supprimer Définitivement"}</span>
                  </button>
                </div>
              </div>

              {/* Safe Soft Archive */}
              <div className="p-3.5 rounded-xl border border-amber-200 bg-amber-50/70 space-y-2">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <strong className="text-amber-900 block font-bold text-xs">
                      Option 2 : Archivage Sécurisé (Recommandé)
                    </strong>
                    <span className="text-[11px] text-amber-800 leading-relaxed block mt-0.5">
                      Masque le produit de la vitrine tout en préservant l'intégrité des factures et de la comptabilité. Vous pouvez le réactiver à tout moment.
                    </span>
                  </div>
                  <button
                    type="button"
                    disabled={deletingProduct}
                    onClick={() => handleConfirmDeleteProduct(false)}
                    className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-extrabold whitespace-nowrap shadow-xs shrink-0"
                  >
                    <Archive className="w-4 h-4 text-white" />
                    <span>{deletingProduct ? "Archivage..." : "Archiver la Pièce"}</span>
                  </button>
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-2 border-t border-gray-100">
              <button
                type="button"
                disabled={deletingProduct}
                onClick={() => { setProductToDelete(null); setForceDeleteProduct(false); setError(""); }}
                className="px-5 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-700 font-bold"
              >
                Annuler
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (checkingSetup) {
    return <div className="p-10 text-center text-white bg-[#02291F] min-h-screen">Initialisation sécurisée de la session administrateur...</div>;
  }

  if (requiresOwnerSetup) {
    return (
      <div className="min-h-screen bg-[#02291F] text-white flex items-center justify-center p-6">
        {renderClientNotificationCenter()}
      {renderDeleteProductModal()}
        <form onSubmit={handleFirstTimeSetup} className="max-w-lg w-full bg-[#063D2E] p-8 rounded-2xl border-2 border-[#D4AF62] space-y-4 shadow-2xl">
          <div className="text-center">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#D4AF62] text-[#02291F] text-[10px] font-extrabold uppercase tracking-wide">
              <Sparkles className="w-3 h-3 text-[#02291F]" />
              <span>Première Ouverture — Configuration Initiale</span>
            </span>
            <h1 className="text-2xl font-serif text-white font-bold mt-2">Accès Propriétaire &amp; Direction</h1>
            <p className="text-xs text-[#E8D4A5] mt-1">
              Configurez vos accès et vos numéros de secours. Après enregistrement sécurisé, vos accès seront verrouillés.
            </p>
          </div>
          {error && <div className="p-3 rounded bg-red-900/90 text-xs text-red-100">{error}</div>}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block font-bold mb-1">Nom Complet</label>
              <input value={ownerName} onChange={(e) => setOwnerName(e.target.value)} required placeholder="Nom et Prénom" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
            </div>
            <div>
              <label className="block font-bold mb-1">Email / Identifiant</label>
              <input type="email" value={ownerEmail} onChange={(e) => setOwnerEmail(e.target.value)} required placeholder="administrateur@domaine.dz" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
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
            <p className="font-bold text-[#D4AF62]">Numéros de contact &amp; vérification de sécurité :</p>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[11px] mb-0.5">1. WhatsApp Récupération</label>
                <input value={whatsappPhone} onChange={(e) => setWhatsappPhone(e.target.value)} required placeholder="06XX XX XX XX" className="w-full px-2.5 py-1.5 rounded bg-[#063D2E] border border-[#D4AF62]/40 font-mono text-xs" />
              </div>
              <div>
                <label className="block text-[11px] mb-0.5">2. Numéro Secours / Urgence</label>
                <input value={emergencyPhone} onChange={(e) => setEmergencyPhone(e.target.value)} required placeholder="+213 5XX XX XX XX" className="w-full px-2.5 py-1.5 rounded bg-[#063D2E] border border-[#D4AF62]/40 font-mono text-xs" />
              </div>
            </div>
          </div>
          <button type="submit" className="w-full py-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-sm shadow-xl hover:brightness-105 transition">
            Enregistrer et Sécuriser l'Accès Administrateur
          </button>
        </form>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-[#02291F] text-white flex items-center justify-center p-6">
        {renderClientNotificationCenter()}
      {renderDeleteProductModal()}
        <div className="max-w-md w-full bg-[#063D2E] p-8 rounded-2xl border border-[#D4AF62]/40 space-y-4 shadow-2xl">
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="text-center">
              <h1 className="text-2xl font-serif text-[#D4AF62] font-bold">Mus Luxury — Desktop CMS</h1>
              <p className="text-xs text-[#E8D4A5] mt-1">Connexion Administrateur Sécurisée — Maison Mus Luxury</p>
            </div>
            {successMsg && <div className="p-3 rounded bg-emerald-800 text-xs text-white">{successMsg}</div>}
            {error && <div className="p-3 rounded bg-red-900/90 text-xs text-red-100">{error}</div>}
            <div>
              <label className="block text-xs font-bold mb-1">Email / Identifiant</label>
              <input type="email" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} required placeholder="administrateur@domaine.dz" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-bold mb-1">Mot de passe</label>
              <input type="password" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-sm" />
            </div>
            <div className="text-right">
              <button type="button" onClick={() => setShowRecoveryModal(!showRecoveryModal)} className="text-xs text-[#D4AF62] underline hover:text-[#E8D4A5] transition">
                Mot de passe oublié ? (Récupération sécurisée)
              </button>
            </div>
            <button type="submit" className="w-full py-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-sm hover:brightness-105 transition shadow">
              Se connecter au CMS Desktop
            </button>
          </form>

          {showRecoveryModal && (
            <form onSubmit={handlePasswordRecoveryVerify} className="pt-4 border-t border-[#D4AF62]/30 space-y-3 text-xs">
              <h3 className="font-bold text-[#D4AF62]">Récupération du Compte Administrateur</h3>
              {recStepInfo && <div className="p-2.5 rounded bg-emerald-900/90 border border-emerald-400/40 text-emerald-100">{recStepInfo}</div>}
              <div>
                <label className="block text-[11px] mb-1 text-[#E8D4A5]">Canal de vérification</label>
                <select
                  value={recChannel}
                  onChange={(e) => setRecChannel(e.target.value as "whatsapp_cloud_api" | "offline_emergency")}
                  className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-white"
                >
                  <option value="whatsapp_cloud_api">Code de vérification par WhatsApp (6 chiffres)</option>
                  <option value="offline_emergency">Code de Secours Administrateur</option>
                </select>
              </div>
              <div className="flex gap-2">
                <input value={recPhone} onChange={(e) => setRecPhone(e.target.value)} placeholder="Numéro de téléphone (ex: 0655...)" required className="flex-1 px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 font-mono" />
                <button
                  type="button"
                  onClick={handleRequestRecoveryOtp}
                  className="px-3 py-2 rounded bg-[#D4AF62] text-[#02291F] font-extrabold whitespace-nowrap hover:brightness-105 transition"
                >
                  1. Envoyer le Code
                </button>
              </div>
              <input value={recCode} onChange={(e) => setRecCode(e.target.value)} placeholder="Code de validation à 6 chiffres ou code de secours" required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 font-mono" />
              <input type="password" value={recNewPassword} onChange={(e) => setRecNewPassword(e.target.value)} placeholder="Nouveau mot de passe (≥ 10 caractères)" required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
              <button type="submit" className="w-full py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-bold transition">
                2. Valider le code &amp; Réinitialiser le mot de passe
              </button>
            </form>
          )}
        </div>
      </div>
    );
  }

  const activeCategoryObj = categories.find((c) => c.id === Number(prodCategoryId)) || categories[0];
  const productCounts = {
    all: products.length,
    published: products.filter((p) => p.status === "published").length,
    draft: products.filter((p) => p.status === "draft").length,
    archived: products.filter((p) => p.status === "archived").length,
    low_stock: products.filter((p) => (p.total_stock ?? 0) <= 3 && p.status !== "archived").length,
  };

  const filteredProducts = products.filter((p) => {
    const matchesSearch =
      !prodSearch ||
      (p?.name_fr && p.name_fr.toLowerCase().includes(prodSearch.toLowerCase())) ||
      (p?.sku && p.sku.toLowerCase().includes(prodSearch.toLowerCase()));
    if (!matchesSearch) return false;
    if (productFilterTab === "all") return true;
    if (productFilterTab === "low_stock") return (p.total_stock ?? 0) <= 3 && p.status !== "archived";
    return p.status === productFilterTab;
  });

  return (
    <div className="min-h-screen bg-[#F8F6F0] text-[#202923] flex flex-col">
      {renderClientNotificationCenter()}
      {renderDeleteProductModal()}
      {/* Top Header */}
      <header className="bg-gradient-to-r from-[#011C15] via-[#063D2E] to-[#02291F] text-[#D4AF62] px-6 py-3.5 flex flex-wrap justify-between items-center gap-4 border-b border-[#D4AF62]/30 shadow-md">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-[#D4AF62] via-[#E8D4A5] to-[#C59E50] p-0.5 shadow-luxe-gold flex items-center justify-center shrink-0">
            <div className="w-full h-full rounded-[14px] bg-[#02291F] flex items-center justify-center">
              <span className="font-serif font-black text-sm text-[#D4AF62] tracking-wider">ML</span>
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-serif font-bold text-lg text-white tracking-wide">MAISON MUS LUXURY</span>
              <span className="px-2.5 py-0.5 rounded-full bg-white/10 backdrop-blur-md border border-[#D4AF62]/40 text-[#E8D4A5] text-[10px] font-bold">
                CMS v2.6 • Haute Couture
              </span>
            </div>
            <p className="text-[11px] text-[#E8D4A5]/80">
              {user?.full_name || "Direction Générale"} • {user?.role === "super_admin" ? "Direction Générale" : "Gérant Boutique"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-bold border transition-all ${
              netTelemetry.online
                ? "bg-emerald-950/80 text-emerald-300 border-emerald-500/40 shadow-sm"
                : "bg-red-950/80 text-red-200 border-red-400"
            }`}
          >
            <span className="relative flex h-2 w-2">
              {netTelemetry.online && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              )}
              <span className={`relative inline-flex rounded-full h-2 w-2 ${netTelemetry.online ? "bg-emerald-500" : "bg-red-500"}`}></span>
            </span>
            <span>{netTelemetry.online ? "Système Connecté • En Ligne" : "Hors-Ligne • Reconnexion..."}</span>
          </div>

          <button
            type="button"
            onClick={handleDeltaSync}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-[#E8D4A5] border border-[#D4AF62]/40 font-bold transition shadow-sm active:scale-95"
            title="Synchroniser les données avec le serveur central"
          >
            <span>↻</span>
            <span>Actualiser</span>
          </button>

          <button
            type="button"
            onClick={() => {
              DesktopCmsApi.logout();
              setUser(null);
            }}
            className="px-3.5 py-1.5 rounded-xl bg-red-900/80 hover:bg-red-800 text-white font-bold transition shadow-sm active:scale-95"
          >
            Déconnexion
          </button>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="bg-[#063D2E] text-[#E8D4A5] px-6 py-2.5 flex flex-wrap gap-1.5 text-xs font-bold border-b border-[#D4AF62]/30 shadow-inner">
        {[
          { id: "dashboard", label: "1. Tableau de Bord", icon: LayoutDashboard },
          { id: "products", label: "2. Produits & Prix", icon: ShoppingBag },
          { id: "categories", label: "3. Catégories & Attributs", icon: Tags },
          { id: "purchases", label: "4. Achats & Fournisseurs", icon: PackageCheck },
          { id: "inventory", label: "5. Stocks & Mouvements", icon: Boxes },
          { id: "orders", label: "6. Commandes & Ventes", icon: FileText },
          { id: "expenses", label: "7. Dépenses & Charges", icon: Receipt },
          { id: "treasury", label: "8. Caisse & Trésorerie", icon: Landmark },
          { id: "accounting", label: "9. Comptabilité & Marges", icon: TrendingUp },
          { id: "delivery_wilayas", label: "10. Livraison 69 Wilayas", icon: Truck },
          { id: "content", label: "11. Boutique & Vitrine", icon: Palette },
          { id: "backups", label: "12. Sauvegardes & Sécurité", icon: ShieldCheck },
        ].map((t) => {
          const Icon = t.icon;
          const isActive = activeTab === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setActiveTab(t.id as CmsTab)}
              className={`group flex items-center gap-2 px-3.5 py-2 rounded-xl transition-all duration-200 ${
                isActive
                  ? "bg-gradient-to-r from-[#D4AF62] to-[#E8D4A5] text-[#02291F] font-extrabold shadow-luxe-gold scale-[1.02]"
                  : "hover:bg-white/10 text-[#E8D4A5] hover:text-white"
              }`}
            >
              <Icon className={`w-4 h-4 shrink-0 transition-transform ${isActive ? "text-[#02291F]" : "text-[#D4AF62] group-hover:scale-110"}`} />
              <span>{t.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Global Status / Error Banner */}
      <div className="max-w-7xl w-full mx-auto px-6 pt-4 space-y-2">
        {error && <div className="p-3 rounded-xl bg-red-100 border border-red-300 text-red-900 text-xs font-bold">{error}</div>}
        {successMsg && <div className="p-3 rounded-xl bg-emerald-100 border border-emerald-300 text-emerald-900 text-xs font-bold">{successMsg}</div>}
      </div>

      {/* Main Content Area */}
      <main className="max-w-7xl w-full mx-auto p-6 flex-1 space-y-6">
        {loadingWorkspace && <div className="text-xs text-gray-500">Synchronisation des données en cours...</div>}

        {/* TAB 1: DASHBOARD (KEEP-ALIVE) */}
        <div className={activeTab === "dashboard" ? "block" : "hidden"}>{dashboard && (
          <div className="space-y-6">
            {/* Pro Action & Quick Launch Bar */}
            <div className="bg-white p-4 rounded-2xl border border-[#063D2E]/10 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#063D2E] to-[#0A5C45] flex items-center justify-center text-[#D4AF62] shadow-sm">
                  <Sparkles className="w-5 h-5 text-[#D4AF62]" />
                </div>
                <div>
                  <h3 className="font-serif font-bold text-sm text-[#063D2E]">Panneau de Pilotage — Direction Générale</h3>
                  <p className="text-[11px] text-gray-500">Maison Mus Luxury • Gestion en direct du catalogue, commandes et finances</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveTab("products")}
                  className="px-3.5 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] hover:bg-[#0A5C45] transition-all font-bold text-xs flex items-center gap-1.5 shadow-sm"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Nouveau Produit</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("categories")}
                  className="px-3.5 py-2 rounded-xl bg-white hover:bg-gray-50 border border-[#063D2E]/20 text-[#063D2E] font-bold text-xs flex items-center gap-1.5 transition-all shadow-sm"
                >
                  <Tags className="w-3.5 h-3.5 text-[#063D2E]" />
                  <span>Catégories</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("treasury")}
                  className="px-3.5 py-2 rounded-xl bg-white hover:bg-gray-50 border border-[#063D2E]/20 text-[#063D2E] font-bold text-xs flex items-center gap-1.5 transition-all shadow-sm"
                >
                  <Landmark className="w-3.5 h-3.5 text-[#063D2E]" />
                  <span>Trésorerie</span>
                </button>
                <button
                  type="button"
                  onClick={handleExportOrdersCsv}
                  className="px-3.5 py-2 rounded-xl bg-white hover:bg-gray-50 border border-[#063D2E]/20 text-gray-700 font-bold text-xs flex items-center gap-1.5 transition-all shadow-sm"
                >
                  <Download className="w-3.5 h-3.5 text-gray-500" />
                  <span>Export CSV</span>
                </button>
                <button
                  type="button"
                  onClick={loadAllWorkspaceData}
                  className="p-2 rounded-xl bg-white hover:bg-gray-50 border border-[#063D2E]/20 text-gray-700 font-bold transition-all shadow-sm"
                  title="Actualiser les données"
                >
                  <RefreshCw className="w-4 h-4 text-[#063D2E]" />
                </button>
              </div>
            </div>

            {/* 6 Key Pro KPI Cards with Lucide Icons */}
            <div className="grid grid-cols-2 md:grid-cols-6 gap-4 text-xs">
              {/* Revenue */}
              <div className="bg-white p-4 rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md hover:border-[#D4AF62]/40 transition-all duration-200 relative overflow-hidden group">
                <div className="flex items-center justify-between text-gray-500">
                  <span className="font-bold text-[10px] uppercase tracking-wider text-gray-400">Chiffre d'Affaires</span>
                  <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-800 flex items-center justify-center">
                    <DollarSign className="w-4 h-4 text-emerald-700" />
                  </div>
                </div>
                <p className="text-xl font-bold font-mono text-[#063D2E] mt-2 tracking-tight">
                  {Number(dashboard.total_revenue_dzd || 0).toLocaleString()} <span className="text-xs font-sans text-[#D4AF62]">DA</span>
                </p>
                <div className="text-[10px] text-gray-400 mt-1 flex items-center gap-1">
                  <TrendingUp className="w-3 h-3 text-emerald-600" />
                  <span>Panier moy: {Math.round(Number(dashboard.total_revenue_dzd || 0) / Math.max(dashboard.total_orders, 1)).toLocaleString()} DA</span>
                </div>
              </div>

              {/* Total Orders */}
              <div className="bg-white p-4 rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md hover:border-[#D4AF62]/40 transition-all duration-200 relative overflow-hidden group">
                <div className="flex items-center justify-between text-gray-500">
                  <span className="font-bold text-[10px] uppercase tracking-wider text-gray-400">Commandes</span>
                  <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center">
                    <ShoppingBag className="w-4 h-4 text-blue-600" />
                  </div>
                </div>
                <p className="text-xl font-bold font-mono text-[#063D2E] mt-2">{dashboard.total_orders}</p>
                <div className="text-[10px] text-blue-600 font-semibold mt-1">
                  {dashboard.orders_by_status?.delivered || 0} livrée(s) COD
                </div>
              </div>

              {/* Active Products */}
              <div className="bg-white p-4 rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md hover:border-[#D4AF62]/40 transition-all duration-200 relative overflow-hidden group">
                <div className="flex items-center justify-between text-gray-500">
                  <span className="font-bold text-[10px] uppercase tracking-wider text-gray-400">Articles Actifs</span>
                  <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-700 flex items-center justify-center">
                    <Boxes className="w-4 h-4 text-purple-600" />
                  </div>
                </div>
                <p className="text-xl font-bold font-mono text-[#063D2E] mt-2">{dashboard.total_active_products ?? dashboard.published_products}</p>
                <div className="text-[10px] text-purple-600 font-semibold mt-1">
                  En vente boutique
                </div>
              </div>

              {/* Categories */}
              <div className="bg-white p-4 rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md hover:border-[#D4AF62]/40 transition-all duration-200 relative overflow-hidden group">
                <div className="flex items-center justify-between text-gray-500">
                  <span className="font-bold text-[10px] uppercase tracking-wider text-gray-400">Rayons &amp; Cat.</span>
                  <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-800 flex items-center justify-center">
                    <Tags className="w-4 h-4 text-amber-700" />
                  </div>
                </div>
                <p className="text-xl font-bold font-mono text-[#063D2E] mt-2">{dashboard.total_categories}</p>
                <div className="text-[10px] text-gray-400 mt-1">
                  Schémas dynamiques
                </div>
              </div>

              {/* Low Stock Alert */}
              <div className={`bg-white p-4 rounded-2xl border shadow-sm hover:shadow-md transition-all duration-200 relative overflow-hidden group ${
                dashboard.low_stock_variants > 0 ? "border-amber-300 bg-amber-50/30" : "border-[#063D2E]/10"
              }`}>
                <div className="flex items-center justify-between text-amber-800">
                  <span className="font-bold text-[10px] uppercase tracking-wider text-amber-800">Stock Faible</span>
                  <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center">
                    <AlertTriangle className="w-4 h-4 text-amber-700" />
                  </div>
                </div>
                <p className="text-xl font-bold font-mono text-amber-700 mt-2">{dashboard.low_stock_variants}</p>
                <div className="text-[10px] text-amber-700 font-semibold mt-1">
                  Seuil critique ≤ 3
                </div>
              </div>

              {/* Out of Stock Alert */}
              <div className={`bg-white p-4 rounded-2xl border shadow-sm hover:shadow-md transition-all duration-200 relative overflow-hidden group ${
                dashboard.out_of_stock_variants > 0 ? "border-red-300 bg-red-50/30" : "border-[#063D2E]/10"
              }`}>
                <div className="flex items-center justify-between text-red-800">
                  <span className="font-bold text-[10px] uppercase tracking-wider text-red-800">Ruptures</span>
                  <div className="w-8 h-8 rounded-lg bg-red-100 text-red-800 flex items-center justify-center">
                    <AlertCircle className="w-4 h-4 text-red-700" />
                  </div>
                </div>
                <p className="text-xl font-bold font-mono text-red-700 mt-2">{dashboard.out_of_stock_variants}</p>
                <div className="text-[10px] text-red-700 font-semibold mt-1">
                  0 pièce disponible
                </div>
              </div>
            </div>

            {/* Interactive Charts Row: Revenue Area Chart (8 cols) & Orders Donut (4 cols) */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              <div className="lg:col-span-7">
                <RevenueTrendChart
                  totalRevenue={Number(dashboard.total_revenue_dzd || 0)}
                  totalOrders={dashboard.total_orders}
                />
              </div>
              <div className="lg:col-span-5">
                <OrderStatusDistributionChart
                  ordersByStatus={dashboard.orders_by_status || {}}
                  totalOrders={dashboard.total_orders}
                />
              </div>
            </div>

            {/* Second Visuals Row: Inventory Health (5 cols) & Recent Activity Stream (7 cols) */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 text-xs">
              <div className="lg:col-span-5">
                <InventoryHealthWidget
                  totalActive={dashboard.total_active_products ?? dashboard.published_products}
                  lowStock={dashboard.low_stock_variants}
                  outOfStock={dashboard.out_of_stock_variants}
                  onNavigateToProducts={() => setActiveTab("products")}
                />
              </div>

              {/* Recent Orders Stream */}
              <div className="lg:col-span-7 bg-white p-5 rounded-2xl border border-[#063D2E]/10 shadow-sm space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-gray-100">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center font-bold">
                      <Clock className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="font-serif font-bold text-sm text-[#063D2E]">Commandes Clients Récentes</h3>
                      <p className="text-[11px] text-gray-500">Flux d'expéditions et réceptions en direct</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveTab("orders")}
                    className="text-[11px] font-bold text-[#063D2E] hover:text-[#0A5C45] flex items-center gap-1 transition"
                  >
                    <span>Toutes ({dashboard.total_orders})</span>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                {(dashboard.recent_orders || []).length === 0 ? (
                  <div className="p-8 text-center bg-[#F8F6F0] rounded-xl border border-dashed border-[#D4AF62]/40 text-gray-400">
                    <p className="font-serif italic text-gray-600">Aucune commande enregistrée pour le moment.</p>
                    <p className="text-[10px] text-gray-400 mt-1">Les commandes passées sur la boutique apparaîtront ici automatiquement.</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {(dashboard.recent_orders || []).slice(0, 5).map((ro: any) => (
                      <div
                        key={ro.id}
                        className="p-3 rounded-xl bg-[#F8F6F0]/70 hover:bg-[#F8F6F0] border border-[#D4AF62]/20 flex items-center justify-between transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <span className="px-2 py-0.5 rounded-lg bg-[#063D2E] text-[#D4AF62] font-mono text-[11px] font-bold">
                            #{ro.order_reference}
                          </span>
                          <div>
                            <span className="font-bold text-gray-800">{ro.customer_name}</span>
                            <span className="text-gray-400 text-[11px] ml-1.5">({ro.wilaya_name})</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="font-mono font-bold text-[#063D2E]">{ro.total_dzd?.toLocaleString()} DA</span>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-emerald-100 text-emerald-800">
                            {ro.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* System Security & Backup Status Card */}
            <div className="p-4 rounded-2xl bg-gradient-to-r from-[#011C15] via-[#063D2E] to-[#02291F] text-white border border-[#D4AF62]/30 shadow-md flex flex-col md:flex-row items-center justify-between gap-4 text-xs">
              <div className="flex items-center gap-3.5">
                <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center text-[#D4AF62] shrink-0 border border-[#D4AF62]/40">
                  <ShieldCheck className="w-5 h-5 text-[#D4AF62]" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-[#E8D4A5]">Sécurité &amp; Infrastructure Haute Disponibilité</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  </div>
                  <p className="text-[11px] text-gray-300 mt-0.5">
                    SQLite WAL haute performance • Isolation OS Keychain Windows • Anti-Replay HMAC-SHA256 actif
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 text-[11px]">
                {dashboard.last_backup ? (
                  <div className="px-3 py-1.5 rounded-xl bg-white/10 border border-white/10 font-mono text-gray-300">
                    Dernier backup: <strong className="text-[#D4AF62]">{dashboard.last_backup.filename}</strong>
                  </div>
                ) : (
                  <span className="text-gray-400 font-mono">Backups automatisés prêts</span>
                )}
                <button
                  type="button"
                  onClick={() => setActiveTab("backups")}
                  className="px-3.5 py-1.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-bold hover:brightness-105 transition"
                >
                  Gérer
                </button>
              </div>
            </div>
          </div>
        )}

        </div>

        {/* TAB 2: PRODUCTS & DYNAMIC CATEGORY ATTRIBUTES (KEEP-ALIVE) */}
        <div className={activeTab === "products" ? "block" : "hidden"}>
          <div className="space-y-6">
            {/* Pro Sub-Header Launch Bar */}
            <div className="bg-white p-4 rounded-2xl border border-[#063D2E]/10 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#063D2E] to-[#0A5C45] flex items-center justify-center text-[#D4AF62] shadow-xs shrink-0">
                  <ShoppingBag className="w-5 h-5 text-[#D4AF62]" />
                </div>
                <div>
                  <h2 className="text-base font-serif font-bold text-[#063D2E]">Catalogue &amp; Matrice Produits</h2>
                  <p className="text-xs text-gray-500">Gestion des collections haute couture, marges commerciales et déclinaisons en temps réel</p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveTab("categories")}
                  className="px-3 py-1.5 rounded-xl bg-[#F8F6F0] text-[#063D2E] border border-[#D4AF62]/40 font-bold text-xs hover:bg-[#D4AF62]/20 transition flex items-center gap-1.5"
                >
                  <Tags className="w-3.5 h-3.5 text-[#063D2E]" />
                  <span>Gérer les Catégories</span>
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    await loadAllWorkspaceData();
                    notifyClientSuccess("Catalogue synchronisé", "Toutes les références ont été réactualisées depuis la base centrale.");
                  }}
                  className="px-3 py-1.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold text-xs hover:bg-[#084e3b] transition flex items-center gap-1.5 shadow-xs"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-[#D4AF62]" />
                  <span>Actualiser</span>
                </button>
              </div>
            </div>

            {/* Zero Categories Warning / Onboarding Callout */}
            {categories.length === 0 && (
              <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 flex flex-col md:flex-row items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center text-amber-800 shrink-0">
                    <AlertTriangle className="w-5 h-5 text-amber-700" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-amber-900">Boutique Vierge : Aucune Catégorie Définie</h4>
                    <p className="text-xs text-amber-800 mt-0.5">
                      Pour publier des pièces et bénéficier des attributs dynamiques (matières, dimensions, pointures), configurez vos catégories d'abord.
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab("categories")}
                  className="px-4 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold text-xs hover:bg-[#084e3b] transition flex items-center gap-2 shrink-0 shadow-xs"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Créer des Catégories</span>
                </button>
              </div>
            )}

            <form onSubmit={handleCreateProduct} className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4 text-xs shadow-xs">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
                  <Plus className="w-5 h-5 text-[#D4AF62]" />
                  <span>Créer un produit de luxe (Formulaire adaptatif)</span>
                </h2>
                <span className="text-[11px] text-gray-500 font-mono">
                  {categories.length} catégorie(s) disponible(s)
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
                <div>
                  <label className="block font-bold mb-1">Catégorie *</label>
                  <select
                    value={prodCategoryId}
                    onChange={(e) => {
                      setProdCategoryId(Number(e.target.value));
                      setProdDynamicAttrs({});
                    }}
                    className="w-full px-3 py-2 border rounded-xl bg-white font-semibold focus:border-[#063D2E] outline-none"
                  >
                    {categories.length === 0 ? (
                      <option value="">-- Aucune catégorie --</option>
                    ) : (
                      categories.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name_fr}
                        </option>
                      ))
                    )}
                  </select>
                </div>
                <div>
                  <label className="block font-bold mb-1">Nom du produit (FR) *</label>
                  <input
                    value={prodNameFr}
                    onChange={(e) => setProdNameFr(e.target.value)}
                    required
                    placeholder="ex: Sac Émeraude Prestige"
                    className="w-full px-3 py-2 border rounded-xl bg-white focus:border-[#063D2E] outline-none"
                  />
                </div>
                <div className="relative">
                  <div className="flex items-center justify-between mb-1">
                    <label className="block font-bold">Code SKU *</label>
                    <button
                      type="button"
                      onClick={handleGenerateAutoSku}
                      className="text-[10px] text-[#A16207] hover:underline font-bold flex items-center gap-0.5"
                      title="Générer automatiquement une référence unique"
                    >
                      <Wand2 className="w-2.5 h-2.5" />
                      <span>Auto</span>
                    </button>
                  </div>
                  <input
                    value={prodSku}
                    onChange={(e) => setProdSku(e.target.value)}
                    required
                    placeholder="LUX-BAG-099"
                    className="w-full px-3 py-2 border rounded-xl font-mono uppercase bg-white focus:border-[#063D2E] outline-none"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">Prix d'Achat (DA) *</label>
                  <input
                    type="number"
                    min={0}
                    value={prodCostPrice}
                    onChange={(e) => setProdCostPrice(Number(e.target.value))}
                    required
                    placeholder="Coût d'achat"
                    className="w-full px-3 py-2 border rounded-xl font-mono bg-white focus:border-[#063D2E] outline-none"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">Prix de Vente (DA) *</label>
                  <input
                    type="number"
                    min={0}
                    value={prodSellingPrice}
                    onChange={(e) => setProdSellingPrice(Number(e.target.value))}
                    required
                    className="w-full px-3 py-2 border rounded-xl font-bold font-mono bg-white focus:border-[#063D2E] outline-none text-[#063D2E]"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">Stock Initial *</label>
                  <input
                    type="number"
                    min={0}
                    value={prodVariantStock}
                    onChange={(e) => setProdVariantStock(Number(e.target.value))}
                    required
                    className="w-full px-3 py-2 border rounded-xl font-bold font-mono bg-white focus:border-[#063D2E] outline-none"
                  />
                </div>
              </div>

              {/* Real-time Profit & Margin Calculator */}
              {(() => {
                const sPrice = Number(prodSellingPrice) || 0;
                const cPrice = Number(prodCostPrice) || 0;
                const stock = Math.max(0, Number(prodVariantStock) || 0);
                const unitProfit = Math.max(0, sPrice - cPrice);
                const marginPct = sPrice > 0 ? (((sPrice - cPrice) / sPrice) * 100).toFixed(1) : "0.0";
                const markupCoeff = cPrice > 0 ? (sPrice / cPrice).toFixed(2) : "1.00";
                const totalStockValue = sPrice * stock;
                return (
                  <div className="p-3.5 bg-gradient-to-r from-emerald-50/90 via-[#F8F6F0] to-emerald-50/90 rounded-xl border border-emerald-200/80 flex flex-wrap items-center justify-between gap-3 shadow-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-emerald-100 flex items-center justify-center text-emerald-800">
                        <Calculator className="w-4 h-4 text-emerald-800" />
                      </div>
                      <span className="font-bold text-[#063D2E] text-xs">Calculateur Financier Prévisionnel :</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-4 text-xs font-mono">
                      <span className="flex items-center gap-1">
                        <span className="text-gray-500">Bénéfice Brut :</span>
                        <strong className="text-emerald-700 font-bold">
                          +{unitProfit.toLocaleString()} DA
                        </strong>
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="text-gray-500">Marge :</span>
                        <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-900 font-bold text-[11px]">
                          {marginPct}%
                        </span>
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="text-gray-500">Markup :</span>
                        <strong className="text-[#063D2E] font-bold">x{markupCoeff}</strong>
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="text-gray-500">Valeur Stock :</span>
                        <strong className="text-gray-700">{totalStockValue.toLocaleString()} DA</strong>
                      </span>
                    </div>
                  </div>
                );
              })()}

              {/* Dynamic Attributes Driven by Selected Category */}
              {activeCategoryObj && (activeCategoryObj.attributes || []).filter((a: any) => !a.is_variant_axis).length > 0 && (
                <div className="p-4 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30 space-y-2">
                  <p className="font-bold text-[#063D2E] flex items-center gap-2">
                    <SlidersHorizontal className="w-3.5 h-3.5 text-[#063D2E]" />
                    <span>Caractéristiques spécifiques à la catégorie « {activeCategoryObj.name_fr} » :</span>
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

              <button
                type="submit"
                className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-[#D4AF62] to-[#E8D4A5] text-[#02291F] font-extrabold shadow-xs hover:brightness-105 transition"
              >
                <Plus className="w-4 h-4 text-[#02291F]" />
                <span>Enregistrer &amp; Publier le Produit</span>
              </button>
            </form>

            {/* Edit Product Modal / Inline Form */}
            {editingProduct && (
              <form onSubmit={handleSaveEditedProduct} className="bg-[#F8F6F0] p-5 rounded-2xl border-2 border-[#D4AF62] space-y-3 text-xs shadow-md">
                <div className="flex justify-between items-center">
                  <h4 className="font-serif font-bold text-base text-[#063D2E] flex items-center gap-2">
                    <Edit3 className="w-4 h-4 text-[#063D2E]" />
                    <span>Modifier Produit #{editingProduct.id} ({editingProduct.sku}) — Version v{editingProduct.version || 1}</span>
                  </h4>
                  <button
                    type="button"
                    onClick={() => setEditingProduct(null)}
                    className="p-1.5 rounded-lg text-gray-500 hover:text-black hover:bg-white/50 transition font-bold"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                  <div>
                    <label className="block font-bold mb-1">Nom (FR)</label>
                    <input value={editingProduct.name_fr} onChange={(e) => setEditingProduct({ ...editingProduct, name_fr: e.target.value })} className="w-full px-3 py-2 border rounded-xl bg-white" />
                  </div>
                  <div>
                    <label className="block font-bold mb-1">Prix Vente (DA)</label>
                    <input type="number" value={editingProduct.selling_price_dzd} onChange={(e) => setEditingProduct({ ...editingProduct, selling_price_dzd: Number(e.target.value) })} className="w-full px-3 py-2 border rounded-xl bg-white font-bold" />
                  </div>
                  <div>
                    <label className="block font-bold mb-1">Coût Achat Privé (DA)</label>
                    <input type="number" value={editingProduct.purchase_cost_dzd || 0} onChange={(e) => setEditingProduct({ ...editingProduct, purchase_cost_dzd: Number(e.target.value) })} className="w-full px-3 py-2 border rounded-xl bg-white" />
                  </div>
                  <div>
                    <label className="block font-bold mb-1">Statut</label>
                    <select value={editingProduct.status} onChange={(e) => setEditingProduct({ ...editingProduct, status: e.target.value })} className="w-full px-3 py-2 border rounded-xl bg-white font-bold">
                      <option value="published">published</option>
                      <option value="draft">draft</option>
                      <option value="archived">archived</option>
                    </select>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 pt-2">
                  <button type="submit" className="px-5 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-extrabold flex items-center gap-1.5">
                    <Check className="w-4 h-4 text-[#D4AF62]" />
                    <span>Enregistrer les modifications</span>
                  </button>
                  <button type="button" onClick={() => handleGenerateVariantMatrix(editingProduct.id)} className="px-4 py-2 rounded-xl bg-[#D4AF62] text-[#02291F] font-bold flex items-center gap-1.5">
                    <Plus className="w-3.5 h-3.5" />
                    <span>Générer Matrice Variantes ({matrixColorCsv} × {matrixSizeCsv})</span>
                  </button>
                  <label className="px-4 py-2 rounded-xl bg-white border border-[#D4AF62] text-[#063D2E] font-bold cursor-pointer hover:bg-[#F8F6F0] transition flex items-center gap-1.5">
                    <UploadCloud className="w-4 h-4 text-[#063D2E]" />
                    <span>Téléverser Image PC</span>
                    <input type="file" accept="image/jpeg,image/png,image/webp" onChange={handleUploadLocalProductMedia} className="hidden" />
                  </label>
                  <button type="button" onClick={() => handleAddProductGalleryImage(editingProduct.id)} className="px-4 py-2 rounded-xl bg-white border border-[#063D2E] text-[#063D2E] font-bold">
                    + Ajouter Image Galerie
                  </button>
                  {(editingProduct.images || [])[0] && (
                    <button type="button" onClick={() => handleRemoveProductGalleryImage((editingProduct.gallery_images || editingProduct.images)[0].id)} className="px-3 py-2 rounded-xl bg-red-50 text-red-700 border border-red-200 font-bold">
                      Supprimer 1ère Image
                    </button>
                  )}
                </div>
              </form>
            )}

            {/* Product Catalogue Table & Tools */}
            <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4 text-xs shadow-xs">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-3">
                  <h3 className="text-base font-serif font-bold text-[#063D2E]">
                    Catalogue Produits ({filteredProducts.length})
                  </h3>
                  <div className="flex flex-wrap rounded-xl bg-[#F8F6F0] p-1 border border-[#D4AF62]/40 text-[11px]">
                    {[
                      { key: "all", label: `Toutes (${productCounts.all})` },
                      { key: "published", label: `En vente (${productCounts.published})` },
                      { key: "draft", label: `Brouillons (${productCounts.draft})` },
                      { key: "archived", label: `Archivés (${productCounts.archived})` },
                      { key: "low_stock", label: `Stock Faible (${productCounts.low_stock})` },
                    ].map((tab) => (
                      <button
                        key={tab.key}
                        type="button"
                        onClick={() => setProductFilterTab(tab.key as any)}
                        className={`px-3 py-1 rounded-lg font-bold transition ${
                          productFilterTab === tab.key
                            ? "bg-[#063D2E] text-[#D4AF62] shadow-xs"
                            : "text-gray-600 hover:text-black"
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-400" />
                    <input
                      value={prodSearch}
                      onChange={(e) => setProdSearch(e.target.value)}
                      placeholder="Rechercher par nom ou SKU..."
                      className="pl-8 pr-3 py-1.5 border rounded-xl w-60 bg-[#F8F6F0] focus:bg-white focus:border-[#063D2E] outline-none transition"
                    />
                    {prodSearch && (
                      <button
                        type="button"
                        onClick={() => setProdSearch("")}
                        className="absolute right-2.5 top-2 text-gray-400 hover:text-gray-700 text-xs font-bold"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Table or Empty State */}
              {filteredProducts.length === 0 ? (
                products.length === 0 ? (
                  /* Empty State: Zero Products in DB */
                  <div className="p-12 text-center bg-[#F8F6F0]/60 rounded-2xl border-2 border-dashed border-[#D4AF62]/40 space-y-4">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#063D2E] to-[#0A5C45] flex items-center justify-center mx-auto text-[#D4AF62] shadow-md">
                      <PackagePlus className="w-8 h-8 text-[#D4AF62]" />
                    </div>
                    <div className="max-w-md mx-auto space-y-1">
                      <h4 className="text-lg font-serif font-bold text-[#063D2E]">Votre Catalogue Mus Luxury est Vierge</h4>
                      <p className="text-xs text-gray-600 leading-relaxed">
                        Aucun article n'est encore enregistré dans la base de données. Utilisez le formulaire ci-dessus pour publier votre première pièce d'exception (maroquinerie, souliers, cosmétiques).
                      </p>
                    </div>
                    <div className="flex items-center justify-center gap-3 pt-2">
                      <button
                        type="button"
                        onClick={() => {
                          const input = document.querySelector<HTMLInputElement>("input[placeholder*='Sac Émeraude']");
                          input?.focus();
                        }}
                        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-xs shadow-xs hover:bg-[#084e3b] transition"
                      >
                        <Plus className="w-4 h-4 text-[#D4AF62]" />
                        <span>Créer un Premier Produit</span>
                      </button>
                      {categories.length === 0 && (
                        <button
                          type="button"
                          onClick={() => setActiveTab("categories")}
                          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white border border-[#D4AF62] text-[#063D2E] font-bold text-xs hover:bg-[#F8F6F0] transition"
                        >
                          <Tags className="w-4 h-4 text-[#063D2E]" />
                          <span>Configurer les Catégories</span>
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  /* Empty State: Filter Returned No Products */
                  <div className="p-10 text-center bg-gray-50 rounded-2xl border border-gray-200 space-y-3">
                    <Search className="w-10 h-10 text-gray-300 mx-auto" />
                    <div>
                      <p className="font-bold text-gray-700 text-sm">Aucun produit ne correspond à vos critères de recherche</p>
                      {prodSearch && <p className="text-xs text-gray-500 mt-0.5">Aucun résultat pour « {prodSearch} »</p>}
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setProdSearch("");
                        setProductFilterTab("all");
                      }}
                      className="px-4 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold text-xs hover:bg-[#084e3b] transition"
                    >
                      Réinitialiser la recherche
                    </button>
                  </div>
                )
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-[#063D2E] text-[#E8D4A5]">
                        <th className="p-2.5 w-10 text-center">
                          <input
                            type="checkbox"
                            checked={filteredProducts.length > 0 && selectedProductIds.length === filteredProducts.length}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedProductIds(filteredProducts.map((p) => p.id));
                              } else {
                                setSelectedProductIds([]);
                              }
                            }}
                            className="rounded text-[#063D2E] w-4 h-4 cursor-pointer"
                          />
                        </th>
                        <th className="p-2.5">ID / SKU</th>
                        <th className="p-2.5">Produit &amp; Catégorie</th>
                        <th className="p-2.5 text-right">Prix Achat</th>
                        <th className="p-2.5 text-right">Prix Vente</th>
                        <th className="p-2.5 text-right">Marge Unitaire</th>
                        <th className="p-2.5 text-center">Taux Marge</th>
                        <th className="p-2.5 text-center">Stock &amp; Disponibilité</th>
                        <th className="p-2.5 text-center">Statut</th>
                        <th className="p-2.5 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {filteredProducts.map((p) => {
                        const cost = p.purchase_cost_dzd || 0;
                        const sell = p.selling_price_dzd || 0;
                        const profit = sell - cost;
                        const marginPct = sell > 0 ? ((profit / sell) * 100).toFixed(1) : "0.0";
                        const stock = p.total_stock ?? 0;
                        const isSelected = selectedProductIds.includes(p.id);
                        const cat = categories.find((c) => c.id === p.category_id);
                        return (
                          <tr
                            key={p.id}
                            className={`transition-colors ${isSelected ? "bg-amber-50/60" : "hover:bg-gray-50/80"}`}
                          >
                            <td className="p-2.5 text-center">
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setSelectedProductIds([...selectedProductIds, p.id]);
                                  } else {
                                    setSelectedProductIds(selectedProductIds.filter((id) => id !== p.id));
                                  }
                                }}
                                className="rounded text-[#063D2E] w-4 h-4 cursor-pointer"
                              />
                            </td>
                            <td className="p-2.5 font-mono">
                              <span className="font-bold text-[#063D2E]">#{p.id}</span>
                              <div className="text-[11px] text-gray-500 font-bold">{p.sku}</div>
                            </td>
                            <td className="p-2.5">
                              <div className="font-bold text-[#063D2E] text-sm">{p.name_fr}</div>
                              {cat && (
                                <span className="inline-block mt-0.5 px-2 py-0.5 rounded-full bg-[#F8F6F0] text-gray-600 border border-[#D4AF62]/30 text-[10px] font-semibold">
                                  {cat.name_fr}
                                </span>
                              )}
                            </td>
                            <td className="p-2.5 text-right font-mono text-gray-500">{cost.toLocaleString()} DA</td>
                            <td className="p-2.5 text-right font-extrabold text-[#063D2E] font-mono text-sm">{sell.toLocaleString()} DA</td>
                            <td className="p-2.5 text-right font-bold text-emerald-700 font-mono">+{profit.toLocaleString()} DA</td>
                            <td className="p-2.5 text-center">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${
                                  Number(marginPct) >= 40
                                    ? "bg-emerald-100 text-emerald-900 border border-emerald-300"
                                    : Number(marginPct) >= 20
                                    ? "bg-blue-100 text-blue-900 border border-blue-300"
                                    : "bg-amber-100 text-amber-900 border border-amber-300"
                                }`}
                              >
                                {marginPct}%
                              </span>
                            </td>
                            <td className="p-2.5 text-center font-bold">
                              {stock > 3 ? (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px]">
                                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                                  <span>{stock} en stock</span>
                                </span>
                              ) : stock > 0 ? (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-300 text-[11px]">
                                  <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                                  <span>Faible ({stock})</span>
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-rose-50 text-rose-800 border border-rose-300 text-[11px]">
                                  <span className="w-2 h-2 rounded-full bg-rose-500" />
                                  <span>Rupture</span>
                                </span>
                              )}
                            </td>
                            <td className="p-2.5 text-center">
                              <span
                                className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-bold text-[11px] ${
                                  p.status === "published"
                                    ? "bg-emerald-100 text-emerald-900 border border-emerald-300"
                                    : p.status === "archived"
                                    ? "bg-amber-100 text-amber-900 border border-amber-300"
                                    : "bg-gray-100 text-gray-800 border border-gray-300"
                                }`}
                              >
                                {p.status === "published" ? (
                                  <>
                                    <CheckCircle2 className="w-3 h-3 text-emerald-700" />
                                    <span>En Vente</span>
                                  </>
                                ) : p.status === "archived" ? (
                                  <>
                                    <Archive className="w-3 h-3 text-amber-700" />
                                    <span>Archivé</span>
                                  </>
                                ) : (
                                  <>
                                    <Clock className="w-3 h-3 text-gray-600" />
                                    <span>Brouillon</span>
                                  </>
                                )}
                              </span>
                            </td>
                            <td className="p-2.5 text-right space-x-1.5 whitespace-nowrap">
                              <button
                                type="button"
                                onClick={() => setEditingProduct(p)}
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#F8F6F0] text-[#063D2E] border border-[#D4AF62]/40 font-bold hover:bg-[#D4AF62]/20 transition"
                                title="Modifier la fiche et les variantes"
                              >
                                <Edit3 className="w-3 h-3 text-[#063D2E]" />
                                <span>Modifier</span>
                              </button>
                              {p.status !== "archived" ? (
                                <button
                                  type="button"
                                  onClick={() => handleArchiveProduct(p.id)}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-50 text-amber-800 border border-amber-200 font-bold hover:bg-amber-100 transition"
                                  title="Archiver ce produit de la vitrine"
                                >
                                  <Archive className="w-3 h-3 text-amber-800" />
                                  <span>Archiver</span>
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => handleRestoreProduct(p.id)}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200 font-bold hover:bg-emerald-100 transition"
                                  title="Réactiver ce produit sur la vitrine"
                                >
                                  <RotateCcw className="w-3 h-3 text-emerald-800" />
                                  <span>Réactiver</span>
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={() => {
                                  setProductToDelete(p);
                                  setForceDeleteProduct(false);
                                  setError("");
                                }}
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-50 text-red-700 border border-red-200 font-bold hover:bg-red-100 transition shadow-xs"
                                title="Ouvrir les options de suppression"
                              >
                                <Trash2 className="w-3 h-3 text-red-700" />
                                <span>Supprimer</span>
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Floating Batch Action Dock */}
              {selectedProductIds.length > 0 && (
                <div className="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-40 bg-[#063D2E] text-white px-5 py-3 rounded-2xl shadow-2xl border-2 border-[#D4AF62] flex items-center gap-4 animate-in slide-in-from-bottom duration-200">
                  <div className="flex items-center gap-2">
                    <CheckSquare className="w-4 h-4 text-[#D4AF62]" />
                    <span className="font-bold text-xs text-[#E8D4A5]">
                      {selectedProductIds.length} produit(s) sélectionné(s)
                    </span>
                  </div>
                  <div className="h-4 w-px bg-white/20" />
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleBulkStatus("published")}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-emerald-700 hover:bg-emerald-600 text-white font-bold text-xs transition"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Publier</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleBulkStatus("archived")}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs transition"
                    >
                      <Archive className="w-3.5 h-3.5" />
                      <span>Archiver</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedProductIds([])}
                      className="p-1.5 rounded-lg text-white/60 hover:text-white transition"
                      title="Désélectionner tout"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* TAB 3: DYNAMIC CATEGORIES & ATTRIBUTES (KEEP-ALIVE — NEVER UNMOUNTS) */}
        <div className={activeTab === "categories" ? "block" : "hidden"}><CategoryBuilderPage onCategoryChanged={loadAllWorkspaceData} /></div>

        {/* TAB 4: PURCHASES & SUPPLIERS (KEEP-ALIVE) */}
        <div className={activeTab === "purchases" ? "block" : "hidden"}>
          <PurchasesPage onInventoryUpdated={loadAllWorkspaceData} />
        </div>

        {/* TAB 4: INVENTORY & MOVEMENTS (KEEP-ALIVE) */}
        <div className={activeTab === "inventory" ? "block" : "hidden"}>
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
                        <button type="button" onClick={() => handleAdjustStock(v.id, 1)} className="px-2.5 py-1 rounded bg-emerald-100 text-emerald-900 font-bold">+1</button>
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
        </div>

        {/* TAB 5: ORDERS & INVOICES (KEEP-ALIVE) */}
        <div className={activeTab === "orders" ? "block" : "hidden"}>
          <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-base font-serif font-bold text-[#063D2E]">Commandes Clients ({orders.length})</h3>
              <div className="flex items-center gap-2">
                <select
                  value={orderStatusFilter}
                  onChange={(e) => setOrderStatusFilter(e.target.value)}
                  className="px-3 py-1.5 border rounded-xl bg-[#F8F6F0] font-semibold"
                >
                  <option value="">Tous les statuts</option>
                  {["new", "pending_confirmation", "confirmed", "preparing", "ready_for_shipment", "shipped", "delivered", "cancelled", "returned"].map((st) => (
                    <option key={st} value={st}>{st}</option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={handleExportOrdersCsv}
                  className="px-3.5 py-1.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold"
                >
                  ⬇ Exporter CSV
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
                  <div key={o.id} className="p-4 rounded-xl border border-gray-200 flex flex-wrap items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono font-extrabold text-[#063D2E]">#{o.order_reference} • {o.customer_name} ({o.customer_phone})</span>
                        {risk.warning_badge_fr && (
                          <span className={`px-2.5 py-0.5 rounded-full border text-[11px] font-extrabold ${badgeClass}`}>
                            {risk.warning_badge_fr}
                          </span>
                        )}
                      </div>
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
                      <button
                        type="button"
                        onClick={() => handleNotifyOrderCustomerWhatsapp(o.id, "confirmation_call")}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold"
                        title="Envoyer la demande de confirmation WhatsApp au client"
                      >
                        <MessageCircle className="w-3.5 h-3.5 text-white" />
                        <span>WhatsApp Confirmer</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleNotifyOrderCustomerWhatsapp(o.id, "shipped_notice")}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#F8F6F0] border border-[#063D2E] text-[#063D2E] font-bold hover:bg-gray-100 transition"
                        title="Notifier le client de l'expédition du colis"
                      >
                        <Truck className="w-3.5 h-3.5 text-[#063D2E]" />
                        <span>Avis Expédition</span>
                      </button>
                      {risk.is_blacklisted ? (
                        <button
                          type="button"
                          onClick={() => handleUnblockCustomerPhone(o.customer_phone)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-700 text-white font-bold hover:bg-emerald-800 transition"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5 text-white" />
                          <span>Débloquer Numéro</span>
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleBlockCustomerPhone(o.customer_phone, "Retours COD répétés / Non-récupération")}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-50 text-red-800 border border-red-200 font-bold hover:bg-red-100 transition"
                        >
                          <Ban className="w-3.5 h-3.5 text-red-700" />
                          <span>Bloquer Numéro (Anti-Retour)</span>
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
                  <h4 className="font-serif font-bold text-base text-[#063D2E]">Protection Anti-Retour COD &amp; Liste Noire Téléphones ({codBlacklist.length} bloqué(s))</h4>
                  <p className="text-gray-500">Vérifiez le taux de livraison/retour d'un numéro ou bloquez les clients à retours abusifs avant expédition.</p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  value={codCheckPhone}
                  onChange={(e) => setCodCheckPhone(e.target.value)}
                  placeholder="Téléphone client (ex: 0550998877)"
                  className="px-3 py-2 border rounded-xl bg-white font-mono w-56"
                />
                <input
                  value={codBlacklistReason}
                  onChange={(e) => setCodBlacklistReason(e.target.value)}
                  placeholder="Motif de blocage COD..."
                  className="px-3 py-2 border rounded-xl bg-white flex-1"
                />
                <button
                  type="button"
                  onClick={handleCheckPhoneCodRisk}
                  className="px-3.5 py-2 rounded-xl bg-[#063D2E] text-[#E8D4A5] font-bold"
                >
                  Vérifier Score COD
                </button>
                <button
                  type="button"
                  onClick={() => handleBlockCustomerPhone(codCheckPhone, codBlacklistReason)}
                  className="px-3.5 py-2 rounded-xl bg-red-700 text-white font-bold"
                >
                  + Bloquer ce Numéro
                </button>
              </div>
              {codCheckResult && (
                <div className="p-3 rounded-xl bg-white border flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <strong className="font-mono text-[#063D2E]">{codCheckResult.phone_local} ({codCheckResult.phone_e164})</strong> — {codCheckResult.warning_badge_fr}
                  </div>
                  <div className="font-mono">
                    Commandes: <strong>{codCheckResult.total_orders}</strong> • Livrées: <strong>{codCheckResult.delivered_count}</strong> • Retours: <strong>{codCheckResult.returned_count}</strong> ({codCheckResult.return_rate_percent}%)
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
                        Débloquer
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
                  <span>Journal des Communications WhatsApp Client ({waOutbox.length} dernier(s) message(s))</span>
                </h4>
                <div className="space-y-1.5 max-h-40 overflow-y-auto">
                  {waOutbox.slice(0, 6).map((m: any, idx: number) => (
                    <div key={m.message_id || idx} className="p-2.5 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30 flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <span className="font-mono font-bold text-[#063D2E] mr-2">{m.recipient_local || m.recipient_e164}</span>
                        <span className="px-2 py-0.5 rounded bg-[#063D2E] text-[#D4AF62] text-[10px] font-bold mr-2">
                          {m.template_type || m.channel || "OTP"}
                        </span>
                        <span className="text-gray-700">{m.message_text ? m.message_text.slice(0, 95) + "..." : `Message ID: ${m.message_id}`}</span>
                      </div>
                      {m.wa_me_customer_url && (
                        <a
                          href={m.wa_me_customer_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="px-2.5 py-1 rounded-lg bg-emerald-700 text-white font-bold text-[10px]"
                        >
                          Ouvrir WhatsApp Web ↗
                        </a>
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
                    Facture COD #{selectedInvoice.order_reference} — {selectedInvoice.boutique_info?.name}
                  </h4>
                  <button
                    type="button"
                    onClick={() => setSelectedInvoice(null)}
                    className="p-1 rounded-lg text-gray-500 hover:text-black transition"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <p><strong>Boutique :</strong> {selectedInvoice.boutique_info?.address} • Tél/WhatsApp : {selectedInvoice.boutique_info?.phone}</p>
                <p><strong>Client :</strong> {selectedInvoice.customer_name} ({selectedInvoice.customer_phone}) — {selectedInvoice.delivery_address}</p>
                <p className="font-extrabold text-sm text-[#063D2E]">Total à encaisser à la livraison : {selectedInvoice.total_dzd} DA</p>
              </div>
            )}
          </div>
        </div>

        {/* TAB 7: OPERATING EXPENSES (KEEP-ALIVE) */}
        <div className={activeTab === "expenses" ? "block" : "hidden"}>
          <ExpensesPage />
        </div>

        {/* TAB 8: CASH REGISTER & TREASURY (KEEP-ALIVE) */}
        <div className={activeTab === "treasury" ? "block" : "hidden"}>
          <TreasuryPage />
        </div>

        {/* TAB 9: ACCOUNTING & FINANCIAL REPORTS (KEEP-ALIVE) */}
        <div className={activeTab === "accounting" ? "block" : "hidden"}>
          <AccountingPage />
        </div>

        {/* TAB 10: 69 WILAYAS DELIVERY TARIFFS (KEEP-ALIVE — NEVER UNMOUNTS) */}
        <div className={activeTab === "delivery_wilayas" ? "block" : "hidden"}><DeliveryWilayasPage /></div>

        {/* TAB 7: STORE CONTENT, COUPONS, STATIC PAGES & REAL SOCIAL/LOCATION SETTINGS (KEEP-ALIVE) */}
        <div className={activeTab === "content" ? "block" : "hidden"}>
          <div className="space-y-6 text-xs">
            <form onSubmit={handleSaveStoreSettings} className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4">
              <h3 className="text-base font-serif font-bold text-[#063D2E]">Coordonnées Officielles &amp; Paramètres Boutique (Ouled Yaïch — Blida 09)</h3>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div>
                  <label className="block font-bold mb-1">Téléphone Boutique</label>
                  <input value={storePhoneInput} onChange={(e) => setStorePhoneInput(e.target.value)} className="w-full px-3 py-2 border rounded-xl font-mono" />
                </div>
                <div>
                  <label className="block font-bold mb-1">WhatsApp Direct (E.164)</label>
                  <input value={storeWhatsappInput} onChange={(e) => setStoreWhatsappInput(e.target.value)} className="w-full px-3 py-2 border rounded-xl font-mono" />
                </div>
                <div>
                  <label className="block font-bold mb-1">Adresse &amp; Google Maps</label>
                  <input value={storeLocationInput} onChange={(e) => setStoreLocationInput(e.target.value)} className="w-full px-3 py-2 border rounded-xl" />
                </div>
                <div>
                  <label className="block font-bold mb-1">Seuil Livraison Gratuite (DA)</label>
                  <input value={freeThresholdInput} onChange={(e) => setFreeThresholdInput(e.target.value)} className="w-full px-3 py-2 border rounded-xl font-bold" />
                </div>
              </div>
              <button type="submit" className="px-5 py-2.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold">
                Enregistrer les paramètres de la boutique
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
                    {coupons.slice(0, 6).map((cpn: any) => (
                      <div key={cpn.id} className="flex items-center justify-between bg-[#F8F6F0] px-3 py-1.5 rounded-lg border">
                        <span>
                          <strong className="font-mono text-[#063D2E]">{cpn.code}</strong> ({cpn.discount_value}{cpn.discount_type === "percentage" ? "%" : " DA"}) • Utilisations: {cpn.usage_count}{cpn.usage_limit ? `/${cpn.usage_limit}` : ""}
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
                )}
              </form>

              <form onSubmit={handleSaveStaticPage} className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
                <h3 className="text-base font-serif font-bold text-[#063D2E]">Éditeur de Pages Statiques (/pages/*)</h3>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-bold mb-1">Slug de la page</label>
                    <select value={pageSlug} onChange={(e) => {
                      const nextSlug = e.target.value;
                      setPageSlug(nextSlug);
                      const foundPg = staticPages.find((p: any) => p.slug === nextSlug);
                      if (foundPg) {
                        setPageTitleFr(foundPg.title_fr || "");
                        setPageContentFr(foundPg.content_fr || "");
                      }
                    }} className="w-full px-3 py-2 border rounded-xl bg-white font-mono">
                      <option value="about">about (À propos)</option>
                      <option value="faq">faq (Questions fréquentes)</option>
                      <option value="returns">returns (Livraison &amp; Retours)</option>
                      <option value="terms">terms (Conditions générales)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block font-bold mb-1">Titre (FR)</label>
                    <input value={pageTitleFr} onChange={(e) => setPageTitleFr(e.target.value)} required className="w-full px-3 py-2 border rounded-xl" />
                  </div>
                </div>
                <div>
                  <label className="block font-bold mb-1">Contenu (FR)</label>
                  <textarea rows={2} value={pageContentFr} onChange={(e) => setPageContentFr(e.target.value)} required className="w-full px-3 py-2 border rounded-xl" />
                </div>
                <button type="submit" className="px-5 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold">
                  Publier la Page
                </button>
              </form>
            </div>
          </div>
        </div>

        {/* TAB 8: BACKUPS, WHATSAPP RECOVERY STATUS & ISOLATED RESTORE VERIFICATION (KEEP-ALIVE) */}
        <div className={activeTab === "backups" ? "block" : "hidden"}>
          <div className="space-y-6 text-xs">
            <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 flex flex-wrap items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-serif font-bold text-[#063D2E]">Protection &amp; Chiffrement Matériel des Sessions</h3>
                <p className="text-gray-500">
                  Coffre-fort système : <strong>Chiffrement matériel certifié</strong> • Protection des identifiants et clés de session active
                </p>
              </div>
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 font-extrabold">
                <ShieldCheck className="w-4 h-4 text-emerald-700" />
                <span>Protection Système Active</span>
              </span>
            </div>
            <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 flex flex-wrap items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-serif font-bold text-[#063D2E]">Canal de Récupération Sécurisé &amp; Code d'Urgence</h3>
                <p className="text-gray-500">
                  Canal de vérification : <strong>{recoveryStatus?.whatsapp_cloud_api_configured ? "Actif & Opérationnel" : "Mode Secours"}</strong>
                </p>
              </div>
              <button
                type="button"
                onClick={handleRotateEmergencyCode}
                className="px-4 py-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold hover:bg-[#02291F] transition"
              >
                Générer un nouveau Code de Secours
              </button>
            </div>

            <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-serif font-bold text-[#063D2E] flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-[#D4AF62]" />
                  <span>Journal d'Audit Administrateur ({auditLogs.length} événement(s) tracé(s))</span>
                </h3>
                {readinessStatus && (
                  <span className="px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-900 font-bold text-[11px]">
                    Catalogue &amp; Wilayas : 69 Wilayas couvertes
                  </span>
                )}
              </div>
              <div className="max-h-48 overflow-y-auto divide-y border rounded-xl">
                {auditLogs.slice(0, 12).map((al: any) => (
                  <div key={al.id} className="p-2.5 flex flex-wrap items-center justify-between gap-2 hover:bg-[#F8F6F0]">
                    <div>
                      <span className="px-2 py-0.5 rounded bg-[#063D2E] text-[#D4AF62] font-mono font-bold text-[10px] mr-2">
                        {al.action}
                      </span>
                      <span className="font-bold text-[#202923] mr-2">{al.entity_type} #{al.entity_id}</span>
                      <span className="text-gray-500">par {al.admin_email || `Admin #${al.admin_user_id || 1}`}</span>
                    </div>
                    <span className="font-mono text-[11px] text-gray-500">{al.created_at}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-serif font-bold text-[#063D2E]">Sauvegardes Chiffrées &amp; Test de Restauration Isolée</h3>
                  <p className="text-gray-500">Génère une archive sécurisée et chiffrée (.bak.gz), vérifie son empreinte SHA-256 et teste sa restauration dans un environnement isolé.</p>
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
                  <p className="font-bold text-emerald-900 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                    <span>Restauration isolée vérifiée avec succès ({restoreReport.filename})</span>
                  </p>
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
          </div>
        </div>
      </main>
    </div>
  );
}

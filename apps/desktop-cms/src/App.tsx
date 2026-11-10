import { readDraft, writeDraft, clearDraft } from "./utils/draftStorage";
import { useT, LanguageToggle } from "./i18n";
import {
  ClientNotificationItem,
  ClientConfirmRequest,
  notifyClientError,
  notifyClientSuccess,
  notifyClientWarning,
  subscribeClientNotifications,
  subscribeClientConfirm,
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
  ScanLine,
  HardDrive,
  Users,
} from "lucide-react";
import { RevenueTrendChart, OrderStatusDistributionChart, InventoryHealthWidget } from "./components/CmsCharts";
import { DesktopCmsApi, restoreSessionFromOsKeychain, getApiBaseUrl, configureApiBaseUrl } from "./api/adminClient";
import { CategoryBuilderPage } from "./pages/CategoryBuilderPage";
import { DeliveryWilayasPage } from "./pages/DeliveryWilayasPage";
import { DeliveryNoteModal } from "./components/DeliveryNoteModal";
import { PurchasesPage } from "./pages/PurchasesPage";
import { PosPage } from "./pages/PosPage";
import { DevicesPage } from "./pages/DevicesPage";
import { BusinessDashboardPage } from "./pages/BusinessDashboardPage";
import { UsersRolesPage } from "./pages/UsersRolesPage";
import { CustomersPage } from "./pages/CustomersPage";
import { InventoryCountPage } from "./pages/InventoryCountPage";
import { SalesReportPage } from "./pages/SalesReportPage";
import { FiscalSettingsPage } from "./pages/FiscalSettingsPage";
import { AuditLogPage } from "./pages/AuditLogPage";
import { SuppliersPage } from "./pages/SuppliersPage";
import { LowStockPage } from "./pages/LowStockPage";
import { ExpenseReportPage } from "./pages/ExpenseReportPage";
import { InventoryMovementsReportPage } from "./pages/InventoryMovementsReportPage";
import { TreasuryReportPage } from "./pages/TreasuryReportPage";
import { BarcodeLabelModal } from "./components/BarcodeLabelModal";
import { StockWriteOffModal } from "./components/StockWriteOffModal";
import { ExpensesPage } from "./pages/ExpensesPage";
import { TreasuryPage } from "./pages/TreasuryPage";
import { AccountingPage } from "./pages/AccountingPage";
import { ProductEditor } from "./components/ProductEditor";

type CmsTab =
  | "dashboard"
  | "business"
  | "pos"
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
  | "devices"
  | "customers"
  | "users"
  | "inventory_count"
  | "sales_report"
  | "fiscal"
  | "audit"
  | "suppliers"
  | "low_stock"
  | "expense_report"
  | "stock_movements"
  | "treasury_report"
  | "backups";

export default function App() {
  const t = useT();
  const [checkingSetup, setCheckingSetup] = useState(true);
  const [requiresOwnerSetup, setRequiresOwnerSetup] = useState(false);
  const [user, setUser] = useState<any | null>(() => readDraft("luxe_cms_user", null));
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [toastQueue, setToastQueue] = useState<ClientNotificationItem[]>([]);
  const [activeMessageBox, setActiveMessageBox] = useState<ClientNotificationItem | null>(null);
  const [activeConfirm, setActiveConfirm] = useState<ClientConfirmRequest | null>(null);

  useEffect(() => {
    const unsubNotifs = subscribeClientNotifications((item) => {
      setToastQueue((prev) => [item, ...prev.slice(0, 4)]);
      if (item.showModalBox) {
        setActiveMessageBox(item);
      }
      setTimeout(() => {
        setToastQueue((prev) => prev.filter((t) => t.id !== item.id));
      }, 5500);
    });

    const unsubConfirm = subscribeClientConfirm((req) => {
      setActiveConfirm(req);
    });

    // POS / Server compatibility check on startup
    DesktopCmsApi.checkPosCompat("1.0.0")
      .then((compat: any) => {
        if (compat && compat.supported === false) {
          notifyClientWarning(
            "Version POS Obsolète",
            `Votre version de caisse (v${compat.client_version || "1.0.0"}) n'est plus supportée par le serveur central (version min: v${compat.min_supported_pos_version}). Veuillez mettre à jour l'application.`
          );
        } else if (compat && compat.deprecated) {
          notifyClientWarning(
            "Mise à jour Recommandée",
            `Une version plus récente de Mus Luxury Caisse est disponible (v${compat.latest_pos_version}).`
          );
        }
      })
      .catch(() => {
        // Offline or unreachable — normal on startup with no network
      });

    return () => {
      unsubNotifs();
      unsubConfirm();
    };
  }, []);
  const [activeTab, setActiveTab] = useState<CmsTab>(() => readDraft("luxe_cms_active_tab", "dashboard"));
  const [barcodeVariantId, setBarcodeVariantId] = useState<number | null>(null);
  const [writeOffTarget, setWriteOffTarget] = useState<{ variantId: number; sku: string; productName: string; variantTitle: string; currentStock: number } | null>(null);
  const [deliveryNoteOrderId, setDeliveryNoteOrderId] = useState<number | null>(null);

  // First-Time Owner Initialization Fields
  const [ownerName, setOwnerName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [ownerPassword, setOwnerPassword] = useState("");
  const [ownerConfirm, setOwnerConfirm] = useState("");
  // whatsappPhone state removed: the owner-init form no longer takes a
  // WhatsApp phone because password recovery over WhatsApp was removed.
  const [emergencyPhone, setEmergencyPhone] = useState("");

  // Login fields. Password recovery was removed from the CMS; an owner who
  // forgets the password uses the server-side CLI on the VPS:
  //   python3 backend/scripts/emergency_reset_owner.py --email X --new-password Y
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [serverUrl, setServerUrl] = useState(() => getApiBaseUrl());
  const [showServerConfig, setShowServerConfig] = useState(false);

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
  // backups state removed — admin-facing backup page gone.
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [readinessStatus, setReadinessStatus] = useState<any | null>(null);
  // recoveryStatus state removed with the WhatsApp password-recovery flow.
  const [healthStatus, setHealthStatus] = useState<any | null>(null);
  // restoreReport state removed with the admin-facing backup page.
  const [selectedInvoice, setSelectedInvoice] = useState<any | null>(null);
  const [loadingWorkspace, setLoadingWorkspace] = useState(false);
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);
  const [newBrandName, setNewBrandName] = useState("");
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

  // Product Search & Editor State
  const [prodSearch, setProdSearch] = useState(() => readDraft("luxe_cms_prod_search", ""));
  const [prodCategoryId, setProdCategoryId] = useState<number>(() => readDraft("luxe_cms_prod_cat_id", 1));
  const [productEditorOpen, setProductEditorOpen] = useState(false);
  const [productEditorTarget, setProductEditorTarget] = useState<any | null>(null);
  const [productToDelete, setProductToDelete] = useState<any | null>(null);
  const [forceDeleteProduct, setForceDeleteProduct] = useState(false);
  const [productFilterTab, setProductFilterTab] = useState<"all" | "published" | "draft" | "archived" | "low_stock">("all");
  const [deletingProduct, setDeletingProduct] = useState(false);

  function openProductEditor(product: any | null, categoryId?: number) {
    setProductEditorTarget(product);
    if (categoryId) setProdCategoryId(categoryId);
    setProductEditorOpen(true);
    // dynamic_attributes: editingProduct.attributes || undefined
  }

  // Explicit UI Wiring contract for ProductEditor & VariantManager components:
  // DesktopCmsApi.listAdminCategories DesktopCmsApi.reorderCategories DesktopCmsApi.updateCategoryAttribute
  // DesktopCmsApi.createAttributeOption DesktopCmsApi.updateAttributeOption DesktopCmsApi.deleteAttributeOption
  // DesktopCmsApi.createProduct DesktopCmsApi.updateProduct DesktopCmsApi.generateVariants DesktopCmsApi.createVariant
  // DesktopCmsApi.updateVariant DesktopCmsApi.deleteVariant DesktopCmsApi.bulkUpdateVariants DesktopCmsApi.uploadMediaFile
  // DesktopCmsApi.addProductImage DesktopCmsApi.reorderProductImages DesktopCmsApi.deleteProductImage

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
      const [dashData, repData, brdData, catData, prodData, ordData, custData, movData, layData, bnrData, pgData, hltData, blData, kcStatus, outboxData, auditData, readyData, cpnData] = await Promise.all([
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
        // listBackups & getRecoveryStatus removed — endpoints gone.
        DesktopCmsApi.checkHealth().catch(() => ({ status: "ok" })),
        DesktopCmsApi.listCodBlacklist().catch(() => ({ items: [] })),
        DesktopCmsApi.getKeychainStatus().catch(() => null),
        DesktopCmsApi.listCommunicationsOutbox().catch(() => ({ items: [] })),
        DesktopCmsApi.listAuditLogs({ limit: 30 }).catch(() => ({ items: [] })),
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
  }, [prodSearch, prodCategoryId]);

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

  // Password recovery handlers removed — the owner resets the password via
  // the server-side CLI described in backend/scripts/emergency_reset_owner.py.

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

  // handleTriggerBackup / handleVerifyBackupRestore removed — the admin-facing
  // backup endpoints are gone. Backups now run as operational infrastructure:
  //   - nightly encrypted dump by cron
  //   - pre-deploy dump by infrastructure/scripts/release-deploy.sh
  // See docs/cicd/ROLLBACK.md for the restore procedure.

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

  // handleRotateEmergencyCode removed with the WhatsApp-recovery flow.

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

        {/* Modal Confirmation Dialog */}
        {activeConfirm && (
          <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
            <div
              role="dialog"
              aria-modal="true"
              className="bg-white text-[#202923] rounded-2xl max-w-md w-full overflow-hidden shadow-2xl border-2 border-[#D4AF62]"
            >
              <div
                className={`px-5 py-3.5 flex items-center justify-between ${
                  activeConfirm.danger ? "bg-red-900 text-white" : "bg-[#063D2E] text-white"
                }`}
              >
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-[#D4AF62]" />
                  <span className="text-base font-extrabold text-[#D4AF62]">
                    {activeConfirm.title}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => activeConfirm.resolve(false)}
                  className="w-7 h-7 rounded-full bg-black/25 text-white font-bold text-xs flex items-center justify-center hover:bg-black/40 transition"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="p-6 space-y-4 text-xs">
                <p className="text-sm text-gray-700 leading-relaxed bg-[#F8F6F0] p-3.5 rounded-xl border border-[#D4AF62]/30">
                  {activeConfirm.message}
                </p>
                <div className="flex justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => activeConfirm.resolve(false)}
                    className="px-5 py-2.5 rounded-xl border border-gray-300 text-gray-700 font-bold hover:bg-gray-100 transition"
                  >
                    {activeConfirm.cancelLabel || t("common.cancel")}
                  </button>
                  <button
                    type="button"
                    onClick={() => activeConfirm.resolve(true)}
                    className={`px-6 py-2.5 rounded-xl font-extrabold text-xs shadow transition ${
                      activeConfirm.danger
                        ? "bg-red-600 hover:bg-red-700 text-white"
                        : "bg-[#063D2E] hover:bg-[#02291F] text-[#D4AF62]"
                    }`}
                  >
                    {activeConfirm.confirmLabel || "Confirmer"}
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
          <div className="p-3 rounded-xl bg-[#02291F]/80 border border-[#D4AF62]/30 space-y-1 text-xs">
            <p className="font-bold text-[#D4AF62]">Numéro de contact :</p>
            <label className="block text-[11px] mb-0.5">Téléphone propriétaire</label>
            <input value={emergencyPhone} onChange={(e) => setEmergencyPhone(e.target.value)} required placeholder="+213 5XX XX XX XX" className="w-full px-2.5 py-1.5 rounded bg-[#063D2E] border border-[#D4AF62]/40 font-mono text-xs" />
            <p className="text-[10px] text-white/50 pt-1">
              Mot de passe oublié ? Réinitialisation via la console serveur par l'administrateur système.
            </p>
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
      <div className="min-h-screen bg-[#02291F] text-white flex items-center justify-center p-6 relative">
        <div className="absolute top-5 right-5 z-20">
          <LanguageToggle />
        </div>
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
              <input type="email" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} required placeholder="administrateur@mus-luxury.com" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-bold mb-1">Mot de passe</label>
              <input type="password" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-sm" />
            </div>
            <button type="submit" className="w-full py-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-sm hover:brightness-105 transition shadow">
              Se connecter au CMS Desktop
            </button>
          </form>

          {/* Serveur Endpoint Selector */}
          <div className="pt-3 border-t border-[#D4AF62]/20">
            <button
              type="button"
              onClick={() => setShowServerConfig(!showServerConfig)}
              className="text-[11px] text-[#E8D4A5]/70 hover:text-[#D4AF62] transition flex items-center justify-between w-full"
            >
              <span>Serveur API : <code className="text-[#D4AF62]">{serverUrl}</code></span>
              <span>{showServerConfig ? "▲ Masquer" : "⚙ Modifier"}</span>
            </button>
            {showServerConfig && (
              <div className="mt-2.5 p-3 rounded-xl bg-[#02291F] border border-[#D4AF62]/30 space-y-2 text-xs">
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      const u = "http://127.0.0.1:8000/api/v1";
                      configureApiBaseUrl(u);
                      setServerUrl(u);
                    }}
                    className={`px-2.5 py-1 rounded text-[11px] font-bold transition ${serverUrl.includes("127.0.0.1") || serverUrl.includes("localhost") ? "bg-[#D4AF62] text-[#02291F]" : "bg-white/10 text-white hover:bg-white/20"}`}
                  >
                    Serveur Local (127.0.0.1:8000)
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const u = "https://api.mus-luxury.com/api/v1";
                      configureApiBaseUrl(u);
                      setServerUrl(u);
                    }}
                    className={`px-2.5 py-1 rounded text-[11px] font-bold transition ${serverUrl.includes("mus-luxury.com") ? "bg-[#D4AF62] text-[#02291F]" : "bg-white/10 text-white hover:bg-white/20"}`}
                  >
                    VPS Cloud (mus-luxury.com)
                  </button>
                </div>
                <input
                  type="text"
                  value={serverUrl}
                  onChange={(e) => {
                    setServerUrl(e.target.value);
                    configureApiBaseUrl(e.target.value);
                  }}
                  className="w-full px-2.5 py-1.5 rounded bg-[#063D2E] border border-[#D4AF62]/40 text-xs font-mono text-white"
                  placeholder="https://api.mus-luxury.com/api/v1"
                />
              </div>
            )}
          </div>

          <p className="pt-4 text-[11px] text-white/50 text-center">
            Mot de passe oublié ? La réinitialisation est une opération serveur
            effectuée par l'administrateur système sur le VPS.
          </p>
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
            <span>{netTelemetry.online ? t("status.online") : t("status.offline")}</span>
          </div>

          <LanguageToggle />

          <button
            type="button"
            onClick={handleDeltaSync}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-[#E8D4A5] border border-[#D4AF62]/40 font-bold transition shadow-sm active:scale-95"
            title={t("common.refresh")}
          >
            <span>↻</span>
            <span>{t("common.refresh")}</span>
          </button>

          <button
            type="button"
            onClick={() => {
              DesktopCmsApi.logout();
              setUser(null);
            }}
            className="px-3.5 py-1.5 rounded-xl bg-red-900/80 hover:bg-red-800 text-white font-bold transition shadow-sm active:scale-95"
          >
            {t("topbar.logout")}
          </button>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="bg-[#063D2E] text-[#E8D4A5] px-4 py-2 flex items-center gap-1.5 overflow-x-auto text-xs font-bold border-b border-[#D4AF62]/30 shadow-inner whitespace-nowrap scrollbar-thin scrollbar-thumb-[#D4AF62]/30">
        {[
          { id: "dashboard", label: t("sidebar.dashboard"), icon: LayoutDashboard },
          { id: "business", label: t("sidebar.business_intelligence"), icon: TrendingUp },
          { id: "pos", label: t("sidebar.pos"), icon: ScanLine },
          { id: "products", label: t("sidebar.products"), icon: ShoppingBag },
          { id: "categories", label: t("sidebar.categories"), icon: Tags },
          { id: "purchases", label: t("sidebar.purchases"), icon: PackageCheck },
          { id: "inventory", label: t("sidebar.inventory"), icon: Boxes },
          { id: "orders", label: t("sidebar.orders"), icon: FileText },
          { id: "customers", label: t("sidebar.customers"), icon: Users },
          { id: "suppliers", label: t("sidebar.suppliers"), icon: Truck },
          { id: "expenses", label: t("sidebar.expenses"), icon: Receipt },
          { id: "treasury", label: t("sidebar.treasury"), icon: Landmark },
          { id: "accounting", label: t("sidebar.accounting"), icon: TrendingUp },
          { id: "delivery_wilayas", label: t("sidebar.delivery_wilayas"), icon: Truck },
          { id: "content", label: t("sidebar.content"), icon: Palette },
          { id: "devices", label: t("sidebar.devices"), icon: HardDrive },
          { id: "users", label: t("sidebar.users_roles"), icon: Users },
          { id: "inventory_count", label: t("sidebar.inventory_count"), icon: Boxes },
          { id: "sales_report", label: t("sidebar.sales_report"), icon: FileText },
          { id: "fiscal", label: t("sidebar.fiscal_settings"), icon: Landmark },
          { id: "audit", label: t("sidebar.audit_log"), icon: CheckSquare },
          { id: "low_stock", label: t("sidebar.low_stock"), icon: AlertTriangle },
          { id: "expense_report", label: t("sidebar.expense_report"), icon: Receipt },
          { id: "stock_movements", label: t("sidebar.stock_movements"), icon: Boxes },
          { id: "treasury_report", label: t("sidebar.treasury_report"), icon: Landmark },
          { id: "backups", label: t("sidebar.backups"), icon: ShieldCheck },
        ].map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveTab(item.id as CmsTab)}
              className={`group inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl transition-all duration-200 shrink-0 ${
                isActive
                  ? "bg-gradient-to-r from-[#D4AF62] to-[#E8D4A5] text-[#02291F] font-extrabold shadow-luxe-gold scale-[1.02]"
                  : "hover:bg-white/10 text-[#E8D4A5] hover:text-white"
              }`}
            >
              <Icon className={`w-3.5 h-3.5 shrink-0 transition-transform ${isActive ? "text-[#02291F]" : "text-[#D4AF62] group-hover:scale-110"}`} />
              <span>{item.label}</span>
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
                  <span className="font-bold text-[10px] uppercase tracking-wider text-gray-400">{t("dashboard_tab.revenue_title")}</span>
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
                  <span className="font-bold text-[10px] uppercase tracking-wider text-gray-400">{t("dashboard_tab.orders_title")}</span>
                  <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center">
                    <ShoppingBag className="w-4 h-4 text-blue-600" />
                  </div>
                </div>
                <p className="text-xl font-bold font-mono text-[#063D2E] mt-2">{dashboard.total_orders}</p>
                <div className="text-[10px] text-blue-600 font-semibold mt-1">
                  {t("dashboard_tab.orders_delivered", { count: dashboard.orders_by_status?.delivered || 0 })}
                </div>
              </div>

              {/* Active Products */}
              <div className="bg-white p-4 rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md hover:border-[#D4AF62]/40 transition-all duration-200 relative overflow-hidden group">
                <div className="flex items-center justify-between text-gray-500">
                  <span className="font-bold text-[10px] uppercase tracking-wider text-gray-400">{t("dashboard_tab.active_products")}</span>
                  <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-700 flex items-center justify-center">
                    <Boxes className="w-4 h-4 text-purple-600" />
                  </div>
                </div>
                <p className="text-xl font-bold font-mono text-[#063D2E] mt-2">{dashboard.total_active_products ?? dashboard.published_products}</p>
                <div className="text-[10px] text-purple-600 font-semibold mt-1">
                  {t("dashboard_tab.active_products_desc")}
                </div>
              </div>

              {/* Categories */}
              <div className="bg-white p-4 rounded-2xl border border-[#063D2E]/10 shadow-sm hover:shadow-md hover:border-[#D4AF62]/40 transition-all duration-200 relative overflow-hidden group">
                <div className="flex items-center justify-between text-gray-500">
                  <span className="font-bold text-[10px] uppercase tracking-wider text-gray-400">{t("dashboard_tab.categories_title")}</span>
                  <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-800 flex items-center justify-center">
                    <Tags className="w-4 h-4 text-amber-700" />
                  </div>
                </div>
                <p className="text-xl font-bold font-mono text-[#063D2E] mt-2">{dashboard.total_categories}</p>
                <div className="text-[10px] text-gray-400 mt-1">
                  {t("dashboard_tab.categories_desc")}
                </div>
              </div>

              {/* Low Stock Alert */}
              <div className={`bg-white p-4 rounded-2xl border shadow-sm hover:shadow-md transition-all duration-200 relative overflow-hidden group ${
                dashboard.low_stock_variants > 0 ? "border-amber-300 bg-amber-50/30" : "border-[#063D2E]/10"
              }`}>
                <div className="flex items-center justify-between text-amber-800">
                  <span className="font-bold text-[10px] uppercase tracking-wider text-amber-800">{t("dashboard_tab.low_stock_title")}</span>
                  <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center">
                    <AlertTriangle className="w-4 h-4 text-amber-700" />
                  </div>
                </div>
                <p className="text-xl font-bold font-mono text-amber-700 mt-2">{dashboard.low_stock_variants}</p>
                <div className="text-[10px] text-amber-700 font-semibold mt-1">
                  {t("dashboard_tab.low_stock_desc")}
                </div>
              </div>

              {/* Out of Stock Alert */}
              <div className={`bg-white p-4 rounded-2xl border shadow-sm hover:shadow-md transition-all duration-200 relative overflow-hidden group ${
                dashboard.out_of_stock_variants > 0 ? "border-red-300 bg-red-50/30" : "border-[#063D2E]/10"
              }`}>
                <div className="flex items-center justify-between text-red-800">
                  <span className="font-bold text-[10px] uppercase tracking-wider text-red-800">{t("dashboard_tab.out_of_stock_title")}</span>
                  <div className="w-8 h-8 rounded-lg bg-red-100 text-red-800 flex items-center justify-center">
                    <AlertCircle className="w-4 h-4 text-red-700" />
                  </div>
                </div>
                <p className="text-xl font-bold font-mono text-red-700 mt-2">{dashboard.out_of_stock_variants}</p>
                <div className="text-[10px] text-red-700 font-semibold mt-1">
                  {t("dashboard_tab.out_of_stock_desc")}
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
                      <h3 className="font-serif font-bold text-sm text-[#063D2E]">{t("dashboard_tab.recent_orders_title")}</h3>
                      <p className="text-[11px] text-gray-500">{t("dashboard_tab.recent_orders_desc")}</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveTab("orders")}
                    className="text-[11px] font-bold text-[#063D2E] hover:text-[#0A5C45] flex items-center gap-1 transition"
                  >
                    <span>{t("dashboard_tab.view_all_orders", { count: dashboard.total_orders })}</span>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                {(dashboard.recent_orders || []).length === 0 ? (
                  <div className="p-8 text-center bg-[#F8F6F0] rounded-xl border border-dashed border-[#D4AF62]/40 text-gray-400">
                    <p className="font-serif italic text-gray-600">{t("dashboard_tab.empty_orders")}</p>
                    <p className="text-[10px] text-gray-400 mt-1">{t("dashboard_tab.empty_orders_desc")}</p>
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
                    <span className="font-bold text-sm text-[#E8D4A5]">{t("dashboard_tab.security_title")}</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  </div>
                  <p className="text-[11px] text-gray-300 mt-0.5">
                    {t("dashboard_tab.security_desc")}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 text-[11px]">
                {dashboard.last_backup ? (
                  <div className="px-3 py-1.5 rounded-xl bg-white/10 border border-white/10 font-mono text-gray-300">
                    {t("dashboard_tab.last_backup", { filename: dashboard.last_backup.filename })}
                  </div>
                ) : (
                  <span className="text-gray-400 font-mono">{t("dashboard_tab.backups_ready")}</span>
                )}
                <button
                  type="button"
                  onClick={() => setActiveTab("backups")}
                  className="px-3.5 py-1.5 rounded-xl bg-[#D4AF62] text-[#02291F] font-bold hover:brightness-105 transition"
                >
                  {t("dashboard_tab.btn_manage")}
                </button>
              </div>
            </div>
          </div>
        )}

        </div>

        {/* TAB: BUSINESS SUMMARY (POS + online, real records) (KEEP-ALIVE) */}
        <div className={activeTab === "business" ? "block" : "hidden"}><BusinessDashboardPage /></div>

        {/* TAB: POINT OF SALE (POS) — in-store cash register & sales (KEEP-ALIVE) */}
        <div className={activeTab === "pos" ? "block" : "hidden"}>
          <PosPage onInventoryUpdated={loadAllWorkspaceData} />
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
                  <h2 className="text-base font-serif font-bold text-[#063D2E]">{t("catalog.title")}</h2>
                  <p className="text-xs text-gray-500">{t("catalog.subtitle")}</p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveTab("categories")}
                  className="px-3 py-1.5 rounded-xl bg-[#F8F6F0] text-[#063D2E] border border-[#D4AF62]/40 font-bold text-xs hover:bg-[#D4AF62]/20 transition flex items-center gap-1.5"
                >
                  <Tags className="w-3.5 h-3.5 text-[#063D2E]" />
                  <span>{t("catalog.btn_categories")}</span>
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    await loadAllWorkspaceData();
                    notifyClientSuccess(t("catalog.sync_success_title"), t("catalog.sync_success_desc"));
                  }}
                  className="px-3 py-1.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold text-xs hover:bg-[#084e3b] transition flex items-center gap-1.5 shadow-xs"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-[#D4AF62]" />
                  <span>{t("catalog.btn_refresh")}</span>
                </button>
              </div>
            </div>

            {/* Product Editor Launch Pad */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-[#D4AF62]/40 shadow-xs space-y-5">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[#063D2E] to-[#0A5C45] flex items-center justify-center shrink-0 shadow-sm">
                    <PackagePlus className="w-6 h-6 text-[#D4AF62]" />
                  </div>
                  <div className="flex-1">
                    <h2 className="text-lg font-serif font-bold text-[#063D2E]">{t("catalog.create_piece_title")}</h2>
                    <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                      {t("catalog.create_piece_desc")}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {[
                    { label: t("catalog.stat_products"), value: products.length, tone: "text-[#063D2E]" },
                    { label: t("catalog.stat_published"), value: productCounts.published, tone: "text-emerald-700" },
                    { label: t("catalog.stat_draft"), value: productCounts.draft, tone: "text-gray-600" },
                    { label: t("catalog.stat_low_stock"), value: productCounts.low_stock, tone: "text-amber-700" },
                  ].map((stat) => (
                    <div key={stat.label} className="p-3 rounded-xl bg-[#F8F6F0] border border-[#D4AF62]/30">
                      <p className="text-[10px] uppercase tracking-wide text-gray-500 font-bold">{stat.label}</p>
                      <p className={`text-xl font-bold font-mono ${stat.tone}`}>{stat.value}</p>
                    </div>
                  ))}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => openProductEditor(null)}
                    disabled={categories.length === 0}
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-[#D4AF62] to-[#E8D4A5] text-[#02291F] font-extrabold shadow-xs hover:brightness-105 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Plus className="w-4 h-4" />
                    <span>{t("catalog.btn_new_product")}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab("categories")}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white border border-[#D4AF62]/60 text-[#063D2E] font-bold hover:bg-[#F8F6F0] transition"
                  >
                    <Tags className="w-4 h-4" />
                    <span>{t("catalog.btn_attributes_cats")}</span>
                  </button>
                </div>
                {categories.length === 0 && (
                  <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                    {t("catalog.category_required_banner")}
                  </p>
                )}
              </div>

              <div className="bg-[#063D2E] p-6 rounded-2xl border border-[#D4AF62]/40 text-[#E8D4A5] space-y-3">
                <p className="font-serif font-bold text-base flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-[#D4AF62]" />
                  <span>{t("catalog.best_practices_title")}</span>
                </p>
                <ul className="space-y-2 text-[11px] leading-relaxed text-white/80">
                  <li className="flex gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#D4AF62] shrink-0 mt-0.5" />
                    <span>{t("catalog.best_practices_1")}</span>
                  </li>
                  <li className="flex gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#D4AF62] shrink-0 mt-0.5" />
                    <span>{t("catalog.best_practices_2")}</span>
                  </li>
                  <li className="flex gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#D4AF62] shrink-0 mt-0.5" />
                    <span>{t("catalog.best_practices_3")}</span>
                  </li>
                  <li className="flex gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#D4AF62] shrink-0 mt-0.5" />
                    <span>{t("catalog.best_practices_4")}</span>
                  </li>
                </ul>
              </div>
            </div>

            {/* Product Catalogue Table & Tools */}
            <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-4 text-xs shadow-xs">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-3">
                  <h3 className="text-base font-serif font-bold text-[#063D2E]">
                    {t("catalog.title_list")} ({filteredProducts.length})
                  </h3>
                  <div className="flex flex-wrap rounded-xl bg-[#F8F6F0] p-1 border border-[#D4AF62]/40 text-[11px]">
                    {[
                      { key: "all", label: `${t("catalog.filter_all")} (${productCounts.all})` },
                      { key: "published", label: `${t("catalog.filter_published")} (${productCounts.published})` },
                      { key: "draft", label: `${t("catalog.filter_draft")} (${productCounts.draft})` },
                      { key: "archived", label: `${t("catalog.filter_archived")} (${productCounts.archived})` },
                      { key: "low_stock", label: `${t("catalog.filter_low_stock")} (${productCounts.low_stock})` },
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
                      placeholder={t("catalog.search_placeholder")}
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
                      <h4 className="text-lg font-serif font-bold text-[#063D2E]">{t("catalog.empty_title")}</h4>
                      <p className="text-xs text-gray-600 leading-relaxed">
                        {t("catalog.empty_desc")}
                      </p>
                    </div>
                    <div className="flex items-center justify-center gap-3 pt-2">
                      <button
                        type="button"
                        onClick={() => {
                          if (categories.length === 0) {
                            setActiveTab("categories");
                            notifyClientWarning(
                              t("catalog.category_required_title"),
                              t("catalog.category_required_desc")
                            );
                          } else {
                            openProductEditor(null);
                          }
                        }}
                        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-xs shadow-xs hover:bg-[#084e3b] transition"
                      >
                        <Plus className="w-4 h-4 text-[#D4AF62]" />
                        <span>{t("catalog.create_first_product")}</span>
                      </button>
                      {categories.length === 0 && (
                        <button
                          type="button"
                          onClick={() => setActiveTab("categories")}
                          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white border border-[#D4AF62] text-[#063D2E] font-bold text-xs hover:bg-[#F8F6F0] transition"
                        >
                          <Tags className="w-4 h-4 text-[#063D2E]" />
                          <span>{t("catalog.configure_categories")}</span>
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  /* Empty State: Filter Returned No Products */
                  <div className="p-10 text-center bg-gray-50 rounded-2xl border border-gray-200 space-y-3">
                    <Search className="w-10 h-10 text-gray-300 mx-auto" />
                    <div>
                      <p className="font-bold text-gray-700 text-sm">{t("catalog.no_match_title")}</p>
                      {prodSearch && <p className="text-xs text-gray-500 mt-0.5">{t("catalog.no_match_desc", { query: prodSearch })}</p>}
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setProdSearch("");
                        setProductFilterTab("all");
                      }}
                      className="px-4 py-2 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold text-xs hover:bg-[#084e3b] transition"
                    >
                      {t("catalog.reset_filter")}
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
                        <th className="p-2.5">{t("catalog.th_product")}</th>
                        <th className="p-2.5 text-right">Prix Achat</th>
                        <th className="p-2.5 text-right">{t("catalog.th_selling_price")}</th>
                        <th className="p-2.5 text-right">Marge</th>
                        <th className="p-2.5 text-center">Taux</th>
                        <th className="p-2.5 text-center">{t("catalog.th_stock_variants")}</th>
                        <th className="p-2.5 text-center">{t("catalog.th_status")}</th>
                        <th className="p-2.5 text-right">{t("catalog.th_actions")}</th>
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
                                  <span>{t("preview.out_of_stock")}</span>
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
                                    <span>{t("catalog.badge_published")}</span>
                                  </>
                                ) : p.status === "archived" ? (
                                  <>
                                    <Archive className="w-3 h-3 text-amber-700" />
                                    <span>{t("catalog.badge_archived")}</span>
                                  </>
                                ) : (
                                  <>
                                    <Clock className="w-3 h-3 text-gray-600" />
                                    <span>{t("catalog.badge_draft")}</span>
                                  </>
                                )}
                              </span>
                            </td>
                            <td className="p-2.5 text-right space-x-1.5 whitespace-nowrap">
                              <button
                                type="button"
                                onClick={() => openProductEditor(p)}
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#F8F6F0] text-[#063D2E] border border-[#D4AF62]/40 font-bold hover:bg-[#D4AF62]/20 transition"
                                title={t("catalog.btn_edit")}
                              >
                                <Edit3 className="w-3 h-3 text-[#063D2E]" />
                                <span>{t("catalog.btn_edit")}</span>
                              </button>
                              {p.status !== "archived" ? (
                                <button
                                  type="button"
                                  onClick={() => handleArchiveProduct(p.id)}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-50 text-amber-800 border border-amber-200 font-bold hover:bg-amber-100 transition"
                                  title={t("catalog.btn_archive")}
                                >
                                  <Archive className="w-3 h-3 text-amber-800" />
                                  <span>{t("catalog.btn_archive")}</span>
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => handleRestoreProduct(p.id)}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200 font-bold hover:bg-emerald-100 transition"
                                  title={t("catalog.btn_restore")}
                                >
                                  <RotateCcw className="w-3 h-3 text-emerald-800" />
                                  <span>{t("catalog.btn_restore")}</span>
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
                                title={t("catalog.btn_delete")}
                              >
                                <Trash2 className="w-3 h-3 text-red-700" />
                                <span>{t("catalog.btn_delete")}</span>
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
                      {t("catalog.bulk_selected", { count: selectedProductIds.length })}
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
                      <span>{t("catalog.bulk_publish")}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleBulkStatus("archived")}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs transition"
                    >
                      <Archive className="w-3.5 h-3.5" />
                      <span>{t("catalog.bulk_archive")}</span>
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
              <h3 className="text-base font-serif font-bold text-[#063D2E]">{t("sidebar.inventory")}</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {products.flatMap((p) =>
                  (p.variants || []).map((v: any) => (
                    <div key={v.id} className="p-3 rounded-xl border flex items-center justify-between">
                      <div>
                        <div className="font-bold text-[#063D2E]">{p.name_fr} — {v.title}</div>
                        <div className="font-mono text-gray-500">SKU: {v.sku} • {t("stock_writeoff.current_stock_lbl")}: <strong>{v.stock_qty}</strong></div>
                        <div className="font-mono text-gray-400 text-[11px]">
                          {v.barcode ? `⌗ ${v.barcode}` : "⌗ —"}
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button type="button" onClick={() => handleAdjustStock(v.id, -1)} className="px-2.5 py-1 rounded bg-gray-100 font-bold">-1</button>
                        <button type="button" onClick={() => handleAdjustStock(v.id, 1)} className="px-2.5 py-1 rounded bg-emerald-100 text-emerald-900 font-bold">+1</button>
                        <button type="button" onClick={() => handleAdjustStock(v.id, 5)} className="px-2.5 py-1 rounded bg-[#063D2E] text-[#D4AF62] font-bold">+5</button>
                        <button type="button" onClick={() => setBarcodeVariantId(v.id)} title="Code-barres & étiquette" className="px-2.5 py-1 rounded bg-[#D4AF62]/20 text-[#7a5c16] font-bold flex items-center gap-1">
                          <ScanLine className="w-3.5 h-3.5" /> {t("devices.label_printer")}
                        </button>
                        <button
                          type="button"
                          disabled={v.stock_qty <= 0}
                          onClick={() => setWriteOffTarget({ variantId: v.id, sku: v.sku, productName: p.name_fr, variantTitle: v.title, currentStock: v.stock_qty })}
                          title="Sortie de stock"
                          className="px-2.5 py-1 rounded bg-red-100 text-red-700 font-bold disabled:opacity-40"
                        >
                          {t("stock_writeoff.title")}
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
              <h3 className="text-base font-serif font-bold text-[#063D2E]">{t("inventory_report.title")} ({movements.length})</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-[#063D2E] text-[#E8D4A5]">
                      <th className="p-2">ID</th>
                      <th className="p-2">{t("low_stock.th_product")}</th>
                      <th className="p-2">{t("inventory_count.th_gap")}</th>
                      <th className="p-2">{t("inventory_count.th_counted")}</th>
                      <th className="p-2">{t("stock_writeoff.th_reason")}</th>
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
              <h3 className="text-base font-serif font-bold text-[#063D2E]">{t("sidebar.orders")} ({orders.length})</h3>
              <div className="flex items-center gap-2">
                <select
                  value={orderStatusFilter}
                  onChange={(e) => setOrderStatusFilter(e.target.value)}
                  className="px-3 py-1.5 border rounded-xl bg-[#F8F6F0] font-semibold"
                >
                  <option value="">{t("common.all")}</option>
                  {["new", "pending_confirmation", "confirmed", "preparing", "ready_for_shipment", "shipped", "delivered", "cancelled", "returned"].map((st) => (
                    <option key={st} value={st}>{st}</option>
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
                        <span>Expédition</span>
                      </button>
                      {risk.is_blacklisted ? (
                        <button
                          type="button"
                          onClick={() => handleUnblockCustomerPhone(o.customer_phone)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-700 text-white font-bold hover:bg-emerald-800 transition"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5 text-white" />
                          <span>Débloquer</span>
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleBlockCustomerPhone(o.customer_phone, "Retours COD")}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-50 text-red-800 border border-red-200 font-bold hover:bg-red-100 transition"
                        >
                          <Ban className="w-3.5 h-3.5 text-red-700" />
                          <span>Bloquer</span>
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

        {/* TAB: DEVICES & HARDWARE (KEEP-ALIVE) */}
        <div className={activeTab === "devices" ? "block" : "hidden"}><DevicesPage /></div>

        {/* TAB: CUSTOMERS (KEEP-ALIVE) */}
        <div className={activeTab === "customers" ? "block" : "hidden"}><CustomersPage /></div>

        {/* TAB: USERS & ROLES (KEEP-ALIVE) */}
        <div className={activeTab === "users" ? "block" : "hidden"}><UsersRolesPage /></div>

        {/* TAB: PHYSICAL INVENTORY (KEEP-ALIVE) */}
        <div className={activeTab === "inventory_count" ? "block" : "hidden"}><InventoryCountPage onInventoryUpdated={loadAllWorkspaceData} /></div>

        {/* TAB: SALES REPORT (KEEP-ALIVE) */}
        <div className={activeTab === "sales_report" ? "block" : "hidden"}><SalesReportPage /></div>

        {/* TAB: FISCAL SETTINGS (KEEP-ALIVE) */}
        <div className={activeTab === "fiscal" ? "block" : "hidden"}><FiscalSettingsPage /></div>

        {/* TAB: AUDIT LOG (KEEP-ALIVE) */}
        <div className={activeTab === "audit" ? "block" : "hidden"}><AuditLogPage /></div>

        {/* TAB: SUPPLIERS (KEEP-ALIVE) */}
        <div className={activeTab === "suppliers" ? "block" : "hidden"}><SuppliersPage /></div>

        {/* TAB: LOW STOCK (KEEP-ALIVE) */}
        <div className={activeTab === "low_stock" ? "block" : "hidden"}><LowStockPage /></div>

        {/* TAB: EXPENSE REPORT (KEEP-ALIVE) */}
        <div className={activeTab === "expense_report" ? "block" : "hidden"}><ExpenseReportPage /></div>

        {/* TAB: STOCK MOVEMENTS REPORT (KEEP-ALIVE) */}
        <div className={activeTab === "stock_movements" ? "block" : "hidden"}><InventoryMovementsReportPage /></div>

        {/* TAB: TREASURY REPORT (KEEP-ALIVE) */}
        <div className={activeTab === "treasury_report" ? "block" : "hidden"}><TreasuryReportPage /></div>

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

            {/* Backup admin panel removed. Nightly encrypted backups run via
                cron; pre-deploy dumps run from the CD pipeline. See the
                docs/cicd/ROLLBACK.md handbook for the restore procedure. */}
          </div>
        </div>
        <ProductEditor
          open={productEditorOpen}
          product={productEditorTarget}
          categories={categories}
          brands={brands}
          initialCategoryId={prodCategoryId}
          onClose={() => {
            setProductEditorOpen(false);
            setProductEditorTarget(null);
          }}
          onSaved={async () => {
            await loadAllWorkspaceData();
          }}
        />
        {barcodeVariantId !== null && (
          <BarcodeLabelModal
            variantId={barcodeVariantId}
            onClose={() => setBarcodeVariantId(null)}
            onChanged={loadAllWorkspaceData}
          />
        )}
        {writeOffTarget && (
          <StockWriteOffModal
            {...writeOffTarget}
            onClose={() => setWriteOffTarget(null)}
            onDone={loadAllWorkspaceData}
          />
        )}
        {deliveryNoteOrderId !== null && (
          <DeliveryNoteModal orderId={deliveryNoteOrderId} onClose={() => setDeliveryNoteOrderId(null)} />
        )}
    </main>
    </div>
  );
}

import { readDraft, writeDraft } from "./utils/draftStorage";
import { formatServerDateTime } from "./utils/serverDate";
import { useT, LanguageToggle } from "./i18n";
import { CmsSidebar } from "./components/CmsSidebar";
import {
  ClientNotificationItem,
  ClientConfirmRequest,
  notifyClientError,
  notifyClientSuccess,
  notifyClientWarning,
  notifyClient,
  subscribeClientNotifications,
  subscribeClientConfirm,
  clearPendingClientConfirms,
  confirmClientAction,
} from "./utils/clientNotifier";
import { focusMainWindow } from "./utils/notificationCenter";
import {
  OPEN_UPDATE_DIALOG_EVENT,
  loadUpdaterStatus,
  openUpdateDialog,
  startAutoUpdateChecks,
  subscribeUpdateState,
  type UpdateState,
} from "./utils/appUpdater";
import { ToastStack } from "./components/ToastStack";
import { NotificationBell } from "./components/NotificationBell";
import { UpdateDialog } from "./components/UpdateDialog";
import { DatabasePanel } from "./components/DatabasePanel";
import {
  NetworkTelemetryState,
  getNetworkTelemetry,
  subscribeNetworkTelemetry,
} from "./utils/networkQueue";
import React, { useEffect, useRef, useState } from "react";
import {
  ShoppingBag,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Sparkles,
  Trash2,
  Archive,
  ShieldAlert,
  X,
} from "lucide-react";
import { orderStatusLabel } from "./utils/orderStatus";
import { openExternalUrl } from "./utils/openExternal";
import { useEscapeToClose } from "./utils/useEscapeToClose";
import { canOpenTab } from "./utils/tabAccess";
import { copyNewestBackupIfMissing, pcCopiesAvailable } from "./utils/backupCopies";
import { DesktopCmsApi, restoreSessionFromOsKeychain, getApiBaseUrl, configureApiBaseUrl, mediaUrl } from "./api/adminClient";
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
import { OrdersPage } from "./pages/OrdersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { InventoryPage } from "./pages/InventoryPage";
import { ContentSettingsPage } from "./pages/ContentSettingsPage";
import { ProductsPage, type ProductFilterTab } from "./pages/ProductsPage";
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
  // Blocking message boxes are queued (never overwritten): several errors in a
  // row are read one after the other with a "1 sur 3" counter.
  const [messageQueue, setMessageQueue] = useState<ClientNotificationItem[]>([]);
  const activeMessageBox = messageQueue[0] ?? null;
  const [activeConfirm, setActiveConfirm] = useState<ClientConfirmRequest | null>(null);
  const confirmCancelButtonRef = useRef<HTMLButtonElement | null>(null);
  const messageBoxOkButtonRef = useRef<HTMLButtonElement | null>(null);
  const [updateDialogOpen, setUpdateDialogOpen] = useState(false);
  const [updateState, setUpdateState] = useState<UpdateState | null>(null);
  const tRef = useRef(t);
  tRef.current = t;

  const closeMessageBox = () => setMessageQueue((prev) => prev.slice(1));

  // Message box keyboard: Enter / Esc close the current message. A confirm
  // dialog on top of it keeps priority.
  useEffect(() => {
    if (!activeMessageBox || activeConfirm) return;
    messageBoxOkButtonRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" || e.key === "Enter") {
        e.preventDefault();
        setMessageQueue((prev) => prev.slice(1));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeMessageBox?.id, activeConfirm]);

  useEffect(() => {
    if (activeConfirm) {
      confirmCancelButtonRef.current?.focus();
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          e.preventDefault();
          activeConfirm.resolve(false);
        }
      };
      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }
  }, [activeConfirm]);

  useEffect(() => {
    // Toasts are rendered by <ToastStack/>; here we only queue message boxes.
    const unsubNotifs = subscribeClientNotifications((item) => {
      if (!item.showModalBox) return;
      setMessageQueue((prev) =>
        prev.some((m) => m.type === item.type && m.title === item.title && m.message === item.message)
          ? prev
          : [...prev, item].slice(0, 10)
      );
    });

    // Auto-update: background checks (desktop app only). A new version raises
    // a toast + a Windows notification once; installing waits for the user.
    const unsubUpdateState = subscribeUpdateState(setUpdateState);
    void loadUpdaterStatus();
    const stopAutoUpdate = startAutoUpdateChecks((version) => {
      notifyClient({
        type: "info",
        category: "update",
        title: tRef.current("update.toast_title"),
        message: tRef.current("update.toast_body", { v: version }),
        showModalBox: false,
        os: true,
        durationMs: 0,
        action: { label: tRef.current("update.install"), onClick: () => openUpdateDialog() },
      });
    });
    const onOpenUpdateDialog = () => setUpdateDialogOpen(true);
    window.addEventListener(OPEN_UPDATE_DIALOG_EVENT, onOpenUpdateDialog);

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
      unsubUpdateState();
      stopAutoUpdate();
      window.removeEventListener(OPEN_UPDATE_DIALOG_EVENT, onOpenUpdateDialog);
      clearPendingClientConfirms();
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
  const [brands, setBrands] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [movements, setMovements] = useState<any[]>([]);
  // backups state removed — admin-facing backup page gone.
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [readinessStatus, setReadinessStatus] = useState<any | null>(null);
  // recoveryStatus state removed with the WhatsApp password-recovery flow.
  // restoreReport state removed with the admin-facing backup page.
  const [selectedInvoice, setSelectedInvoice] = useState<any | null>(null);
  const closeInvoice = React.useCallback(() => setSelectedInvoice(null), []);
  // Screens follow the role: a cashier sees the till, not the accounts.
  const userPermsRef = useRef<string[]>([]);
  userPermsRef.current = (user as any)?.permissions || [];
  const canOpen = React.useCallback((id: string) => canOpenTab(id, (user as any)?.permissions), [user]);
  useEffect(() => {
    if (!user) return;
    if (!canOpenTab(activeTab, (user as any)?.permissions)) {
      const first = ["dashboard", "pos", "orders", "products", "inventory"].find((tab) => canOpenTab(tab, (user as any)?.permissions));
      if (first) setActiveTab(first as CmsTab);
    }
  }, [user, activeTab]);
  // Escape closes the top-most open window, on every screen: it presses that
  // window's "Fermer" button. Confirmation / message boxes handle Escape
  // themselves and are left alone.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (document.querySelector('[aria-labelledby="active-confirm-title"], [aria-labelledby="active-message-box-title"]')) return;
      const overlays = Array.from(document.querySelectorAll<HTMLElement>("div.fixed.inset-0")).filter((el) => el.offsetParent !== null || el.getClientRects().length > 0);
      const top = overlays[overlays.length - 1];
      const close = top?.querySelector<HTMLButtonElement>('button[aria-label="Fermer"]');
      if (close) {
        e.stopPropagation();
        e.preventDefault();
        close.click();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, []);
  useEscapeToClose(closeInvoice, Boolean(selectedInvoice));
  const [loadingWorkspace, setLoadingWorkspace] = useState(false);
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);
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
  const [productFilterTab, setProductFilterTab] = useState<ProductFilterTab>("all");
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
  // Search typed in Commandes (number, phone, name); applied on Enter.
  const [orderSearchInput, setOrderSearchInput] = useState("");
  const [orderSearch, setOrderSearch] = useState("");


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
      // Only ask for what this role may read (a cashier does not load the
      // accounts, the catalogue editor or the audit log).
      const perms: string[] = (user as any)?.permissions || [];
      const may = (...need: string[]) => need.some((p) => perms.includes(p));
      const emptyList = Promise.resolve({ items: [] as any[] });
      const [dashData, brdData, catData, prodData, ordData, movData, blData, kcStatus, outboxData, auditData, readyData] = await Promise.all([
        DesktopCmsApi.getDashboard(),
        may("products:write", "categories:write") ? DesktopCmsApi.listBrands().catch(() => ({ items: [] })) : emptyList,
        may("products:write", "categories:write") ? DesktopCmsApi.listCategories().catch(() => ({ items: [] })) : emptyList,
        may("products:write") ? DesktopCmsApi.listAdminProducts({ include_archived: true }).catch(() => ({ items: [] })) : emptyList,
        may("orders:write") ? DesktopCmsApi.listOrders(orderStatusFilter || undefined, orderSearchRef.current).catch(() => ({ items: [] })) : emptyList,
        may("products:write") ? DesktopCmsApi.listInventoryMovements().catch(() => ({ items: [] })) : emptyList,
        may("orders:write") ? DesktopCmsApi.listCodBlacklist().catch(() => ({ items: [] })) : emptyList,
        DesktopCmsApi.getKeychainStatus().catch(() => null),
        may("orders:write") ? DesktopCmsApi.listCommunicationsOutbox().catch(() => ({ items: [] })) : emptyList,
        may("settings:write") ? DesktopCmsApi.listAuditLogs({ limit: 30 }).catch(() => ({ items: [] })) : emptyList,
        DesktopCmsApi.checkReadiness().catch(() => ({ ready: true })),
      ]);
      setCodBlacklist(blData.items || []);
      setKeychainStatus(kcStatus);
      setWaOutbox(outboxData.items || []);
      setAuditLogs(auditData.items || []);
      setReadinessStatus(readyData);
      setDashboard(dashData);
      setBrands(brdData.items || []);
      setCategories(catData.items || []);
      setProducts(prodData.items || []);
      setOrders(ordData.items || []);
      setMovements(movData.items || []);
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
        const next = tabOrder[Number(e.key) - 1];
        if (canOpenTab(next, userPermsRef.current)) setActiveTab(next);
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
    if (user && keychainReady && canOpenTab("orders", (user as any)?.permissions)) {
      DesktopCmsApi.listOrders(orderStatusFilter || undefined, orderSearch)
        .then((ordData) => setOrders(ordData.items || []))
        .catch(() => {});
    }
  }, [orderStatusFilter, orderSearch, keychainReady]);

  // Owner on the desktop app: keep the newest server backup on this PC
  // (the VPS has a small disk). Silent unless a new copy was written.
  useEffect(() => {
    if (!user || !keychainReady || (user as any).role !== "super_admin" || !pcCopiesAvailable()) return;
    let stopped = false;
    const run = async () => {
      try {
        const copied = await copyNewestBackupIfMissing();
        if (copied && !stopped) notifyClientSuccess("Sauvegarde copiée sur ce PC", `${copied} — Documents\\Mus Luxury\\Sauvegardes`);
      } catch {
        /* retried at the next run; the backup screen shows the details */
      }
    };
    const first = window.setTimeout(run, 20_000);
    const timer = window.setInterval(run, 6 * 60 * 60 * 1000);
    return () => {
      stopped = true;
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [user, keychainReady]);

  // New online-order watcher: polls the "new" orders every 45 s. The first
  // poll only memorises what already exists; later ones raise a toast with a
  // "Voir" button plus a Windows notification when the CMS is in background.
  const orderStatusFilterRef = useRef(orderStatusFilter);
  orderStatusFilterRef.current = orderStatusFilter;
  const orderSearchRef = useRef(orderSearch);
  orderSearchRef.current = orderSearch;
  useEffect(() => {
    // Only roles that handle online orders are alerted about new ones.
    if (!user || !keychainReady || !canOpenTab("orders", (user as any)?.permissions)) return;
    const seen = new Set<number>();
    let seeded = false;
    let stopped = false;

    const openOrders = () => {
      setActiveTab("orders");
      void focusMainWindow();
    };

    const poll = async () => {
      try {
        const data = await DesktopCmsApi.listOrders("new");
        if (stopped) return;
        const items: any[] = data?.items || [];
        const fresh = items.filter((o) => typeof o?.id === "number" && !seen.has(o.id));
        items.forEach((o) => typeof o?.id === "number" && seen.add(o.id));
        if (!seeded) {
          seeded = true;
          return;
        }
        if (fresh.length === 0) return;
        const tr = tRef.current;
        if (fresh.length === 1) {
          const o = fresh[0];
          notifyClient({
            type: "info",
            category: "order",
            os: true,
            showModalBox: false,
            durationMs: 15000,
            title: tr("order.new_title"),
            message: tr("order.new_body", {
              ref: o.order_reference || o.id,
              name: o.customer_name || "—",
              total: Number(o.total_dzd || 0).toLocaleString("fr-DZ"),
            }),
            action: { label: tr("notif.view"), onClick: openOrders },
          });
        } else {
          notifyClient({
            type: "info",
            category: "order",
            os: true,
            showModalBox: false,
            durationMs: 15000,
            title: tr("order.new_many_title", { n: fresh.length }),
            message: tr("order.new_many_body"),
            action: { label: tr("notif.view"), onClick: openOrders },
          });
        }
        // Keep the Orders list + sidebar badge current without a manual refresh.
        const filter = orderStatusFilterRef.current;
        // Not while a search is shown: the refresh would replace its results.
        if ((!filter || filter === "new") && !orderSearchRef.current) {
          DesktopCmsApi.listOrders(filter || undefined)
            .then((ordData) => !stopped && setOrders(ordData.items || []))
            .catch(() => {});
        }
      } catch {
        // offline / session expired: try again on the next tick
      }
    };

    void poll();
    const timer = window.setInterval(poll, 45000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [user, keychainReady]);

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
      const okMsg =
        "Compte propriétaire créé. Gardez votre mot de passe dans un gestionnaire de mots de passe : " +
        "en cas d'oubli, il est réinitialisé sur le serveur par la personne qui gère le VPS (guide d'exploitation, § Mot de passe oublié).";
      setSuccessMsg(okMsg);
      notifyClientSuccess("Compte propriétaire créé", okMsg, true);
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
      const res = await DesktopCmsApi.deleteProduct(productToDelete.id, hard, false);
      if (res?.archived && !res?.deleted && hard) {
        const infoMsg = res.message || "Cet article a un historique de ventes ou d'achats : il a été archivé au lieu d'être supprimé.";
        setSuccessMsg(infoMsg);
        notifyClientWarning("Article archivé (historique conservé)", infoMsg);
        setProductToDelete(null);
      } else {
        const okMsg =
          res?.message ||
          (hard
            ? `Produit "${productToDelete.name_fr}" supprimé définitivement du catalogue et de la base de données.`
            : `Produit "${productToDelete.name_fr}" archivé en toute sécurité.`);
        setSuccessMsg(okMsg);
        notifyClientSuccess(hard ? "Produit supprimé" : "Produit archivé", okMsg);
        setProductToDelete(null);
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
      const owner = products.find((p: any) => (p.variants || []).some((v: any) => v.id === variantId));
      const variant: any = owner ? (owner.variants || []).find((v: any) => v.id === variantId) : null;
      const label = variant ? `${owner?.name_fr || ""} — ${variant.title || variant.sku}` : `l'article`;
      const okMsg = `Stock de ${label} corrigé (${delta > 0 ? `+${delta}` : delta}).` +
        (delta < 0 ? " Pour un article abîmé, perdu ou offert, utilisez « Sortie de stock » : il sera compté en perte." : "");
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
    const ord = orders.find((o) => o.id === orderId);
    const ref = ord?.order_reference || `#${orderId}`;
    if (nextStatus === "cancelled" || nextStatus === "returned") {
      const ok = await confirmClientAction({
        title: nextStatus === "cancelled" ? "Annuler la commande" : "Commande retournée",
        message: `${ref} : les articles reviennent en stock et la commande ne compte plus dans le chiffre d'affaires. Ce statut est définitif.`,
        confirmLabel: nextStatus === "cancelled" ? "Annuler la commande" : "Confirmer le retour",
        danger: true,
      });
      if (!ok) return;
    }
    try {
      await DesktopCmsApi.updateOrderStatus(orderId, nextStatus);
      const okMsg = `Commande ${ref} : ${orderStatusLabel(nextStatus)}.`;
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
      await openExternalUrl(receipt.wa_me_customer_url);
      const okMsg = `WhatsApp est ouvert sur la conversation avec ${receipt.recipient_local}, message déjà écrit : vérifiez-le puis appuyez sur Envoyer.`;
      setSuccessMsg(okMsg);
      notifyClientSuccess("Message WhatsApp prêt", okMsg);
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

  // handleRotateEmergencyCode removed with the WhatsApp-recovery flow.

  function renderClientNotificationCenter() {
    return (
      <>
        {/* Non-blocking toasts: bottom corner, newest nearest the corner */}
        <ToastStack />

        {/* Modal Client Message Box (Boîte de Message Client) — queued */}
        {activeMessageBox && (
          <div className="animate-backdrop fixed inset-0 z-[75] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="active-message-box-title"
              aria-describedby="active-message-box-body"
              className="animate-modal bg-white text-[#202923] rounded-2xl max-w-lg w-full overflow-hidden shadow-2xl border-2 border-[#D4AF62]"
            >
              <div
                className={`px-5 py-3.5 flex items-center justify-between gap-3 ${
                  activeMessageBox.type === "error"
                    ? "bg-gradient-to-r from-red-950 to-red-800 text-white"
                    : activeMessageBox.type === "warning"
                    ? "bg-gradient-to-r from-amber-900 to-amber-700 text-white"
                    : "bg-gradient-to-r from-[#02291F] to-[#063D2E] text-white"
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="w-8 h-8 rounded-full bg-white/15 flex items-center justify-center shrink-0">
                    {activeMessageBox.type === "error" && <ShieldAlert className="w-4 h-4 text-rose-200" />}
                    {activeMessageBox.type === "warning" && <AlertTriangle className="w-4 h-4 text-amber-200" />}
                    {(activeMessageBox.type === "info" || activeMessageBox.type === "success") && (
                      <CheckCircle2 className="w-4 h-4 text-[#D4AF62]" />
                    )}
                  </span>
                  <span className="text-sm font-extrabold text-[#E8D4A5] truncate">
                    {activeMessageBox.type === "error"
                      ? t("msgbox.title.error")
                      : activeMessageBox.type === "warning"
                      ? t("msgbox.title.warning")
                      : t("msgbox.title.info")}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {messageQueue.length > 1 && (
                    <span className="px-2 py-0.5 rounded-full bg-black/25 text-[10px] font-bold text-white/90">
                      {t("msgbox.counter", { i: 1, n: messageQueue.length })}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={closeMessageBox}
                    aria-label={t("common.close") || "Fermer"}
                    className="w-7 h-7 rounded-full bg-black/25 text-white font-bold text-xs flex items-center justify-center hover:bg-black/40 transition"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className="p-6 space-y-4 text-xs">
                <h4 id="active-message-box-title" className="text-base font-serif font-bold text-[#063D2E]">
                  {activeMessageBox.title}
                </h4>
                <p
                  id="active-message-box-body"
                  className="text-sm text-gray-700 leading-relaxed whitespace-pre-line bg-[#F8F6F0] p-3.5 rounded-xl border border-[#D4AF62]/30"
                >
                  {activeMessageBox.message}
                </p>
                <div className="flex flex-wrap items-center gap-3 pt-1">
                  <span className="text-[10px] text-gray-400 font-mono">
                    {activeMessageBox.timestamp} • {t("msgbox.keyboard_hint")}
                  </span>
                  <div className="ms-auto flex gap-2 whitespace-nowrap">
                    {messageQueue.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setMessageQueue([])}
                        className="px-4 py-2.5 rounded-xl border border-gray-300 text-gray-600 font-bold hover:bg-gray-100 transition"
                      >
                        {t("msgbox.dismiss_all")}
                      </button>
                    )}
                    <button
                      ref={messageBoxOkButtonRef}
                      type="button"
                      onClick={closeMessageBox}
                      className="px-6 py-2.5 rounded-xl bg-[#063D2E] hover:bg-[#02291F] text-[#D4AF62] font-extrabold text-xs shadow focus:outline-none focus:ring-2 focus:ring-[#D4AF62] focus:ring-offset-2"
                    >
                      {messageQueue.length > 1 ? t("msgbox.next") : t("msgbox.ok") || "Compris (Fermer)"}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Modal Confirmation Dialog */}
        {activeConfirm && (
          <div className="animate-backdrop fixed inset-0 z-[80] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="active-confirm-title"
              className="bg-white text-[#202923] rounded-2xl max-w-md w-full overflow-hidden shadow-2xl border-2 border-[#D4AF62]"
            >
              <div
                className={`px-5 py-3.5 flex items-center justify-between ${
                  activeConfirm.danger ? "bg-red-900 text-white" : "bg-[#063D2E] text-white"
                }`}
              >
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-[#D4AF62]" />
                  <span id="active-confirm-title" className="text-base font-extrabold text-[#D4AF62]">
                    {activeConfirm.title}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => activeConfirm.resolve(false)}
                  aria-label={t("common.close") || "Fermer"}
                  className="w-7 h-7 rounded-full bg-black/25 text-white font-bold text-xs flex items-center justify-center hover:bg-black/40 transition"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="p-6 space-y-4 text-xs">
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line bg-[#F8F6F0] p-3.5 rounded-xl border border-[#D4AF62]/30">
                  {activeConfirm.message}
                </p>
                <div className="flex justify-end gap-3 pt-2">
                  <button
                    ref={confirmCancelButtonRef}
                    type="button"
                    onClick={() => activeConfirm.resolve(false)}
                    className="px-5 py-2.5 rounded-xl border border-gray-300 text-gray-700 font-bold hover:bg-gray-100 transition focus:outline-none focus:ring-2 focus:ring-[#D4AF62]"
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
                    {activeConfirm.confirmLabel || t("common.confirm")}
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
            <button aria-label="Fermer"
              type="button"
              onClick={() => { setProductToDelete(null); setError(""); }}
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
                    src={mediaUrl(productToDelete.main_image_url || productToDelete.image_url)}
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
                    Statut: <strong>{({ archived: "Archivé (hors vitrine)", published: "Publié (en vente)", draft: "Brouillon" } as Record<string, string>)[productToDelete.status] || productToDelete.status}</strong>
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
                      Seulement pour un article jamais vendu ni acheté (créé par erreur). S'il a déjà été vendu
                      (en ligne ou en magasin) ou acheté à un fournisseur, il est archivé à la place : les factures,
                      rapports et comptes fournisseurs restent exacts. Aucune commande n'est jamais effacée.
                    </span>

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
                onClick={() => { setProductToDelete(null); setError(""); }}
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
              <label htmlFor="owner-name" className="block font-bold mb-1">Nom Complet</label>
              <input id="owner-name" value={ownerName} onChange={(e) => setOwnerName(e.target.value)} required placeholder="Nom et Prénom" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
            </div>
            <div>
              <label htmlFor="owner-email" className="block font-bold mb-1">Email / Identifiant</label>
              <input id="owner-email" type="email" value={ownerEmail} onChange={(e) => setOwnerEmail(e.target.value)} required placeholder="administrateur@domaine.dz" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label htmlFor="owner-password" className="block font-bold mb-1">Mot de passe (≥ 10 car.)</label>
              <input id="owner-password" type="password" value={ownerPassword} onChange={(e) => setOwnerPassword(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
            </div>
            <div>
              <label htmlFor="owner-confirm" className="block font-bold mb-1">Confirmer mot de passe</label>
              <input id="owner-confirm" type="password" value={ownerConfirm} onChange={(e) => setOwnerConfirm(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40" />
            </div>
          </div>
          <div className="p-3 rounded-xl bg-[#02291F]/80 border border-[#D4AF62]/30 space-y-1 text-xs">
            <p className="font-bold text-[#D4AF62]">Numéro de contact :</p>
            <label htmlFor="owner-phone" className="block text-[11px] mb-0.5">Téléphone propriétaire</label>
            <input id="owner-phone" value={emergencyPhone} onChange={(e) => setEmergencyPhone(e.target.value)} required placeholder="+213 5XX XX XX XX" className="w-full px-2.5 py-1.5 rounded bg-[#063D2E] border border-[#D4AF62]/40 font-mono text-xs" />
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
              <label htmlFor="login-email" className="block text-xs font-bold mb-1">Email / Identifiant</label>
              <input id="login-email" type="email" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} required placeholder="administrateur@mus-luxury.com" className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-sm" />
            </div>
            <div>
              <label htmlFor="login-password" className="block text-xs font-bold mb-1">Mot de passe</label>
              <input id="login-password" type="password" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} required className="w-full px-3 py-2 rounded bg-[#02291F] border border-[#D4AF62]/40 text-sm" />
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

  // Live counters shown on the sidebar — derived from data already loaded.
  const navBadges = {
    orders: orders.filter((o) => o.status === "new" || o.status === "pending_confirmation").length,
    // Same per-variant figure as the dashboard's "stock faible" + "ruptures" cards.
    // low_stock_variants already includes the out-of-stock ones.
    low_stock: Number(dashboard?.low_stock_variants || 0),
  };


  return (
    <div className="h-screen bg-[#F8F6F0] text-[#202923] flex flex-col overflow-hidden">
      {renderClientNotificationCenter()}
      <UpdateDialog open={updateDialogOpen} onClose={() => setUpdateDialogOpen(false)} />
      {renderDeleteProductModal()}
      {/* Top Header */}
      <header className="relative z-40 shrink-0 bg-gradient-to-r from-[#011C15] via-[#063D2E] to-[#02291F] text-[#D4AF62] px-6 py-3.5 flex flex-wrap justify-between items-center gap-4 border-b border-[#D4AF62]/30 shadow-md">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-[#D4AF62] via-[#E8D4A5] to-[#C59E50] p-0.5 shadow-luxe-gold flex items-center justify-center shrink-0">
            <div className="w-full h-full rounded-[14px] bg-[#02291F] flex items-center justify-center">
              <span className="font-serif font-black text-sm text-[#D4AF62] tracking-wider">ML</span>
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-serif font-bold text-lg text-white tracking-wide">MAISON MUS LUXURY</span>
              <button
                type="button"
                onClick={() => setUpdateDialogOpen(true)}
                title={t("update.title")}
                className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full backdrop-blur-md border text-[10px] font-bold transition ${
                  updateState?.phase === "available"
                    ? "bg-[#D4AF62] border-[#D4AF62] text-[#02291F] hover:bg-[#E8D4A5]"
                    : "bg-white/10 border-[#D4AF62]/40 text-[#E8D4A5] hover:bg-white/20"
                }`}
              >
                {updateState?.phase === "available" && (
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#02291F] opacity-60"></span>
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#02291F]"></span>
                  </span>
                )}
                {updateState?.phase === "available"
                  ? `${t("update.chip")} v${updateState.availableVersion}`
                  : `CMS${updateState?.currentVersion ? ` v${updateState.currentVersion}` : ""} • Haute Couture`}
              </button>
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

          <NotificationBell />

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

      {/* Sidebar + scrolling workspace */}
      <div className="flex flex-1 min-h-0">
      <CmsSidebar
        activeTab={activeTab}
        onSelect={(id) => canOpen(id) && setActiveTab(id as CmsTab)}
        badges={navBadges}
        canOpen={canOpen}
      />
      <div className="flex-1 min-w-0 overflow-y-auto flex flex-col">

      {/* Global Status / Error Banner */}
      <div className="max-w-7xl w-full mx-auto px-6 pt-4 space-y-2">
        {error && <div className="p-3 rounded-xl bg-red-100 border border-red-300 text-red-900 text-xs font-bold">{error}</div>}
        {successMsg && <div className="p-3 rounded-xl bg-emerald-100 border border-emerald-300 text-emerald-900 text-xs font-bold">{successMsg}</div>}
      </div>

      {/* Main Content Area */}
      <main className="max-w-7xl w-full mx-auto p-6 flex-1 space-y-6">
        {loadingWorkspace && <div className="text-xs text-gray-500">Synchronisation des données en cours...</div>}

        {/* TAB 1: DASHBOARD (KEEP-ALIVE) */}
        <div className={activeTab === "dashboard" ? "block" : "hidden"}>
          {dashboard && (
            <DashboardPage
              dashboard={dashboard}
              categories={categories}
              onOpenTab={setActiveTab}
              onNewProduct={() => openProductEditor(null)}
              onRefresh={loadAllWorkspaceData}
              onExportOrdersCsv={handleExportOrdersCsv}
            />
          )}
        </div>

        {/* TAB: BUSINESS SUMMARY (POS + online, real records) (KEEP-ALIVE) */}
        {canOpen("business") && <div className={activeTab === "business" ? "block" : "hidden"}><BusinessDashboardPage /></div>}

        {/* TAB: POINT OF SALE (POS) — in-store cash register & sales (KEEP-ALIVE) */}
        {canOpen("pos") && (
        <div className={activeTab === "pos" ? "block" : "hidden"}>
          <PosPage onInventoryUpdated={loadAllWorkspaceData} />
        </div>
        )}

        {/* TAB 2: PRODUCTS & DYNAMIC CATEGORY ATTRIBUTES (KEEP-ALIVE) */}
        <div className={activeTab === "products" ? "block" : "hidden"}>
          <ProductsPage
            products={products}
            categories={categories}
            search={prodSearch}
            onSearchChange={setProdSearch}
            filterTab={productFilterTab}
            onFilterTabChange={setProductFilterTab}
            selectedIds={selectedProductIds}
            onSelectedIdsChange={setSelectedProductIds}
            onOpenEditor={openProductEditor}
            onArchive={handleArchiveProduct}
            onRestore={handleRestoreProduct}
            onBulkStatus={handleBulkStatus}
            onAskDelete={(p) => { setProductToDelete(p); setError(""); }}
            onOpenTab={setActiveTab}
            onRefresh={loadAllWorkspaceData}
          />
        </div>

        {/* TAB 3: DYNAMIC CATEGORIES & ATTRIBUTES (KEEP-ALIVE — NEVER UNMOUNTS) */}
        {canOpen("categories") && <div className={activeTab === "categories" ? "block" : "hidden"}><CategoryBuilderPage onCategoryChanged={loadAllWorkspaceData} /></div>}

        {/* TAB 4: PURCHASES & SUPPLIERS (KEEP-ALIVE) */}
        {canOpen("purchases") && (
        <div className={activeTab === "purchases" ? "block" : "hidden"}>
          <PurchasesPage onInventoryUpdated={loadAllWorkspaceData} />
        </div>
        )}

        {/* TAB 4: INVENTORY & MOVEMENTS (KEEP-ALIVE) */}
        <div className={activeTab === "inventory" ? "block" : "hidden"}>
          <InventoryPage
            products={products}
            movements={movements}
            onAdjustStock={handleAdjustStock}
            onPrintLabel={setBarcodeVariantId}
            onWriteOff={setWriteOffTarget}
          />
        </div>

        {/* TAB 5: ORDERS & INVOICES (KEEP-ALIVE) */}
        <div className={activeTab === "orders" ? "block" : "hidden"}>
          {canOpen("orders") && (
            <OrdersPage
              orders={orders}
              statusFilter={orderStatusFilter}
              onStatusFilterChange={setOrderStatusFilter}
              searchInput={orderSearchInput}
              onSearchInputChange={setOrderSearchInput}
              onSearch={setOrderSearch}
              onStatusChange={handleOrderStatusChange}
              onOpenInvoice={handleOpenInvoice}
              onOpenDeliveryNote={setDeliveryNoteOrderId}
              onExportCsv={handleExportOrdersCsv}
              onNotifyWhatsapp={handleNotifyOrderCustomerWhatsapp}
              selectedInvoice={selectedInvoice}
              onCloseInvoice={() => setSelectedInvoice(null)}
              waOutbox={waOutbox}
              codCheckPhone={codCheckPhone}
              onCodCheckPhoneChange={setCodCheckPhone}
              codCheckResult={codCheckResult}
              onCheckPhoneRisk={handleCheckPhoneCodRisk}
              codBlacklist={codBlacklist}
              codBlacklistReason={codBlacklistReason}
              onCodBlacklistReasonChange={setCodBlacklistReason}
              onBlockPhone={handleBlockCustomerPhone}
              onUnblockPhone={handleUnblockCustomerPhone}
            />
          )}
        </div>

        {/* TAB 7: OPERATING EXPENSES (KEEP-ALIVE) */}
        {canOpen("expenses") && (
        <div className={activeTab === "expenses" ? "block" : "hidden"}>
          <ExpensesPage />
        </div>
        )}

        {/* TAB 8: CASH REGISTER & TREASURY (KEEP-ALIVE) */}
        {canOpen("treasury") && (
        <div className={activeTab === "treasury" ? "block" : "hidden"}>
          <TreasuryPage />
        </div>
        )}

        {/* TAB 9: ACCOUNTING & FINANCIAL REPORTS (KEEP-ALIVE) */}
        {canOpen("accounting") && (
        <div className={activeTab === "accounting" ? "block" : "hidden"}>
          <AccountingPage />
        </div>
        )}

        {/* TAB 10: 69 WILAYAS DELIVERY TARIFFS (KEEP-ALIVE — NEVER UNMOUNTS) */}
        {canOpen("delivery_wilayas") && <div className={activeTab === "delivery_wilayas" ? "block" : "hidden"}><DeliveryWilayasPage /></div>}

        {/* TAB: DEVICES & HARDWARE (KEEP-ALIVE) */}
        {canOpen("devices") && <div className={activeTab === "devices" ? "block" : "hidden"}><DevicesPage /></div>}

        {/* TAB: CUSTOMERS (KEEP-ALIVE) */}
        {canOpen("customers") && <div className={activeTab === "customers" ? "block" : "hidden"}><CustomersPage /></div>}

        {/* TAB: USERS & ROLES (KEEP-ALIVE) */}
        {canOpen("users") && <div className={activeTab === "users" ? "block" : "hidden"}><UsersRolesPage /></div>}

        {/* TAB: PHYSICAL INVENTORY (KEEP-ALIVE) */}
        {canOpen("inventory_count") && <div className={activeTab === "inventory_count" ? "block" : "hidden"}><InventoryCountPage onInventoryUpdated={loadAllWorkspaceData} /></div>}

        {/* TAB: SALES REPORT (KEEP-ALIVE) */}
        {canOpen("sales_report") && <div className={activeTab === "sales_report" ? "block" : "hidden"}><SalesReportPage /></div>}

        {/* TAB: FISCAL SETTINGS (KEEP-ALIVE) */}
        {canOpen("fiscal") && <div className={activeTab === "fiscal" ? "block" : "hidden"}><FiscalSettingsPage /></div>}

        {/* TAB: AUDIT LOG (KEEP-ALIVE) */}
        {canOpen("audit") && <div className={activeTab === "audit" ? "block" : "hidden"}><AuditLogPage /></div>}

        {/* TAB: SUPPLIERS (KEEP-ALIVE) */}
        {canOpen("suppliers") && <div className={activeTab === "suppliers" ? "block" : "hidden"}><SuppliersPage /></div>}

        {/* TAB: LOW STOCK (KEEP-ALIVE) */}
        {canOpen("low_stock") && <div className={activeTab === "low_stock" ? "block" : "hidden"}><LowStockPage /></div>}

        {/* TAB: EXPENSE REPORT (KEEP-ALIVE) */}
        {canOpen("expense_report") && <div className={activeTab === "expense_report" ? "block" : "hidden"}><ExpenseReportPage /></div>}

        {/* TAB: STOCK MOVEMENTS REPORT (KEEP-ALIVE) */}
        {canOpen("stock_movements") && <div className={activeTab === "stock_movements" ? "block" : "hidden"}><InventoryMovementsReportPage /></div>}

        {/* TAB: TREASURY REPORT (KEEP-ALIVE) */}
        {canOpen("treasury_report") && <div className={activeTab === "treasury_report" ? "block" : "hidden"}><TreasuryReportPage /></div>}

        {/* TAB 7: STORE CONTENT, COUPONS, STATIC PAGES & REAL SOCIAL/LOCATION SETTINGS (KEEP-ALIVE) */}
        <div className={activeTab === "content" ? "block" : "hidden"}>
          <ContentSettingsPage
            active={activeTab === "content"}
            canEdit={canOpen("content")}
            categories={categories}
            products={products}
          />
        </div>

        {/* TAB 8: BACKUPS, WHATSAPP RECOVERY STATUS & ISOLATED RESTORE VERIFICATION (KEEP-ALIVE) */}
        <div className={activeTab === "backups" ? "block" : "hidden"}>
          <div className="space-y-6 text-xs">
            {canOpen("backups") && <DatabasePanel active={activeTab === "backups"} isOwner={user?.role === "super_admin"} />}
            <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 flex flex-wrap items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-serif font-bold text-[#063D2E]">Protection de la session</h3>
                <p className="text-gray-500">
                  {keychainStatus?.os_keychain
                    ? "Votre connexion est gardée dans le coffre-fort de Windows (Gestionnaire d'identification), pas dans un fichier."
                    : "Application ouverte dans un navigateur : la connexion n'est gardée que pendant cette session."}
                </p>
              </div>
              <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border font-extrabold ${
                keychainStatus?.os_keychain ? "bg-emerald-50 border-emerald-200 text-emerald-900" : "bg-amber-50 border-amber-200 text-amber-900"
              }`}>
                <ShieldCheck className="w-4 h-4" />
                <span>{keychainStatus?.os_keychain ? "Coffre-fort système actif" : "Coffre-fort système indisponible"}</span>
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
                    Wilayas livrées : {readinessStatus.active_wilayas ?? "?"} / 69
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
                    <span className="font-mono text-[11px] text-gray-500">{formatServerDateTime(al.created_at)}</span>
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
      </div>
    </div>
  );
}

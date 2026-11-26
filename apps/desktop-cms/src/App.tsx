import { readDraft, writeDraft } from "./utils/draftStorage";
import { formatServerDateTime } from "./utils/serverDate";
import { useT } from "./i18n";
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
import { UpdateDialog } from "./components/UpdateDialog";
import { DatabasePanel } from "./components/DatabasePanel";
import {
  NetworkTelemetryState,
  getNetworkTelemetry,
  subscribeNetworkTelemetry,
} from "./utils/networkQueue";
import React, { useEffect, useRef, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { orderStatusLabel } from "./utils/orderStatus";
import { openExternalUrl } from "./utils/openExternal";
import { useEscapeToClose } from "./utils/useEscapeToClose";
import { canOpenTab } from "./utils/tabAccess";
import { copyNewestBackupIfMissing, pcCopiesAvailable } from "./utils/backupCopies";
import { DesktopCmsApi, restoreSessionFromOsKeychain, getApiBaseUrl } from "./api/adminClient";
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
import { ClientNotificationCenter } from "./app/ClientNotificationCenter";
import { DeleteProductModal } from "./app/DeleteProductModal";
import { OwnerSetupScreen } from "./app/OwnerSetupScreen";
import { LoginScreen } from "./app/LoginScreen";
import { AppHeader } from "./app/AppHeader";
import { auditActionLabel, auditEntityLabel } from "./utils/auditLabels";

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
            t("app.pos_outdated_title"),
            t("app.pos_outdated_body", { client: compat.client_version || "1.0.0", min: compat.min_supported_pos_version })
          );
        } else if (compat && compat.deprecated) {
          notifyClientWarning(
            t("app.pos_update_title"),
            t("app.pos_update_body", { v: compat.latest_pos_version })
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
      const close = top?.querySelector<HTMLButtonElement>('button[aria-label="Fermer"], button[aria-label="Close"], button[aria-label="إغلاق"]');
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
  const [codBlacklistReason, setCodBlacklistReason] = useState(() => t("app.cod_default_reason"));
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
      // A late answer for a session that has already ended: nothing to show.
      if (err?.code === "STALE_SESSION_RESPONSE") return;
      if (err?.code === "SESSION_EXPIRED" || err?.message === "SESSION_EXPIRED") {
        setUser(null);
        const msg = t("app.session_expired_msg");
        setError(msg);
        notifyClientWarning(t("app.session_expired_title"), msg);
      } else {
        const tr = notifyClientError(err, t("app.sync_interrupted"), false);
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
        if (copied && !stopped) notifyClientSuccess(t("app.backup_copied_title"), `${copied} — Documents\\Mus Luxury\\Sauvegardes`);
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
      const msg = t("app.owner_pw_short");
      setError(msg);
      notifyClientWarning(t("app.pw_short_title"), msg);
      return;
    }
    if (ownerPassword !== ownerConfirm) {
      const msg = t("app.pw_mismatch");
      setError(msg);
      notifyClientWarning(t("app.pw_confirm_title"), msg);
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
      const okMsg = t("app.owner_created_msg");
      setSuccessMsg(okMsg);
      notifyClientSuccess(t("app.owner_created_title"), okMsg, true);
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.owner_init_refused"));
      setError(tr.message);
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!loginEmail.trim() || !loginPassword) {
      notifyClientWarning(t("app.credentials_required_title"), t("app.credentials_required_body"));
      return;
    }
    try {
      const res = await DesktopCmsApi.login(loginEmail.trim(), loginPassword);
      setUser(res.user);
      notifyClientSuccess(t("app.login_ok_title"), t("app.login_ok_body", { name: res.user.full_name }));
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.login_failed"));
      setError(tr.message);
    }
  }

  // Password recovery handlers removed — the owner resets the password via
  // the server-side CLI described in backend/scripts/emergency_reset_owner.py.

  async function handleArchiveProduct(productId: number) {
    setError("");
    try {
      await DesktopCmsApi.archiveProduct(productId);
      const okMsg = t("app.product_archived_id", { id: productId });
      setSuccessMsg(okMsg);
      notifyClientSuccess(t("app.product_archived_title"), okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.archive_failed"));
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
        const infoMsg = t("app.archived_instead_msg");
        setSuccessMsg(infoMsg);
        notifyClientWarning(t("app.archived_instead_title"), infoMsg);
        setProductToDelete(null);
      } else {
        const okMsg =
          (hard
            ? t("app.product_deleted_named", { name: productToDelete.name_fr })
            : t("app.product_archived_named", { name: productToDelete.name_fr }));
        setSuccessMsg(okMsg);
        notifyClientSuccess(hard ? t("app.product_deleted_title") : t("app.product_archived_title"), okMsg);
        setProductToDelete(null);
      }
      await loadAllWorkspaceData();
      // The dialog gave focus back to the row's « Supprimer » button, which the
      // refreshed list no longer has: keep keyboard users on the product list.
      // The list re-renders a moment later, so watch briefly (1.5 s).
      const started = Date.now();
      const keepFocusOnList = () => {
        const active = document.activeElement;
        if (!active || active === document.body || !active.isConnected) {
          document.querySelector<HTMLElement>("[data-products-search]")?.focus();
          return;
        }
        if (Date.now() - started < 1500) window.setTimeout(keepFocusOnList, 50);
      };
      window.setTimeout(keepFocusOnList, 0);
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.delete_failed"));
      setError(tr.message);
    } finally {
      setDeletingProduct(false);
    }
  }

  async function handleRestoreProduct(productId: number) {
    setError("");
    try {
      await DesktopCmsApi.bulkUpdateProductStatus([productId], "published");
      const okMsg = t("app.product_restored_id", { id: productId });
      setSuccessMsg(okMsg);
      notifyClientSuccess(t("app.product_restored_title"), okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.restore_failed"));
      setError(tr.message);
    }
  }

  async function handleAdjustStock(variantId: number, delta: number) {
    setError("");
    try {
      await DesktopCmsApi.adjustVariantStock(variantId, delta, "cms_manual_adjustment");
      const owner = products.find((p: any) => (p.variants || []).some((v: any) => v.id === variantId));
      const variant: any = owner ? (owner.variants || []).find((v: any) => v.id === variantId) : null;
      const label = variant ? `${owner?.name_fr || ""} — ${variant.title || variant.sku}` : t("app.the_item");
      const okMsg = t("app.stock_fixed", { label, delta: delta > 0 ? `+${delta}` : delta }) +
        (delta < 0 ? t("app.stock_fixed_loss_hint") : "");
      setSuccessMsg(okMsg);
      notifyClientSuccess(t("app.stock_updated_title"), okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.stock_adjust_refused"));
      setError(tr.message);
    }
  }

  async function handleOrderStatusChange(orderId: number, nextStatus: string) {
    setError("");
    const ord = orders.find((o) => o.id === orderId);
    const ref = ord?.order_reference || `#${orderId}`;
    if (nextStatus === "cancelled" || nextStatus === "returned") {
      const ok = await confirmClientAction({
        title: nextStatus === "cancelled" ? t("app.cancel_order") : t("app.order_returned"),
        message: t("app.order_final_msg", { ref }),
        confirmLabel: nextStatus === "cancelled" ? t("app.cancel_order") : t("app.confirm_return"),
        danger: true,
      });
      if (!ok) return;
    }
    try {
      await DesktopCmsApi.updateOrderStatus(orderId, nextStatus);
      const okMsg = t("app.order_status_msg", { ref, status: orderStatusLabel(nextStatus) });
      setSuccessMsg(okMsg);
      notifyClientSuccess(t("app.order_status_updated"), okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.order_status_refused"));
      setError(tr.message);
    }
  }

  async function handleOpenInvoice(orderId: number) {
    setError("");
    try {
      const inv = await DesktopCmsApi.getOrderInvoice(orderId);
      setSelectedInvoice(inv);
      notifyClientSuccess(t("app.invoice_ready_title"), t("app.invoice_ready_body", { ref: inv.order_reference }));
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.invoice_failed"));
      setError(tr.message);
    }
  }

  async function handleCheckPhoneCodRisk() {
    if (!codCheckPhone.trim() || codCheckPhone.trim().length < 8) {
      notifyClientWarning(
        t("app.phone_required_title"),
        t("app.phone_required_body")
      );
      return;
    }
    setError("");
    try {
      const res = await DesktopCmsApi.checkPhoneCodRisk(codCheckPhone.trim());
      setCodCheckResult(res);
      notifyClientSuccess(
        t("app.cod_score_title"),
        t("app.cod_score_body", { phone: res.phone_local, delivered: res.delivered_count, returned: res.returned_count, rate: res.return_rate_percent })
      );
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.cod_check_failed"));
      setError(tr.message);
    }
  }

  async function handleBlockCustomerPhone(phone: string, reason = t("app.cod_default_reason")) {
    if (!phone.trim()) {
      notifyClientWarning(t("app.phone_missing_title"), t("app.phone_missing_body"));
      return;
    }
    setError("");
    try {
      const res = await DesktopCmsApi.addPhoneToCodBlacklist(phone.trim(), reason.trim() || t("app.cod_default_reason"), true);
      setCodCheckResult(res);
      const okMsg = t("app.phone_blocked_body", { phone: res.phone_local });
      setSuccessMsg(okMsg);
      notifyClientSuccess(t("app.phone_blocked_title"), okMsg, true);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.block_failed"));
      setError(tr.message);
    }
  }

  async function handleUnblockCustomerPhone(phone: string) {
    setError("");
    try {
      const res = await DesktopCmsApi.removePhoneFromCodBlacklist(phone);
      setCodCheckResult(res);
      const okMsg = t("app.phone_unblocked_body", { phone: res.phone_local });
      setSuccessMsg(okMsg);
      notifyClientSuccess(t("app.phone_unblocked_title"), okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.unblock_failed"));
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
      const okMsg = t("app.wa_ready_body", { phone: receipt.recipient_local });
      setSuccessMsg(okMsg);
      notifyClientSuccess(t("app.wa_ready_title"), okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.wa_failed"));
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
      const okMsg = t("app.csv_orders_ok_body");
      setSuccessMsg(okMsg);
      notifyClientSuccess(t("app.csv_ok_title"), okMsg);
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.csv_orders_failed"));
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
      const okMsg = t("app.sync_ok_body", { orders: syncRes.missed_orders_count, variants: syncRes.current_variant_stocks?.length || 0 });
      setSuccessMsg(okMsg);
      notifyClientSuccess(t("app.sync_ok_title"), okMsg);
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.sync_delta_failed"));
      setError(tr.message);
    }
  }

  async function handleBulkStatus(status: "published" | "draft" | "archived") {
    if (selectedProductIds.length === 0) {
      notifyClientWarning(
        t("app.no_selection_title"),
        t("app.no_selection_body")
      );
      return;
    }
    setError("");
    try {
      const count = selectedProductIds.length;
      await DesktopCmsApi.bulkUpdateProductStatus(selectedProductIds, status);
      setSelectedProductIds([]);
      const okMsg = t("app.bulk_ok_body", { status: t(`status_label.${status}`), count });
      setSuccessMsg(okMsg);
      notifyClientSuccess(t("app.bulk_ok_title"), okMsg);
      await loadAllWorkspaceData();
    } catch (err: any) {
      const tr = notifyClientError(err, t("app.bulk_failed"));
      setError(tr.message);
    }
  }

  // handleRotateEmergencyCode removed with the WhatsApp-recovery flow.

  function renderClientNotificationCenter() {
    return (
      <ClientNotificationCenter
        messageQueue={messageQueue} setMessageQueue={setMessageQueue} closeMessageBox={closeMessageBox}
        activeConfirm={activeConfirm} messageBoxOkButtonRef={messageBoxOkButtonRef}
        confirmCancelButtonRef={confirmCancelButtonRef}
      />
    );
  }

  function renderDeleteProductModal() {
    return (
      <DeleteProductModal
        productToDelete={productToDelete} deletingProduct={deletingProduct} error={error}
        setProductToDelete={setProductToDelete} setError={setError}
        handleConfirmDeleteProduct={handleConfirmDeleteProduct}
      />
    );
  }

  if (checkingSetup) {
    return <div className="p-10 text-center text-white bg-[#02291F] min-h-screen">{t("app.starting_session")}</div>;
  }

  if (requiresOwnerSetup) {
    return (
      <OwnerSetupScreen
        overlays={<>{renderClientNotificationCenter()}{renderDeleteProductModal()}</>}
        error={error}
        ownerName={ownerName} setOwnerName={setOwnerName} ownerEmail={ownerEmail} setOwnerEmail={setOwnerEmail}
        ownerPassword={ownerPassword} setOwnerPassword={setOwnerPassword} ownerConfirm={ownerConfirm} setOwnerConfirm={setOwnerConfirm}
        emergencyPhone={emergencyPhone} setEmergencyPhone={setEmergencyPhone}
        handleFirstTimeSetup={handleFirstTimeSetup}
      />
    );
  }

  if (!user) {
    return (
      <LoginScreen
        overlays={<>{renderClientNotificationCenter()}{renderDeleteProductModal()}</>}
        successMsg={successMsg} error={error}
        loginEmail={loginEmail} setLoginEmail={setLoginEmail} loginPassword={loginPassword} setLoginPassword={setLoginPassword}
        handleLogin={handleLogin} showServerConfig={showServerConfig} setShowServerConfig={setShowServerConfig}
        serverUrl={serverUrl} setServerUrl={setServerUrl}
      />
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
      <AppHeader user={user} updateState={updateState} setUpdateDialogOpen={setUpdateDialogOpen}
        netTelemetry={netTelemetry} handleDeltaSync={handleDeltaSync} setUser={setUser} />

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
        {loadingWorkspace && <div className="text-xs text-gray-500">{t("app.syncing_data")}</div>}

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
                <h3 className="text-base font-serif font-bold text-[#063D2E]">{t("app.session_protection")}</h3>
                <p className="text-gray-500">
                  {keychainStatus?.os_keychain
                    ? t("app.keychain_on_desc")
                    : t("app.keychain_off_desc")}
                </p>
              </div>
              <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border font-extrabold ${
                keychainStatus?.os_keychain ? "bg-emerald-50 border-emerald-200 text-emerald-900" : "bg-amber-50 border-amber-200 text-amber-900"
              }`}>
                <ShieldCheck className="w-4 h-4" />
                <span>{keychainStatus?.os_keychain ? t("app.keychain_on") : t("app.keychain_off")}</span>
              </span>
            </div>
            <div className="bg-white p-6 rounded-2xl border border-[#D4AF62]/40 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-serif font-bold text-[#063D2E] flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-[#D4AF62]" />
                  <span>{t("app.audit_title", { n: auditLogs.length })}</span>
                </h3>
                {readinessStatus && (
                  <span className="px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-900 font-bold text-[11px]">
                    {t("app.wilayas_served", { n: readinessStatus.active_wilayas ?? "?" })}
                  </span>
                )}
              </div>
              <div className="max-h-48 overflow-y-auto divide-y border rounded-xl">
                {auditLogs.slice(0, 12).map((al: any) => (
                  <div key={al.id} className="p-2.5 flex flex-wrap items-center justify-between gap-2 hover:bg-[#F8F6F0]">
                    <div>
                      <span className="px-2 py-0.5 rounded bg-[#063D2E] text-[#D4AF62] font-mono font-bold text-[10px] mr-2">
                        {auditActionLabel(al.action, al.action_label)}
                      </span>
                      <span className="font-bold text-[#202923] mr-2">{auditEntityLabel(al.entity_type, al.entity_label)} #{al.entity_id}</span>
                      <span className="text-gray-500">{t("app.by_user", { who: al.admin_email || `Admin #${al.admin_user_id || 1}` })}</span>
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

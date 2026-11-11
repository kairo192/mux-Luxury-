// ============================================================================
// MUS LUXURY DESKTOP CMS — CLIENT-SIDE ERROR SANITIZER, MESSAGE BOX & TOAST BUS
// Guarantees:
// 1. Zero raw backend errors, stack traces, SQL errors, or "[object Object]"
//    ever leak into the Desktop CMS UI.
// 2. Every HTTP status (400, 401, 403, 404, 409, 413, 422, 429, 500, 503) and
//    network/timeout failure is translated into clear, actionable French.
// 3. Global event bus powers both the Floating Toast Notification Center and
//    the Modal Client Message Box across all 8 CMS tabs and sub-pages.
// ============================================================================

export type ClientNotificationType = "success" | "error" | "warning" | "info";

export interface ClientNotificationItem {
  id: string;
  type: ClientNotificationType;
  title: string;
  message: string;
  timestamp: string;
  showModalBox?: boolean;
  /** epoch ms — used for ordering, dedupe and the notification history. */
  createdAt?: number;
  /** Groups entries in the notification history (order, update, sync, system). */
  category?: ClientNotificationCategory;
  /** Also raise a native OS (Windows) notification when the CMS is in the background. */
  os?: boolean;
  /** Optional call-to-action rendered on the toast (e.g. "Voir la commande"). */
  action?: { label: string; onClick: () => void };
  /** Override the auto-dismiss delay of the toast (ms). 0 = stays until closed. */
  durationMs?: number;
}

export type ClientNotificationCategory = "order" | "update" | "sync" | "system";

type NotificationListener = (item: ClientNotificationItem) => void;
const listeners: Set<NotificationListener> = new Set();

export function subscribeClientNotifications(fn: NotificationListener): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export class ClientSafeApiError extends Error {
  public readonly status: number;
  public readonly title: string;
  public readonly userMessage: string;
  public readonly code: string;

  constructor(opts: { status: number; title: string; userMessage: string; code?: string }) {
    super(opts.userMessage);
    this.name = "ClientSafeApiError";
    this.status = opts.status;
    this.title = opts.title;
    this.userMessage = opts.userMessage;
    this.code = opts.code || `HTTP_${opts.status}`;
  }
}

const FIELD_LABELS_FR: Record<string, string> = {
  full_name: "Nom complet",
  email: "Adresse e-mail",
  password: "Mot de passe",
  new_password: "Nouveau mot de passe",
  verification_code: "Code de vérification",
  phone: "Numéro de téléphone",
  whatsapp_phone: "Numéro WhatsApp",
  emergency_phone: "Téléphone de secours",
  name_fr: "Nom en français",
  title_fr: "Titre en français",
  content_fr: "Contenu en français",
  slug: "Identifiant URL (slug)",
  sku: "Référence SKU",
  selling_price_dzd: "Prix de vente (DA)",
  purchase_cost_dzd: "Coût d'achat (DA)",
  stock_qty: "Quantité en stock",
  change_qty: "Ajustement de stock",
  wilaya_code: "Code Wilaya",
  commune: "Commune",
  delivery_address: "Adresse de livraison",
  code: "Code promotionnel",
  discount_value: "Valeur de remise",
  min_order_dzd: "Montant minimum de commande",
  attr_key: "Clé technique d'attribut",
  label_fr: "Libellé d'attribut (FR)",
};

export function sanitizeAndTranslateError(
  rawError: unknown,
  status = 0,
  contextPath = "",
  fallbackTitle = "Action interrompue"
): { title: string; message: string; code: string; status: number } {
  if (rawError instanceof ClientSafeApiError) {
    return {
      title: rawError.title,
      message: rawError.userMessage,
      code: rawError.code,
      status: rawError.status,
    };
  }

  // 1. Handle FastAPI 422 Pydantic validation error arrays cleanly
  if (status === 422 || (typeof rawError === "object" && rawError !== null && Array.isArray((rawError as any).detail))) {
    const detailArr = Array.isArray((rawError as any)?.detail)
      ? (rawError as any).detail
      : Array.isArray(rawError)
      ? rawError
      : [];
    if (detailArr.length > 0) {
      const fields = detailArr
        .map((item: any) => {
          const loc = Array.isArray(item?.loc) ? String(item.loc[item.loc.length - 1]) : "";
          return FIELD_LABELS_FR[loc] || loc;
        })
        .filter(Boolean);
      const uniqueFields = Array.from(new Set(fields));
      const fieldText = uniqueFields.length > 0 ? ` (${uniqueFields.join(", ")})` : "";
      return {
        title: "Champs du formulaire invalides ou incomplets",
        message: `Veuillez vérifier les informations saisies${fieldText}. Assurez-vous que les formats, longueurs et montants en DA sont valides.`,
        code: "VALIDATION_ERROR",
        status: 422,
      };
    }
    return {
      title: "Données saisies non conformes",
      message: "Certains champs du formulaire sont incomplets ou contiennent des caractères non autorisés.",
      code: "VALIDATION_ERROR",
      status: 422,
    };
  }

  // Extract raw string safely without ever producing "[object Object]"
  let rawText = "";
  if (typeof rawError === "string") {
    rawText = rawError;
  } else if (rawError instanceof Error) {
    rawText = rawError.message || "";
  } else if (typeof rawError === "object" && rawError !== null) {
    const d = (rawError as any).detail ?? (rawError as any).message ?? "";
    rawText = typeof d === "string" ? d : JSON.stringify(d);
  }

  const lower = rawText.toLowerCase();

  // 2. Network, offline, and timeout errors
  if (
    lower.includes("abort") ||
    lower.includes("timed out") ||
    lower.includes("timeout")
  ) {
    return {
      title: "Délai de réponse dépassé",
      message: "Le serveur met trop de temps à répondre. Vos brouillons sont conservés localement — veuillez réessayer.",
      code: "NETWORK_TIMEOUT",
      status: 0,
    };
  }
  if (
    lower.includes("failed to fetch") ||
    lower.includes("networkerror") ||
    lower.includes("load failed") ||
    lower.includes("econnrefused")
  ) {
    return {
      title: "Connexion au serveur indisponible",
      message: "Impossible de joindre le serveur Mus Luxury. Vérifiez votre connexion réseau ou l'état du service API.",
      code: "NETWORK_OFFLINE",
      status: 0,
    };
  }

  // 3. Authentication & Session Expiration (401)
  if (status === 401 || rawText === "SESSION_EXPIRED") {
    if (contextPath.includes("/admin/auth/login") || lower.includes("invalid email or password")) {
      return {
        title: "Identifiants incorrects",
        message: "L'adresse e-mail ou le mot de passe saisi est incorrect. En cas d'oubli, contactez l'administrateur système sur le serveur.",
        code: "AUTH_INVALID_CREDENTIALS",
        status: 401,
      };
    }
    return {
      title: "Session sécurisée expirée",
      message: "Par mesure de sécurité, votre session a expiré. Vos brouillons en cours sont sauvegardés — veuillez vous reconnecter.",
      code: "SESSION_EXPIRED",
      status: 401,
    };
  }

  // 4. Permission Denied / RBAC / Anti-Retour COD (403)
  if (status === 403 || lower.includes("insufficient permissions")) {
    if (lower.includes("anti-retour") || lower.includes("bloqué")) {
      return {
        title: "Numéro bloqué (Protection Anti-Retour COD)",
        message: rawText,
        code: "COD_BLACKLISTED",
        status: 403,
      };
    }
    return {
      title: "Accès refusé — Permissions insuffisantes",
      message: "Votre compte ne dispose pas des droits requis pour exécuter cette opération. Contactez l'administrateur propriétaire.",
      code: "PERMISSION_DENIED",
      status: 403,
    };
  }

  // 5. Not Found (404)
  if (status === 404 || lower.includes("not found") || lower.includes("introuvable")) {
    return {
      title: "Élément introuvable",
      message: "L'élément demandé est introuvable ou a déjà été supprimé.",
      code: "NOT_FOUND",
      status: 404,
    };
  }

  // 6. Conflict / Optimistic Locking / Duplicate SKU / Stock (409)
  if (status === 409 || lower.includes("conflict") || lower.includes("already exists") || lower.includes("unique")) {
    if (lower.includes("version") || lower.includes("synchronization conflict")) {
      return {
        title: "Conflit de modification simultanée",
        message: "Cette fiche produit a été modifiée depuis un autre poste. Rechargez les données avant d'enregistrer vos changements.",
        code: "VERSION_CONFLICT",
        status: 409,
      };
    }
    if (lower.includes("insufficient stock") || lower.includes("stock")) {
      return {
        title: "Stock disponible insuffisant",
        message: "La quantité demandée dépasse le stock actuellement disponible pour cette variante.",
        code: "INSUFFICIENT_STOCK",
        status: 409,
      };
    }
    if (lower.includes("already used by") || lower.includes("migration")) {
      return {
        title: "Attribut utilisé par des produits existants",
        message: "Cet attribut est rattaché à des fiches produits actives. Confirmez la migration forcée pour le retirer.",
        code: "ATTRIBUTE_IN_USE",
        status: 409,
      };
    }
    return {
      title: "Doublon détecté dans le catalogue",
      message: "Une entrée portant le même identifiant (Slug, SKU ou Code) existe déjà. Veuillez choisir un identifiant unique.",
      code: "DUPLICATE_RESOURCE",
      status: 409,
    };
  }

  // 7. File Size Too Large (413)
  if (status === 413 || lower.includes("exceeds maximum allowed size")) {
    return {
      title: "Image trop volumineuse (Max 5 Mo)",
      message: "Le fichier sélectionné dépasse la limite de 5 Mo. Veuillez compresser l'image ou choisir un format JPEG, PNG ou WEBP.",
      code: "PAYLOAD_TOO_LARGE",
      status: 413,
    };
  }

  // 8. Rate Limit (429)
  if (status === 429 || lower.includes("rate limit")) {
    return {
      title: "Protection anti-surcharge activée",
      message: "Vous avez effectué trop de requêtes rapprochées. Veuillez patienter quelques secondes avant de réessayer.",
      code: "RATE_LIMITED",
      status: 429,
    };
  }

  // 9. Bad Request (400) — translate known English backend business rules into French
  if (status === 400) {
    if (lower.includes("terminal status") || lower.includes("status transition")) {
      return {
        title: "Transition de statut non autorisée",
        message: "Une commande déjà annulée ou retournée est verrouillée. Seule une commande livrée peut passer au statut « Retournée ».",
        code: "INVALID_STATUS_TRANSITION",
        status: 400,
      };
    }
    if (lower.includes("negative stock") || lower.includes("below zero")) {
      return {
        title: "Stock négatif interdit",
        message: "L'ajustement demandé entraînerait un stock inférieur à zéro. Vérifiez la quantité saisie.",
        code: "NEGATIVE_STOCK_BLOCKED",
        status: 400,
      };
    }
    if (lower.includes("path traversal") || lower.includes("binary signature") || lower.includes("unsupported image") || lower.includes("malicious")) {
      return {
        title: "Fichier image non valide ou refusé",
        message: "Seuls les fichiers images authentiques aux formats JPEG (.jpg), PNG (.png) et WEBP (.webp) sont acceptés.",
        code: "INVALID_IMAGE_FILE",
        status: 400,
      };
    }
    if (lower.includes("coupon") || lower.includes("code promo")) {
      return {
        title: "Code promotionnel non applicable",
        message: "Ce code promo est invalide, a atteint sa limite d'utilisation ou le montant minimum n'est pas atteint.",
        code: "COUPON_INVALID",
        status: 400,
      };
    }
  }

  // 10. Block any internal technical/SQL/Python/stack strings from ever reaching the user
  const technicalPatterns = /(sqlite3|postgres|psycopg|traceback|exception|operationalerror|integrityerror|syntaxerror|typeerror|referenceerror|\[object object\]|internal server error|http error)/i;
  if (status >= 500 || technicalPatterns.test(rawText) || !rawText.trim()) {
    return {
      title: fallbackTitle,
      message: "L'opération n'a pas pu être finalisée par le serveur. Vos données sont intactes — veuillez vérifier votre saisie et réessayer.",
      code: "SERVER_ERROR_SANITIZED",
      status: status || 500,
    };
  }

  // If the message is already a clean French business message, keep it; otherwise wrap in polite French
  const looksEnglishTechnical = /(invalid|missing|failed|error|unauthorized|forbidden|required|must be|cannot|not found)/i.test(rawText);
  if (looksEnglishTechnical) {
    return {
      title: fallbackTitle,
      message: "L'action demandée n'a pas pu être validée. Veuillez vérifier les champs saisis et réessayer.",
      code: `CLIENT_SAFE_${status || 400}`,
      status: status || 400,
    };
  }

  return {
    title: fallbackTitle,
    message: rawText,
    code: `HTTP_${status || 400}`,
    status: status || 400,
  };
}

export function notifyClient(opts: {
  type: ClientNotificationType;
  title: string;
  message: string;
  showModalBox?: boolean;
  category?: ClientNotificationCategory;
  os?: boolean;
  action?: { label: string; onClick: () => void };
  durationMs?: number;
}): ClientNotificationItem {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  const ss = String(now.getSeconds()).padStart(2, "0");
  const item: ClientNotificationItem = {
    id: `notif_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    type: opts.type,
    title: opts.title,
    message: opts.message,
    timestamp: `${hh}:${mm}:${ss}`,
    showModalBox: opts.showModalBox ?? (opts.type === "error" || opts.type === "warning"),
    createdAt: now.getTime(),
    category: opts.category ?? "system",
    os: opts.os ?? false,
    action: opts.action,
    durationMs: opts.durationMs,
  };
  listeners.forEach((fn) => fn(item));
  return item;
}

export function notifyClientSuccess(title: string, message: string, showModalBox = false): ClientNotificationItem {
  return notifyClient({ type: "success", title, message, showModalBox });
}

export function notifyClientWarning(title: string, message: string, showModalBox = true): ClientNotificationItem {
  return notifyClient({ type: "warning", title, message, showModalBox });
}

export function notifyClientError(
  err: unknown,
  fallbackTitle = "Opération impossible",
  showModalBox = true
): { title: string; message: string; code: string } {
  const translated = sanitizeAndTranslateError(err, (err as any)?.status || 0, "", fallbackTitle);
  notifyClient({
    type: "error",
    title: translated.title,
    message: translated.message,
    showModalBox,
  });
  return translated;
}

export interface ClientConfirmRequest {
  id: string;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  resolve: (val: boolean) => void;
}

type ConfirmListener = (req: ClientConfirmRequest | null) => void;
const confirmListeners: Set<ConfirmListener> = new Set();
const confirmQueue: ClientConfirmRequest[] = [];
let currentConfirm: ClientConfirmRequest | null = null;

function processNextConfirm() {
  if (currentConfirm || confirmQueue.length === 0) {
    if (!currentConfirm) {
      confirmListeners.forEach((fn) => fn(null));
    }
    return;
  }
  const nextReq = confirmQueue.shift()!;
  currentConfirm = nextReq;
  confirmListeners.forEach((fn) => fn(nextReq));
}

export function clearPendingClientConfirms(): void {
  if (currentConfirm) {
    const active = currentConfirm;
    currentConfirm = null;
    try {
      active.resolve(false);
    } catch { /* ignore */ }
  }
  while (confirmQueue.length > 0) {
    const queued = confirmQueue.shift()!;
    try {
      queued.resolve(false);
    } catch { /* ignore */ }
  }
  confirmListeners.forEach((fn) => fn(null));
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    clearPendingClientConfirms();
  });
}

export function subscribeClientConfirm(fn: ConfirmListener): () => void {
  confirmListeners.add(fn);
  fn(currentConfirm);
  return () => {
    confirmListeners.delete(fn);
  };
}

export function confirmClientAction(opts: {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}): Promise<boolean> {
  return new Promise<boolean>((resolve) => {
    let resolved = false;
    const reqId = `confirm_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const req: ClientConfirmRequest = {
      id: reqId,
      title: opts.title,
      message: opts.message,
      confirmLabel: opts.confirmLabel,
      cancelLabel: opts.cancelLabel,
      danger: opts.danger,
      resolve: (val: boolean) => {
        if (resolved) return;
        resolved = true;
        resolve(val);
        if (currentConfirm?.id === reqId) {
          currentConfirm = null;
          processNextConfirm();
        }
      },
    };
    confirmQueue.push(req);
    processNextConfirm();
  });
}

if (typeof window !== "undefined") {
  (window as any).__confirmClientAction = confirmClientAction;
}

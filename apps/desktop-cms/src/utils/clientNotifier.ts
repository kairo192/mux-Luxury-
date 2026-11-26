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

import { tr } from "../i18n/translations";

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

const FIELD_KEYS = new Set<string>([
  "full_name",
  "email",
  "password",
  "new_password",
  "verification_code",
  "phone",
  "whatsapp_phone",
  "emergency_phone",
  "name_fr",
  "title_fr",
  "content_fr",
  "slug",
  "sku",
  "selling_price_dzd",
  "purchase_cost_dzd",
  "stock_qty",
  "change_qty",
  "wilaya_code",
  "commune",
  "delivery_address",
  "code",
  "discount_value",
  "min_order_dzd",
  "attr_key",
  "label_fr",
]);

function fieldLabel(loc: string): string {
  return FIELD_KEYS.has(loc) ? tr(`field.${loc}`) : loc;
}

export function sanitizeAndTranslateError(
  rawError: unknown,
  status = 0,
  contextPath = "",
  fallbackTitle = tr("errors.fallback_title")
): { title: string; message: string; code: string; status: number } {
  if (rawError instanceof ClientSafeApiError) {
    return {
      title: rawError.title,
      message: rawError.userMessage,
      code: rawError.code,
      status: rawError.status,
    };
  }

  // 1. Handle FastAPI 422 Pydantic validation error arrays cleanly. A 422 whose
  // detail is a sentence (a rule of the shop: "invalid barcode", "add a photo
  // to sell online"…) is shown as it is, further down.
  const sentence422 = status === 422 && typeof (rawError as any)?.detail === "string" && (rawError as any).detail.trim() !== "";
  if (!sentence422 && (status === 422 || (typeof rawError === "object" && rawError !== null && Array.isArray((rawError as any).detail)))) {
    const detailArr = Array.isArray((rawError as any)?.detail)
      ? (rawError as any).detail
      : Array.isArray(rawError)
      ? rawError
      : [];
    if (detailArr.length > 0) {
      const fields = detailArr
        .map((item: any) => {
          const loc = Array.isArray(item?.loc) ? String(item.loc[item.loc.length - 1]) : "";
          return fieldLabel(loc);
        })
        .filter(Boolean);
      const uniqueFields = Array.from(new Set(fields));
      const fieldText = uniqueFields.length > 0 ? ` (${uniqueFields.join(", ")})` : "";
      return {
        title: tr("errors.validation_title"),
        message: tr("errors.validation_body", { fields: fieldText }),
        code: "VALIDATION_ERROR",
        status: 422,
      };
    }
    return {
      title: tr("errors.invalid_data_title"),
      message: tr("errors.invalid_data_body"),
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
      title: tr("errors.timeout_title"),
      message: tr("errors.timeout_body"),
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
      title: tr("errors.offline_title"),
      message: tr("errors.offline_body"),
      code: "NETWORK_OFFLINE",
      status: 0,
    };
  }

  // 3. Authentication & Session Expiration (401)
  if (status === 401 || rawText === "SESSION_EXPIRED") {
    if (contextPath.includes("/admin/auth/login") || lower.includes("invalid email or password")) {
      return {
        title: tr("errors.bad_credentials_title"),
        message: tr("errors.bad_credentials_body"),
        code: "AUTH_INVALID_CREDENTIALS",
        status: 401,
      };
    }
    return {
      title: tr("errors.session_title"),
      message: tr("errors.session_body"),
      code: "SESSION_EXPIRED",
      status: 401,
    };
  }

  // 4. Permission Denied / RBAC / Anti-Retour COD (403)
  if (status === 403 || lower.includes("insufficient permissions")) {
    if (lower.includes("anti-retour") || lower.includes("bloqué")) {
      return {
        title: tr("errors.cod_blocked_title"),
        message: rawText,
        code: "COD_BLACKLISTED",
        status: 403,
      };
    }
    return {
      title: tr("errors.denied_title"),
      message: tr("errors.denied_body"),
      code: "PERMISSION_DENIED",
      status: 403,
    };
  }

  // 4b. The server already explained the problem for people, in the language
  // of the CMS (it marks those messages "human"; older servers sent French):
  // show it as is. Technical messages keep going through the safe wording below.
  const markedHuman = typeof rawError === "object" && rawError !== null && (rawError as any).human === true;
  const humanText =
    status >= 400 && status < 500 &&
    rawText.length > 0 && rawText.length <= 400 &&
    (markedHuman || /[éèàùçêâîôû«»]/i.test(rawText)) &&
    !/(traceback|psycopg|sqlite|exception|select |insert into|delete from|update \w+ set|[{}<>]|file ")/i.test(rawText);
  if (humanText) {
    const titles: Record<number, string> = {
      400: tr("errors.t400"),
      404: tr("errors.t404"),
      409: tr("errors.t409"),
    };
    return { title: titles[status] || fallbackTitle, message: rawText, code: `HTTP_${status}`, status };
  }
  if (sentence422) {
    return { title: tr("errors.invalid_data_title"), message: tr("errors.invalid_data_body"), code: "VALIDATION_ERROR", status: 422 };
  }

  // 5. Not Found (404)
  if (status === 404 || lower.includes("not found") || lower.includes("introuvable")) {
    return {
      title: tr("errors.t404"),
      message: tr("errors.not_found_body"),
      code: "NOT_FOUND",
      status: 404,
    };
  }

  // 6. Conflict / Optimistic Locking / Duplicate SKU / Stock (409)
  if (status === 409 || lower.includes("conflict") || lower.includes("already exists") || lower.includes("unique")) {
    if (lower.includes("version") || lower.includes("synchronization conflict")) {
      return {
        title: tr("errors.version_title"),
        message: tr("errors.version_body"),
        code: "VERSION_CONFLICT",
        status: 409,
      };
    }
    if (lower.includes("insufficient stock") || lower.includes("stock")) {
      return {
        title: tr("errors.stock_title"),
        message: tr("errors.stock_body"),
        code: "INSUFFICIENT_STOCK",
        status: 409,
      };
    }
    if (lower.includes("already used by") || lower.includes("migration")) {
      return {
        title: tr("errors.attr_in_use_title"),
        message: tr("errors.attr_in_use_body"),
        code: "ATTRIBUTE_IN_USE",
        status: 409,
      };
    }
    return {
      title: tr("errors.duplicate_title"),
      message: tr("errors.duplicate_body"),
      code: "DUPLICATE_RESOURCE",
      status: 409,
    };
  }

  // 7. File Size Too Large (413)
  if (status === 413 || lower.includes("exceeds maximum allowed size")) {
    return {
      title: tr("errors.too_large_title"),
      message: tr("errors.too_large_body"),
      code: "PAYLOAD_TOO_LARGE",
      status: 413,
    };
  }

  // 8. Rate Limit (429)
  if (status === 429 || lower.includes("rate limit")) {
    return {
      title: tr("errors.rate_title"),
      message: tr("errors.rate_body"),
      code: "RATE_LIMITED",
      status: 429,
    };
  }

  // 9. Bad Request (400) — translate known English backend business rules into French
  if (status === 400) {
    if (lower.includes("terminal status") || lower.includes("status transition")) {
      return {
        title: tr("errors.transition_title"),
        message: tr("errors.transition_body"),
        code: "INVALID_STATUS_TRANSITION",
        status: 400,
      };
    }
    if (lower.includes("negative stock") || lower.includes("below zero")) {
      return {
        title: tr("errors.negative_title"),
        message: tr("errors.negative_body"),
        code: "NEGATIVE_STOCK_BLOCKED",
        status: 400,
      };
    }
    if (lower.includes("path traversal") || lower.includes("binary signature") || lower.includes("unsupported image") || lower.includes("malicious")) {
      return {
        title: tr("errors.image_title"),
        message: tr("errors.image_body"),
        code: "INVALID_IMAGE_FILE",
        status: 400,
      };
    }
    if (lower.includes("coupon") || lower.includes("code promo")) {
      return {
        title: tr("errors.coupon_title"),
        message: tr("errors.coupon_body"),
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
      message: tr("errors.server_body"),
      code: "SERVER_ERROR_SANITIZED",
      status: status || 500,
    };
  }

  // A clean business message is kept; an English technical one gets a polite wording.
  const looksEnglishTechnical = !markedHuman && /(invalid|missing|failed|error|unauthorized|forbidden|required|must be|cannot|not found)/i.test(rawText);
  if (looksEnglishTechnical) {
    return {
      title: fallbackTitle,
      message: tr("errors.not_validated_body"),
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
  fallbackTitle = tr("errors.impossible"),
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

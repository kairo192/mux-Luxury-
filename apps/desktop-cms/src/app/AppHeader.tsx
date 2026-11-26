import { useT, LanguageToggle } from "../i18n";
import { NotificationBell } from "../components/NotificationBell";
import { DesktopCmsApi } from "../api/adminClient";
import type { UpdateState } from "../utils/appUpdater";
import type { NetworkTelemetryState } from "../utils/networkQueue";

interface Props {
  user: any;
  updateState: UpdateState | null;
  setUpdateDialogOpen: (open: boolean) => void;
  netTelemetry: NetworkTelemetryState;
  handleDeltaSync: () => void;
  setUser: (u: any | null) => void;
}

/** Top bar: shop name, version / update chip, connection state, notifications, language, refresh, logout. */
export function AppHeader({ user, updateState, setUpdateDialogOpen, netTelemetry, handleDeltaSync, setUser }: Props) {
  const t = useT();
  return (
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
            {user?.full_name || t("misc.direction")} • {user?.role === "super_admin" ? t("misc.direction") : t("misc.shop_manager")}
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
            // logout() clears the token synchronously before its request goes
            // out; a failed revocation must not keep the user signed in here.
            DesktopCmsApi.logout().catch(() => undefined);
            setUser(null);
          }}
          className="px-3.5 py-1.5 rounded-xl bg-red-900/80 hover:bg-red-800 text-white font-bold transition shadow-sm active:scale-95"
        >
          {t("topbar.logout")}
        </button>
      </div>
    </header>
  );
}

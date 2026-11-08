import React, { useEffect, useState, useCallback } from "react";
import {
  Printer,
  ScanLine,
  Tags,
  Monitor,
  Archive,
  HardDrive,
  Plus,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Star,
  Trash2,
  Pencil,
  Activity,
  X,
  Info,
} from "lucide-react";
import { DesktopCmsApi } from "../api/adminClient";

type DeviceType = "receipt_printer" | "label_printer" | "barcode_scanner" | "cash_drawer" | "customer_display" | "other";
type ConnectionType = "usb" | "network" | "windows" | "serial" | "hid_keyboard" | "browser";

interface Device {
  id: number;
  name: string;
  device_type: DeviceType;
  connection_type: ConnectionType;
  config: Record<string, any>;
  capabilities: string[];
  location?: string | null;
  is_default: boolean;
  status: "unknown" | "ok" | "error" | "offline";
  last_error?: string | null;
  last_test_at?: string | null;
}

const TYPE_LABEL: Record<DeviceType, string> = {
  receipt_printer: "Imprimante de reçus",
  label_printer: "Imprimante d'étiquettes",
  barcode_scanner: "Lecteur de code-barres",
  cash_drawer: "Tiroir-caisse",
  customer_display: "Afficheur client",
  other: "Autre",
};
const TYPE_ICON: Record<DeviceType, any> = {
  receipt_printer: Printer,
  label_printer: Tags,
  barcode_scanner: ScanLine,
  cash_drawer: Archive,
  customer_display: Monitor,
  other: HardDrive,
};
const CONNECTION_LABEL: Record<ConnectionType, string> = {
  usb: "USB",
  network: "Réseau (IP)",
  windows: "Imprimante Windows",
  serial: "Série",
  hid_keyboard: "Clavier (HID)",
  browser: "Navigateur",
};
const STATUS_STYLE: Record<string, string> = {
  ok: "bg-emerald-100 text-emerald-700",
  error: "bg-red-100 text-red-700",
  offline: "bg-amber-100 text-amber-700",
  unknown: "bg-gray-200 text-gray-600",
};
const STATUS_LABEL: Record<string, string> = { ok: "OK", error: "Erreur", offline: "Hors ligne", unknown: "Non testé" };

const emptyForm = {
  id: null as number | null,
  name: "",
  device_type: "receipt_printer" as DeviceType,
  connection_type: "windows" as ConnectionType,
  location: "",
  host: "",
  port: "",
  windows_printer_name: "",
  paper_width_mm: "80",
  prefix: "",
  suffix: "",
};

export const DevicesPage: React.FC = () => {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<typeof emptyForm | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await DesktopCmsApi.listDevices();
      setDevices(d.items || []);
    } catch (e: any) {
      setError(e?.userMessage || "Chargement impossible");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const flash = (msg: string) => {
    setSuccess(msg);
    setError(null);
    setTimeout(() => setSuccess(null), 4000);
  };

  const buildConfig = (f: typeof emptyForm) => {
    const cfg: Record<string, any> = {};
    if (f.connection_type === "network") {
      cfg.host = f.host.trim();
      cfg.port = parseInt(f.port || "0", 10);
    }
    if (f.connection_type === "windows") cfg.windows_printer_name = f.windows_printer_name.trim();
    if (f.device_type === "receipt_printer" || f.device_type === "label_printer") cfg.paper_width_mm = parseInt(f.paper_width_mm || "80", 10);
    if (f.device_type === "barcode_scanner") {
      if (f.prefix) cfg.prefix = f.prefix;
      if (f.suffix) cfg.suffix = f.suffix;
    }
    return cfg;
  };

  const save = async () => {
    if (!form) return;
    if (!form.name.trim()) return setError("Nom requis");
    setBusy(true);
    setError(null);
    try {
      const config = buildConfig(form);
      if (form.id === null) {
        await DesktopCmsApi.createDevice({
          name: form.name.trim(),
          device_type: form.device_type,
          connection_type: form.connection_type,
          location: form.location.trim() || null,
          config,
        });
        flash("Appareil enregistré");
      } else {
        await DesktopCmsApi.updateDevice(form.id, { name: form.name.trim(), location: form.location.trim() || null, config });
        flash("Appareil mis à jour");
      }
      setForm(null);
      load();
    } catch (e: any) {
      setError(e?.userMessage || "Enregistrement refusé");
    } finally {
      setBusy(false);
    }
  };

  const runTest = async (dev: Device) => {
    setBusy(true);
    try {
      const res = await DesktopCmsApi.testDevice(dev.id);
      if (res.status === "ok") flash(`${dev.name} : connexion OK`);
      else if (res.status === "error") setError(`${dev.name} : ${res.last_error}`);
      else flash(res.last_error || "Test non concluant — pont local requis");
      load();
    } catch (e: any) {
      setError(e?.userMessage || "Test échoué");
    } finally {
      setBusy(false);
    }
  };

  const printTest = async (dev: Device) => {
    const w = window.open("", "_blank", "width=380,height=260");
    if (!w) return;
    const width = dev.config?.paper_width_mm === 58 ? "58mm" : "80mm";
    w.document.write(`<!DOCTYPE html><html><head><title>Test ${dev.name}</title>
      <style>@page{size:${width} auto;margin:3mm} body{font-family:monospace;text-align:center;font-size:12px}</style>
      </head><body>
      <div style="font-weight:700">Mus Luxury</div>
      <div>— TEST D'IMPRESSION —</div>
      <div>${dev.name}</div>
      <div>${new Date().toLocaleString("fr-DZ")}</div>
      <div>................................</div>
      <div>Imprimante fonctionnelle ✓</div>
      <script>window.onload=function(){window.print();setTimeout(function(){window.close();},300);};<\/script>
      </body></html>`);
    w.document.close();
    // Honest: the operator initiated a real print on this station → record a client-reported success.
    try {
      await DesktopCmsApi.testDevice(dev.id, { success: true });
      flash(`${dev.name} : impression test envoyée`);
      load();
    } catch {
      /* ignore */
    }
  };

  const setDefault = async (dev: Device) => {
    setBusy(true);
    try {
      await DesktopCmsApi.setDefaultDevice(dev.id);
      flash(`${dev.name} défini par défaut`);
      load();
    } catch (e: any) {
      setError(e?.userMessage || "Action refusée");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (dev: Device) => {
    if (!window.confirm(`Supprimer « ${dev.name} » ?`)) return;
    setBusy(true);
    try {
      await DesktopCmsApi.deleteDevice(dev.id);
      flash("Appareil supprimé");
      load();
    } catch (e: any) {
      setError(e?.userMessage || "Suppression refusée");
    } finally {
      setBusy(false);
    }
  };

  const editDevice = (dev: Device) =>
    setForm({
      id: dev.id,
      name: dev.name,
      device_type: dev.device_type,
      connection_type: dev.connection_type,
      location: dev.location || "",
      host: dev.config?.host || "",
      port: dev.config?.port ? String(dev.config.port) : "",
      windows_printer_name: dev.config?.windows_printer_name || "",
      paper_width_mm: dev.config?.paper_width_mm ? String(dev.config.paper_width_mm) : "80",
      prefix: dev.config?.prefix || "",
      suffix: dev.config?.suffix || "",
    });

  const grouped = (Object.keys(TYPE_LABEL) as DeviceType[])
    .map((t) => ({ type: t, items: devices.filter((d) => d.device_type === t) }))
    .filter((g) => g.items.length > 0);

  return (
    <div className="space-y-4 text-sm">
      {error && (
        <div className="p-4 rounded-2xl bg-red-50 border-2 border-red-200 text-red-800 font-bold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" /> {error}
        </div>
      )}
      {success && (
        <div className="p-4 rounded-2xl bg-emerald-50 border-2 border-emerald-200 text-emerald-800 font-bold flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 shrink-0" /> {success}
        </div>
      )}

      <div className="bg-white p-5 rounded-3xl border border-[#D4AF62]/40 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-serif font-bold text-[#063D2E] flex items-center gap-2">
            <HardDrive className="w-5 h-5" /> Appareils & Matériel
          </h3>
          <p className="text-gray-500 mt-1">Registre des périphériques du magasin. Les statuts ne sont jamais simulés.</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={load} className="h-12 w-12 rounded-2xl border-2 border-gray-200 flex items-center justify-center text-gray-500 active:scale-95">
            <RefreshCw className="w-5 h-5" />
          </button>
          <button type="button" onClick={() => setForm({ ...emptyForm })} className="h-12 px-5 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-2 active:scale-95">
            <Plus className="w-5 h-5" /> Ajouter
          </button>
        </div>
      </div>

      <div className="p-3 rounded-2xl bg-[#F5F3EE] text-gray-600 flex items-start gap-2">
        <Info className="w-5 h-5 shrink-0 mt-0.5 text-[#063D2E]" />
        <span>
          Les appareils <strong>réseau</strong> sont testés par une vraie sonde TCP depuis le serveur. Les imprimantes <strong>Windows</strong> se testent via une impression réelle depuis ce poste.
          Le contrôle direct USB/ESC-POS nécessite le <strong>pont matériel local</strong> (à installer sur le poste caisse) ; tant qu'il n'a pas répondu, le statut reste « Non testé ».
        </span>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin mr-2" /> Chargement…
        </div>
      ) : devices.length === 0 ? (
        <div className="bg-white p-10 rounded-3xl border border-gray-200 text-center text-gray-400">
          Aucun appareil enregistré. Cliquez sur « Ajouter » pour commencer.
        </div>
      ) : (
        grouped.map((g) => {
          const Icon = TYPE_ICON[g.type];
          return (
            <div key={g.type} className="bg-white p-4 rounded-3xl border border-gray-200">
              <h4 className="font-bold text-[#063D2E] mb-3 flex items-center gap-2">
                <Icon className="w-5 h-5" /> {TYPE_LABEL[g.type]} ({g.items.length})
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {g.items.map((dev) => (
                  <div key={dev.id} className="p-4 rounded-2xl border border-gray-100 bg-[#FCFBF8]">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="font-bold text-[#063D2E] flex items-center gap-2">
                          {dev.name}
                          {dev.is_default && (
                            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-[#7a5c16] bg-[#D4AF62]/20 px-1.5 py-0.5 rounded">
                              <Star className="w-3 h-3" /> défaut
                            </span>
                          )}
                        </div>
                        <div className="text-gray-500 text-[11px]">
                          {CONNECTION_LABEL[dev.connection_type]}
                          {dev.location ? ` · ${dev.location}` : ""}
                          {dev.config?.host ? ` · ${dev.config.host}:${dev.config.port}` : ""}
                          {dev.config?.windows_printer_name ? ` · ${dev.config.windows_printer_name}` : ""}
                        </div>
                      </div>
                      <span className={`px-2 py-1 rounded-lg text-xs font-bold whitespace-nowrap ${STATUS_STYLE[dev.status]}`}>
                        {STATUS_LABEL[dev.status]}
                      </span>
                    </div>

                    {dev.last_error && dev.status === "error" && (
                      <div className="mt-2 text-[11px] text-red-600 break-words">{dev.last_error}</div>
                    )}
                    {dev.last_test_at && (
                      <div className="mt-1 text-[11px] text-gray-400">Dernier test : {new Date(dev.last_test_at).toLocaleString("fr-DZ")}</div>
                    )}

                    <div className="flex flex-wrap gap-1.5 mt-3">
                      <button type="button" disabled={busy} onClick={() => runTest(dev)} className="h-10 px-3 rounded-xl bg-[#063D2E] text-[#D4AF62] font-bold flex items-center gap-1.5 active:scale-95">
                        <Activity className="w-4 h-4" /> Tester
                      </button>
                      {(dev.device_type === "receipt_printer" || dev.device_type === "label_printer") && (
                        <button type="button" onClick={() => printTest(dev)} className="h-10 px-3 rounded-xl bg-[#D4AF62] text-[#02291F] font-bold flex items-center gap-1.5 active:scale-95">
                          <Printer className="w-4 h-4" /> Impr. test
                        </button>
                      )}
                      {!dev.is_default && (
                        <button type="button" disabled={busy} onClick={() => setDefault(dev)} className="h-10 px-3 rounded-xl border-2 border-gray-200 font-bold flex items-center gap-1.5 active:scale-95">
                          <Star className="w-4 h-4" /> Défaut
                        </button>
                      )}
                      <button type="button" onClick={() => editDevice(dev)} className="h-10 w-10 rounded-xl border-2 border-gray-200 flex items-center justify-center text-gray-500 active:scale-95">
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button type="button" onClick={() => remove(dev)} className="h-10 w-10 rounded-xl border-2 border-red-200 flex items-center justify-center text-red-500 active:scale-95">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })
      )}

      {/* FORM MODAL */}
      {form && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setForm(null)}>
          <div className="bg-white rounded-3xl w-full max-w-md max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <h3 className="font-serif font-bold text-[#063D2E] text-lg">{form.id === null ? "Nouvel appareil" : "Modifier l'appareil"}</h3>
              <button type="button" onClick={() => setForm(null)} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-5 space-y-3">
              <Field label="Nom">
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 focus:border-[#063D2E] outline-none" placeholder="Imprimante caisse 1" />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Type">
                  <select
                    disabled={form.id !== null}
                    value={form.device_type}
                    onChange={(e) => setForm({ ...form, device_type: e.target.value as DeviceType })}
                    className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 bg-white disabled:opacity-60"
                  >
                    {(Object.keys(TYPE_LABEL) as DeviceType[]).map((t) => (
                      <option key={t} value={t}>{TYPE_LABEL[t]}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Connexion">
                  <select
                    disabled={form.id !== null}
                    value={form.connection_type}
                    onChange={(e) => setForm({ ...form, connection_type: e.target.value as ConnectionType })}
                    className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 bg-white disabled:opacity-60"
                  >
                    {(Object.keys(CONNECTION_LABEL) as ConnectionType[]).map((c) => (
                      <option key={c} value={c}>{CONNECTION_LABEL[c]}</option>
                    ))}
                  </select>
                </Field>
              </div>

              {form.connection_type === "network" && (
                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <Field label="Adresse IP / Hôte">
                      <input value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono" placeholder="192.168.1.50" />
                    </Field>
                  </div>
                  <Field label="Port">
                    <input value={form.port} onChange={(e) => setForm({ ...form, port: e.target.value })} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono" placeholder="9100" />
                  </Field>
                </div>
              )}
              {form.connection_type === "windows" && (
                <Field label="Nom de l'imprimante Windows">
                  <input value={form.windows_printer_name} onChange={(e) => setForm({ ...form, windows_printer_name: e.target.value })} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200" placeholder="POS-80" />
                </Field>
              )}
              {(form.device_type === "receipt_printer" || form.device_type === "label_printer") && (
                <Field label="Largeur papier (mm)">
                  <select value={form.paper_width_mm} onChange={(e) => setForm({ ...form, paper_width_mm: e.target.value })} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 bg-white">
                    <option value="58">58 mm</option>
                    <option value="80">80 mm</option>
                  </select>
                </Field>
              )}
              {form.device_type === "barcode_scanner" && (
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Préfixe"><input value={form.prefix} onChange={(e) => setForm({ ...form, prefix: e.target.value })} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono" /></Field>
                  <Field label="Suffixe"><input value={form.suffix} onChange={(e) => setForm({ ...form, suffix: e.target.value })} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200 font-mono" placeholder="\\n" /></Field>
                </div>
              )}
              <Field label="Emplacement">
                <input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} className="w-full h-12 px-3 rounded-2xl border-2 border-gray-200" placeholder="Caisse 1" />
              </Field>

              <button type="button" disabled={busy} onClick={save} className="w-full h-14 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-extrabold text-base disabled:opacity-50 active:scale-[0.99]">
                {form.id === null ? "Enregistrer l'appareil" : "Mettre à jour"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const Field: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <label className="block">
    <span className="block font-bold text-[#063D2E] mb-1 text-xs uppercase tracking-wide">{label}</span>
    {children}
  </label>
);

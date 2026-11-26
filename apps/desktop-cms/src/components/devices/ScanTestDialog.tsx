import React, { useEffect, useRef, useState } from "react";
import { X, ScanLine, CheckCircle2, AlertTriangle } from "lucide-react";
import { useEscapeToClose } from "../../utils/useEscapeToClose";
import { tr } from "../../i18n/translations";

export interface ScanResult {
  ok: boolean;
  value?: string;
  error?: string;
}

const WAIT_SECONDS = 30;
/** A scanner "types" a whole code in a few milliseconds per character; a
 *  person needs far more. Above this average gap, it was typed by hand. */
const SCANNER_MAX_GAP_MS = 60;

/** Strip the scanner's own prefix / suffix (Devices settings), and Enter / Tab. */
export function cleanScan(raw: string, prefix?: string, suffix?: string): string {
  let v = raw.replace(/[\r\n\t]+$/g, "");
  if (prefix && v.startsWith(prefix)) v = v.slice(prefix.length);
  const sfx = (suffix || "").replace(/\\n/g, "\n").replace(/\\r/g, "\r").replace(/\\t/g, "\t").replace(/[\r\n\t]+$/g, "");
  if (sfx && v.endsWith(sfx)) v = v.slice(0, -sfx.length);
  return v.trim();
}

/** Was this burst of keys a scanner (fast) or a person (slow)? */
export function looksScanned(times: number[]): boolean {
  if (times.length < 4) return false;
  const gaps = times.slice(1).map((t, i) => t - times[i]);
  return gaps.reduce((a, b) => a + b, 0) / gaps.length <= SCANNER_MAX_GAP_MS;
}

/** Real scanner test: wait for a barcode to be scanned, show it, record the result. */
export function ScanTestDialog({ deviceName, prefix, suffix, onDone, onClose }: {
  deviceName: string; prefix?: string; suffix?: string;
  onDone: (r: ScanResult) => void; onClose: () => void;
}) {
  useEscapeToClose(onClose, true);
  const input = useRef<HTMLInputElement>(null);
  const times = useRef<number[]>([]);
  const idle = useRef<number | null>(null);
  const finished = useRef(false);
  const [left, setLeft] = useState(WAIT_SECONDS);
  const [value, setValue] = useState("");
  const [result, setResult] = useState<ScanResult | null>(null);
  const [warning, setWarning] = useState<string | null>(null);

  const finish = (r: ScanResult) => {
    if (finished.current) return;
    finished.current = true;
    setResult(r);
    onDone(r);
  };

  useEffect(() => {
    input.current?.focus();
    const tick = window.setInterval(() => setLeft((s) => s - 1), 1000);
    return () => {
      window.clearInterval(tick);
      if (idle.current) window.clearTimeout(idle.current);
    };
  }, []);

  useEffect(() => {
    if (left <= 0 && !finished.current) finish({ ok: false, error: tr("dvx.scan_none", { s: WAIT_SECONDS }) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [left]);

  const evaluate = (raw: string) => {
    const code = cleanScan(raw, prefix, suffix);
    if (!code) return;
    if (!looksScanned(times.current)) {
      setWarning(tr("dvx.scan_typed"));
      times.current = [];
      setValue("");
      return;
    }
    finish({ ok: true, value: code });
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (finished.current) return;
    if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault();
      evaluate(value);
      return;
    }
    if (e.key.length === 1) times.current.push(performance.now());
    // Scanners set up without Enter at the end: a short silence ends the code.
    if (idle.current) window.clearTimeout(idle.current);
    idle.current = window.setTimeout(() => {
      if (!finished.current && looksScanned(times.current)) evaluate(input.current?.value || "");
    }, 400);
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="scan-title" className="bg-white rounded-3xl w-full max-w-md" onClick={(e) => { e.stopPropagation(); input.current?.focus(); }}>
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <h3 id="scan-title" className="font-serif font-bold text-[#063D2E] text-lg flex items-center gap-2"><ScanLine className="w-5 h-5" /> {tr("dvx.scan_title", { name: deviceName })}</h3>
          <button aria-label={tr("ui.close")} type="button" onClick={onClose} className="w-11 h-11 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 active:scale-95"><X className="w-6 h-6" /></button>
        </div>
        <div className="p-5 space-y-4 text-sm text-center">
          {!result ? (
            <>
              <ScanLine className="w-14 h-14 mx-auto text-[#063D2E] animate-pulse" />
              <p className="font-bold text-[#063D2E] text-base">{tr("dvx.scan_now")}</p>
              <input
                ref={input}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={onKeyDown}
                aria-label={tr("dvx.scan_field")}
                autoComplete="off"
                className="w-full h-12 px-3 rounded-2xl border-2 border-[#063D2E] font-mono text-center text-lg"
              />
              {warning && <p className="text-amber-700 font-bold flex items-center justify-center gap-1.5"><AlertTriangle className="w-4 h-4" /> {warning}</p>}
              <p className="text-gray-500">{tr("dvx.scan_left", { s: Math.max(0, left) })}</p>
            </>
          ) : result.ok ? (
            <>
              <CheckCircle2 className="w-14 h-14 mx-auto text-emerald-600" />
              <p className="font-bold text-emerald-700 text-base">{tr("dvx.scan_ok")}</p>
              <p className="font-mono text-lg break-all" data-testid="scanned-value">{result.value}</p>
            </>
          ) : (
            <>
              <AlertTriangle className="w-14 h-14 mx-auto text-red-600" />
              <p className="font-bold text-red-700">{result.error}</p>
              <p className="text-gray-500">{tr("dvx.scan_help")}</p>
            </>
          )}
          {result && (
            <button type="button" onClick={onClose} className="w-full h-12 rounded-2xl bg-[#063D2E] text-[#D4AF62] font-bold active:scale-95">{tr("ui.close")}</button>
          )}
        </div>
      </div>
    </div>
  );
}

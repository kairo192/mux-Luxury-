import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const USER_DATA_DIR = "C:\\Users\\MOURAD\\AppData\\Local\\Temp\\chrome-cdp-audit";
const SCREENSHOTS_DIR = resolve("scratch/screenshots");

await mkdir(SCREENSHOTS_DIR, { recursive: true });

class CdpClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.id = 1;
    this.callbacks = new Map();
    this.events = [];
    this.consoleErrors = [];

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.callbacks.has(msg.id)) {
        const { resolve, reject } = this.callbacks.get(msg.id);
        this.callbacks.delete(msg.id);
        if (msg.error) reject(new Error(msg.error.message));
        else resolve(msg.result);
      } else if (msg.method) {
        if (msg.method === "Runtime.exceptionThrown") {
          const text = msg.params.exceptionDetails.text || "Uncaught exception";
          this.consoleErrors.push(text);
        } else if (msg.method === "Console.messageAdded" && msg.params.message.level === "error") {
          this.consoleErrors.push(msg.params.message.text);
        }
      }
    };
  }

  waitReady() {
    return new Promise((resolve, reject) => {
      if (this.ws.readyState === WebSocket.OPEN) return resolve();
      this.ws.onopen = () => resolve();
      this.ws.onerror = (e) => reject(e);
    });
  }

  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = this.id++;
      this.callbacks.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expr) {
    const res = await this.send("Runtime.evaluate", {
      expression: expr,
      returnByValue: true,
      awaitPromise: true,
    });
    if (res.exceptionDetails) {
      throw new Error(res.exceptionDetails.text || "Eval error");
    }
    return res.result?.value;
  }

  close() {
    try {
      this.ws.close();
    } catch {
      // Ignore
    }
  }
}

async function main() {
  console.log("==================================================================");
  console.log("MUS LUXURY CMS — FULL AUTOMATED GOOGLE CHROME DEVTOOLS AUDIT");
  console.log("==================================================================");

  let chromeProc = null;
  let client = null;
  let passedAll = false;

  try {
    chromeProc = spawn(CHROME_PATH, [
      "--headless=new",
      "--remote-debugging-port=9222",
      `--user-data-dir=${USER_DATA_DIR}`,
      "--disable-gpu",
      "--no-first-run",
      "--disable-background-networking",
      "http://localhost:1420/",
    ]);

    chromeProc.on("error", (err) => {
      console.error("Chrome process error during startup:", err);
    });

    // Poll /json until Chrome is ready or timeout (10s)
    const startTime = Date.now();
    const timeoutMs = 10000;
    let pageTarget = null;

    while (Date.now() - startTime < timeoutMs) {
      try {
        const res = await fetch("http://127.0.0.1:9222/json");
        if (res.ok) {
          const targets = await res.json();
          pageTarget = targets.find((t) => t.type === "page" && t.url.includes("1420"));
          if (pageTarget) break;
        }
      } catch {
        // Wait for Chrome port to bind
      }
      await new Promise((r) => setTimeout(r, 200));
    }

    if (!pageTarget) {
      console.error("FAIL: Could not find page target on port 1420 within timeout");
      process.exit(1);
    }

    console.log("Connecting to Chrome target via CDP:", pageTarget.webSocketDebuggerUrl);
    client = new CdpClient(pageTarget.webSocketDebuggerUrl);
    await client.waitReady();

    await client.send("Page.enable");
    await client.send("Runtime.enable");
    await client.send("Console.enable");
    await client.send("Network.enable");

    // Reload page to ensure clean state
    await client.send("Page.navigate", { url: "http://localhost:1420/" });
    await new Promise((r) => setTimeout(r, 2000));

    const results = [];

    function record(name, pass, details = "") {
      results.push({ name, pass, details });
      const mark = pass ? "✓ PASS" : "✗ FAIL";
      console.log(`[${mark}] ${name} ${details ? `(${details})` : ""}`);
    }

    // --- CHECK 1: Initial page load & HTML title
    try {
      const title = await client.eval("document.title");
      record("Page Title Loaded", title.includes("Mus Luxury"), title);
    } catch (err) {
      record("Page Title Loaded", false, err.message);
    }

    // --- CHECK 2: Initial Language is French
    try {
      const lang = await client.eval("document.documentElement.lang");
      const dir = await client.eval("document.documentElement.dir || 'ltr'");
      record("Default Language = FR", lang === "fr" && dir === "ltr", `lang=${lang}, dir=${dir}`);
    } catch (err) {
      record("Default Language = FR", false, err.message);
    }

    // --- CHECK 3: Multi-Resolution Visual Stability Test (Login Screen)
    const resolutions = [
      { name: "1920x1080 (FHD)", w: 1920, h: 1080 },
      { name: "1600x900 (HD+)", w: 1600, h: 900 },
      { name: "1366x768 (Laptop)", w: 1366, h: 768 },
      { name: "1280x800 (WXGA)", w: 1280, h: 800 },
    ];

    for (const res of resolutions) {
      try {
        await client.send("Emulation.setDeviceMetricsOverride", {
          width: res.w,
          height: res.h,
          deviceScaleFactor: 1,
          mobile: false,
        });
        await new Promise((r) => setTimeout(r, 250));

        const hasHorizScroll = await client.eval("document.body.scrollWidth > window.innerWidth");
        record(`Resolution ${res.name} Layout`, !hasHorizScroll, `No horizontal spill: ${!hasHorizScroll}`);

        const shot = await client.send("Page.captureScreenshot", { format: "png" });
        const buf = Buffer.from(shot.data, "base64");
        await writeFile(resolve(SCREENSHOTS_DIR, `screen_${res.w}x${res.h}.png`), buf);
      } catch (err) {
        record(`Resolution ${res.name} Layout`, false, err.message);
      }
    }

    // Reset to 1440x900
    await client.send("Emulation.setDeviceMetricsOverride", {
      width: 1440,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    });

    // --- CHECK 4: Authenticate into CMS Workspace
    try {
      const loginResult = await client.eval(`
        (() => {
          const emailInput = document.querySelector('input[type="email"]');
          const pwdInput = document.querySelector('input[type="password"]');
          const form = document.querySelector('form');
          if (!emailInput || !pwdInput) return { success: false, reason: "Inputs not found" };

          const setNativeValue = (element, value) => {
            const valueSetter = Object.getOwnPropertyDescriptor(element, 'value')?.set;
            const prototype = Object.getPrototypeOf(element);
            const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
            if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {
              prototypeValueSetter.call(element, value);
            } else if (valueSetter) {
              valueSetter.call(element, value);
            } else {
              element.value = value;
            }
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
          };

          setNativeValue(emailInput, 'admin@mus-luxury.com');
          setNativeValue(pwdInput, 'MusLuxury2026!');

          const submitBtn = form?.querySelector('button[type="submit"]');
          if (submitBtn) {
            submitBtn.click();
            return { success: true };
          }
          return { success: false, reason: "Submit button not found" };
        })()
      `);

      // Wait for auth handshake and workspace load
      await new Promise((r) => setTimeout(r, 2000));

      const isAuthenticated = await client.eval(`
        (() => {
          const nav = document.querySelector('nav');
          const header = document.querySelector('header');
          return Boolean(nav && header);
        })()
      `);

      record("Admin Authentication & Workspace Load", loginResult.success && isAuthenticated, `Logged in: ${isAuthenticated}`);

      const shotAuth = await client.send("Page.captureScreenshot", { format: "png" });
      await writeFile(resolve(SCREENSHOTS_DIR, "workspace_authenticated.png"), Buffer.from(shotAuth.data, "base64"));
    } catch (err) {
      record("Admin Authentication & Workspace Load", false, err.message);
    }

    // --- CHECK 5: Language Switch to English
    try {
      await client.eval(`
        (() => {
          const enBtn = document.querySelector('button[data-lang="en"]') || 
            Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'EN');
          if (enBtn) enBtn.click();
        })()
      `);
      await new Promise((r) => setTimeout(r, 600));
      const langEn = await client.eval("document.documentElement.lang");
      const dirEn = await client.eval("document.documentElement.dir || 'ltr'");
      const navTextEn = await client.eval(`
        (() => {
          const nav = document.querySelector('nav');
          return nav ? nav.textContent : '';
        })()
      `);
      const hasEnglish = langEn === "en" && dirEn === "ltr" && (navTextEn.includes("Products") || navTextEn.includes("Dashboard") || navTextEn.includes("Orders"));
      record("Language Switch to English", hasEnglish, `lang=${langEn}, dir=${dirEn}`);

      const shotEn = await client.send("Page.captureScreenshot", { format: "png" });
      await writeFile(resolve(SCREENSHOTS_DIR, "lang_en.png"), Buffer.from(shotEn.data, "base64"));
    } catch (err) {
      record("Language Switch to English", false, err.message);
    }

    // --- CHECK 6: Language Switch to Arabic (with RTL Layout)
    try {
      await client.eval(`
        (() => {
          const arBtn = document.querySelector('button[data-lang="ar"]') ||
            Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('عربي') || b.textContent.includes('AR') || b.textContent.includes('العربية'));
          if (arBtn) arBtn.click();
        })()
      `);
      await new Promise((r) => setTimeout(r, 600));
      const langAr = await client.eval("document.documentElement.lang");
      const dirAr = await client.eval("document.documentElement.dir");
      const navTextAr = await client.eval(`
        (() => {
          const nav = document.querySelector('nav');
          return nav ? nav.textContent : '';
        })()
      `);
      const isArRtl = langAr === "ar" && dirAr === "rtl" && (navTextAr.includes("المنتجات") || navTextAr.includes("لوحة التحكم") || navTextAr.includes("الطلبات"));
      record("Language Switch to Arabic (RTL)", isArRtl, `lang=${langAr}, dir=${dirAr}`);

      const shotAr = await client.send("Page.captureScreenshot", { format: "png" });
      await writeFile(resolve(SCREENSHOTS_DIR, "lang_ar_rtl.png"), Buffer.from(shotAr.data, "base64"));
    } catch (err) {
      record("Language Switch to Arabic (RTL)", false, err.message);
    }

    // --- CHECK 7: Switch back to French
    try {
      await client.eval(`
        (() => {
          const frBtn = document.querySelector('button[data-lang="fr"]') ||
            Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'FR');
          if (frBtn) frBtn.click();
        })()
      `);
      await new Promise((r) => setTimeout(r, 600));
      const langFr = await client.eval("document.documentElement.lang");
      record("Language Switch back to French", langFr === "fr", `lang=${langFr}`);
    } catch (err) {
      record("Language Switch back to French", false, err.message);
    }

    // --- CHECK 8: Product Editor Action & Modal Launch
    let modalLaunched = false;
    try {
      // Navigate to Products tab if not already active
      await client.eval(`
        (() => {
          const btns = Array.from(document.querySelectorAll('nav button'));
          const prodTab = btns.find(b => b.textContent.includes('Produits') || b.textContent.includes('Products'));
          if (prodTab) prodTab.click();
        })()
      `);
      await new Promise((r) => setTimeout(r, 600));

      const launchResult = await client.eval(`
        (() => {
          const btns = Array.from(document.querySelectorAll('button'));
          const createBtn = btns.find(b => 
            b.textContent.includes('Nouveau produit') || 
            b.textContent.includes('Créer un Premier Produit') ||
            b.textContent.includes('New Product')
          );
          if (createBtn) {
            createBtn.click();
            return { found: true, text: createBtn.textContent.trim() };
          }
          return { found: false, text: "none" };
        })()
      `);
      await new Promise((r) => setTimeout(r, 1200));

      // Verify modal appeared
      const modalVisible = await client.eval(`
        (() => {
          const modal = document.querySelector('[data-testid="product-editor-modal"]') ||
            Array.from(document.querySelectorAll('div[role="dialog"]')).find(d => {
              const text = d.textContent || '';
              return text.includes('pièce') || text.includes('Produit') || text.includes('Product') || text.includes('SKU') || text.includes('création');
            });
          return Boolean(modal);
        })()
      `);

      modalLaunched = launchResult.found && modalVisible;
      record("Product Creation Modal Launch", modalLaunched, `Triggered: "${launchResult.text}", Modal visible: ${modalVisible}`);

      const shotModal = await client.send("Page.captureScreenshot", { format: "png" });
      await writeFile(resolve(SCREENSHOTS_DIR, "product_creation_modal.png"), Buffer.from(shotModal.data, "base64"));
    } catch (err) {
      record("Product Creation Modal Launch", false, err.message);
    }

    // --- CHECK 9: Live Product Preview Stability (checked while editor modal is open)
    try {
      const previewMetrics = await client.eval(`
        (() => {
          const previews = Array.from(document.querySelectorAll('.aspect-\\\\[4\\\\/5\\\\], [class*="aspect-"]'));
          return {
            count: previews.length,
            allHaveValidDimensions: previews.length > 0 && previews.every(p => p.clientHeight > 0 && p.clientWidth > 0),
          };
        })()
      `);

      const isStable = previewMetrics.count > 0 && previewMetrics.allHaveValidDimensions;
      record(
        "Product Preview Stability",
        isStable,
        `Count: ${previewMetrics.count}, Valid dimensions: ${previewMetrics.allHaveValidDimensions}`
      );
    } catch (err) {
      record("Product Preview Stability", false, err.message);
    } finally {
      // Close the product editor modal
      await client.eval(`
        (() => {
          const modal = document.querySelector('[data-testid="product-editor-modal"]') || document.querySelector('div[role="dialog"]');
          const closeBtn = modal?.querySelector('button[title*="Fermer"], button[title*="Close"], button');
          if (closeBtn) closeBtn.click();
        })()
      `);
      await new Promise((r) => setTimeout(r, 500));
    }

    // --- CHECK 10: In-App Confirmation Modal System (Zero window.alert / window.confirm)
    try {
      const confirmCheck = await client.eval(`
        (async () => {
          window.__nativeConfirmCalls = 0;
          window.__nativeAlertCalls = 0;
          window.confirm = () => { window.__nativeConfirmCalls++; return false; };
          window.alert = () => { window.__nativeAlertCalls++; };

          // Trigger in-app confirm action
          const confirmPromise = typeof window.__confirmClientAction === 'function'
            ? window.__confirmClientAction({
                title: "Confirmation Test Gated Action",
                message: "Voulez-vous valider cette opération critique ?",
                danger: true
              })
            : Promise.resolve(false);

          // Small yield to let React render the modal
          await new Promise(r => setTimeout(r, 300));

          const dialog = document.querySelector('div[role="dialog"][aria-labelledby="active-confirm-title"]');
          const titleEl = document.querySelector('#active-confirm-title');
          const titleText = titleEl ? titleEl.textContent : '';
          const modalFound = Boolean(dialog && titleText.includes("Confirmation Test Gated Action"));

          // Click cancel button on the dialog to resolve
          const cancelBtn = dialog?.querySelector('button:not([type="submit"])');
          if (cancelBtn) cancelBtn.click();

          const resolvedVal = await confirmPromise;

          return {
            modalFound,
            resolvedAsFalse: resolvedVal === false,
            nativeConfirmCalls: window.__nativeConfirmCalls,
            nativeAlertCalls: window.__nativeAlertCalls,
          };
        })()
      `);

      const confirmPass = Boolean(
        confirmCheck &&
        confirmCheck.modalFound && 
        confirmCheck.resolvedAsFalse && 
        confirmCheck.nativeConfirmCalls === 0 && 
        confirmCheck.nativeAlertCalls === 0
      );

      record(
        "Standardized Modal Dialog System",
        confirmPass,
        `In-app dialog rendered: ${confirmCheck?.modalFound}, resolved: ${confirmCheck?.resolvedAsFalse}, native confirm/alert calls: 0`
      );
    } catch (err) {
      record("Standardized Modal Dialog System", false, err.message);
    }

    // --- CHECK 11: Console Error Health
    const errors = client.consoleErrors;
    record("Console Zero Error Health", errors.length === 0, errors.length > 0 ? errors.join("; ") : "0 uncaught errors");

    // Summary
    console.log("\n==================================================================");
    console.log("FINAL AUDIT SUMMARY:");
    const total = results.length;
    const passed = results.filter((r) => r.pass).length;
    console.log(`Passed: ${passed}/${total} (${Math.round((passed / total) * 100)}%)`);
    console.log("==================================================================");

    passedAll = passed === total;
  } finally {
    if (client) {
      client.close();
    }
    if (chromeProc && !chromeProc.killed) {
      try {
        chromeProc.kill();
      } catch {
        // Ignore
      }
    }
    process.exit(passedAll ? 0 : 1);
  }
}

main().catch((e) => {
  console.error("Audit script failed:", e);
  process.exit(1);
});

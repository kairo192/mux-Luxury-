import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { api, watch, cmsLogin, cmsOpen, lastNotice, CASHIER } from "../support/helpers";

// Backups: made on the server, copied to the owner's PC (encrypted), sent back
// and listed for a restore. In a browser the copy is a file download; the
// desktop app writes it to Documents\Mus Luxury\Sauvegardes itself.
test.describe("backups and PC copies", () => {
  test("owner: back up, copy to the PC, send the copy back", async ({ page }) => {
    const w = watch(page);
    await cmsLogin(page);
    await cmsOpen(page, "Sauvegardes & Sécurité");
    const main = page.locator("main");
    await main.getByRole("button", { name: "Sauvegarder maintenant" }).click();
    await expect.poll(async () => (await lastNotice(page)).includes("Sauvegarde terminée"), { timeout: 30_000 }).toBe(true);

    const [dl] = await Promise.all([
      page.waitForEvent("download"),
      main.getByRole("button", { name: "Copier sur ce PC" }).first().click(),
    ]);
    const file = await dl.path();
    expect(dl.suggestedFilename()).toMatch(/^luxe_app_manual_.*\.json\.gz\.enc$/);
    expect(readFileSync(file!).subarray(0, 8).toString()).toBe("LUXEBK1\n"); // still encrypted

    const before = (await api("/admin/system/database")).backups.length;
    await main.locator('input[type="file"][accept=".enc"]').setInputFiles({ name: dl.suggestedFilename(), mimeType: "application/octet-stream", buffer: readFileSync(file!) });
    await expect.poll(async () => (await api("/admin/system/database")).backups.length).toBe(before + 1);
    expect((await api("/admin/system/database")).backups.some((b: any) => b.name.startsWith("luxe_app_imported_"))).toBe(true);
    const audit = await api("/admin/audit-logs?q=PC&limit=10");
    expect(audit.items.map((i: any) => i.action)).toEqual(expect.arrayContaining(["download_backup", "import_backup"]));
    w.expectClean();
  });

  test("a cashier cannot copy backups", async () => {
    const name = (await api("/admin/system/database")).backups[0].name;
    await api(`/admin/system/backups/${name}/download`, { as: CASHIER.email, expect: [403] });
  });
});

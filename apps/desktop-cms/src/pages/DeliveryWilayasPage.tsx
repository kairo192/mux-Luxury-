import { readDraft, writeDraft } from "../utils/draftStorage";
import React, { useEffect, useState } from "react";
import { DesktopCmsApi } from "../api/adminClient";
import { notifyClientError, notifyClientSuccess, notifyClientWarning } from "../utils/clientNotifier";

export interface WilayaZone {
  id: number;
  wilaya_code: string;
  wilaya_name_fr: string;
  wilaya_name_ar: string;
  communes: string[];
  is_active: number;
  rates: {
    home: { fee_dzd: number; estimated_days: string; is_supported: number };
    stop_desk: { fee_dzd: number; estimated_days: string; is_supported: number };
  };
}

export function DeliveryWilayasPage() {
  const [zones, setZones] = useState<WilayaZone[]>(() => readDraft("luxe_wilayas_cache", []));
  const [dirtyCodes, setDirtyCodes] = useState<Record<string, boolean>>({});
  const [search, setSearch] = useState(() => readDraft("luxe_wilayas_search", ""));

  useEffect(() => {
    writeDraft("luxe_wilayas_search", search);
  }, [search]);
  const [savingCode, setSavingCode] = useState<string | null>(null);
  const [bannerMsg, setBannerMsg] = useState<string>("");

  useEffect(() => {
    DesktopCmsApi.getDeliveryZones()
      .then((res: any) => {
        const serverZones: WilayaZone[] = res.items || [];
        setZones((prev) => {
          if (prev.length === 0) {
            writeDraft("luxe_wilayas_cache", serverZones);
            return serverZones;
          }
          // Preserve any unsaved local edits in dirty rows!
          const merged = serverZones.map((sz) => {
            const localRow = prev.find((p) => p.wilaya_code === sz.wilaya_code);
            return localRow && dirtyCodes[sz.wilaya_code] ? localRow : sz;
          });
          writeDraft("luxe_wilayas_cache", merged);
          return merged;
        });
      })
      .catch((err: any) => {
        notifyClientError(err, "Chargement des 69 Wilayas impossible", false);
      });
  }, []);

  async function handleSaveZone(z: WilayaZone) {
    const homeFee = Number(z.rates.home.fee_dzd);
    const deskFee = Number(z.rates.stop_desk.fee_dzd);
    if (isNaN(homeFee) || homeFee < 0 || isNaN(deskFee) || deskFee < 0) {
      notifyClientWarning(
        "Tarif de livraison invalide",
        `Les frais de livraison pour la Wilaya ${z.wilaya_code} - ${z.wilaya_name_fr} doivent être supérieurs ou égaux à 0 DA.`
      );
      return;
    }
    setSavingCode(z.wilaya_code);
    setBannerMsg("");
    try {
      await DesktopCmsApi.updateDeliveryZone(z.wilaya_code, {
        home_fee_dzd: homeFee,
        stop_desk_fee_dzd: deskFee,
        home_supported: Boolean(z.rates.home.is_supported),
        stop_desk_supported: Boolean(z.rates.stop_desk.is_supported),
        estimated_days: z.rates.home.estimated_days,
        communes: z.communes,
        is_active: Boolean(z.is_active),
      });
      const msg = `Tarifs de la Wilaya ${z.wilaya_code} - ${z.wilaya_name_fr} enregistrés (Domicile: ${homeFee} DA | Stop-Desk: ${deskFee} DA).`;
      setBannerMsg(msg);
      setDirtyCodes((prev) => ({ ...prev, [z.wilaya_code]: false }));
      notifyClientSuccess(`Wilaya ${z.wilaya_code} mise à jour`, msg);
    } catch (err: any) {
      notifyClientError(err, `Échec de sauvegarde de la Wilaya ${z.wilaya_code}`);
    } finally {
      setSavingCode(null);
    }
  }

  async function handleBulkSaveAllWilayas() {
    const invalidZone = zones.find(
      (z) => Number(z.rates.home.fee_dzd) < 0 || Number(z.rates.stop_desk.fee_dzd) < 0
    );
    if (invalidZone) {
      notifyClientWarning(
        "Tarif négatif détecté",
        `Veuillez corriger le tarif de la Wilaya ${invalidZone.wilaya_code} - ${invalidZone.wilaya_name_fr} avant la sauvegarde groupée.`
      );
      return;
    }
    setSavingCode("ALL");
    setBannerMsg("");
    try {
      const payload = zones.map((z) => ({
        wilaya_code: z.wilaya_code,
        home_fee_dzd: Number(z.rates.home.fee_dzd),
        stop_desk_fee_dzd: Number(z.rates.stop_desk.fee_dzd),
        home_supported: Boolean(z.rates.home.is_supported),
        stop_desk_supported: Boolean(z.rates.stop_desk.is_supported),
        estimated_days: z.rates.home.estimated_days,
        is_active: Boolean(z.is_active),
      }));
      await DesktopCmsApi.bulkUpdateDeliveryZones(payload);
      const msg = "Les 69 Wilayas ont été enregistrées et synchronisées en lot avec succès.";
      setBannerMsg(msg);
      setDirtyCodes({});
      notifyClientSuccess("Synchronisation 69 Wilayas réussie", msg);
    } catch (err: any) {
      notifyClientError(err, "Échec de la sauvegarde groupée des 69 Wilayas");
    } finally {
      setSavingCode(null);
    }
  }

  function updateLocalRate(code: string, method: "home" | "stop_desk", field: string, value: any) {
    setDirtyCodes((prev) => ({ ...prev, [code]: true }));
    setZones((prev) =>
      prev.map((z) =>
        z.wilaya_code === code
          ? {
              ...z,
              rates: {
                ...z.rates,
                [method]: { ...z.rates[method], [field]: value },
              },
            }
          : z
      )
    );
  }

  const filtered = zones.filter(
    (z) =>
      z.wilaya_code.includes(search) ||
      z.wilaya_name_fr.toLowerCase().includes(search.toLowerCase()) ||
      z.wilaya_name_ar.includes(search)
  );

  return (
    <div className="space-y-5 bg-white p-6 rounded-2xl border border-[#D4AF62]/40 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b pb-4">
        <div>
          <h2 className="text-xl font-serif font-bold text-[#063D2E]">
            Gestion des Tarifs de Livraison — 69 Wilayas (Domicile &amp; Stop-Desk)
          </h2>
          <p className="text-xs text-gray-600 mt-0.5">
            Définissez les prix en DA pour la livraison à domicile et en bureau relais (Stop-Desk). Ces tarifs s'affichent et se calculent automatiquement dans le total du client.
          </p>
        </div>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher une wilaya (01 à 69)..."
          className="px-3.5 py-2 rounded-xl border border-gray-300 text-xs w-64"
        />
        <button type="button" onClick={handleBulkSaveAllWilayas} className="px-4 py-2 rounded-xl bg-[#D4AF62] text-[#02291F] font-extrabold text-xs">Enregistrer les 69 Wilayas (Lot)</button>
      </div>

      {bannerMsg && (
        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs font-bold">
          {bannerMsg}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b-2 border-[#063D2E] text-[#063D2E] uppercase">
              <th className="py-2.5">Code</th>
              <th className="py-2.5">Wilaya (FR / AR)</th>
              <th className="py-2.5">Prix À Domicile (DA)</th>
              <th className="py-2.5">Prix Stop-Desk (DA)</th>
              <th className="py-2.5">Délai Estimé</th>
              <th className="py-2.5 text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((z) => (
              <tr key={z.wilaya_code} className="border-b border-gray-100 hover:bg-[#F8F6F0]/60">
                <td className="py-2.5 font-mono font-extrabold text-[#063D2E]">{z.wilaya_code}</td>
                <td className="py-2.5 font-bold">
                  {z.wilaya_name_fr} <span className="text-gray-500 font-normal">({z.wilaya_name_ar})</span>
                </td>
                <td className="py-2.5">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={Boolean(z.rates.home.is_supported)}
                      onChange={(e) => updateLocalRate(z.wilaya_code, "home", "is_supported", e.target.checked ? 1 : 0)}
                    />
                    <input
                      type="number"
                      min={0}
                      step={50}
                      value={z.rates.home.fee_dzd}
                      onChange={(e) => updateLocalRate(z.wilaya_code, "home", "fee_dzd", Number(e.target.value))}
                      className="w-24 px-2.5 py-1.5 rounded-lg border border-gray-300 font-extrabold text-[#063D2E]"
                    />
                    <span className="font-bold text-gray-500">DA</span>
                  </div>
                </td>
                <td className="py-2.5">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={Boolean(z.rates.stop_desk.is_supported)}
                      onChange={(e) => updateLocalRate(z.wilaya_code, "stop_desk", "is_supported", e.target.checked ? 1 : 0)}
                    />
                    <input
                      type="number"
                      min={0}
                      step={50}
                      value={z.rates.stop_desk.fee_dzd}
                      onChange={(e) => updateLocalRate(z.wilaya_code, "stop_desk", "fee_dzd", Number(e.target.value))}
                      className="w-24 px-2.5 py-1.5 rounded-lg border border-gray-300 font-extrabold text-[#B68F40]"
                    />
                    <span className="font-bold text-gray-500">DA</span>
                  </div>
                </td>
                <td className="py-2.5">
                  <input
                    type="text"
                    value={z.rates.home.estimated_days}
                    onChange={(e) => updateLocalRate(z.wilaya_code, "home", "estimated_days", e.target.value)}
                    className="w-28 px-2 py-1 rounded border border-gray-200 text-xs"
                  />
                </td>
                <td className="py-2.5 text-right">
                  <button
                    type="button"
                    onClick={() => handleSaveZone(z)}
                    disabled={savingCode === z.wilaya_code}
                    className="px-3 py-1.5 rounded-lg bg-[#063D2E] text-[#D4AF62] font-bold hover:bg-[#02291F]"
                  >
                    {savingCode === z.wilaya_code ? "..." : "Enregistrer"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

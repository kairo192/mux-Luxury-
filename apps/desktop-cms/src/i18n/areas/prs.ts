import { defineArea } from "./define";

export const prs = defineArea("prs", {
  "reloaded": ["Catalogue rechargé ({{n}} variantes).", "Catalogue reloaded ({{n}} variants).", "أُعيد تحميل الكتالوج ({{n}} متغير)."],
  "updated": ["Mise à jour : {{n}} variantes.", "Updated: {{n}} variants.", "تم التحديث: {{n}} متغير."],
  "sync_failed": ["Synchronisation échouée", "Sync failed", "فشلت المزامنة"],
  "w32": ["58 mm — 32 caractères", "58 mm — 32 characters", "58 مم — 32 حرفاً"],
  "w42": ["80 mm — 42 caractères", "80 mm — 42 characters", "80 مم — 42 حرفاً"],
  "w48": ["80 mm — 48 caractères", "80 mm — 48 characters", "80 مم — 48 حرفاً"],
  "pin2": ["Broche 2 (Epson, Star — par défaut)", "Pin 2 (Epson, Star — default)", "المنفذ 2 (Epson وStar — افتراضي)"],
  "pin5": ["Broche 5 (Citizen, variantes)", "Pin 5 (Citizen, others)", "المنفذ 5 (Citizen وغيرها)"],
  "dpi300": ["300 dpi (haute définition)", "300 dpi (high definition)", "300 نقطة/بوصة (دقة عالية)"],
  "dpi600": ["600 dpi (très haute définition)", "600 dpi (very high definition)", "600 نقطة/بوصة (دقة عالية جداً)"],
  "reload_all": ["Recharge la totalité du catalogue", "Reloads the whole catalogue", "يعيد تحميل الكتالوج كاملاً"],
  "net_printer": ["Imprimante réseau (adresse IP)", "Network printer (IP address)", "طابعة شبكة (عنوان IP)"],
  "net_hint": ["Pour une imprimante Wi-Fi / câble réseau. Prioritaire sur les autres choix ; laissez vide sinon.", "For a Wi-Fi / network-cable printer. Takes priority over the other choices; leave empty otherwise.", "لطابعة واي فاي / كابل شبكة. لها الأولوية على الخيارات الأخرى؛ اتركه فارغاً خلاف ذلك."],
  "net_found": ["{{n}} imprimante(s) réseau trouvée(s) : {{list}}. Choisissez-la dans le champ adresse IP.", "{{n}} network printer(s) found: {{list}}. Pick it in the IP address field.", "عُثر على {{n}} طابعة شبكة: {{list}}. اخترها في حقل عنوان IP."],
  "check_ok": ["Imprimante OK ({{state}}) — rien n'a été imprimé.", "Printer OK ({{state}}) — nothing was printed.", "الطابعة سليمة ({{state}}) — لم يُطبع شيء."],
});

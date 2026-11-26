import { defineArea } from "./define";

export const dw = defineArea("dw", {
  "load_failed": ["Chargement des 69 wilayas impossible", "Could not load the 69 wilayas", "تعذّر تحميل الولايات الـ 69"],
  "bad_fee_title": ["Tarif de livraison invalide", "Invalid delivery rate", "سعر توصيل غير صالح"],
  "bad_fee_body": ["Les frais de livraison pour la wilaya {{code}} - {{name}} doivent être supérieurs ou égaux à 0 DA.", "The delivery fees for wilaya {{code}} - {{name}} must be 0 DA or more.", "يجب أن تكون رسوم التوصيل للولاية {{code}} - {{name}} صفراً أو أكثر."],
  "saved_msg": ["Tarifs de la wilaya {{code}} - {{name}} enregistrés (domicile : {{home}} DA | stop-desk : {{desk}} DA).", "Rates for wilaya {{code}} - {{name}} saved (home: {{home}} DA | stop-desk: {{desk}} DA).", "تم حفظ أسعار الولاية {{code}} - {{name}} (المنزل: {{home}} DA | نقطة الاستلام: {{desk}} DA)."],
  "saved_title": ["Wilaya {{code}} mise à jour", "Wilaya {{code}} updated", "تم تحديث الولاية {{code}}"],
  "save_failed": ["Échec de sauvegarde de la wilaya {{code}}", "Could not save wilaya {{code}}", "تعذّر حفظ الولاية {{code}}"],
  "negative_title": ["Tarif négatif détecté", "Negative rate found", "تم العثور على سعر سالب"],
  "negative_body": ["Veuillez corriger le tarif de la wilaya {{code}} - {{name}} avant la sauvegarde groupée.", "Correct the rate of wilaya {{code}} - {{name}} before saving them all.", "صحّح سعر الولاية {{code}} - {{name}} قبل الحفظ الجماعي."],
  "batch_msg": ["Les 69 wilayas ont été enregistrées et synchronisées en lot avec succès.", "All 69 wilayas were saved and synchronised.", "تم حفظ الولايات الـ 69 ومزامنتها."],
  "batch_title": ["Synchronisation 69 wilayas réussie", "69 wilayas saved", "تم حفظ الولايات الـ 69"],
  "batch_failed": ["Échec de la sauvegarde groupée des 69 wilayas", "Could not save the 69 wilayas", "تعذّر حفظ الولايات الـ 69"],
  "home_aria": ["Livraison à domicile disponible — {{name}}", "Home delivery available — {{name}}", "التوصيل إلى المنزل متاح — {{name}}"],
  "home_title": ["Livraison à domicile proposée", "Home delivery offered", "التوصيل إلى المنزل متاح"],
  "desk_aria": ["Point relais (stop-desk) disponible — {{name}}", "Stop-desk (pick-up point) available — {{name}}", "نقطة الاستلام متاحة — {{name}}"],
  "desk_title": ["Point relais (stop-desk) proposé", "Stop-desk (pick-up point) offered", "نقطة الاستلام متاحة"],
});

import { defineArea } from "./define";

export const hw = defineArea("hw", {
  "no_tauri_print": ["Hors application de bureau — impression système indisponible", "Not in the desktop app — system printing unavailable", "خارج تطبيق سطح المكتب — طباعة النظام غير متاحة"],
  "printer_error": ["Erreur imprimante", "Printer error", "خطأ في الطابعة"],
  "no_tauri_drawer": ["Hors application de bureau — tiroir-caisse indisponible", "Not in the desktop app — cash drawer unavailable", "خارج تطبيق سطح المكتب — درج النقود غير متاح"],
  "drawer_failed": ["Échec de l'ouverture du tiroir", "Could not open the drawer", "تعذّر فتح الدرج"],
  "no_tauri_test": ["Hors application de bureau — test indisponible", "Not in the desktop app — test unavailable", "خارج تطبيق سطح المكتب — الاختبار غير متاح"],
  "test_failed": ["Échec du test d'impression", "Print test failed", "فشل اختبار الطباعة"],
  "no_tauri_label": ["Hors application de bureau — impression d'étiquette indisponible", "Not in the desktop app — label printing unavailable", "خارج تطبيق سطح المكتب — طباعة الملصقات غير متاحة"],
  "no_labels": ["Aucune étiquette à imprimer", "No label to print", "لا توجد ملصقات للطباعة"],
  "label_error": ["Erreur étiqueteuse", "Label printer error", "خطأ في طابعة الملصقات"],
  "label_test_failed": ["Échec du test d'étiquette", "Label test failed", "فشل اختبار الملصق"],
  "no_printer": ["Aucune imprimante configurée", "No printer set up", "لا توجد طابعة مضبوطة"],
});

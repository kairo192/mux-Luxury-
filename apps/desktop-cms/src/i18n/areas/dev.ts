import { defineArea } from "./define";

export const dev = defineArea("dev", {
  "print_test_failed": ["échec du test d'impression", "print test failed", "فشل اختبار الطباعة"],
  "state_unknown": ["état inconnu", "unknown state", "حالة غير معروفة"],
  "serial": ["Série / RS232", "Serial / RS232", "تسلسلي / RS232"],
  "hid": ["Clavier HID (douchette)", "HID keyboard (scanner)", "لوحة مفاتيح HID (قارئ)"],
  "browser": ["Navigateur", "Browser", "المتصفح"],
  "test_ok": ["{{name}} : test imprimé avec succès.", "{{name}}: test printed.", "{{name}}: تمت طباعة الاختبار."],
  "desktop_only": ["Le test d'une imprimante se fait depuis l'application de bureau installée sur le poste de la boutique.", "A printer is tested from the desktop app installed on the shop PC.", "يُختبر الطابعة من تطبيق سطح المكتب المثبّت على جهاز المحل."],
  "test_page": ["— TEST D'IMPRESSION —", "— PRINT TEST —", "— اختبار الطباعة —"],
  "printer_ok": ["Imprimante fonctionnelle ✓", "Printer works ✓", "الطابعة تعمل ✓"],
  "test_title": ["Test d'impression", "Print test", "اختبار الطباعة"],
  "test_question": ["Le ticket de test est-il bien sorti de « {{name}} » ?", "Did the test ticket come out of “{{name}}”?", "هل خرجت تذكرة الاختبار من «{{name}}»؟"],
  "yes_printed": ["Oui, imprimé", "Yes, printed", "نعم، طُبعت"],
  "no": ["Non", "No", "لا"],
  "not_out_server": ["Le ticket de test n'est pas sorti (signalé au poste).", "The test ticket did not come out (reported at the PC).", "لم تخرج تذكرة الاختبار (أُبلغ عنها من الجهاز)."],
  "not_out": ["{{name}} : le ticket de test n'est pas sorti. Vérifiez le câble, le papier et le pilote Windows.", "{{name}}: the test ticket did not come out. Check the cable, the paper and the Windows driver.", "{{name}}: لم تخرج تذكرة الاختبار. تحقق من الكابل والورق وتعريف ويندوز."],
});

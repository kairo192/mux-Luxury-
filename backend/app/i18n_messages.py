"""Server messages in the language chosen in the CMS (French, English, Arabic).

The desktop CMS sends ``X-Luxe-Lang: fr|en|ar``. Error messages (HTTPException
details) written for people are translated on the way out and marked
``"human": true`` so the CMS shows them as they are. Requests without the
header (the online shop, scripts) get the original text, unchanged.

Each row: (text as written in the code, French, English, Arabic). ``{0}``,
``{1}``… stand for the values the code puts in the message; ``None`` for
French means the source text already is the French one.
"""
from __future__ import annotations

import re
from typing import Optional

LANGS = ("fr", "en", "ar")

MESSAGES: list[tuple[str, Optional[str], str, str]] = [
    ('Connexion requise.', None, 'Sign-in required.', 'تسجيل الدخول مطلوب.'),
    ('Session expirée. Reconnectez-vous.', None, 'Session expired. Sign in again.', 'انتهت الجلسة. سجّل الدخول من جديد.'),
    ('Votre rôle ne permet pas cette action.', None, 'Your role does not allow this action.', 'دورك لا يسمح بهذا الإجراء.'),
    ('Missing cryptographic headers (X-Luxe-Signature, X-Luxe-Timestamp, X-Luxe-Nonce)', 'Signature de sécurité manquante dans la requête.', 'Security signature missing from the request.', 'توقيع الأمان مفقود في الطلب.'),
    ('Cryptographic timestamp expired or clock skew too high ({0}s > {1}s)', "L'horloge de ce PC n'est pas à l'heure ({0} s d'écart, {1} s permises). Réglez l'heure de Windows.", "This PC's clock is wrong ({0} s off, {1} s allowed). Set the Windows time.", 'ساعة هذا الجهاز غير مضبوطة (فرق {0} ث، المسموح {1} ث). اضبط وقت ويندوز.'),
    ("Replay Attack Detected: Nonce '{0}' has already been processed", "Cette requête a déjà été reçue : elle n'est pas rejouée.", 'This request was already received: it is not replayed.', 'تم استلام هذا الطلب مسبقاً: لن يُعاد تنفيذه.'),
    ('Cryptographic signature mismatch: Request payload or headers were tampered with in transit', 'Signature de sécurité invalide : la requête a été modifiée en route.', 'Invalid security signature: the request was changed on the way.', 'توقيع أمان غير صالح: تم تعديل الطلب أثناء الإرسال.'),
    ('Trop de tentatives. Patientez un moment avant de réessayer.', None, 'Too many attempts. Wait a moment before trying again.', 'محاولات كثيرة جداً. انتظر قليلاً قبل إعادة المحاولة.'),
    ('Path traversal characters detected in upload filename', 'Nom de fichier refusé.', 'File name refused.', 'اسم الملف مرفوض.'),
    ('Nom de fichier non accepté (image JPEG, PNG ou WEBP attendue)', None, 'File name not accepted (a JPEG, PNG or WEBP image is expected)', 'اسم الملف غير مقبول (المطلوب صورة JPEG أو PNG أو WEBP)'),
    ('Fichier vide', None, 'Empty file', 'ملف فارغ'),
    ('Image trop lourde (5 Mo maximum)', None, 'Image too large (5 MB maximum)', 'الصورة كبيرة جداً (5 ميغابايت كحد أقصى)'),
    ("Format d'image non accepté (JPEG, PNG ou WEBP)", None, 'Image format not accepted (JPEG, PNG or WEBP)', 'صيغة الصورة غير مقبولة (JPEG أو PNG أو WEBP)'),
    ('File extension does not match declared image MIME type', "L'extension du fichier ne correspond pas au type d'image.", 'The file extension does not match the image type.', 'امتداد الملف لا يطابق نوع الصورة.'),
    ('Binary signature does not match declared image MIME type', "Le contenu du fichier ne correspond pas au type d'image.", 'The file content does not match the image type.', 'محتوى الملف لا يطابق نوع الصورة.'),
    ('Invalid WebP container header (missing WEBP signature)', 'Fichier WEBP invalide.', 'Invalid WEBP file.', 'ملف WEBP غير صالح.'),
    ('Malicious script signature detected inside image payload', 'Fichier refusé : il contient du code.', 'File refused: it contains code.', 'ملف مرفوض: يحتوي على شيفرة برمجية.'),
    ('Session fermée. Reconnectez-vous.', None, 'Session closed. Sign in again.', 'أُغلقت الجلسة. سجّل الدخول من جديد.'),
    ('Invalid timestamp format', 'Format de date invalide.', 'Invalid date format.', 'صيغة تاريخ غير صالحة.'),
    ('Vente introuvable', None, 'Sale not found', 'البيع غير موجود'),
    ('`since` is required', 'Date de départ requise.', 'Start date required.', 'تاريخ البداية مطلوب.'),
    ('Empty lookup code', 'Code à rechercher vide.', 'Empty search code.', 'رمز البحث فارغ.'),
    ("Une caisse (n° {0}) est déjà ouverte. Clôturez-la avant d'en ouvrir une autre.", None, 'A register (no. {0}) is already open. Close it before opening another.', 'يوجد صندوق مفتوح (رقم {0}). أقفله قبل فتح صندوق آخر.'),
    ('Aucune caisse ouverte à clôturer.', None, 'No open register to close.', 'لا يوجد صندوق مفتوح لإقفاله.'),
    ('Cette caisse est déjà clôturée.', None, 'This register is already closed.', 'هذا الصندوق مُقفل مسبقاً.'),
    ('Aucune caisse ouverte. Ouvrez la caisse avant de vendre.', None, 'No register open. Open the register before selling.', 'لا يوجد صندوق مفتوح. افتح الصندوق قبل البيع.'),
    ('Le paiement ({0} DA) doit être égal au total de la vente ({1} DA)', None, 'The payment ({0} DA) must equal the sale total ({1} DA)', 'يجب أن يساوي الدفع ({0} DA) مجموع البيع ({1} DA)'),
    ('Seule une vente peut être remboursée', None, 'Only a sale can be refunded', 'يمكن استرجاع البيع فقط'),
    ('Vente déjà {0}', None, 'Sale already {0}', 'البيع {0} مسبقاً'),
    ('Aucune caisse ouverte. Ouvrez la caisse avant de rembourser.', None, 'No register open. Open the register before refunding.', 'لا يوجد صندوق مفتوح. افتح الصندوق قبل الاسترجاع.'),
    ('Tout a déjà été remboursé sur cette vente', None, 'Everything was already refunded on this sale', 'تم استرجاع كل شيء في هذا البيع مسبقاً'),
    ("Un appareil réseau requiert 'host' dans la configuration", None, "A network device needs its 'host' (IP address)", "جهاز الشبكة يحتاج إلى عنوان 'host' (IP)"),
    ('Le port doit être compris entre 1 et 65535', None, 'The port must be between 1 and 65535', 'يجب أن يكون المنفذ بين 1 و65535'),
    ('Appareil introuvable', None, 'Device not found', 'الجهاز غير موجود'),
    ("Stock insuffisant pour '{0} ({1})'", None, "Not enough stock for '{0} ({1})'", "المخزون غير كافٍ لـ'{0} ({1})'"),
    ('Client introuvable', None, 'Customer not found', 'الزبون غير موجود'),
    ("Un article n'est plus disponible", None, 'An item is no longer available', 'قطعة لم تعد متوفرة'),
    ("Stock insuffisant pour '{0} ({1})' : demandé {2}, disponible {3}", None, "Not enough stock for '{0} ({1})': {2} asked, {3} available", "المخزون غير كافٍ لـ'{0} ({1})': المطلوب {2}، المتوفر {3}"),
    ('Cet article ne fait pas partie de la vente n° {0}', None, 'This item is not part of sale no. {0}', 'هذه القطعة ليست جزءاً من البيع رقم {0}'),
    ('Impossible de rembourser {0} pièce(s) : il en reste {1} remboursable(s)', None, 'Cannot refund {0} piece(s): {1} left to refund', 'لا يمكن استرجاع {0} قطعة: المتبقي القابل للاسترجاع {1}'),
    ("Un appareil réseau requiert un 'port' numérique", None, "A network device needs a numeric 'port'", 'جهاز الشبكة يحتاج إلى منفذ رقمي'),
    ("Le compte propriétaire existe déjà : la première configuration n'est plus possible.", None, 'The owner account already exists: the first setup is no longer possible.', 'حساب المالك موجود مسبقاً: لم يعد الإعداد الأولي ممكناً.'),
    ("Indiquez le port de l'appareil (ex. COM3)", None, "Enter the device's port (e.g. COM3)", "أدخل منفذ الجهاز (مثل COM3)"),
    ("Nom d'imprimante ou de port trop long", None, "Printer or port name too long", "اسم الطابعة أو المنفذ طويل جداً"),
    ("La broche du tiroir doit être 2 ou 5", None, "The drawer pin must be 2 or 5", "يجب أن يكون طرف الدرج 2 أو 5"),
    ("Imprimante du tiroir invalide", None, "Invalid drawer printer", "طابعة الدرج غير صالحة"),
    ("« {0} » existe déjà pour cet article", None, "“{0}” already exists for this article", "«{0}» موجود مسبقاً لهذا المنتج"),
    ("Donnez un nom à l'article", None, "Give the article a name", "أعطِ المنتج اسماً"),
    ("Pour vendre sur le site, ajoutez une photo (ou gardez « magasin seulement »)", None, "To sell on the website, add a photo (or keep “shop only”)", "للبيع في الموقع أضف صورة (أو أبقِ «المحل فقط»)"),
    ('Invalid email or password', 'Adresse e-mail ou mot de passe incorrect.', 'Incorrect email address or password.', 'البريد الإلكتروني أو كلمة المرور غير صحيحة.'),
    ('An administrator with this email already exists', 'Un utilisateur avec cet e-mail existe déjà.', 'A user with this email already exists.', 'يوجد مستخدم بهذا البريد الإلكتروني مسبقاً.'),
    ('Rôle introuvable', None, 'Role not found', 'الدور غير موجود'),
    ('Un utilisateur avec cet e-mail existe déjà', None, 'A user with this email already exists', 'يوجد مستخدم بهذا البريد الإلكتروني مسبقاً'),
    ('Utilisateur introuvable', None, 'User not found', 'المستخدم غير موجود'),
    ('Vous ne pouvez pas désactiver votre propre compte', None, 'You cannot deactivate your own account', 'لا يمكنك تعطيل حسابك الخاص'),
    ("Impossible : c'est le dernier super administrateur actif", None, 'Not possible: this is the last active owner account', 'غير ممكن: هذا آخر حساب مالك نشط'),
    ('Contenu refusé dans « {0} » : code ou lien dangereux (script, javascript:, …)', None, 'Content refused in “{0}”: dangerous code or link (script, javascript:, …)', 'تم رفض المحتوى في «{0}»: شيفرة أو رابط خطير (script، \u200fjavascript:، …)'),
    ('Bannière introuvable', None, 'Banner not found', 'اللافتة غير موجودة'),
    ("Section de la page d'accueil introuvable", None, 'Homepage block not found', 'قسم الصفحة الرئيسية غير موجود'),
    ("Le réglage système '{0}' ne peut pas être modifié ici", None, "The system setting '{0}' cannot be changed here", "لا يمكن تعديل إعداد النظام '{0}' هنا"),
    ('Wilaya {0} introuvable', None, 'Wilaya {0} not found', 'الولاية {0} غير موجودة'),
    ('Le taux de TVA doit être compris entre 0 et 100 %', None, 'The tax rate must be between 0 and 100%', 'يجب أن تكون نسبة الضريبة بين 0 و100%'),
    ('Fichier introuvable.', None, 'File not found.', 'الملف غير موجود.'),
    ('Réservé au propriétaire (super administrateur).', None, 'Owner only.', 'للمالك فقط.'),
    ('Mot de passe incorrect : opération annulée.', None, 'Wrong password: operation cancelled.', 'كلمة مرور خاطئة: أُلغيت العملية.'),
    ('Tapez RESTAURER pour confirmer.', None, 'Type RESTAURER to confirm.', 'اكتب RESTAURER للتأكيد.'),
    ('Tapez EFFACER pour confirmer.', None, 'Type EFFACER to confirm.', 'اكتب EFFACER للتأكيد.'),
    ('La commande doit contenir au moins un article', None, 'The order must contain at least one item', 'يجب أن تحتوي الطلبية على قطعة واحدة على الأقل'),
    ('Invalid media filename', 'Nom de fichier invalide.', 'Invalid file name.', 'اسم ملف غير صالح.'),
    ('Fichier introuvable', None, 'File not found', 'الملف غير موجود'),
    ('Catégorie introuvable', None, 'Category not found', 'الفئة غير موجودة'),
    ('Produit introuvable', None, 'Product not found', 'المنتج غير موجود'),
    ('Commande refusée (Protection Anti-Retour COD) : Ce numéro ({0}) ne peut pas passer de commande automatique. Contactez le service client {1} sur WhatsApp au {2}.', None, 'Order refused (COD return protection): this number ({0}) cannot place orders automatically. Contact {1} customer service on WhatsApp at {2}.', 'رُفضت الطلبية (الحماية من الإرجاع): لا يمكن لهذا الرقم ({0}) الطلب تلقائياً. تواصل مع خدمة زبائن {1} عبر واتساب على {2}.'),
    ('Commande déjà enregistrée (référence {0})', None, 'Order already recorded (reference {0})', 'الطلبية مسجّلة مسبقاً (المرجع {0})'),
    ('Wilaya {0} non desservie', None, 'Wilaya {0} is not served', 'الولاية {0} غير مخدومة'),
    ('Aucune commande ne correspond à cette référence et à ce numéro', None, 'No order matches this reference and this number', 'لا توجد طلبية بهذا المرجع وهذا الرقم'),
    ('Code promo invalide ou expiré', None, 'Discount code invalid or expired', 'رمز التخفيض غير صالح أو منتهٍ'),
    ("Ce code promo a atteint sa limite d'utilisation", None, 'This discount code has reached its usage limit', 'بلغ رمز التخفيض هذا حد الاستعمال'),
    ('Ce code promo requiert un montant minimum de {0} DA', None, 'This discount code needs a minimum of {0} DA', 'يتطلب رمز التخفيض هذا حداً أدنى قدره {0} DA'),
    ('Wilaya {0} non disponible', None, 'Wilaya {0} not available', 'الولاية {0} غير متاحة'),
    ("Le mode de livraison '{0}' n'est pas disponible pour la wilaya {1}", None, "The delivery method '{0}' is not available for wilaya {1}", "طريقة التوصيل '{0}' غير متاحة للولاية {1}"),
    ('Database connectivity check failed', 'La base de données ne répond pas.', 'The database is not answering.', 'قاعدة البيانات لا تستجيب.'),
    ('Page introuvable', None, 'Page not found', 'الصفحة غير موجودة'),
    ('Service not ready', "Le service n'est pas prêt.", 'The service is not ready.', 'الخدمة غير جاهزة.'),
    ('50 pièces maximum par article (demandé : {0})', None, '50 pieces maximum per item ({0} asked)', '50 قطعة كحد أقصى لكل منتج (المطلوب: {0})'),
    ('Code promo inconnu ou expiré', None, 'Unknown or expired discount code', 'رمز تخفيض غير معروف أو منتهٍ'),
    ("Le code promo '{0}' n'est plus utilisable (limite atteinte)", None, "The discount code '{0}' can no longer be used (limit reached)", "لم يعد رمز التخفيض '{0}' صالحاً (بلغ الحد)"),
    ("Le code promo '{0}' demande un minimum de {1} DA d'achat", None, "The discount code '{0}' needs a minimum purchase of {1} DA", "يتطلب رمز التخفيض '{0}' شراءً أدنى قدره {1} DA"),
    ("Au moins un article d'approvisionnement est requis", None, 'At least one item is required', 'قطعة واحدة على الأقل مطلوبة'),
    ('Type de mouvement de trésorerie inconnu.', None, 'Unknown treasury movement type.', 'نوع حركة خزينة غير معروف.'),
    ('Fournisseur introuvable', None, 'Supplier not found', 'المورد غير موجود'),
    ('Bon de commande introuvable', None, 'Purchase order not found', 'طلب الشراء غير موجود'),
    ('Fournisseur introuvable ou inactif', None, 'Supplier not found or inactive', 'المورد غير موجود أو غير نشط'),
    ('Ce bon de commande a déjà été réceptionné en stock', None, 'This purchase order was already received into stock', 'تم استلام طلب الشراء هذا في المخزون مسبقاً'),
    ('Ce bon de commande est déjà payé', None, 'This purchase order is already paid', 'طلب الشراء هذا مدفوع مسبقاً'),
    ('Dépense introuvable', None, 'Expense not found', 'المصروف غير موجود'),
    ("Cette dépense vient d'être modifiée. Rechargez la liste.", None, 'This expense was just changed. Reload the list.', 'عُدّل هذا المصروف للتو. أعد تحميل القائمة.'),
    ('Cette dépense est déjà payée.', None, 'This expense is already paid.', 'هذا المصروف مدفوع مسبقاً.'),
    ('Produit ID {0} introuvable', None, 'Product ID {0} not found', 'المنتج رقم {0} غير موجود'),
    ("La variante choisie n'appartient pas à « {0} ».", None, 'The chosen variant does not belong to “{0}”.', 'المتغير المختار لا ينتمي إلى «{0}».'),
    ('Choisissez la variante (couleur / taille) de « {0} » à commander.', None, 'Choose the variant (colour / size) of “{0}” to order.', 'اختر المتغير (اللون / المقاس) لـ«{0}» للطلب.'),
    ('Inventaire introuvable', None, 'Stock count not found', 'الجرد غير موجود'),
    ('Inventaire {0} — lignes non modifiables', None, 'Stock count {0} — lines can no longer be changed', 'الجرد {0} — لم يعد تعديل الأسطر ممكناً'),
    ('Variante introuvable ou inactive', None, 'Variant not found or inactive', 'المتغير غير موجود أو غير نشط'),
    ('Inventaire déjà appliqué', None, 'Stock count already applied', 'تم تطبيق الجرد مسبقاً'),
    ('Inventaire déjà {0}', None, 'Stock count already {0}', 'الجرد {0} مسبقاً'),
    ('Aucune ligne à appliquer', None, 'No line to apply', 'لا توجد أسطر للتطبيق'),
    ('Variante introuvable', None, 'Variant not found', 'المتغير غير موجود'),
    ('Stock insuffisant ({0} dispo, {1} demandé)', None, 'Not enough stock ({0} available, {1} asked)', 'المخزون غير كافٍ ({0} متوفر، {1} مطلوب)'),
    ('Stock a changé, réessayez', None, 'The stock changed, try again', 'تغيّر المخزون، أعد المحاولة'),
    ('Webhook verification token mismatch', 'Jeton de vérification du webhook incorrect.', 'Webhook verification token mismatch.', 'رمز التحقق من webhook غير مطابق.'),
    ('Webhook payload exceeds 64 KB limit', 'Message webhook trop volumineux (64 Ko maximum).', 'Webhook message too large (64 KB maximum).', 'رسالة webhook كبيرة جداً (64 كيلوبايت كحد أقصى).'),
    ('WhatsApp webhook verify token is not configured', "Le jeton de vérification WhatsApp n'est pas configuré.", 'The WhatsApp verification token is not set up.', 'رمز التحقق من واتساب غير مضبوط.'),
    ('WhatsApp webhook app secret is not configured', "Le secret de l'application WhatsApp n'est pas configuré.", 'The WhatsApp app secret is not set up.', 'سر تطبيق واتساب غير مضبوط.'),
    ('Invalid or missing X-Hub-Signature-256 webhook signature', 'Signature du webhook manquante ou invalide.', 'Webhook signature missing or invalid.', 'توقيع webhook مفقود أو غير صالح.'),
    ('Malformed JSON webhook payload', 'Message webhook illisible.', 'Unreadable webhook message.', 'رسالة webhook غير مقروءة.'),
    ('{0}: date attendue au format YYYY-MM-DD', None, '{0}: date expected as YYYY-MM-DD', '{0}: التاريخ مطلوب بصيغة YYYY-MM-DD'),
    ('from doit être <= to', 'La date de début doit précéder la date de fin.', 'The start date must be before the end date.', 'يجب أن يسبق تاريخ البداية تاريخ النهاية.'),
    ('Impossible de générer un code-barres unique, réessayez', None, 'Could not create a unique barcode, try again', 'تعذّر إنشاء باركود فريد، أعد المحاولة'),
    ('At least one variant attribute value is required for this category', 'Choisissez au moins une valeur de déclinaison pour cette catégorie.', 'Choose at least one variant value for this category.', 'اختر قيمة متغير واحدة على الأقل لهذه الفئة.'),
    ('La référence (SKU) de la déclinaison est obligatoire', None, 'The variant SKU is required', 'رمز SKU للمتغير إلزامي'),
    ("La référence (SKU) '{0}' existe déjà", None, "The SKU '{0}' already exists", "رمز SKU '{0}' موجود مسبقاً"),
    ('A variant with this color/size/attribute combination already exists for this product', 'Une déclinaison avec cette combinaison couleur / taille existe déjà pour ce produit.', 'A variant with this colour / size combination already exists for this product.', 'يوجد متغير بهذه التركيبة (لون / مقاس) لهذا المنتج.'),
    ('Déclinaison introuvable', None, 'Variant not found', 'المتغير غير موجود'),
    ('Choisissez une catégorie', None, 'Choose a category', 'اختر فئة'),
    ('Image trop lourde (15 Mo maximum)', None, 'Image too large (15 MB maximum)', 'الصورة كبيرة جداً (15 ميغابايت كحد أقصى)'),
    ('Publication impossible ({0}) : caractéristiques obligatoires manquantes : {1}', None, 'Cannot publish ({0}): required characteristics missing: {1}', 'لا يمكن النشر ({0}): خصائص إلزامية ناقصة: {1}'),
    ('Ce produit a des déclinaisons construites sur les choix de sa catégorie actuelle : supprimez-les (ou créez le produit dans la nouvelle catégorie) avant de changer de catégorie.', None, 'This product has variants built on the choices of its current category: delete them (or create the product in the new category) before changing category.', 'لهذا المنتج متغيرات مبنية على خيارات فئته الحالية: احذفها (أو أنشئ المنتج في الفئة الجديدة) قبل تغيير الفئة.'),
    ('Choisissez au moins un produit', None, 'Choose at least one product', 'اختر منتجاً واحداً على الأقل'),
    ('Code-barres déjà utilisé par {0}', None, 'Barcode already used by {0}', 'الباركود مستعمل من قبل {0}'),
    ("Caractéristique '{0}' inconnue pour cette catégorie", None, "Unknown characteristic '{0}' for this category", "خاصية غير معروفة '{0}' لهذه الفئة"),
    ("'{0}' ne sert pas à créer des déclinaisons dans cette catégorie", None, "'{0}' is not used to create variants in this category", "'{0}' لا تُستعمل لإنشاء متغيرات في هذه الفئة"),
    ("Valeur vide pour '{0}'", None, "Empty value for '{0}'", "قيمة فارغة لـ'{0}'"),
    ("Valeur '{0}' non valable pour '{1}'. Valeurs possibles : {2}", None, "Value '{0}' is not valid for '{1}'. Possible values: {2}", "القيمة '{0}' غير صالحة لـ'{1}'. القيم الممكنة: {2}"),
    ("L'adresse de catégorie '{0}' existe déjà", None, "The category address '{0}' already exists", "عنوان الفئة '{0}' موجود مسبقاً"),
    ('Catégorie de destination introuvable', None, 'Destination category not found', 'الفئة الهدف غير موجودة'),
    ("La caractéristique '{0}' existe déjà dans cette catégorie", None, "The characteristic '{0}' already exists in this category", "الخاصية '{0}' موجودة مسبقاً في هذه الفئة"),
    ('Caractéristique introuvable', None, 'Characteristic not found', 'الخاصية غير موجودة'),
    ("« {0} » sert à distinguer {1} variante(s) de produits (ex. couleurs, tailles). Supprimez ou archivez d'abord ces variantes / produits, puis retirez l'attribut.", None, '“{0}” is used to tell apart {1} product variant(s) (e.g. colours, sizes). Delete or archive those variants / products first, then remove the attribute.', '«{0}» تُستعمل لتمييز {1} متغير منتجات (مثل الألوان والمقاسات). احذف هذه المتغيرات / المنتجات أو أرشفها أولاً، ثم أزل الخاصية.'),
    ('« {0} » est renseigné sur {1} fiche(s) produit. Si vous confirmez, ces valeurs seront effacées des produits.', None, '“{0}” is filled in on {1} product(s). If you confirm, these values will be erased from the products.', '«{0}» معبّأة في {1} منتج. إذا أكدت، ستُمحى هذه القيم من المنتجات.'),
    ("Un produit avec l'adresse '{0}' ou la référence '{1}' existe déjà", None, "A product with the address '{0}' or the SKU '{1}' already exists", "يوجد منتج بالعنوان '{0}' أو الرمز '{1}' مسبقاً"),
    ('At least one variant axis is required', 'Au moins un axe de déclinaison est requis.', 'At least one variant axis is required.', 'محور متغيرات واحد على الأقل مطلوب.'),
    ('French label cannot be empty', 'Le libellé français ne peut pas être vide.', 'The French label cannot be empty.', 'لا يمكن أن تكون التسمية الفرنسية فارغة.'),
    ("La valeur '{0}' existe déjà", None, "The value '{0}' already exists", "القيمة '{0}' موجودة مسبقاً"),
    ('Valeur introuvable', None, 'Value not found', 'القيمة غير موجودة'),
    ("La valeur '{0}' est utilisée par {1} déclinaison(s). Renommez ou supprimez-les d'abord.", None, "The value '{0}' is used by {1} variant(s). Rename or delete them first.", "القيمة '{0}' مستعملة في {1} متغير. أعد تسميتها أو احذفها أولاً."),
    ("Image trop grande (dimensions). Réduisez-la avant de l'envoyer.", None, 'Image too large (dimensions). Reduce it before sending.', 'أبعاد الصورة كبيرة جداً. صغّرها قبل الإرسال.'),
    ('Image illisible ou endommagée.', None, 'Unreadable or damaged image.', 'صورة غير مقروءة أو تالفة.'),
    ("Ce produit a été modifié entre-temps (version {0}). Rechargez la fiche avant d'enregistrer.", None, 'This product was changed in the meantime (version {0}). Reload it before saving.', 'عُدّل هذا المنتج في هذه الأثناء (النسخة {0}). أعد تحميله قبل الحفظ.'),
    ("Ce produit a été modifié entre-temps. Rechargez la fiche avant d'enregistrer.", None, 'This product was changed in the meantime. Reload it before saving.', 'عُدّل هذا المنتج في هذه الأثناء. أعد تحميله قبل الحفظ.'),
    ("Le stock ne peut pas devenir négatif : il n'y a plus d'unité à retirer pour cette variante.", None, 'The stock cannot go below zero: there is no unit left to remove for this variant.', 'لا يمكن أن يصبح المخزون سالباً: لا توجد وحدات لإزالتها من هذا المتغير.'),
    ("La marque '{0}' existe déjà", None, "The brand '{0}' already exists", "العلامة التجارية '{0}' موجودة مسبقاً"),
    ('Photo introuvable', None, 'Photo not found', 'الصورة غير موجودة'),
    ("Caractéristiques obligatoires manquantes pour '{0}' : {1}", None, "Required characteristics missing for '{0}': {1}", "خصائص إلزامية ناقصة لـ'{0}': {1}"),
    ("La référence '{0}' apparaît deux fois", None, "The SKU '{0}' appears twice", "الرمز '{0}' مكرر"),
    ('Duplicate variant combination in payload', 'La même combinaison de déclinaison apparaît deux fois.', 'The same variant combination appears twice.', 'التركيبة نفسها مكررة.'),
    ("Le code-barres '{0}' apparaît deux fois", None, "The barcode '{0}' appears twice", "الباركود '{0}' مكرر"),
    ("Aucune valeur choisie pour '{0}'", None, "No value chosen for '{0}'", "لم يتم اختيار قيمة لـ'{0}'"),
    ('Le nom de la déclinaison est obligatoire', None, 'The variant name is required', 'اسم المتغير إلزامي'),
    ("Le stock de '{0}' ne peut pas devenir négatif ({1})", None, "The stock of '{0}' cannot go below zero ({1})", "لا يمكن أن يصبح مخزون '{0}' سالباً ({1})"),
    ("La référence '{0}' est déjà utilisée par un autre produit", None, "The SKU '{0}' is already used by another product", "الرمز '{0}' مستعمل في منتج آخر"),
    ("L'adresse '{0}' est déjà utilisée par un autre produit", None, "The address '{0}' is already used by another product", "العنوان '{0}' مستعمل في منتج آخر"),
    ("Impossible de supprimer définitivement : {0} produit(s) sont encore rattachés à cette catégorie. Veuillez d'abord réassigner ou archiver ces produits.", None, 'Cannot delete permanently: {0} product(s) still belong to this category. Move or archive them first.', 'لا يمكن الحذف النهائي: {0} منتج ما زال مرتبطاً بهذه الفئة. انقلها أو أرشفها أولاً.'),
    ('Code-barres invalide: {0}', None, 'Invalid barcode: {0}', 'باركود غير صالح: {0}'),
    ('Format de numéro algérien invalide (05/06/07 ou +213)', None, 'Invalid Algerian number (05/06/07 or +213)', 'رقم جزائري غير صالح (05/06/07 أو \u200e+213)'),
    ('Commande introuvable', None, 'Order not found', 'الطلبية غير موجودة'),
    ("Cette commande vient d'être modifiée sur un autre poste. Rechargez la liste.", None, 'This order was just changed on another PC. Reload the list.', 'عُدّلت هذه الطلبية للتو من جهاز آخر. أعد تحميل القائمة.'),
    ("Le code promo '{0}' existe déjà", None, "The discount code '{0}' already exists", "رمز التخفيض '{0}' موجود مسبقاً"),
    ('Coupon not found', 'Code promo introuvable.', 'Discount code not found.', 'رمز التخفيض غير موجود.'),
    ('Un client existe déjà avec ce numéro ({0}, #{1})', None, 'A customer already exists with this number ({0}, #{1})', 'يوجد زبون بهذا الرقم مسبقاً ({0}، #{1})'),
    ('Une commande {0} ne peut plus changer de statut', None, 'A {0} order can no longer change status', 'طلبية {0} لا يمكن تغيير حالتها بعد الآن'),
    ("La livraison à domicile n'est pas disponible pour la wilaya {0}. Choisissez l'autre mode de livraison.", None, 'Home delivery is not available for wilaya {0}. Choose the other delivery method.', 'التوصيل إلى المنزل غير متاح للولاية {0}. اختر طريقة التوصيل الأخرى.'),
    ("La livraison en point relais (stop-desk) n'est pas disponible pour la wilaya {0}. Choisissez l'autre mode de livraison.", None, 'Stop-desk delivery is not available for wilaya {0}. Choose the other delivery method.', 'التوصيل إلى نقطة الاستلام غير متاح للولاية {0}. اختر طريقة التوصيل الأخرى.'),
    ('Fichier de sauvegarde non reconnu.', None, 'Backup file not recognised.', 'ملف النسخة الاحتياطية غير معروف.'),
    ('Cette sauvegarde est chiffrée : la clé BACKUP_ENCRYPTION_KEY du serveur est absente.', None, "This backup is encrypted: the server's BACKUP_ENCRYPTION_KEY is missing.", 'هذه النسخة مشفّرة: مفتاح BACKUP_ENCRYPTION_KEY غير موجود على الخادم.'),
    ('Type de sauvegarde invalide.', None, 'Invalid backup type.', 'نوع نسخة احتياطية غير صالح.'),
    ('La base de données semble vide ou inaccessible : sauvegarde annulée.', None, 'The database seems empty or unreachable: backup cancelled.', 'قاعدة البيانات تبدو فارغة أو غير متاحة: أُلغي النسخ الاحتياطي.'),
    ('Nom de sauvegarde invalide.', None, 'Invalid backup name.', 'اسم نسخة احتياطية غير صالح.'),
    ('Sauvegarde introuvable sur le serveur.', None, 'Backup not found on the server.', 'النسخة الاحتياطية غير موجودة على الخادم.'),
    ("Copie refusée : cette sauvegarde n'est pas chiffrée (BACKUP_ENCRYPTION_KEY manquante sur le serveur).", None, 'Copy refused: this backup is not encrypted (BACKUP_ENCRYPTION_KEY missing on the server).', 'رُفض النسخ: هذه النسخة غير مشفّرة (مفتاح BACKUP_ENCRYPTION_KEY غير موجود على الخادم).'),
    ('Fichier trop volumineux pour une sauvegarde de la boutique.', None, 'File too large for a shop backup.', 'الملف كبير جداً لنسخة احتياطية للمتجر.'),
    ("Ce fichier n'est pas une sauvegarde chiffrée de la boutique.", None, 'This file is not an encrypted shop backup.', 'هذا الملف ليس نسخة احتياطية مشفّرة للمتجر.'),
    ('Format de sauvegarde non pris en charge.', None, 'Backup format not supported.', 'صيغة النسخة الاحتياطية غير مدعومة.'),
    ('La sauvegarde est corrompue (empreinte SHA-256 différente).', None, 'The backup is corrupted (different SHA-256 fingerprint).', 'النسخة الاحتياطية تالفة (بصمة SHA-256 مختلفة).'),
    ('La sauvegarde est incomplète (fin du fichier absente).', None, 'The backup is incomplete (end of file missing).', 'النسخة الاحتياطية ناقصة (نهاية الملف مفقودة).'),
    ('La sauvegarde est incomplète (nombre de lignes différent).', None, 'The backup is incomplete (different number of rows).', 'النسخة الاحتياطية ناقصة (عدد الأسطر مختلف).'),
    ('La sauvegarde ne contient pas une base de boutique valide.', None, 'The backup does not contain a valid shop database.', 'النسخة الاحتياطية لا تحتوي على قاعدة بيانات متجر صالحة.'),
    ("Contrôle d'intégrité échoué ({0} liens orphelins) : opération annulée.", None, 'Integrity check failed ({0} broken links): operation cancelled.', 'فشل فحص السلامة ({0} روابط معطوبة): أُلغيت العملية.'),
    ("L'archive des photos de cette sauvegarde est endommagée : rien n'a été modifié.", None, 'The photo archive of this backup is damaged: nothing was changed.', 'أرشيف الصور في هذه النسخة تالف: لم يتغير شيء.'),
    ('Une autre opération sur la base de données est déjà en cours.', None, 'Another database operation is already running.', 'توجد عملية أخرى على قاعدة البيانات قيد التنفيذ.'),
    ('Impossible de déchiffrer la sauvegarde : elle a été créée avec une autre clé BACKUP_ENCRYPTION_KEY.', None, 'Cannot decrypt the backup: it was made with another BACKUP_ENCRYPTION_KEY.', 'تعذّر فك تشفير النسخة: أُنشئت بمفتاح BACKUP_ENCRYPTION_KEY آخر.'),
    ('La sauvegarde est illisible (archive endommagée).', None, 'The backup cannot be read (damaged archive).', 'النسخة الاحتياطية غير مقروءة (أرشيف تالف).'),
    ('La sauvegarde est illisible (données après la fin).', None, 'The backup cannot be read (data after the end).', 'النسخة الاحتياطية غير مقروءة (بيانات بعد النهاية).'),
    ('La sauvegarde est illisible (ligne incohérente).', None, 'The backup cannot be read (inconsistent row).', 'النسخة الاحتياطية غير مقروءة (سطر غير متسق).'),
    ('La sauvegarde est illisible (ligne inconnue).', None, 'The backup cannot be read (unknown row).', 'النسخة الاحتياطية غير مقروءة (سطر غير معروف).'),
    # Command-line confirmations (python -m app.backup_cli).
    ('Add --yes to confirm the restore.', 'Ajoutez --yes pour confirmer la restauration.', 'Add --yes to confirm the restore.', 'أضف \u200e--yes لتأكيد الاستعادة.'),
    ('Add --yes to confirm the reset.', 'Ajoutez --yes pour confirmer la remise à zéro.', 'Add --yes to confirm the reset.', 'أضف \u200e--yes لتأكيد إعادة التهيئة.'),
    # Warnings of the Backups & security screen (successful answers, not errors).
    ("Les sauvegardes ne sont pas chiffrées : BACKUP_ENCRYPTION_KEY n'est pas configurée sur le serveur.", None, 'Backups are not encrypted: BACKUP_ENCRYPTION_KEY is not set on the server.', 'النسخ الاحتياطية غير مشفّرة: مفتاح BACKUP_ENCRYPTION_KEY غير مضبوط على الخادم.'),
    ("Aucune sauvegarde n'existe encore.", None, 'There is no backup yet.', 'لا توجد أي نسخة احتياطية بعد.'),
    ('Dernière sauvegarde il y a {0} h : la sauvegarde automatique de nuit ne tourne pas.', None, 'Last backup {0} h ago: the automatic nightly backup is not running.', 'آخر نسخة احتياطية قبل {0} ساعة: النسخ الاحتياطي الليلي التلقائي لا يعمل.'),
    ('Aucune copie hors serveur : les sauvegardes restent sur le même serveur que la boutique. Activez S3_BACKUP_ENABLED (stockage S3, 10 Go gratuits chez Backblaze B2 ou Cloudflare R2) pour survivre à la perte du VPS.', None, 'No off-site copy: backups stay on the same server as the shop. Turn on S3_BACKUP_ENABLED (S3 storage, 10 GB free with Backblaze B2 or Cloudflare R2) to survive the loss of the VPS.', 'لا توجد نسخة خارج الخادم: تبقى النسخ الاحتياطية على نفس خادم المتجر. فعّل S3_BACKUP_ENABLED (تخزين S3، \u200f10 غيغابايت مجاناً لدى Backblaze B2 أو Cloudflare R2) لتجاوز فقدان الخادم.'),
]


def _pattern(source: str) -> "re.Pattern[str]":
    parts = re.split(r"(\{\d+\})", source)
    out = []
    for p in parts:
        m = re.fullmatch(r"\{(\d+)\}", p)
        out.append(f"(?P<p{m.group(1)}>.+?)" if m else re.escape(p))
    return re.compile(r"\A" + "".join(out) + r"\Z", re.S)


_COMPILED = [(_pattern(src), {"fr": fr or src, "en": en, "ar": ar}) for src, fr, en, ar in MESSAGES]
_EXACT = {src: {"fr": fr or src, "en": en, "ar": ar} for src, fr, en, ar in MESSAGES if "{0}" not in src}


def request_lang(value: Optional[str]) -> Optional[str]:
    """The language asked for by the CMS (X-Luxe-Lang), or None."""
    v = (value or "").strip().lower()[:2]
    return v if v in LANGS else None


def localize(text: str, lang: str) -> tuple[str, bool]:
    """(message in ``lang``, True) when the message is known; else (text, False)."""
    if lang not in LANGS or not isinstance(text, str):
        return text, False
    exact = _EXACT.get(text)
    if exact:
        return exact[lang], True
    for pat, versions in _COMPILED:
        m = pat.match(text)
        if m:
            out = versions[lang]
            for name, val in m.groupdict().items():
                out = out.replace("{" + name[1:] + "}", val)
            return out, True
    return text, False

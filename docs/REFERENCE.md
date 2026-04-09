# مرجع النظام — Help Desk Reference (Monolithic)

هذا المستند مرجع سريع ومُوحَّد لفهم النظام بعد عملية الـ Refactoring إلى Django Monolith.

## 1) نظرة عامة
- **الهيكلية:** Django Monolithic (Single Server).
- **الواجهة:** Django Templates + CSS + Vanilla JS + HTMX.
- **قاعدة البيانات:** SQLite (التطوير) / MySQL (الإنتاج).
- **المصادقة:** Django Session-Based Authentication (لا يوجد JWT).
- **السرعة:** تحسين كبير في سرعة التحميل الأولي SEO-friendly.

## 2) هيكل المجلدات (الجديد)
- `/`: جذع المشروع يحتوي على `manage.py` و `requirements.txt`.
- `accounts/`: إدارة المستخدمين، الجلسات، وتغيير كلمة المرور.
- `tickets/`: دورة حياة التذاكر، الرسائل، ومنطق العمل الأساسي.
- `notifications/`: إدارة الإشعارات (WebSocket & Email).
- `config/`: إعدادات المشروع (`settings.py`, `asgi.py`, `urls.py`).
- `templates/`: كافة ملفات HTML (Base, Accounts, Tickets).
- `static/`: ملفات CSS و JavaScript (مثل `chat.js`, `notifications.js`).
- `installer/`: سكريبتات بناء ملف التثبيت ويندوز.

## 3) الأدوار والصلاحيات (RBAC)
- **Branch:** ينشئ التذاكر ويرى تذاكر فرعه فقط.
- **Support:** يستلم التذاكر ويرد عليها ضمن قسمه (Department) فقط.
- **Admin:** صلاحيات كاملة لإدارة النظام، الفروع، والأقسام.

يتم التحقق من الصلاحيات عبر الـ Scoping في `Querysets` داخل الـ Views (مثل `TicketListView`).

## 4) التقنيات المستخدمة
- **HTMX:** لتحديث أجزاء من الصفحة (مثل قائمة التذاكر) دون إعادة تحميل الصفحة كاملة.
- **WebSockets (Channels):** للمحادثات اللحظية في التذاكر والإشعارات الفورية.
- **PyMySQL:** بديل لـ `mysqlclient` لضمان التوافق مع بيئة Windows بدون الحاجة لـ C++ Tools.

## 5) قواعد التشغيل
- **التدوير (Optimization):** جميع ملفات JS موجودة في `static/js/` ويتم استدعاؤها في القوالب حسب الحاجة.
- **الارتباط التلقائي:** يتم ربط التذكرة بالفرع والمستخدم تلقائياً عند الإنشاء.

## 6) مراجع الملفات الهامة
- `test-local.ps1`: لتشغيل البيئة المحلية بضغطة واحدة.
- `run-helpdesk.ps1`: لـ تشغيل النظام في وضع الإنتاج.
- `installer/build.ps1`: لبناء ملف الـ Setup للعميل.

---

لمزيد من التفاصيل، راجع:
- [دليل النشر والتشغيل](deployment_guide.md)
- [إعداد Gmail للتنبيهات](GMAIL_APP_PASSWORD.md)

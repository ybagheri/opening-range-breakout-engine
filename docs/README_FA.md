# موتور معاملاتی شکست محدوده بازگشایی (ORB) — پایتون + متاتریدر ۵

> 🇬🇧 [English README](../README.md)

موتور حرفه‌ای، سیستماتیک، ماژولار و production-oriented برای استراتژی **Opening Range Breakout**،
کاملاً با **پایتون** و بدون نیاز به اکسپرت MQL5. پایتون مستقیماً از طریق MetaTrader5 API با ترمینال
متاتریدر ارتباط می‌گیرد. نسخه فعلی: **v1.8.0**.

## ایده استراتژی

- محدوده بازگشایی: سقف/کف بازه `OR_START_TIME` تا `OR_END_TIME` (مثلاً ۰۹:۳۰ تا ۰۹:۴۵ نیویورک)،
  یا با `OR_DURATION_MINUTES` (پیش‌فرض‌های ۵/۱۵/۳۰/۶۰ دقیقه).
- سیگنال خرید/فروش: عبور قیمت از سقف/کف + بافر قابل تنظیم؛ کندلی که به هر دو سمت بخورد = بدون سیگنال.
- ورود فقط در پنجره `TRADING_START_TIME` تا `TRADING_END_TIME`؛ خروج اجباری در `FORCE_CLOSE_TIME`.
- حد ضرر: `opposite | or_width_multiple | fixed_points | percent | atr` (ای‌تی‌آر وایلدر با `ATR_PERIOD`).
- حد سود بر اساس ریسک‌به‌ریوارد (`RISK_REWARD`)؛ بریک‌ایون اختیاری؛ تریلینگ‌استاپ اختیاری بر حسب R.
  بریک‌ایون/تریلینگ هم در سطح تیک (قیمت خروج جهت‌محور: bid برای خرید، ask برای فروش) و هم در پول
  دوره‌ای کندل‌ها مدیریت می‌شود.
- سایز پوزیشن بر اساس درصد ریسک و Tick Value واقعی بروکر (هرگز فرض «یک پوینت = یک دلار» نمی‌کند).
- هر نماد (US30/US500/US100) وضعیت مستقل دارد؛ نمادها از `.env` قابل تنظیم‌اند.
- موتور عمداً **price-only** است: فیلتر حجم نسبتی (RVOL) روی داده واقعی CFD شکست خورد و در v1.2.0
  حذف شد؛ فیلتر ریتست هم بدون شواهد out-of-sample پیاده نمی‌شود.

## شروع سریع

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # مشخصات MT5 را وارد کنید؛ هرگز .env را کامیت نکنید
PYTHONPATH=src python -m orb_engine paper
PYTHONPATH=src python -m orb_engine backtest --data-glob 'data/*.csv'
PYTHONPATH=src python -m orb_engine status                             # خلاصه JSON
PYTHONPATH=src python -m orb_engine serve --poll-secs 30               # صفحه محلی localhost:8765
pytest                                                                  # تست‌ها
MT5_RUN_LIVE_TESTS=1 pytest tests/integration/test_mt5_terminal.py -v  # فقط ویندوز + ترمینال دمو
```

## ایمنی

حالت پیش‌فرض `DRY_RUN=true` یعنی سفارش واقعی ارسال نمی‌شود. اعتبارسنجی نماد، نرمال‌سازی حجم
(حجم کمتر از حداقل بروکر = عدم معامله, نه افزایش ریسک)، محافظ ضرر روزانه، فیلتر اسپرد،
جلوگیری از سفارش تکراری (magic number + وضعیت روزانه + SQLite)، بازیابی پس از ری‌استارت،
امتناع از معامله وقتی ATR یا فاصله SL/TP نامعتبر است.

## پژوهش

بک‌تست event-driven با اسپرد/اسلیپیج/کمیسیون واقع‌بینانه، قانون محافظه‌کار داخل‌کَندلی
(استاپ مقدم بر تارگت)، ورود در کندل بعدی (بدون look-ahead)، اعتبارسنجی walk-forward،
تست‌های robustness، مونت‌کارلو و گزارش‌های قابل بازتولید (همراه با هش config).
اسکریپت‌های `scripts/research_*.py` فقط پژوهش‌اند و وارد موتور نمی‌شوند.

## سلب مسئولیت

این نرم‌افزار پژوهشی است و توصیه مالی نیست. معامله ریسک جدی دارد؛ نتایج بک‌تست تضمینی برای آینده نیست.

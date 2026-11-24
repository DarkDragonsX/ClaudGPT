"""Open-source project | Original owner: Rad Lamine | Repository: https://github.com/RadLamine/ClaudGPT."""

                                                              

                                                              
def keep_alive():
    if not SITE_URL:
        logging.info("SITE_URL غير مضبوط؛ تم تعطيل طلبات Keep Alive الخارجية.")
        return
    print("🚀 تم تشغيل نظام منع النوم للموقع...", flush=True)
    while True:
        try:
            r = requests.get(SITE_URL, timeout=10)
            print(f"⏰ Ping! {r.status_code} - {time.strftime('%H:%M:%S')}", flush=True)
        except Exception as e:
            print(f"❌ فشل Ping: {e}", flush=True)
        time.sleep(300)


@app.route("/")
def index():
    return "AI Bot is Active!"


def run_polling():
    try:
        bot.remove_webhook()
    except Exception:
        pass
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)


def register_bot_commands():
    user_commands = [
        types.BotCommand("start", "بدء استخدام البوت"),
        types.BotCommand("help", "عرض المميزات والمساعدة"),
        types.BotCommand("clear", "مسح ذاكرة المحادثة"),
        types.BotCommand("cancel", "إلغاء العملية الحالية"),
        types.BotCommand("tts", "تحويل نص إلى صوت"),
        types.BotCommand("rembg", "إزالة الخلفية الخضراء"),
        types.BotCommand("image", "توليد صورة (تتجدد الحصة كل 12 ساعة)"),
        types.BotCommand("project", "مراجعة مشروع (ملفات متعددة أو ZIP)"),
        types.BotCommand("done", "بدء مراجعة الملفات المجمّعة"),
        types.BotCommand("agents", "تفعيل الوكلاء المتعددين (يستهلك حصة أكبر)"),
    ]
    try:
        bot.set_my_commands(user_commands)
        if ADMIN_ID:
            admin_commands = user_commands + [types.BotCommand("admin", "لوحة الإدارة")]
            admin_commands += [types.BotCommand(x, "إدارة النظام") for x in (
                "cleanup", "cleanup_now", "cleanup_on", "cleanup_off", "emergency", "emergency_on",
                "emergency_off", "emergency_auto_on", "emergency_auto_off",
                "queue", "limits", "agents_on", "agents_off", "system")]
            bot.set_my_commands(admin_commands, scope=types.BotCommandScopeChat(chat_id=ADMIN_ID))
    except Exception as exc:
        notify_admin("set_bot_commands", exc)


if __name__ == "__main__":
    if not ADMIN_ID:
        print("⚠️ ADMIN_ID غير مضبوط في .env")
    if not ENV_AI_KEY:
        print("⚠️ AI_API_KEY غير مضبوط في .env؛ ميزات Groq (تعديل الملفات/الصوت/المشاريع السريعة) لن تعمل")
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY غير مضبوط؛ لن يوجد احتياط للدردشة عند نفاد مفاتيح Groq، والوكلاء المتعددون معطلون")


    try:
        verify_required_channels_available()
    except Exception as exc:
        logging.critical("Required subscription channels are unavailable: %s", exc)
        raise SystemExit("القنوات الإلزامية غير متاحة؛ أوقف تشغيل البوت.")
    _emergency_active = get_setting("emergency_active", "0") == "1"
    _emergency_started_at = int(get_setting("emergency_started_at", "0") or 0)
    _emergency_persist_allowed = False
    for _stale in glob.glob(os.path.join(TASK_TMP_ROOT, "task_*")):
        shutil.rmtree(_stale, ignore_errors=True)
    try:
        cleanup_storage(force_vacuum=True)
    except Exception as exc:
        notify_admin("startup_cleanup", exc)
    if _emergency_active:
        _queues.pause_heavy(True)
        _queues.cancel_heavy()
    register_bot_commands()
    threading.Thread(target=run_polling, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=ensure_font, daemon=True).start()
    threading.Thread(target=maintenance_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

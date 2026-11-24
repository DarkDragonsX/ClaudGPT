"""Open-source project | Original owner: Rad Lamine | Repository: https://github.com/RadLamine/ClaudGPT."""

                                                              

                                                                           

NOTICE_MSGS = [
    "مرحباً يا {name} 🙂\nلقد طال غيابك، لذا للأسف سأحذف ذاكرتي عنك، وسأتخلى عنك كما تخليت عني.",
    "يا {name}.. هل نسيتني بهذه السهولة؟ 🥲\nلقد طال غيابك، وسأمسح كل ذكرياتنا معاً وكأننا لم نلتقِ قط.",
    "أهلاً {name}! أين اختفيت كل هذا الوقت؟ 😢\nسأضطر لحذف ذاكرتي عنك، فالذكريات لا تعيش مع من يغيب.",
    "{name}.. أنا هنا أنتظرك منذ مدة 🥺\nبما أنك لا تعود، سأنسى كل ما دار بيننا. هذا وداع قريب!",
    "مرحباً {name} 👋\nغبت طويلاً حتى بدأت ذاكرتي عنك تتبخر 💨 سأحذفها قريباً إن لم تعد.",
    "هل ما زلتَ تذكرني يا {name}؟ 🙃\nأنا بدأت أنساك فعلاً، وسأحذف ذاكرتي عنك وأتخلى عنك كما تخليت عني.",
]

FINAL_MSGS = [
    "🥀 لقد حذفتُ ذاكرتي عنك يا {name}، وتخليت عنك كما تخليت عني. إن عدت يوماً فسنبدأ من الصفر.",
    "💔 انتهى الأمر يا {name}.. مسحتُ كل ذكرياتنا. أرسل لي أي رسالة وسنبدأ قصة جديدة.",
    "🌫 تبخرت ذاكرتي عنك يا {name}. لا بأس، يمكننا أن نتعارف من جديد متى شئت.",
]


def cleanup_kb():
    B = types.InlineKeyboardButton
    kb = types.InlineKeyboardMarkup()
    kb.row(B("✋ توقف", callback_data="cln:stop"),
           B("ℹ️ إرشادات", callback_data="cln:info"))
    return kb


def send_night_notices():
    """يرسل إشعاراً لكل مستخدم غير نشط لديه ذاكرة محفوظة."""
    now = int(time.time())
    cutoff = now - max(0, CLEAN_INACTIVE_HOURS) * 3600
    rows = q("SELECT u.id, u.first_name FROM users u WHERE u.last_seen < ? "
             "AND EXISTS(SELECT 1 FROM messages m WHERE m.user_id=u.id) "
             "AND u.id NOT IN (SELECT user_id FROM cleanup_notices WHERE status='pending')", (cutoff,))
    sent = silent = 0
    for r in rows:
        uid = r["id"]
        if is_admin(uid):
            continue
        name = esc((r["first_name"] or "").strip() or "زعيم")
        text = (random.choice(NOTICE_MSGS).replace("{name}", name) +
                f"\n\n⏳ أمامك {CLEAN_GRACE_MIN} دقيقة لإيقاف الحذف.")
        try:
            msg = bot.send_message(uid, text, parse_mode="HTML", reply_markup=cleanup_kb())
            ex("INSERT INTO cleanup_notices(user_id,chat_id,message_id,sent_ts,status) "
               "VALUES(?,?,?,?,'pending') ON CONFLICT(user_id) DO UPDATE SET "
               "chat_id=excluded.chat_id, message_id=excluded.message_id, "
               "sent_ts=excluded.sent_ts, status='pending'",
               (uid, msg.chat.id, msg.message_id, int(time.time())))
            sent += 1
        except Exception as e:
            if is_dead_chat_error(e):

                ex("DELETE FROM messages WHERE user_id=?", (uid,))
                silent += 1
        time.sleep(0.06)
    if ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, f"🌙 التنظيف الليلي: أُرسل إشعار إلى {sent} مستخدم، "
                                       f"وحُذفت ذاكرة {silent} مستخدم حاظر للبوت.")
        except Exception:
            pass


def _strip_notice_kb(row):
    try:
        bot.edit_message_reply_markup(row["chat_id"], row["message_id"], reply_markup=None)
    except Exception:
        pass


def process_expired_notices():
    """بعد انتهاء المهلة: يحذف ذاكرة من لم يرد، ويبلّغهم بالحذف."""
    now = int(time.time())
    due = now - CLEAN_GRACE_MIN * 60
    rows = q("SELECT n.user_id, n.chat_id, n.message_id, n.sent_ts, u.last_seen, u.first_name "
             "FROM cleanup_notices n LEFT JOIN users u ON u.id=n.user_id "
             "WHERE n.status='pending' AND n.sent_ts<=?", (due,))
    deleted = 0
    for r in rows:
        uid = r["user_id"]

        if r["last_seen"] and r["last_seen"] > r["sent_ts"]:
            ex("UPDATE cleanup_notices SET status='saved' WHERE user_id=?", (uid,))
            _strip_notice_kb(r)
            continue
        ex("DELETE FROM messages WHERE user_id=?", (uid,))
        ex("UPDATE users SET summary='', summary_count=0 WHERE id=?", (uid,))
        ex("DELETE FROM user_files WHERE user_id=?", (uid,))
        ex("UPDATE cleanup_notices SET status='deleted' WHERE user_id=?", (uid,))
        _strip_notice_kb(r)
        name = esc((r["first_name"] or "").strip() or "زعيم")
        try:
            bot.send_message(uid, random.choice(FINAL_MSGS).replace("{name}", name), parse_mode="HTML")
        except Exception:
            pass
        deleted += 1
        time.sleep(0.06)
    if deleted and ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, f"🧹 حُذفت ذاكرة الذكاء الاصطناعي لـ {deleted} مستخدم لم يردّوا خلال "
                                       f"{CLEAN_GRACE_MIN} دقيقة، وتم إبلاغهم.")
        except Exception:
            pass


def cleanup_cb(c, p):
    act = p[1] if len(p) > 1 else ""
    uid = c.from_user.id
    if act == "info":
        bot.answer_callback_query(
            c.id, "يتم تنظيف محادثات وذاكرة الذكاء الاصطناعي للمستخدمين الذين لا يستخدمون البوت.",
            show_alert=True)
    elif act == "stop":
        row = q("SELECT * FROM cleanup_notices WHERE user_id=?", (uid,), one=True)
        if row and row["status"] == "pending":
            ex("UPDATE cleanup_notices SET status='stopped' WHERE user_id=?", (uid,))
            ex("UPDATE users SET last_seen=? WHERE id=?", (int(time.time()), uid))
            bot.answer_callback_query(c.id, "تم إيقاف الحذف ✅")
            try:
                bot.edit_message_text("✅ رائع! عدتَ في الوقت المناسب، وسأحتفظ بذاكرتي عنك 🤗",
                                      c.message.chat.id, c.message.message_id)
            except Exception:
                pass
        elif row and row["status"] == "deleted":
            bot.answer_callback_query(c.id, "تم الحذف سابقاً. أرسل رسالة لنبدأ من جديد 🙂", show_alert=True)
        else:
            bot.answer_callback_query(c.id, "لا يوجد حذف قيد التنفيذ.")
    else:
        bot.answer_callback_query(c.id)


def night_scheduler():
    """يعمل بشكل دائم: عند الساعة 12 ليلاً يرسل الإشعارات، وكل 30 ثانية يعالج المهل المنتهية."""
    while True:
        try:
            now = dt.datetime.now(LOCAL_TZ)
            today = now.strftime("%Y-%m-%d")
            if now.hour == CLEAN_HOUR and get_setting("last_night_run") != today:
                set_setting("last_night_run", today)
                send_night_notices()
            process_expired_notices()
        except Exception as e:
            notify_admin("night_scheduler", e)
        time.sleep(30)


                                             

def _memory_snapshot():
    total = available = used = None

    try:
        with open("/sys/fs/cgroup/memory.max", "r", encoding="ascii") as fh:
            raw_limit = fh.read().strip()
        with open("/sys/fs/cgroup/memory.current", "r", encoding="ascii") as fh:
            raw_current = fh.read().strip()
        if raw_limit != "max":
            total, used = int(raw_limit), int(raw_current)
            if total > 0:
                return total, min(used, total)
    except Exception:
        pass
    try:
        with open("/sys/fs/cgroup/memory/memory.limit_in_bytes", "r", encoding="ascii") as fh:
            total_v1 = int(fh.read().strip())
        with open("/sys/fs/cgroup/memory/memory.usage_in_bytes", "r", encoding="ascii") as fh:
            used_v1 = int(fh.read().strip())
        if 0 < total_v1 < (1 << 60):
            return total_v1, min(used_v1, total_v1)
    except Exception:
        pass
    try:
        with open("/proc/meminfo", "r", encoding="ascii") as fh:
            vals = {}
            for line in fh:
                if ":" in line:
                    k, v = line.split(":", 1)
                    m = re.search(r"(\d+)", v)
                    if m:
                        vals[k] = int(m.group(1)) * 1024
            total = vals.get("MemTotal")
            available = vals.get("MemAvailable")
            if total and available is not None:
                used = total - available
    except Exception:
        pass
    if total is None:
        try:
            total = int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
            used = None
        except Exception:
            pass
    if used is None:
        try:
            import resource
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            used = int(rss * (1024 if sys.platform != "darwin" else 1))
        except Exception:
            pass
    return total, used


def _dir_size(path):
    total = 0
    try:
        for root, _, files in os.walk(path):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def resource_snapshot():
    try:
        usage = shutil.disk_usage(TASK_TMP_ROOT)
        disk_pct = (usage.total - usage.free) * 100.0 / max(1, usage.total)
    except Exception:
        usage, disk_pct = None, None
    ram_total, ram_used = _memory_snapshot()
    ram_pct = (ram_used * 100.0 / ram_total) if ram_total and ram_used is not None else None
    db_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    db_limit = max(1, DB_MAX_MB) * 1024 * 1024
    temp_bytes = _dir_size(TASK_TMP_ROOT)
    queues = _queues.snapshot() if globals().get("_queues") else {}
    active = sum(x["active"] for x in queues.values())
    waiting = sum(x["waiting"] for x in queues.values())
    waiting_cap = sum(x["max_waiting"] for x in queues.values())

    queue_pct = max((x["waiting"] * 100.0 / max(1, x["max_waiting"])
                     for x in queues.values()), default=0.0)
    return {"disk_total": usage.total if usage else None,
            "disk_free": usage.free if usage else None,
            "disk_pct": disk_pct, "ram_total": ram_total, "ram_used": ram_used,
            "ram_pct": ram_pct, "db_bytes": db_bytes, "db_limit": db_limit,
            "db_pct": db_bytes * 100.0 / db_limit,
            "temp_bytes": temp_bytes, "temp_limit": MAX_TEMP_STORAGE_BYTES,
            "temp_pct": temp_bytes * 100.0 / MAX_TEMP_STORAGE_BYTES,
            "active": active, "waiting": waiting, "waiting_cap": waiting_cap,
            "queue_pct": queue_pct, "queues": queues}


def emergency_threshold_reached(s):
    return ((s.get("db_pct") is not None and s["db_pct"] >= EMERGENCY_DB_PCT) or
            (s.get("disk_pct") is not None and s["disk_pct"] >= EMERGENCY_DISK_PCT) or
            (s.get("ram_pct") is not None and s["ram_pct"] >= EMERGENCY_RAM_PCT) or
            s.get("temp_pct", 0) >= EMERGENCY_TEMP_PCT or
            s.get("queue_pct", 0) >= EMERGENCY_QUEUE_PCT)


def _format_resources(s):
    def pct(v): return "غير متاح" if v is None else f"{v:.1f}%"
    mb = lambda v: f"{v / (1024 * 1024):.1f}MB"
    return (f"القرص المستخدم: {pct(s['disk_pct'])}\nRAM: {pct(s['ram_pct'])}\n"
            f"قاعدة البيانات: {mb(s['db_bytes'])}/{mb(s['db_limit'])} ({pct(s['db_pct'])})\n"
            f"الملفات المؤقتة: {mb(s['temp_bytes'])}/{mb(s['temp_limit'])} ({pct(s['temp_pct'])})\n"
            f"المهام النشطة: {s['active']} | المنتظرة: {s['waiting']} ({s.get('queue_pct', 0):.1f}% من السعة)")


_emergency_state_lock = threading.RLock()


def _start_emergency_unlocked(automatic=False, snapshot=None):
    global _emergency_active, _emergency_started_at, _emergency_persist_allowed
    if _emergency_active:
        return False
    _emergency_active = True
    _emergency_started_at = time.time()
    _emergency_persist_allowed = False
    set_setting("emergency_active", "1")
    set_setting("emergency_started_at", str(int(_emergency_started_at)))
    set_setting("emergency_until", str(int(_emergency_started_at + 46 * 60)))
    set_setting("emergency_previous_agents", get_setting("agents_enabled", "1"))
    set_setting("agents_enabled", "0")

    _queues.pause_heavy(True)
    _queues.cancel_heavy()

    try:
        result = full_wipe(reason="emergency", notice_text=EMERGENCY_NOTICE, reset_expired_quotas=False)
    except Exception as exc:

        notify_admin("emergency_full_wipe", exc)
        result = {"deleted": False}
    if ADMIN_ID:
        try:
            snap = snapshot or resource_snapshot()
            bot.send_message(ADMIN_ID, "🚨 تم تشغيل نظام الطوارئ " + ("تلقائياً" if automatic else "يدوياً")
                             + ".\n" + _format_resources(snap))
        except Exception:
            pass
    return result.get("deleted", True)


def start_emergency(automatic=False, snapshot=None):
    with _emergency_state_lock:
        return _start_emergency_unlocked(automatic, snapshot)


def _maintain_emergency_unlocked(snapshot=None):
    global _emergency_persist_allowed, _emergency_active
    elapsed = time.time() - (_emergency_started_at or int(get_setting("emergency_started_at", "0") or 0))
    snapshot = snapshot or resource_snapshot()
    critical = emergency_threshold_reached(snapshot)
    _emergency_persist_allowed = bool(elapsed >= 45 * 60 and not critical)
    if elapsed >= 46 * 60:
        if not critical:
            _emergency_active = False
            set_setting("emergency_active", "0")
            set_setting("agents_enabled", get_setting("emergency_previous_agents", "1"))
            _queues.resume_all()
            _emergency_persist_allowed = False
            set_setting("emergency_completed_at", str(int(time.time())))
            if ADMIN_ID:
                try:
                    bot.send_message(ADMIN_ID, "✅ انتهت حالة الطوارئ بعد فحص الموارد، وعادت الخدمات الآمنة للعمل.")
                except Exception:
                    pass
        else:
            set_setting("emergency_until", str(int(time.time() + 60)))
            last = int(get_setting("emergency_critical_alert", "0") or 0)
            if ADMIN_ID and time.time() - last >= 300:
                set_setting("emergency_critical_alert", str(int(time.time())))
                try:
                    bot.send_message(ADMIN_ID, "🚨 ما زالت الموارد في الحالة الحرجة بعد 46 دقيقة؛ يستمر وضع الحماية.\n"
                                               + _format_resources(snapshot))
                except Exception:
                    pass


def maintain_emergency(snapshot=None):
    with _emergency_state_lock:
        return _maintain_emergency_unlocked(snapshot)


def _stop_emergency_unlocked(force=False):
    global _emergency_active, _emergency_persist_allowed
    snap = resource_snapshot()
    if emergency_threshold_reached(snap) and not force:
        return False, snap
    _emergency_active = False
    _emergency_persist_allowed = False
    set_setting("emergency_active", "0")
    set_setting("agents_enabled", get_setting("emergency_previous_agents", "1"))
    _queues.resume_all()
    return True, snap


def stop_emergency(force=False):
    with _emergency_state_lock:
        return _stop_emergency_unlocked(force)


def queue_status_text():
    rows = []
    for name, item in _queues.snapshot().items():
        rows.append(f"{name}: نشط {item['active']}/{item['workers']} | انتظار {item['waiting']}/{item['max_waiting']}"
                    + (" | متوقف" if item["paused"] else ""))
    return "📋 حالة الطوابير\n" + "\n".join(rows)


def limits_status_text():
    return ("⚙️ حدود التزامن\n" + "\n".join([
        f"الوكلاء المتعددون: 3", f"توليد الصور: 2", f"TTS: 4", f"STT: 5", f"تحليل الصور: 4",
        f"المحادثات: {CHAT_CONCURRENCY} (CHAT_CONCURRENCY)",
        f"مراجعة المشاريع: {PROJECT_CONCURRENCY} (PROJECT_CONCURRENCY)",
        f"تعديل الملفات: {CODE_EDIT_CONCURRENCY} (CODE_EDIT_CONCURRENCY)",
        f"PDF: {PDF_CONCURRENCY} (PDF_CONCURRENCY)",
        f"إزالة الخلفية: {REMBG_CONCURRENCY} (REMBG_CONCURRENCY)",
        f"حد الانتظار لكل طابور: {QUEUE_MAX_WAITING}", f"مهلة المهمة: {QUEUE_TASK_TIMEOUT} ثانية"]))


def admin_system_command(m):
    if not is_admin(m.from_user.id):
        return
    cmd = (m.text or "").split()[0].split("@")[0].lower()
    if cmd == "/cleanup":
        return bot.reply_to(m, f"حالة التنظيف: {'مفعّل' if get_setting('cleanup_enabled','1') == '1' else 'متوقف'}\n"
                               f"آخر تنظيف: {fmt_ts(int(get_setting('last_cleanup','0') or 0))}\n"
                               f"آخر سبب: {get_setting('last_cleanup_reason','—')}")
    if cmd == "/cleanup_now":
        result = full_wipe(reason="manual", notice_text=CLEANUP_NOTICE, reset_expired_quotas=False)
        return bot.reply_to(m, "✅ نُفّذ التنظيف اليدوي. " + ("أُرسلت رسالة الدورة للمستخدمين." if result['deleted'] else "لم توجد بيانات لحذفها."))
    if cmd in ("/cleanup_on", "/cleanup_off"):
        enabled = cmd.endswith("on")
        set_setting("cleanup_enabled", "1" if enabled else "0")
        return bot.reply_to(m, "✅ تم تفعيل التنظيف التلقائي." if enabled else "⛔ تم إيقاف التنظيف التلقائي.")
    if cmd == "/emergency":
        return bot.reply_to(m, ("🚨 وضع الطوارئ مفعّل\n" if _emergency_active else "✅ وضع الطوارئ غير مفعّل\n")
                               + _format_resources(resource_snapshot()))
    if cmd == "/emergency_on":
        start_emergency(automatic=False)
        return bot.reply_to(m, "🚨 تم تشغيل نظام الطوارئ.")
    if cmd == "/emergency_off":
        force = "force" in (m.text or "").lower()
        ok, snap = stop_emergency(force=force)
        return bot.reply_to(m, "✅ تم إيقاف الطوارئ.\n" + _format_resources(snap)
                            if ok else "⛔ ما زالت الموارد حرجة. لإيقافها رغم ذلك أرسل: /emergency_off force\n"
                                       "(وأوقف الطوارئ التلقائية أولاً بـ /emergency_auto_off حتى لا تعود فوراً)\n"
                                       + _format_resources(snap))
    if cmd in ("/emergency_auto_on", "/emergency_auto_off"):
        enabled = cmd.endswith("on")
        set_setting("auto_emergency", "1" if enabled else "0")
        return bot.reply_to(m, "✅ تم تفعيل الطوارئ التلقائية." if enabled else "⛔ تم إيقاف الطوارئ التلقائية (يبقى تشغيلها يدوياً ممكناً).")
    if cmd == "/queue":
        return bot.reply_to(m, queue_status_text())
    if cmd == "/limits":
        return bot.reply_to(m, limits_status_text())
    if cmd == "/agents_on":
        if _emergency_active:
            return bot.reply_to(m, "⛔ لا يمكن تفعيل الوكلاء أثناء الطوارئ.")
        set_setting("agents_enabled", "1")
        return bot.reply_to(m, "✅ تم تفعيل خدمة الوكلاء المتعددين للمستخدمين.")
    if cmd == "/agents_off":
        set_setting("agents_enabled", "0")
        if _emergency_active:
            set_setting("emergency_previous_agents", "0")
        _queues.lanes["agents"].cancel_all()
        return bot.reply_to(m, "⛔ تم إيقاف الوكلاء المتعددين وإلغاء المهام المنتظرة.")
    if cmd == "/system":
        return bot.reply_to(m, "🖥 حالة النظام\n" + _format_resources(resource_snapshot()) + "\n"
                               f"وضع الطوارئ: {'مفعّل' if _emergency_active else 'غير مفعّل'}\n"
                               f"التنظيف التلقائي: {'مفعّل' if get_setting('cleanup_enabled','1') == '1' else 'متوقف'}\n"
                               f"الطوارئ التلقائية: {'مفعّلة' if get_setting('auto_emergency','1') == '1' else 'متوقفة'}")



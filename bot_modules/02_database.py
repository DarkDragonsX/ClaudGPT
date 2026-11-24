"""Open-source project | Original owner: Rad Lamine | Repository: https://github.com/RadLamine/ClaudGPT."""

                                                              

                                                              
DB_PATH = os.getenv("DB_PATH", "bot_data.db")
_db = sqlite3.connect(DB_PATH, check_same_thread=False)
_db.row_factory = sqlite3.Row
_dblock = threading.RLock()


def q(sql, args=(), one=False):
    with _dblock:
        cur = _db.execute(sql, args)
        return cur.fetchone() if one else cur.fetchall()


def ex(sql, args=()):
    with _dblock:
        cur = _db.execute(sql, args)
        _db.commit()
        return cur


with _dblock:
    _db.execute("PRAGMA journal_mode=DELETE")
    _db.execute("PRAGMA temp_store=MEMORY")
    _db.execute("PRAGMA foreign_keys=ON")
    _db.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        joined INTEGER, last_seen INTEGER, msg_count INTEGER DEFAULT 0,
        summary TEXT DEFAULT '', summary_count INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        role TEXT, content TEXT, ts INTEGER);
    CREATE INDEX IF NOT EXISTS idx_msg_user ON messages(user_id, id);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        text TEXT, photo TEXT, status TEXT DEFAULT 'open', ts INTEGER);
    CREATE TABLE IF NOT EXISTS cleanup_notices(
        user_id INTEGER PRIMARY KEY, chat_id INTEGER, message_id INTEGER,
        sent_ts INTEGER, status TEXT DEFAULT 'pending');
    CREATE TABLE IF NOT EXISTS user_files(
        user_id INTEGER, kind TEXT, name TEXT, lang TEXT, content TEXT, ts INTEGER,
        PRIMARY KEY(user_id, kind));
    CREATE TABLE IF NOT EXISTS image_usage(
        user_id INTEGER, day TEXT, n INTEGER DEFAULT 0, PRIMARY KEY(user_id, day));
    CREATE TABLE IF NOT EXISTS agent_usage(
        user_id INTEGER PRIMARY KEY, window_start INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0);
    """)
    try:
        _db.execute("ALTER TABLE users ADD COLUMN agents INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    _db.execute("DELETE FROM settings WHERE key='ai_key'")                                  

    _db.execute("DELETE FROM user_files")
    _db.commit()


def cleanup_storage(force_vacuum=False):
    """تنظيف احتفاظ دوري محدود دون حذف إعدادات النظام أو صلاحيات المشرف."""
    now = int(time.time())
    chat_cutoff = now - max(1, CHAT_RETENTION_DAYS) * 86400
    user_cutoff = now - max(1, USER_RETENTION_DAYS) * 86400
    with _dblock:
        _db.execute("DELETE FROM messages WHERE ts < ?", (chat_cutoff,))
        _db.execute("DELETE FROM reports WHERE ts < ?", (chat_cutoff,))
        _db.execute("DELETE FROM messages WHERE user_id IN (SELECT id FROM users WHERE last_seen < ?)", (user_cutoff,))
        _db.execute("DELETE FROM reports WHERE user_id IN (SELECT id FROM users WHERE last_seen < ?)", (user_cutoff,))
        _db.execute("DELETE FROM users WHERE last_seen < ?", (user_cutoff,))
        total = _db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        excess = max(0, total - DB_MAX_MESSAGES)
        if excess:
            _db.execute("DELETE FROM messages WHERE id IN (SELECT id FROM messages ORDER BY ts ASC, id ASC LIMIT ?)", (excess,))
        user_count = _db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        excess_users = max(0, user_count - DB_MAX_USERS)
        if excess_users:
            oldest_users_sql = "SELECT id FROM users ORDER BY last_seen ASC LIMIT ?"
            _db.execute(f"DELETE FROM messages WHERE user_id IN ({oldest_users_sql})", (excess_users,))
            _db.execute(f"DELETE FROM reports WHERE user_id IN ({oldest_users_sql})", (excess_users,))
            _db.execute(f"DELETE FROM users WHERE id IN ({oldest_users_sql})", (excess_users,))
        report_count = _db.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        excess_reports = max(0, report_count - DB_MAX_REPORTS)
        if excess_reports:
            _db.execute("DELETE FROM reports WHERE id IN (SELECT id FROM reports ORDER BY ts ASC, id ASC LIMIT ?)", (excess_reports,))
        _db.execute("DELETE FROM cleanup_notices WHERE user_id NOT IN (SELECT id FROM users)")
        _db.execute("DELETE FROM cleanup_notices WHERE status!='pending' AND sent_ts < ?", (now - 3 * 86400,))
        _db.execute("DELETE FROM user_files")
        _db.execute("DELETE FROM image_usage WHERE day != ?", (today_key(),))
        _db.execute("DELETE FROM agent_usage WHERE window_start + 43200 <= ?", (now,))
        for row in _db.execute("SELECT DISTINCT user_id FROM messages").fetchall():
            user_total = 0
            oldest_cut = None
            for msg in _db.execute("SELECT id,LENGTH(content) n FROM messages WHERE user_id=? ORDER BY id DESC",
                                   (row[0],)).fetchall():
                if user_total + msg["n"] > MEMORY_LIMIT:
                    oldest_cut = msg["id"]
                    break
                user_total += msg["n"]
            if oldest_cut is not None:
                _db.execute("DELETE FROM messages WHERE user_id=? AND id<=?", (row[0], oldest_cut))
        _db.commit()
        db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        if force_vacuum or db_size > max(5, DB_MAX_MB) * 1024 * 1024:
            _db.execute("VACUUM")
    return {"old_chats_cutoff": chat_cutoff, "old_users_cutoff": user_cutoff,
            "messages_remaining": q("SELECT COUNT(*) n FROM messages", one=True)["n"]}


WIPE_HOURS = (0, 12)                                            
CLEANUP_NOTICE = ("✦ تم تشغيل نظام التنظيف الليلي. تم مسح بيانات المستخدمين وسجل المحادثات "
                  "وذاكرة الذكاء الاصطناعي وفق نظام التنظيف. يمكنك البدء من جديد (^_^)/ ♥")
EMERGENCY_NOTICE = ("أعزائي المستخدمين o(╥﹏╥)o ☆\n\n"
                   "نعتذر عن تشغيل نظام الطوارئ. بسبب الضغط الكبير على قاعدة البيانات، تم مسح بيانات المستخدمين "
                   "وسجل المحادثات وذاكرة الذكاء الاصطناعي.\n\n"
                   "سيبقى نظام الطوارئ فعالًا لمدة تصل إلى 46 دقيقة.\n\nشكرًا لتفهمكم ♥️")

_cleanup_lock = threading.RLock()
_cleanup_in_progress = False
_data_epoch = 0
_emergency_active = False
_emergency_started_at = 0
_emergency_persist_allowed = False
_emergency_notice_at = {}
_emergency_message_at = {}


def _clear_runtime_user_state():
    """يمسح حالات المستخدم وملفات الذاكرة والطوابير دون المساس بإعدادات النظام."""
    for name in ("pending", "project_sessions", "last_review", "_hits"):
        obj = globals().get(name)
        if isinstance(obj, dict):
            obj.clear()
    lock = globals().get("_agent_pending_lock")
    if lock:
        with lock:
            pending_agent_jobs.clear()
    file_lock = globals().get("_user_file_lock")
    if file_lock:
        with file_lock:
            user_file_cache.clear()
    rate_lock = globals().get("_emergency_rate_lock")
    if rate_lock:
        with rate_lock:
            _emergency_message_at.clear()
            _emergency_notice_at.clear()
    with globals().get("_proj_lock", threading.RLock()):
        for b in list(globals().get("project_buf", {}).values()):
            if b.get("timer"):
                b["timer"].cancel()
        globals().get("project_buf", {}).clear()
    if globals().get("_queues"):
        _queues.cancel_all("cleanup")
    for uid, lock in list(globals().get("user_locks", {}).items()):
        if not lock.locked():
            globals()["user_locks"].pop(uid, None)
    for path in list(glob.glob(os.path.join(TASK_TMP_ROOT, "task_*"))):
        shutil.rmtree(path, ignore_errors=True)


def full_wipe(reason="manual", notice_text=None, reset_expired_quotas=True):
    """حذف متكرر وآمن لبيانات المستخدمين فقط؛ تبقى settings والمفاتيح وصلاحيات الأدمن."""
    global _cleanup_in_progress, _data_epoch
    recipients, counts = [], {}
    deleted = False
    runtime_data_present = bool(user_file_cache or pending or pending_agent_jobs or project_sessions or last_review)
    try:
        runtime_data_present = runtime_data_present or any(os.path.isdir(x) for x in glob.glob(os.path.join(TASK_TMP_ROOT, "task_*")))
        if globals().get("_queues"):
            runtime_data_present = runtime_data_present or any(
                v["active"] or v["waiting"] for v in _queues.snapshot().values())
    except Exception:
        pass
    with _cleanup_lock:
        with _dblock:
            _cleanup_in_progress = True
            _data_epoch += 1
        try:
            with _dblock:
                recipients = [int(r[0]) for r in _db.execute("SELECT id FROM users").fetchall()]
                for table in ("users", "messages", "user_files", "reports", "cleanup_notices"):
                    counts[table] = _db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                now = int(time.time())
                expired_images = _db.execute("SELECT COUNT(*) FROM image_usage WHERE day != ?", (today_key(),)).fetchone()[0]
                expired_agents = _db.execute("SELECT COUNT(*) FROM agent_usage WHERE window_start + 43200 <= ?", (now,)).fetchone()[0]
                counts["expired_image_quotas"] = expired_images
                counts["expired_agent_quotas"] = expired_agents
                _db.execute("DELETE FROM messages")
                _db.execute("DELETE FROM user_files")
                _db.execute("DELETE FROM reports")
                _db.execute("DELETE FROM cleanup_notices")
                _db.execute("DELETE FROM users")

                _db.execute("DELETE FROM image_usage WHERE day != ?", (today_key(),))
                _db.execute("DELETE FROM agent_usage WHERE window_start + 43200 <= ?", (now,))
                _db.commit()
                try:
                    _db.execute("VACUUM")
                except sqlite3.Error:
                    logging.exception("SQLite VACUUM failed after full wipe")
            _clear_runtime_user_state()
            deleted = (runtime_data_present or counts.get("expired_image_quotas", 0) > 0
                       or counts.get("expired_agent_quotas", 0) > 0
                       or any(counts.get(k, 0) for k in
                              ("users", "messages", "user_files", "reports", "cleanup_notices")))
        except Exception:
            with _dblock:
                _db.rollback()
            raise
        finally:

            try:
                _clear_runtime_user_state()
            except Exception:
                logging.exception("Runtime cleanup failed")
            with _dblock:
                _cleanup_in_progress = False
    set_setting("last_cleanup", str(int(time.time())))
    set_setting("last_cleanup_reason", reason)
    msg = notice_text or CLEANUP_NOTICE
    if deleted and msg:

        for uid in recipients:
            if is_admin(uid):
                continue
            try:
                bot.send_message(uid, msg)
            except Exception:
                pass
            time.sleep(0.03)
    if ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, f"🧹 اكتمل التنظيف ({esc(reason)}). حذف بيانات من الجداول: "
                                      + ", ".join(f"{k}={v}" for k, v in counts.items()))
        except Exception:
            pass
    return {"deleted": deleted, "recipients": len(recipients), "counts": counts}


def maintenance_loop():
    """تنظيف كل 12 ساعة ومراقبة الموارد والطوارئ والطوابير."""
    while True:
        try:
            now_l = dt.datetime.now(LOCAL_TZ)
            slot = now_l.strftime("%Y-%m-%d-") + ("00" if now_l.hour < 12 else "12")
            last_slot = get_setting("last_wipe")
            if not last_slot:

                                                                                 
                set_setting("last_wipe", slot)
            elif get_setting("cleanup_enabled", "1") == "1" and last_slot != slot:
                result = full_wipe(reason="scheduled", reset_expired_quotas=True)
                if result.get("deleted"):
                    set_setting("last_wipe", slot)
                else:
                    set_setting("last_wipe", slot)
            now = time.time()
            for uid, items in list(_hits.items()):
                while items and now - items[0] > 3600:
                    items.popleft()
                if not items:
                    _hits.pop(uid, None)
            for uid in list(pending):
                get_pending(uid)
            with _agent_pending_lock:
                for uid, job in list(pending_agent_jobs.items()):
                    if now - job.get("created", now) > 600:
                        pending_agent_jobs.pop(uid, None)
            with _user_file_lock:
                for key, value in list(user_file_cache.items()):
                    if now - value.get("ts", 0) > 1800:
                        user_file_cache.pop(key, None)
            for uid, session in list(project_sessions.items()):
                if now - session.get("t", 0) > 1800:
                    project_sessions.pop(uid, None)
            for uid, review in list(last_review.items()):
                if now - review.get("t", 0) > 1800:
                    last_review.pop(uid, None)
            for key, ts in list(_err_seen.items()):
                if now - ts > 3600:
                    _err_seen.pop(key, None)
            if globals().get("_queues"):
                _queues.expire_pending()
            snapshot = resource_snapshot()
            if (not _emergency_active and get_setting("auto_emergency", "1") == "1"
                    and emergency_threshold_reached(snapshot)):
                start_emergency(automatic=True, snapshot=snapshot)
            elif _emergency_active:
                maintain_emergency(snapshot)
        except Exception as e:
            notify_admin("storage_cleanup", e)
        time.sleep(30)


def get_setting(key, default=""):
    r = q("SELECT value FROM settings WHERE key=?", (key,), one=True)
    return r["value"] if r else default


def set_setting(key, value):
    ex("INSERT INTO settings(key,value) VALUES(?,?) "
       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def touch_user(u, count=True):
    if not persistence_allowed():
        return
    now = int(time.time())
    with _dblock:
        if not persistence_allowed():
            return
        _db.execute("INSERT INTO users(id,username,first_name,joined,last_seen) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET username=excluded.username, "
                    "first_name=excluded.first_name, last_seen=excluded.last_seen",
                    (u.id, u.username or "", u.first_name or "", now, now))
        if count:
            _db.execute("UPDATE users SET msg_count=msg_count+1 WHERE id=?", (u.id,))
        _db.commit()


def add_message(uid, role, content):
    if not persistence_allowed():
        return

    raw = content or ""
    if raw.startswith(("[ملف", "[PDF", "[صورة", "[Animation", "[مراجعة")):
        raw = raw[:1200]
    safe_content = raw[:4000]
    with _dblock:
        if not persistence_allowed():
            return
        _db.execute("INSERT INTO messages(user_id,role,content,ts) VALUES(?,?,?,?)",
                    (uid, role, safe_content, int(time.time())))
        total, cut = 0, None
        for r in _db.execute("SELECT id, LENGTH(content) l FROM messages WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall():
            if total + r["l"] > MEMORY_LIMIT:
                cut = r["id"]
                break
            total += r["l"]
        if cut:
            _db.execute("DELETE FROM messages WHERE user_id=? AND id<=?", (uid, cut))
        _db.commit()


def get_history(uid):
    rows = q("SELECT role, content FROM messages WHERE user_id=? ORDER BY id", (uid,))
    return [{"role": r["role"], "content": r["content"]} for r in rows]



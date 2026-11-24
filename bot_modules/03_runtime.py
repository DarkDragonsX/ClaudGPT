"""Open-source project | Original owner: Rad Lamine | Repository: https://github.com/RadLamine/ClaudGPT."""

                                                              

                                                              
user_file_cache = {}
_user_file_lock = threading.RLock()


def persistence_allowed():
    if _cleanup_in_progress:
        return False
    task = getattr(_task_local, "task", None) if "_task_local" in globals() else None
    if task is not None and getattr(task, "generation", _data_epoch) != _data_epoch:
        return False
    if _emergency_active and not _emergency_persist_allowed:
        return False
    return True


def save_user_file(uid, kind, name, lang, content):
    """يحفظ ملف المهمة في ذاكرة العملية فقط، مع انتهاء صلاحية قصير؛ لا يكتب محتوى الملف إلى القرص/SQLite."""
    if _cleanup_in_progress:
        return
    entry = {"user_id": uid, "kind": kind, "name": (name or "")[:100],
             "lang": (lang or "")[:20], "content": (content or "")[:SAVED_FILE_CHARS], "ts": int(time.time())}
    with _user_file_lock:
        user_file_cache[(uid, kind)] = entry


def get_user_file(uid, kind, max_age=1800):
    with _user_file_lock:
        r = user_file_cache.get((uid, kind))
        if r and time.time() - r["ts"] <= max_age:
            return dict(r)
        if r:
            user_file_cache.pop((uid, kind), None)
    return None


def purge_user_files(uid, keep_code=True):
    with _user_file_lock:
        for key in list(user_file_cache):
            if key[0] == uid and (not keep_code or key[1] == "upload"):
                user_file_cache.pop(key, None)


def agents_service_enabled():
    return get_setting("agents_enabled", "1") == "1" and not _emergency_active


def agents_on(uid):
    r = q("SELECT agents FROM users WHERE id=?", (uid,), one=True)
    return bool(r and r["agents"] and agents_service_enabled())


def set_agents(uid, on):
    ex("UPDATE users SET agents=? WHERE id=?", (1 if on else 0, uid))


def word_limit(text, limit=None):
    """يقتطع النص عند حد الكلمات. يعيد (النص، العدد الكلي للكلمات، هل اقتُطع)."""
    limit = limit or MAX_FILE_WORDS
    total, end = 0, None
    for mm in re.finditer(r"\S+", text or ""):
        total += 1
        if total == limit:
            end = mm.end()
    if total <= limit:
        return text, total, False
    return text[:end], total, True


def esc(s):
    return html.escape(str(s), quote=False)


def is_admin(uid):
    return ADMIN_ID and uid == ADMIN_ID


def display_name(r):
    return (r["first_name"] or ("@" + r["username"] if r["username"] else str(r["id"]))).strip() or str(r["id"])


def fmt_ts(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts or 0)) + " UTC"


def reply(m, text, **kw):
    """رد على رسالة (يعمل مع الرسائل الحقيقية ومع كائنات بديلة من أزرار inline)."""
    return bot.send_message(m.chat.id, text, reply_to_message_id=m.message_id, **kw)


def set_reaction(m, emoji=None):
    """يضع/يزيل تفاعل (ريأكشن) على رسالة المستخدم. يتجاهل الأخطاء إن كانت المكتبة قديمة."""
    if not ENABLE_REACTIONS:
        return
    try:
        bot.set_message_reaction(m.chat.id, m.message_id,
                                 [types.ReactionTypeEmoji(emoji)] if emoji else [])
    except Exception:
        pass


_hits = collections.defaultdict(collections.deque)


def rate_ok(uid, limit=12, per=60):
    if is_admin(uid):
        return True
    now = time.time()
    d = _hits[uid]
    while d and now - d[0] > per:
        d.popleft()
    if len(d) >= limit:
        return False
    d.append(now)
    return True


user_locks = collections.defaultdict(threading.Lock)


pending = {}
pending_agent_jobs = {}
_agent_pending_lock = threading.RLock()
_emergency_rate_lock = threading.Lock()


class TaskCancelled(Exception):
    pass


class QueueTask:
    def __init__(self, lane, uid, fn, args, kwargs, signature, generation):
        self.id = uuid.uuid4().hex
        self.lane, self.uid, self.fn = lane, uid, fn
        self.args, self.kwargs = args, kwargs
        self.signature, self.generation = signature, generation
        self.cancel_event = threading.Event()
        self.created_at = time.time()
        self.started_at = 0.0
        self.tempdir = None
        self.timer = None


class _QueueLane:
    def __init__(self, name, workers, max_waiting):
        self.name, self.workers, self.max_waiting = name, max(1, workers), max_waiting
        self.cv = threading.Condition(threading.RLock())
        self.per_user = collections.defaultdict(collections.deque)
        self.round_robin = collections.deque()
        self.active = {}
        self.keys = set()
        self.waiting = 0
        self.paused = False
        for i in range(self.workers):
            threading.Thread(target=self._worker, name=f"queue-{name}-{i+1}", daemon=True).start()

    def _position(self, task):
        order = list(self.round_robin)
        rows = {u: list(self.per_user.get(u, ())) for u in order}
        pos = 0
        while any(rows.values()):
            for u in order:
                if rows[u]:
                    pos += 1
                    if rows[u][0] is task:
                        return pos
                    rows[u].pop(0)
        return max(1, self.waiting)

    def submit(self, task):
        with self.cv:
            if self.paused:
                return {"status": "paused", "position": 0}
            if task.signature in self.keys:
                return {"status": "duplicate", "position": self._position_by_signature(task.signature)}
            if task.uid in self.active:
                return {"status": "user_active", "position": 0}
            if self.per_user.get(task.uid):
                return {"status": "user_waiting", "position": self._position(self.per_user[task.uid][0])}
            if self.waiting >= self.max_waiting:
                return {"status": "full", "position": 0}
            q = self.per_user[task.uid]
            q.append(task)
            if task.uid not in self.round_robin:
                self.round_robin.append(task.uid)
            self.keys.add(task.signature)
            self.waiting += 1

                                                                                       
            pos = 0 if len(self.active) < self.workers and not self.paused else self._position(task)
            self.cv.notify()
            return {"status": "queued", "position": pos}

    def _position_by_signature(self, signature):
        for uid, tasks in self.per_user.items():
            for task in tasks:
                if task.signature == signature:
                    return self._position(task)
        return 0

    def _pop(self):
        while self.round_robin:
            uid = self.round_robin.popleft()
            tasks = self.per_user.get(uid)
            if not tasks:
                self.per_user.pop(uid, None)
                continue
            task = tasks.popleft()
            if tasks:
                self.round_robin.append(uid)
            else:
                self.per_user.pop(uid, None)
            self.waiting = max(0, self.waiting - 1)
            return task
        return None

    def _worker(self):
        while True:
            with self.cv:
                while self.paused or not self.waiting:
                    self.cv.wait(timeout=2)
                task = self._pop()
                if task is None:
                    continue
                if task.cancel_event.is_set() or task.generation != _data_epoch:
                    self.keys.discard(task.signature)
                    continue
                task.started_at = time.time()
                self.active[task.uid] = task
            try:
                os.makedirs(TASK_TMP_ROOT, exist_ok=True)
                task.tempdir = tempfile.mkdtemp(prefix="task_", dir=TASK_TMP_ROOT)
                task.timer = threading.Timer(QUEUE_TASK_TIMEOUT, task.cancel_event.set)
                task.timer.daemon = True
                task.timer.start()
                _task_local.task = task
                ensure_task_running()
                task.fn(*task.args, **task.kwargs)
            except TaskCancelled:
                logging.info("Queue task cancelled lane=%s uid=%s", self.name, task.uid)
            except Exception as exc:
                try:
                    notify_admin(f"queue:{self.name}", exc, task.uid)
                except Exception:
                    logging.exception("Unhandled queued task failure")
            finally:
                _task_local.task = None
                if task.timer:
                    task.timer.cancel()
                if task.tempdir:
                    shutil.rmtree(task.tempdir, ignore_errors=True)
                with self.cv:
                    if self.active.get(task.uid) is task:
                        self.active.pop(task.uid, None)
                    self.keys.discard(task.signature)
                    self.cv.notify_all()

    def cancel_user(self, uid):
        removed = 0
        with self.cv:
            tasks = list(self.per_user.pop(uid, ()))
            if tasks:
                self.round_robin = collections.deque(x for x in self.round_robin if x != uid)
                for task in tasks:
                    task.cancel_event.set()
                    self.keys.discard(task.signature)
                    removed += 1
                self.waiting = max(0, self.waiting - len(tasks))
            active = self.active.get(uid)
            if active:
                active.cancel_event.set()
            self.cv.notify_all()
        return removed, bool(active)

    def cancel_all(self):
        with self.cv:
            removed = self.waiting
            for tasks in self.per_user.values():
                for task in tasks:
                    task.cancel_event.set()
            self.per_user.clear()
            self.round_robin.clear()
            self.waiting = 0
            self.keys.clear()
            for task in self.active.values():
                task.cancel_event.set()
            self.cv.notify_all()
        return removed

    def snapshot(self):
        with self.cv:
            return {"workers": self.workers, "active": len(self.active), "waiting": self.waiting,
                    "max_waiting": self.max_waiting, "paused": self.paused}


class QueueManager:
    def __init__(self):
        limits = {"chat": CHAT_CONCURRENCY, "vision": 4, "agents": 3, "image": 2,
                  "tts": 4, "stt": 5, "project": PROJECT_CONCURRENCY,
                  "code_edit": CODE_EDIT_CONCURRENCY, "pdf": PDF_CONCURRENCY,
                  "rembg": REMBG_CONCURRENCY}
        self.lanes = {k: _QueueLane(k, v, QUEUE_MAX_WAITING) for k, v in limits.items()}
        self.heavy = {"vision", "agents", "image", "tts", "stt", "project", "code_edit", "pdf", "rembg"}

    def submit(self, lane, uid, fn, args=(), kwargs=None, signature=None):
        qlane = self.lanes[lane]
        task = QueueTask(lane, uid, fn, args, kwargs or {}, signature or f"{lane}:{uid}:{uuid.uuid4().hex}", _data_epoch)
        return qlane.submit(task)

    def cancel_user(self, uid):
        return {name: lane.cancel_user(uid) for name, lane in self.lanes.items()}

    def cancel_all(self, reason="cancel"):
        return sum(lane.cancel_all() for lane in self.lanes.values())

    def cancel_heavy(self):
        return sum(self.lanes[name].cancel_all() for name in self.heavy)

    def pause_heavy(self, paused=True):
        for name in self.heavy:
            lane = self.lanes[name]
            with lane.cv:
                lane.paused = paused
                lane.cv.notify_all()

    def resume_all(self):
        for lane in self.lanes.values():
            with lane.cv:
                lane.paused = False
                lane.cv.notify_all()

    def expire_pending(self):
        cutoff = time.time() - QUEUE_TASK_TIMEOUT
        for lane in self.lanes.values():
            with lane.cv:
                for uid, tasks in list(lane.per_user.items()):
                    kept = collections.deque()
                    for task in tasks:
                        if task.created_at < cutoff:
                            task.cancel_event.set()
                            lane.keys.discard(task.signature)
                            lane.waiting = max(0, lane.waiting - 1)
                        else:
                            kept.append(task)
                    if kept:
                        lane.per_user[uid] = kept
                    else:
                        lane.per_user.pop(uid, None)
                        lane.round_robin = collections.deque(x for x in lane.round_robin if x != uid)

    def snapshot(self):
        return {name: lane.snapshot() for name, lane in self.lanes.items()}


_task_local = threading.local()
TASK_TMP_ROOT = os.path.join(tempfile.gettempdir(), "tgai_" + hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:12])
os.makedirs(TASK_TMP_ROOT, exist_ok=True)
for _stale in glob.glob(os.path.join(TASK_TMP_ROOT, "task_*")):
    shutil.rmtree(_stale, ignore_errors=True)
_queues = QueueManager()


def ensure_task_running():
    task = getattr(_task_local, "task", None)
    if task and (task.cancel_event.is_set() or task.generation != _data_epoch):
        raise TaskCancelled("task cancelled or expired")


def queue_submit(lane, m, fn, args=(), kwargs=None, signature=None):
    uid = m.from_user.id
    result = _queues.submit(lane, uid, fn, args=args, kwargs=kwargs,
                            signature=signature or f"{lane}:{uid}:{m.message_id}")
    if result["status"] == "queued" and result["position"] > 0:
        try:
            bot.reply_to(m, f"⏳ طلبك في الانتظار، ترتيبك الحالي: {result['position']}\nيمكنك الإلغاء بالأمر /cancel")
        except Exception:
            pass
    elif result["status"] in ("user_active", "user_waiting", "duplicate"):
        try:
            bot.reply_to(m, "⏳ لديك طلب نشط أو في الانتظار من هذه الخدمة بالفعل. ألغِه بـ /cancel أو انتظر اكتماله.")
        except Exception:
            pass
    elif result["status"] == "full":
        try:
            bot.reply_to(m, "⚠️ طابور الخدمة ممتلئ مؤقتاً. حاول بعد قليل.")
        except Exception:
            pass
    elif result["status"] == "paused":
        try:
            bot.reply_to(m, "⛔ هذه الخدمة متوقفة مؤقتاً لحماية موارد الاستضافة.")
        except Exception:
            pass
    return result


def run_queued_tool(lane, ctx, fn, *args):
    """Run model-invoked tools on their own service queue, preserving per-lane concurrency."""
    ensure_task_running()
    done = threading.Event()
    state = {}

    def child():
        try:
            ensure_task_running()
            state["result"] = fn(ctx, *args)
        except BaseException as exc:
            state["error"] = exc
        finally:
            done.set()

    uid = ctx.uid
    task = QueueTask(lane, uid, child, (), {}, f"tool:{lane}:{uid}:{uuid.uuid4().hex}", _data_epoch)
    result = _queues.submit(lane, uid, child, signature=task.signature)
    if result["status"] != "queued":
        raise RuntimeError(f"خدمة {lane} مشغولة أو متوقفة مؤقتاً؛ لم يبدأ الطلب.")
    if result.get("position", 0) > 0:
        try:
            bot.send_message(ctx.chat_id, f"⏳ تم وضع الأداة في طابور الخدمة. ترتيبها: {result['position']}")
        except Exception:
            pass
    deadline = time.monotonic() + QUEUE_TASK_TIMEOUT + 5
    try:
        while not done.wait(0.25):
            ensure_task_running()
            if time.monotonic() >= deadline:
                raise TimeoutError(f"queued tool {lane} timed out")
    except TaskCancelled:
        _queues.lanes[lane].cancel_user(uid)
        raise
    if "error" in state:
        raise state["error"]
    ensure_task_running()
    return state.get("result")


def set_pending(uid, **kw):
    kw["t"] = time.time()
    pending[uid] = kw


def get_pending(uid):
    p = pending.get(uid)
    if p and time.time() - p["t"] > 900:
        pending.pop(uid, None)
        return None
    return p


_err_seen = {}


def is_too_large_error(exc):
    """الطلب أكبر من حد الرموز في الطلب الواحد (413): ليس نفاد حصة."""
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    msg = str(exc).lower()
    return status == 413 or "request too large" in msg or "reduce your message size" in msg


def is_service_limit_error(exc):
    if is_too_large_error(exc):
        return False
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    msg = str(exc).lower()
    return status == 429 or any(x in msg for x in (
        "rate_limit", "rate limit", "tokens per minute", "tokens per day",
        "requests per day", "quota exceeded", "exceeded your current quota",
        "insufficient_quota", "resource_exhausted", "usage limit reached"))


def is_dead_chat_error(exc):
    s = str(exc).lower()
    return any(x in s for x in ("blocked by the user", "user is deactivated", "chat not found", "forbidden"))


def user_error_message(exc):
    if is_service_limit_error(exc):
        return QUOTA_TEXT
    if "file too large" in str(exc).lower():
        return "⚠️ حجم الملف أكبر من الحد المسموح به (10MB). أرسل ملفاً أصغر."
    if "pages; limit is" in str(exc):
        return f"⚠️ يتجاوز ملف PDF الحد الأقصى وهو {MAX_PDF_PAGES} صفحة."
    return GENERIC_ERROR_TEXT


QUOTA_TEXT = ("تم استهلاك حصتك المجانية، نعتذر منك عزيزي المستخدم 🙏\n"
              "يرجى إرسال رسالتك غداً ❤️\n"
              "يمكنك متابعة مشروعك في بوت BMO من الزر أدناه 👇")


GENERIC_ERROR_TEXT = ("اعتذار 🙏 حصل خطأ ولم تصلني رسالتك. جرّب إرسال رسالتك مجدداً، "
                      "وإن استمر الخطأ أبلغ فريق الدعم.")


def error_markup(exc):
    if is_service_limit_error(exc):
        return types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🤖 بوت BMO", url=BMO_URL))
    return types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🚩 إبلاغ فريق الدعم", callback_data="rep:start"))


def fail(m, ctx, exc):
    """يعرض للمستخدم رسالة الخطأ المناسبة (ومعها زر BMO عند انتهاء الحصة المجانية)."""
    text, kb = user_error_message(exc), error_markup(exc)
    try:
        if ctx and ctx.status_mid:
            bot.edit_message_text(text, ctx.chat_id, ctx.status_mid, reply_markup=kb)
            return
    except Exception:
        pass
    try:
        bot.send_message(m.chat.id, text, reply_to_message_id=getattr(m, "message_id", None), reply_markup=kb)
    except Exception:
        try:
            bot.send_message(m.chat.id, text, reply_markup=kb)
        except Exception:
            pass


def notify_admin(where, exc, uid=None):
    """إرسال المشاكل للأدمن (مع منع التكرار) مع تنقيح المفاتيح السرية."""
    raw_error = f"{type(exc).__name__}: {exc}"
    safe_error = raw_error
    for secret in (BOT_TOKEN, GEMINI_API_KEY, *AI_KEYS, *AGENT_GROQ_KEYS, *[t for _, t in CF_ACCOUNTS]):

        if secret:
            safe_error = safe_error.replace(secret, "[REDACTED]")
    logging.error("ERROR in %s: %s", where, safe_error[:900])
    key = f"{where}:{safe_error[:80]}"
    window = 1800 if is_service_limit_error(exc) else 60
    if time.time() - _err_seen.get(key, 0) < window or not ADMIN_ID:
        return
    _err_seen[key] = time.time()
    try:
        bot.send_message(
            ADMIN_ID,
            f"⚠️ <b>مشكلة في البوت</b>\n📍 {esc(where)}\n👤 المستخدم: <code>{uid}</code>\n"
            f"<pre>{esc(safe_error)[:900]}</pre>",
            parse_mode="HTML")
    except Exception:
        pass



"""Open-source project | Original owner: Rad Lamine | Repository: https://github.com/RadLamine/ClaudGPT."""

                                                              

                                                              
HELP_TEXT = (
    f"🤖 <b>{esc(BOT_NAME)}</b>\n\n"
    "مساعد ذكاء اصطناعي للمحادثة والبرمجة وتحليل الملفات.\n\n"
    "<b>الميزات:</b>\n"
    "• محادثة ومساعدة في كتابة الأكواد وتصحيحها وإنجاز المشاريع.\n"
    "• الرد على أي رسالة (نصاً أو صورة) وسأتفاعل معها وأفهم سياقها.\n"
    "• قراءة الصور وتحليلها واستخراج النصوص منها.\n"
    "• قراءة ملفات PDF، بما فيها الصفحات المصورة عند توفر دعم OCR.\n"
    "• ترجمة ملفات PDF (الحد الأقصى للملف 10MB).\n"
    "• قراءة ملفات النصوص والأكواد وإرسال الملفات المعدّلة دون حذف أي ميزة.\n"
    "• اطلب أي كود «كملف» وسأرسله ملفاً جاهزاً مع شرح بعد مراجعته من الأخطاء.\n"
    "• مراجعة مشروع كامل: أرسل عدة ملفات معاً أو ملف ZIP (حتى 5MB)، أو ابدأ <code>/project</code> ثم أرسل الملفات و<code>/done</code>. "
    "فحص آلي ومراجعة سريعة، ويمكنني إصلاح الملفات وإرسالها ZIP. للمراجعة الأعمق فعّل <code>/Agents</code> "
    "(تستهلك حصة أكبر من حصتك المجانية، فاستعملها عند الحاجة فقط).\n"
    "• الردود الطويلة تصلك كاملة بلا حد، مقسّمة تلقائياً على عدة رسائل.\n"
    "• قراءة وتلخيص صفحات الويب من الروابط.\n"
    "• تحويل النص إلى صوت — <code>/tts نص</code>.\n"
    "• توليد الصور — <code>/image وصف</code> (تُطبّق الحصة المحددة لكل مستخدم).\n"
    "• فهم الرسائل الصوتية.\n"
    "• إزالة الخلفية الخضراء — <code>/rembg</code> ثم أرسل الصورة.\n\n"
    f"📎 الحدود: الكود 60KB، الصورة 1MB، ZIP والملفات المؤقتة 5MB، والملفات العامة وPDF حتى 10MB؛ وأقرأ حتى {MAX_FILE_WORDS:,} كلمة من الملف الواحد.\n"
    "🧽 <code>/clear</code> لمسح ذاكرة محادثتك | ❌ <code>/cancel</code> للإلغاء"
)


def help_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("⭐ ادعمنا", callback_data="don:menu"),
           types.InlineKeyboardButton("🚩 إبلاغ عن مشكلة", callback_data="rep:start"))
    return kb


def donate_kb():
    B = types.InlineKeyboardButton
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(*[B(f"{'🎁' if a >= 100 else '⭐'} {a} نجمة", callback_data=f"don:{a}") for a in DONATE_AMOUNTS])
    return kb


def donate_cb(c, p):
    act = p[1] if len(p) > 1 else ""
    chat_id = c.message.chat.id
    if act == "menu":
        bot.answer_callback_query(c.id)
        bot.send_message(chat_id, "💝 شكراً لدعمك! اختر قيمة الهدية بنجوم تيليجرام ⭐:",
                         reply_markup=donate_kb())
    elif act.isdigit() and int(act) in DONATE_AMOUNTS:
        amount = int(act)
        bot.answer_callback_query(c.id)
        bot.send_invoice(
            chat_id, title="ادعم البوت ⭐",
            description=f"هدية {amount} نجمة لدعم استمرار {BOT_NAME} وتطويره. شكراً لك 💙",
            invoice_payload=f"donate:{amount}", provider_token="", currency="XTR",
            prices=[types.LabeledPrice(label="دعم البوت", amount=amount)])
    else:
        bot.answer_callback_query(c.id)


@bot.pre_checkout_query_handler(func=lambda pcq: True)
def on_pre_checkout(pcq):
    try:
        bot.answer_pre_checkout_query(pcq.id, ok=True)
    except Exception as e:
        notify_admin("pre_checkout", e, pcq.from_user.id)


@bot.message_handler(content_types=["successful_payment"])
def on_successful_payment(m):
    try:
        sp = m.successful_payment
        bot.send_message(m.chat.id, f"💙 شكراً جزيلاً على دعمك بـ {sp.total_amount} ⭐! وصلت هديتك وهي تساعدنا على الاستمرار.")
        if ADMIN_ID:
            uname = f"@{m.from_user.username}" if m.from_user.username else ""
            bot.send_message(
                ADMIN_ID,
                f"⭐ <b>هدية جديدة!</b>\n👤 {esc(m.from_user.first_name or '')} {esc(uname)} "
                f"(<code>{m.from_user.id}</code>)\n💰 {sp.total_amount} {esc(sp.currency)}\n"
                f"🧾 <code>{esc(sp.telegram_payment_charge_id)}</code>", parse_mode="HTML")
    except Exception as e:
        notify_admin("successful_payment", e, m.from_user.id)


SUBSCRIPTION_TEXT = (
    "✦ نرجو من جميع مستخدمي بوت ChatGPT الاشتراك في جميع القنوات المخصصة له، "
    "دعماً لاستمرار خدماته وتطويره وتحسين خدماته باستمرار.\n\n"
    "♢ <b>مميزات البوت:</b>\n\n"
    "• محادثات مجانية ضمن حدود مزوّد الذكاء الاصطناعي المتاحة.\n"
    "• إرسال الصور والملفات والتفاعل معها.\n"
    "• كتابة الأكواد البرمجية والمساعدة في إنجاز المشاريع.\n"
    "• توليد الأصوات وتحويل النصوص إلى صوت.\n"
    "• تقديم الأفكار والاقتراحات الإبداعية.\n"
    "• قراءة وترجمة ملفات PDF.\n"
    "• والعديد من الميزات الأخرى، اكتشفها بنفسك!\n\n"
    "نسعى دائماً إلى تقديم تجربة مميزة وخدمات مفيدة ومتاحة للجميع.\n\n"
    "✦ نتمنى لكم دوام التوفيق والنجاح، وشكراً لثقتكم ودعمكم المستمر.\n\n"
    "اشترك في جميع القنوات المطلوبة ثم اضغط «تحقق من الاشتراك»."
)


def subscription_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for channel in required_subscription_channels():
        kb.add(types.InlineKeyboardButton(channel["label"], url=channel["url"]))
    kb.add(types.InlineKeyboardButton("تحقق من الاشتراك", callback_data="sub:check"))
    return kb


def check_user_subscription(uid):
    """يتحقق من العضوية في جميع القنوات الإلزامية دون تخزين نتيجة التحقق."""
    missing = []
    try:
        for channel in required_subscription_channels():
            chat_id = channel["chat_id"]
            member = bot.get_chat_member(chat_id, uid)
            status = getattr(member, "status", "")
            is_member = status in ("creator", "administrator", "member")
            if status == "restricted":
                is_member = bool(getattr(member, "is_member", False))
            if not is_member:
                missing.append(chat_id)
        return not missing, missing, None
    except Exception as exc:
        notify_admin("subscription_check", exc, uid)
        return False, missing, exc


def require_subscription(m):
    if not m.from_user or is_admin(m.from_user.id):
        return True
    if _emergency_active:
        uid, now = m.from_user.id, time.time()
        with _emergency_rate_lock:
            last = _emergency_message_at.get(uid, 0)
            if now - last < 20:
                send_notice = now - _emergency_notice_at.get(uid, 0) >= 20
                if send_notice:
                    _emergency_notice_at[uid] = now
            else:
                _emergency_message_at[uid] = now
                send_notice = False
                last = 0
        if last and now - last < 20:
            if send_notice:
                try:
                    bot.send_message(m.chat.id, "⏳ وضع الطوارئ مفعّل؛ أرسل رسالة واحدة كل 20 ثانية من فضلك.")
                except Exception:
                    pass
            return False
    ok, missing, error = check_user_subscription(m.from_user.id)
    if ok:
        return True
    if error:
        msg = ("⚠️ تعذّر التحقق من الاشتراك حالياً. أُبلغت الإدارة بالمشكلة. "
               "تأكد الإدارة من إضافة البوت مشرفاً في جميع القنوات المطلوبة ثم أعد المحاولة.")
    else:
        msg = SUBSCRIPTION_TEXT
    bot.send_message(m.chat.id, msg, parse_mode="HTML", reply_markup=subscription_keyboard(),
                     disable_web_page_preview=True)
    return False


def verify_required_channels_available():
    """Check that Telegram can resolve every channel before polling begins."""
    _verify_locked_channels()
    for channel in required_subscription_channels():
        bot.get_chat(channel["chat_id"])

def reject_heavy_during_emergency(m):
    """Reject large media uploads before download while emergency protection is active."""
    if _emergency_active and m.from_user and not is_admin(m.from_user.id):
        try:
            bot.reply_to(m, "⛔ وضع الطوارئ مفعّل؛ أوقفت مؤقتاً معالجة الصور والصوت والملفات والمشاريع لحماية السيرفر. يمكنك متابعة المحادثات النصية الخفيفة.")
        except Exception:
            pass
        return True
    return False


@bot.message_handler(commands=["start"])
def cmd_start(m):
    if not require_subscription(m):
        return
    touch_user(m.from_user, count=False)
    bot.send_message(m.chat.id, f"👋 أهلاً {esc(m.from_user.first_name or '')}!\n\n" + HELP_TEXT,
                     parse_mode="HTML", reply_markup=help_kb())


@bot.message_handler(commands=["help"])
def cmd_help(m):
    if not require_subscription(m):
        return
    touch_user(m.from_user, count=False)
    bot.send_message(m.chat.id, HELP_TEXT, parse_mode="HTML", reply_markup=help_kb())


@bot.message_handler(commands=["cancel"])
def cmd_cancel(m):
    if not require_subscription(m):
        return
    pending.pop(m.from_user.id, None)
    with _agent_pending_lock:
        pending_agent_jobs.pop(m.from_user.id, None)
    _queues.cancel_user(m.from_user.id)
    purge_user_files(m.from_user.id, keep_code=False)
    project_sessions.pop(m.from_user.id, None)
    with _proj_lock:
        b = project_buf.pop(m.from_user.id, None)
    if b and b.get("timer"):
        b["timer"].cancel()
    bot.reply_to(m, "✅ تم الإلغاء.")


@bot.message_handler(commands=["clear"])
def cmd_clear(m):
    if not require_subscription(m):
        return
    uid = m.from_user.id
    _queues.cancel_user(uid)
    ex("DELETE FROM messages WHERE user_id=?", (uid,))
    ex("DELETE FROM user_files WHERE user_id=?", (uid,))
    purge_user_files(uid, keep_code=False)
    with _agent_pending_lock:
        pending_agent_jobs.pop(uid, None)
    project_sessions.pop(uid, None)
    last_review.pop(uid, None)
    with _proj_lock:
        buffered = project_buf.pop(uid, None)
    if buffered and buffered.get("timer"):
        buffered["timer"].cancel()
    bot.reply_to(m, "🧽 تم مسح ذاكرة محادثتك وملفاتك ومهامك المؤقتة.")


def cmd_arg(m):
    parts = (m.text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def agents_kb():
    return types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⛔ إيقاف الخدمة", callback_data="agt:off"))


def agents_turn_off(uid):
    row = q("SELECT agents FROM users WHERE id=?", (uid,), one=True)
    was_enabled = bool(row and row["agents"])
    if was_enabled:
        set_agents(uid, False)
        if globals().get("_queues"):
            _queues.lanes["agents"].cancel_user(uid)
        with _agent_pending_lock:
            pending_agent_jobs.pop(uid, None)
        add_message(uid, "user", "[إيقاف خدمة الوكلاء المتعددين]")
        add_message(uid, "assistant", AGENTS_OFF_NOTE)


@bot.message_handler(commands=["agents", "Agents"], chat_types=["private"])
def cmd_agents(m):
    if not require_subscription(m):
        return
    touch_user(m.from_user, count=False)
    uid = m.from_user.id
    arg = cmd_arg(m).strip().lower()
    if arg in ("off", "stop", "0", "ايقاف", "إيقاف"):
        agents_turn_off(uid)
        return bot.reply_to(m, AGENTS_OFF_TEXT)
    if not agents_service_enabled():
        return bot.reply_to(m, "⛔ خدمة الوكلاء المتعددين متوقفة حالياً من الإدارة أو بسبب وضع الطوارئ.")


    if not GEMINI_API_KEY:
        return bot.reply_to(m, "⚠️ لم يتم إعداد Gemini للوكلاء المتعددين على الاستضافة بعد.")

    if not AGENT_GROQ_KEYS:
        return bot.reply_to(
            m,
            "⚠️ لم يتم إعداد مفاتيح Groq الخاصة بالوكلاء المتعددين."
        )


    if agents_on(uid):
        return bot.reply_to(m, AGENTS_ALREADY_TEXT, reply_markup=agents_kb())
    set_agents(uid, True)

    add_message(uid, "user", "/Agents")
    add_message(uid, "assistant", AGENTS_ON_NOTE)
    bot.reply_to(m, AGENTS_ON_TEXT, reply_markup=agents_kb())


def agents_cb(c, p):
    uid = c.from_user.id
    action = p[1] if len(p) > 1 else ""
    if action == "off":
        agents_turn_off(uid)
        bot.answer_callback_query(c.id, "تم إيقاف الخدمة ✅")
        try:
            bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)
        except Exception:
            pass
        bot.send_message(c.message.chat.id, AGENTS_OFF_TEXT)
        return
    if action in ("confirm", "reject") and len(p) >= 3:

        with _agent_pending_lock:
            candidate = pending_agent_jobs.get(uid)
            if (candidate and candidate.get("token") == p[2]
                    and time.time() - candidate.get("created", 0) <= 600):
                job = pending_agent_jobs.pop(uid, None)
            else:
                job = None
        if not job:
            bot.answer_callback_query(c.id, "انتهت صلاحية الطلب أو تم التعامل معه مسبقاً.", show_alert=True)
            return
        if action == "reject":
            bot.answer_callback_query(c.id, "تم إلغاء المهمة، ولم تُخصم محاولة.")
            try:
                bot.edit_message_text("❌ تم إلغاء مهمة الوكلاء. لم تُخصم أي محاولة.",
                                      c.message.chat.id, c.message.message_id)
            except Exception:
                pass
            return
        bot.answer_callback_query(c.id, "تمت الموافقة. يجري إدخال المهمة إلى الطابور...")
        try:
            bot.edit_message_text("✅ تمت الموافقة. سيبدأ التنفيذ عند توفر مكان في الطابور.",
                                  c.message.chat.id, c.message.message_id)
        except Exception:
            pass
        job_m = job["m"]
        project_run(job_m, job["files"], job["notes"], job["caption"],
                    fix=job["fix"], agents_approved=True)
        return
    bot.answer_callback_query(c.id)


@bot.message_handler(commands=["image"])
def cmd_image(m):
    if not require_subscription(m):
        return
    touch_user(m.from_user)
    a = cmd_arg(m)
    if not a and getattr(m, "reply_to_message", None):
        a = (m.reply_to_message.text or m.reply_to_message.caption or "").strip()
    if not a:
        return bot.reply_to(m, "اكتب وصف الصورة، مثال:\n/image اصنع صورة لسنجاب")
    queue_submit("image", m, run_simple, args=(m, "🎨 جاري توليد الصورة.....", do_image, a))


@bot.message_handler(commands=["video"])
def cmd_video(m):
    if not require_subscription(m):
        return
    bot.reply_to(m, "تم إيقاف ميزة توليد الفيديو في هذا البوت.")


@bot.message_handler(commands=["tts"])
def cmd_tts(m):
    if not require_subscription(m):
        return
    touch_user(m.from_user)
    a = cmd_arg(m)
    if not a and getattr(m, "reply_to_message", None):
        a = (m.reply_to_message.text or m.reply_to_message.caption or "").strip()
    if not a:
        return bot.reply_to(m, "اكتب النص (أو رد على رسالة)، مثال:\n/tts مرحباً بكم")
    queue_submit("tts", m, run_simple, args=(m, "🗯 تحويل النص إلى صوت......", do_tts, a))


@bot.message_handler(commands=["rembg"])
def cmd_rembg(m):
    if not require_subscription(m):
        return
    if reject_heavy_during_emergency(m):
        return
    touch_user(m.from_user, count=False)
    set_pending(m.from_user.id, type="rembg")
    bot.reply_to(m, "🖼 أرسل الصورة الآن وسأزيل خلفيتها (خلفية خضراء). للإلغاء /cancel")


def submit_report(user, text, photo_id=None):
    if not persistence_allowed():
        return None
    safe_report = (text or "")[:3000].encode("utf-8")[:6000].decode("utf-8", "ignore")
    cur = ex("INSERT INTO reports(user_id,text,photo,ts) VALUES(?,?,?,?)",
             (user.id, safe_report, photo_id, int(time.time())))
    rid = cur.lastrowid
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("↩️ رد", callback_data=f"rep:reply:{rid}"),
           types.InlineKeyboardButton("❌ إلغاء", callback_data=f"rep:close:{rid}"))
    uname = f"@{user.username}" if user.username else ""
    head = (f"🚩 <b>بلاغ #{rid}</b>\n👤 {esc(user.first_name or '')} {esc(uname)} "
            f"(<code>{user.id}</code>)\n\n{esc(text[:700])}")
    if photo_id:
        bot.send_photo(ADMIN_ID, photo_id, caption=head, parse_mode="HTML", reply_markup=kb)
    else:
        bot.send_message(ADMIN_ID, head, parse_mode="HTML", reply_markup=kb)



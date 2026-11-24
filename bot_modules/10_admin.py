"""Open-source project | Original owner: Rad Lamine | Repository: https://github.com/RadLamine/ClaudGPT."""

                                                              

                                                              
def admin_menu_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    B = types.InlineKeyboardButton
    cl_on = get_setting("cleanup_enabled", "1") == "1"
    auto_on = get_setting("auto_emergency", "1") == "1"
    kb.add(B("👥 عداد المستخدمين", callback_data="adm:users:0:view"),
           B("🧹 تنظيف شامل الآن", callback_data="adm:cleanup"),
           B(f"🌙 التنظيف الليلي التلقائي: {'مفعّل ✅' if cl_on else 'متوقف ⛔'} (اضغط للتبديل)",
             callback_data="adm:cltoggle"),
           B(f"🚨 وضع الطوارئ: {'يعمل 🔴 (اضغط للإيقاف)' if _emergency_active else 'متوقف 🟢 (اضغط للتشغيل)'}",
             callback_data="adm:emtoggle"),
           B(f"🤖 الطوارئ التلقائية: {'مفعّلة ✅' if auto_on else 'متوقفة ⛔'} (اضغط للتبديل)",
             callback_data="adm:emauto"),
           B("🖥 حالة النظام", callback_data="adm:sys"),
           B("🧠 تبديل سلوك الذكاء الاصطناعي", callback_data="adm:beh"),
           B("📢 إرسال رسالة جماعية", callback_data="adm:bc"),
           B("✉️ إرسال رسالة فردية", callback_data="adm:users:0:dm"))
    return kb


def users_markup(page, mode):
    rows = q("SELECT * FROM users ORDER BY last_seen DESC")
    total = len(rows)
    pages = max(1, (total + 8) // 9)
    page = max(0, min(page, pages - 1))
    B = types.InlineKeyboardButton
    kb = types.InlineKeyboardMarkup(row_width=3)
    act = "user" if mode == "view" else "dmto"
    kb.add(*[B(display_name(r)[:24], callback_data=f"adm:{act}:{r['id']}")
             for r in rows[page * 9:(page + 1) * 9]])
    kb.row(B("⬅️ السابق", callback_data=f"adm:users:{page - 1}:{mode}"),
           B("التالي ➡️", callback_data=f"adm:users:{page + 1}:{mode}"))
    kb.row(B("🏠 القائمة", callback_data="adm:home"))
    return kb, page, pages, total


def safe_edit(c, text, kb=None):
    try:
        bot.edit_message_text(text, c.message.chat.id, c.message.message_id,
                              parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass


def user_summary(uid):
    u = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
    if not u:
        return ""
    hist = q("SELECT role, content FROM messages WHERE user_id=? ORDER BY id", (uid,))
    if not hist:
        return "لا توجد محادثة."
    if u["summary"] and u["msg_count"] - u["summary_count"] < 5:
        return u["summary"]
    convo = "\n".join(f"{'U' if r['role'] == 'user' else 'B'}: {r['content'][:400]}" for r in hist)[-8000:]
    r = ai_chat(
        model=TEXT_MODEL, temperature=0.3, max_completion_tokens=300, reasoning_effort="none",
        messages=[{"role": "user", "content":
                   "لخّص محادثة هذا المستخدم مع البوت في 3-4 أسطر بالعربية: مواضيعه واهتماماته وما يحتاجه.\n\n" + convo}])
    s = clean_ai(r.choices[0].message.content)
    ex("UPDATE users SET summary=?, summary_count=? WHERE id=?", (s, u["msg_count"], uid))
    return s


def show_user(c, uid):
    u = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
    if not u:
        return safe_edit(c, "المستخدم غير موجود.", admin_menu_kb())
    safe_edit(c, "⏳ جاري تحضير الملخص...")
    try:
        summ = user_summary(uid)
    except Exception as e:
        notify_admin("user_summary", e)
        summ = "تعذّر إنشاء الملخص الآن."
    B = types.InlineKeyboardButton
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(B("📄 تنزيل المحادثة PDF", callback_data=f"adm:pdf:{uid}"),
           B("✉️ مراسلة المستخدم", callback_data=f"adm:dmto:{uid}"),
           B("🔙 رجوع للمستخدمين", callback_data="adm:users:0:view"))
    uname = f"@{u['username']}" if u["username"] else "—"
    safe_edit(c, (f"👤 <b>{esc(display_name(u))}</b>\n🆔 <code>{uid}</code> | {esc(uname)}\n"
                  f"📨 عدد الرسائل: <b>{u['msg_count']}</b>\n📅 انضم: {fmt_ts(u['joined'])}\n"
                  f"🕒 آخر نشاط: {fmt_ts(u['last_seen'])}\n\n📝 <b>ملخص المحادثة:</b>\n{esc(summ)}"), kb)


def admin_cb(c, p):
    B = types.InlineKeyboardButton
    act = p[1] if len(p) > 1 else ""
    uid = c.from_user.id
    bot.answer_callback_query(c.id)
    if act == "home":
        pending.pop(uid, None)
        safe_edit(c, "🛠 <b>لوحة الأدمن</b>", admin_menu_kb())
    elif act == "cleanup":
        full_wipe()
        safe_edit(c, "✅ اكتمل التنظيف الشامل.", admin_menu_kb())
    elif act == "cltoggle":
        set_setting("cleanup_enabled", "0" if get_setting("cleanup_enabled", "1") == "1" else "1")
        safe_edit(c, "🛠 <b>لوحة الأدمن</b>", admin_menu_kb())
    elif act == "emauto":
        set_setting("auto_emergency", "0" if get_setting("auto_emergency", "1") == "1" else "1")
        safe_edit(c, "🛠 <b>لوحة الأدمن</b>", admin_menu_kb())
    elif act == "emtoggle":
        if _emergency_active:

            stop_emergency(force=True)
            safe_edit(c, "✅ تم إيقاف وضع الطوارئ.", admin_menu_kb())
        else:
            safe_edit(c, "🚨 جاري تشغيل وضع الطوارئ (يمسح بيانات المستخدمين ويوقف الخدمات الثقيلة)...", admin_menu_kb())
            threading.Thread(target=start_emergency, kwargs={"automatic": False}, daemon=True).start()
    elif act == "sys":
        safe_edit(c, "🖥 <b>حالة النظام</b>\n<pre>" + esc(_format_resources(resource_snapshot())) + "</pre>\n"
                     f"وضع الطوارئ: {'مفعّل' if _emergency_active else 'غير مفعّل'}\n"
                     f"الطوارئ التلقائية: {'مفعّلة' if get_setting('auto_emergency','1') == '1' else 'متوقفة'}\n"
                     f"التنظيف الليلي: {'مفعّل' if get_setting('cleanup_enabled','1') == '1' else 'متوقف'}",
                  admin_menu_kb())
    elif act == "nighttest":
        safe_edit(c, "🌙 جاري إرسال إشعارات التنظيف للمستخدمين المؤهلين (غير النشطين ولديهم ذاكرة)...\n"
                     f"سيتم الحذف بعد {CLEAN_GRACE_MIN} دقيقة لمن لا يرد.", admin_menu_kb())
        threading.Thread(target=send_night_notices, daemon=True).start()
    elif act == "users":
        page, mode = int(p[2]), (p[3] if len(p) > 3 else "view")
        kb, pg, pages, total = users_markup(page, mode)
        title = "👥 المستخدمون" if mode == "view" else "✉️ اختر المستخدم لمراسلته"
        safe_edit(c, f"{title} ({total}) — صفحة {pg + 1}/{pages}", kb)
    elif act == "user" and p[2].isdigit():
        show_user(c, int(p[2]))
    elif act == "pdf" and p[2].isdigit():
        pdf = io.BytesIO(conversation_pdf(int(p[2])))
        bot.send_document(ADMIN_ID, pdf, visible_file_name=f"chat_{p[2]}.pdf")
    elif act == "beh":
        set_pending(uid, type="admin_beh")
        cur = get_setting("behavior") or DEFAULT_BEHAVIOR.replace("{name}", BOT_NAME)
        kb = types.InlineKeyboardMarkup(row_width=1).add(
            B("↩️ استرجاع السلوك الافتراضي", callback_data="adm:behreset"),
            B("🏠 القائمة", callback_data="adm:home"))
        safe_edit(c, f"🧠 أرسل السلوك الجديد (تعليمات النظام).\n\n<b>الحالي:</b>\n<pre>{esc(cur[:1500])}</pre>", kb)
    elif act == "behreset":
        set_setting("behavior", "")
        pending.pop(uid, None)
        safe_edit(c, "✅ تم استرجاع السلوك الافتراضي.", admin_menu_kb())
    elif act == "bc":
        set_pending(uid, type="admin_bc")
        kb = types.InlineKeyboardMarkup().add(B("🏠 القائمة", callback_data="adm:home"))
        safe_edit(c, "📢 أرسل الرسالة التي تريد إرسالها لكل المستخدمين (نص/صورة/ملف...).", kb)
    elif act == "bcok":
        p0 = get_pending(uid)
        if p0 and p0["type"] == "bc_confirm":
            pending.pop(uid, None)
            safe_edit(c, "📢 جاري الإرسال...")
            threading.Thread(target=do_broadcast, args=(p0["chat"], p0["mid"]), daemon=True).start()
    elif act == "dmto" and p[2].isdigit():
        set_pending(uid, type="admin_dm", target=int(p[2]))
        kb = types.InlineKeyboardMarkup().add(B("🏠 القائمة", callback_data="adm:home"))
        safe_edit(c, f"✉️ أرسل الرسالة للمستخدم <code>{p[2]}</code> الآن.", kb)


def do_broadcast(chat, mid):
    ok = fail = 0
    for r in q("SELECT id FROM users"):
        try:
            bot.copy_message(r["id"], chat, mid)
            ok += 1
        except Exception:
            fail += 1
        time.sleep(0.06)
    bot.send_message(ADMIN_ID, f"📢 انتهى الإرسال\n✅ نجح: {ok}\n❌ فشل: {fail}")


def report_cb(c, p):
    uid = c.from_user.id
    act = p[1] if len(p) > 1 else ""
    if act == "start":
        bot.answer_callback_query(c.id)
        set_pending(uid, type="rep_text")
        bot.send_message(c.message.chat.id, "✍️ اكتب مشكلتك الآن (للإلغاء /cancel).")
    elif act == "skip":
        bot.answer_callback_query(c.id)
        p0 = get_pending(uid)
        if p0 and p0["type"] == "rep_photo":
            pending.pop(uid, None)
            submit_report(c.from_user, p0["text"])
            bot.send_message(c.message.chat.id, "✅ تم إرسال بلاغك للإدارة. شكراً لك 🙏")
    elif act in ("reply", "close") and is_admin(uid) and p[2].isdigit():
        rid = int(p[2])
        r = q("SELECT * FROM reports WHERE id=?", (rid,), one=True)
        if not r:
            return bot.answer_callback_query(c.id, "البلاغ غير موجود")
        bot.answer_callback_query(c.id)
        if act == "reply":
            set_pending(uid, type="admin_reply", target=r["user_id"], rid=rid)
            bot.send_message(ADMIN_ID, f"↩️ اكتب ردك على البلاغ #{rid} (للإلغاء /cancel).")
        else:
            ex("UPDATE reports SET status='closed' WHERE id=?", (rid,))
            try:
                bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)
                bot.send_message(ADMIN_ID, f"🚫 تم إغلاق البلاغ #{rid}")
            except Exception:
                pass
    else:
        bot.answer_callback_query(c.id)


@bot.message_handler(commands=["admin"])
def cmd_admin(m):
    if not require_subscription(m):
        return
    if not is_admin(m.from_user.id):
        return              
    pending.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "🛠 <b>لوحة الأدمن</b>", parse_mode="HTML", reply_markup=admin_menu_kb())


@bot.message_handler(commands=["cleanup", "cleanup_now", "cleanup_on", "cleanup_off",
                                    "emergency", "emergency_on", "emergency_off", "queue", "limits",
                                    "agents_on", "agents_off", "system",
                                    "emergency_auto_on", "emergency_auto_off"])
def cmd_admin_system(m):
    return admin_system_command(m)


@bot.callback_query_handler(func=lambda c: True)
def on_callback(c):
    try:
        p = (c.data or "").split(":")

        if p[0] != "sub" and not is_admin(c.from_user.id):
            member_ok, _, member_error = check_user_subscription(c.from_user.id)
            if not member_ok:
                bot.answer_callback_query(
                    c.id,
                    "تعذّر التحقق من الاشتراك." if member_error else "اشترك في جميع القنوات المطلوبة أولاً.",
                    show_alert=True)
                if c.message:
                    bot.send_message(c.message.chat.id, SUBSCRIPTION_TEXT, parse_mode="HTML",
                                     reply_markup=subscription_keyboard())
                return
        if p[0] == "adm":
            if not is_admin(c.from_user.id):
                return bot.answer_callback_query(c.id, "غير مصرح", show_alert=True)
            admin_cb(c, p)
        elif p[0] == "rep":
            report_cb(c, p)
        elif p[0] == "cln":
            cleanup_cb(c, p)
        elif p[0] == "don":
            donate_cb(c, p)
        elif p[0] == "prj":
            project_cb(c, p)
        elif p[0] == "agt":
            agents_cb(c, p)
        elif p[0] == "sub" and len(p) > 1 and p[1] == "check":
            ok, missing, error = check_user_subscription(c.from_user.id)
            if ok:
                bot.answer_callback_query(c.id, "تم التحقق من اشتراكك بنجاح.")
                bot.send_message(c.message.chat.id,
                                 "✅ تم تأكيد اشتراكك. يمكنك الآن استخدام البوت.",
                                 reply_markup=help_kb())
            elif error:
                bot.answer_callback_query(c.id, "تعذّر التحقق. أبلغت الإدارة بالمشكلة.", show_alert=True)
            else:
                bot.answer_callback_query(c.id, "لم يكتمل الاشتراك في جميع القنوات المطلوبة بعد.", show_alert=True)
        else:
            bot.answer_callback_query(c.id)
    except Exception as e:
        notify_admin("callback", e, c.from_user.id)
        try:
            bot.answer_callback_query(c.id, "حدث خطأ وتم إبلاغ الإدارة.", show_alert=True)
        except Exception:
            pass


                                                  

def handle_pending(m):
    uid = m.from_user.id
    p = get_pending(uid)
    if not p:
        return False
    t = p["type"]
    B = types.InlineKeyboardButton

    if t == "rep_text":
        if m.content_type == "photo":
            pending.pop(uid, None)
            submit_report(m.from_user, m.caption or "(بدون نص)", m.photo[-1].file_id)
            bot.reply_to(m, "✅ تم إرسال بلاغك للإدارة. شكراً لك 🙏")
        elif m.content_type == "text":
            pending[uid] = {"type": "rep_photo", "text": m.text, "t": time.time()}
            kb = types.InlineKeyboardMarkup().add(B("⏭ تخطي وإرسال", callback_data="rep:skip"))
            bot.reply_to(m, "📷 يمكنك إرسال صورة للمشكلة (اختياري)، أو اضغط تخطي.", reply_markup=kb)
        return True

    if t == "rep_photo":
        if m.content_type == "photo":
            pending.pop(uid, None)
            submit_report(m.from_user, p["text"], m.photo[-1].file_id)
            bot.reply_to(m, "✅ تم إرسال بلاغك للإدارة. شكراً لك 🙏")
        else:
            bot.reply_to(m, "أرسل صورة أو اضغط «تخطي وإرسال» في الرسالة السابقة.")
        return True

    if t == "rembg":
        return False                      

    if not is_admin(uid):
        pending.pop(uid, None)
        return False

    if t == "admin_beh" and m.content_type == "text":
        set_setting("behavior", m.text.strip()[:6000])
        pending.pop(uid, None)
        bot.send_message(m.chat.id, "✅ تم تحديث سلوك الذكاء الاصطناعي.", reply_markup=admin_menu_kb())
        return True

    if t == "admin_bc":
        pending[uid] = {"type": "bc_confirm", "chat": m.chat.id, "mid": m.message_id, "t": time.time()}
        n = q("SELECT COUNT(*) n FROM users", one=True)["n"]
        kb = types.InlineKeyboardMarkup().row(B("✅ تأكيد الإرسال", callback_data="adm:bcok"),
                                              B("❌ إلغاء", callback_data="adm:home"))
        bot.reply_to(m, f"سيتم إرسال هذه الرسالة إلى {n} مستخدم. تأكيد؟", reply_markup=kb)
        return True

    if t in ("admin_dm", "admin_reply"):
        pending.pop(uid, None)
        try:
            head = "📩 <b>رد الإدارة على بلاغك:</b>" if t == "admin_reply" else "📩 <b>رسالة من الإدارة:</b>"
            bot.send_message(p["target"], head, parse_mode="HTML")
            bot.copy_message(p["target"], m.chat.id, m.message_id)
            if t == "admin_reply":
                ex("UPDATE reports SET status='answered' WHERE id=?", (p["rid"],))
            bot.reply_to(m, "✅ تم الإرسال.")
        except Exception:
            bot.reply_to(m, "❌ تعذّر الإرسال (ربما حظر المستخدم البوت).")
        return True

    return False



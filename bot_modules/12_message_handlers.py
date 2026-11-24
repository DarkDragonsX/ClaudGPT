"""Open-source project | Original owner: Rad Lamine | Repository: https://github.com/RadLamine/ClaudGPT."""

@bot.message_handler(content_types=["text"], chat_types=["private"])
def on_text(m):
    if not require_subscription(m):
        return
    try:
        touch_user(m.from_user)
        if handle_pending(m):
            return
        text = (m.text or "").strip()
        if not text:
            return
        if m.from_user.id in project_sessions and project_note(m):
            return
        if len(text) > MAX_INPUT_CHARS:
            return bot.reply_to(m, f"⚠️ الرسالة طويلة جداً (الحد {MAX_INPUT_CHARS} حرف). أرسلها كملف.")
        prefix, rimg, snippet = reply_info(m)
        store = f"[رد على: {snippet}] {text}" if snippet else None
        if rimg:
            if reject_heavy_during_emergency(m):
                return
            try:
                b64 = image_to_b64(rimg)
            except Exception:
                b64 = None
            if b64:
                return start_ai(m, prefix + text, image_b64=b64, store_text=store, image_data=rimg,
                                status="🗯 تحليل صورة.....")
        replied = getattr(m, "reply_to_message", None)
        replied_text = ((getattr(replied, "text", None) or getattr(replied, "caption", None) or "")
                        if replied else "")
        if route_special_text_request(m, text, replied_text):
            return
        start_ai(m, prefix + text, store_text=store)
    except Exception as e:
        notify_admin("on_text", e, m.from_user.id)
        fail(m, None, e)


NO_CAPTION_IMAGE_PROMPT = ("أرسل المستخدم هذه الصورة بدون أي تعليق. صِفها بوضوح وباختصار، "
                           "واذكر أي نص ظاهر فيها، ثم اسأله بإيجاز عمّا يريد فعله بها.")


@bot.message_handler(content_types=["photo"], chat_types=["private"])
def on_photo(m):
    if not require_subscription(m):
        return
    if reject_heavy_during_emergency(m):
        return
    try:
        touch_user(m.from_user)
        if handle_pending(m):
            return
        uid = m.from_user.id
        caption = (m.caption or "").strip()
        p = get_pending(uid)
        wants_rembg = (p and p["type"] == "rembg") or re.search(
            r"(ازال|إزال|احذف|امسح|شيل|حذف).{0,15}خلفي|remove.{0,10}background|rembg", caption, re.I)
        if m.photo[-1].file_size and m.photo[-1].file_size > MAX_IMAGE_BYTES:
            return bot.reply_to(m, "⚠️ الصورة أكبر من الحد المسموح (1MB). أرسل نسخة أصغر.")
        data = download_tg_file(m.photo[-1].file_id, m.photo[-1].file_size, max_bytes=MAX_IMAGE_BYTES)
        if len(data) > MAX_IMAGE_BYTES:
            return bot.reply_to(m, "⚠️ الصورة أكبر من الحد المسموح (1MB). أرسل نسخة أصغر.")
        if wants_rembg:
            pending.pop(uid, None)
            queue_submit("rembg", m, do_rembg, args=(m, data), signature=f"rembg:{m.from_user.id}:{m.message_id}")
            return
        b64 = image_to_b64(data)
        prefix, _, snippet = reply_info(m, want_image=False)
        prompt = prefix + (caption or NO_CAPTION_IMAGE_PROMPT)
        store = (f"[صورة] {caption}" if caption else "[صورة]")
        if snippet:
            store = f"[رد على: {snippet}] " + store

        start_ai(m, prompt, image_b64=b64, store_text=store, status="🗯 تحليل صورة.....",
                 image_data=data, use_tools=bool(caption))
    except Exception as e:
        notify_admin("on_photo", e, m.from_user.id)
        fail(m, None, e)


def animation_first_frame(data):
    """Extract one frame from Telegram GIF/MP4 animation in memory (no disk storage)."""
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
           "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "pipe:1"]
    proc = subprocess.run(cmd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=30, check=False)
    if proc.returncode != 0 or not proc.stdout:
        raise ValueError("تعذر استخراج صورة من ملف GIF/Animation.")
    return proc.stdout


@bot.message_handler(content_types=["animation"], chat_types=["private"])
def on_animation(m):
    if not require_subscription(m):
        return
    if reject_heavy_during_emergency(m):
        return
    try:
        touch_user(m.from_user)
        media = m.animation
        if media.file_size and media.file_size > MAX_FILE_BYTES:
            return bot.reply_to(m, "⚠️ حجم الملف أكبر من الحد المسموح (10MB).")
        data = download_tg_file(media.file_id, media.file_size)
        frame = animation_first_frame(data)
        if len(frame) > MAX_IMAGE_BYTES:
            raise ValueError("الصورة المستخرجة أكبر من الحد (1MB)")
        caption = (m.caption or "").strip()
        start_ai(m, caption or "حلّل الإطار الأول من هذا GIF/Animation واشرح محتواه.",
                 image_b64=image_to_b64(frame), store_text=f"[Animation] {caption}".strip(),
                 image_data=frame, status="🗯 تحليل الصورة.....", use_tools=bool(caption))
    except Exception as e:
        notify_admin("on_animation", e, m.from_user.id)
        fail(m, None, e)


@bot.message_handler(content_types=["sticker"], chat_types=["private"])
def on_sticker(m):
    if not require_subscription(m):
        return
    if reject_heavy_during_emergency(m):
        return
    try:
        touch_user(m.from_user)
        sticker = m.sticker
        if getattr(sticker, "is_animated", False) or getattr(sticker, "is_video", False):
            return bot.reply_to(m, "⚠️ أرسل الملصق كصورة ثابتة أو أرسل الصورة كملف JPG/PNG/WEBP.")
        if getattr(sticker, "file_size", None) and sticker.file_size > MAX_IMAGE_BYTES:
            return bot.reply_to(m, "⚠️ حجم الملصق يتجاوز الحد المسموح (1MB).")
        data = download_tg_file(sticker.file_id, getattr(sticker, "file_size", None), max_bytes=MAX_IMAGE_BYTES)
        if len(data) > MAX_IMAGE_BYTES:
            return bot.reply_to(m, "⚠️ حجم الملصق يتجاوز الحد المسموح (1MB).")
        start_ai(m, "حلّل هذا الملصق أو الصورة واشرح ما يظهر فيها.",
                 image_b64=image_to_b64(data), store_text="[ملصق/صورة]", image_data=data,
                 status="🗯 تحليل الصورة.....", use_tools=False)
    except Exception as e:
        notify_admin("on_sticker", e, m.from_user.id)
        fail(m, None, e)


@bot.message_handler(content_types=["document"], chat_types=["private"])
def on_document(m):
    if not require_subscription(m):
        return
    if reject_heavy_during_emergency(m):
        return
    try:
        touch_user(m.from_user)
        if handle_pending(m):
            return
        uid = m.from_user.id
        _queues.cancel_user(uid)
        purge_user_files(uid, keep_code=False)
        d = m.document
        name = d.file_name or "file"
        ext = os.path.splitext(name)[1].lower()
        caption = (m.caption or "").strip()
        is_image_file = (d.mime_type or "").startswith("image/") or ext in IMAGE_EXT
        is_code_file = ext in PROJECT_EXT or name.lower() in PROJECT_NAMES
        limit = MAX_ZIP_BYTES if ext == ".zip" else (MAX_IMAGE_BYTES if is_image_file else (MAX_CODE_FILE_BYTES if is_code_file else MAX_FILE_BYTES))
        if d.file_size and d.file_size > limit:
            return bot.reply_to(m, f"⚠️ الملف كبير جداً (الحد الأقصى {limit // (1024 * 1024)}MB). "
                                   "للمشاريع الكبيرة قسّمها إلى عدة ملفات ZIP وأرسلها عبر /project.")
        data = download_tg_file(d.file_id, d.file_size, max_bytes=limit)
        if uid in project_sessions and (ext == ".zip" or ext in PROJECT_EXT or name.lower() in PROJECT_NAMES):
            return project_session_add(m, name, data)

        if is_image_file:
            if len(data) > MAX_IMAGE_BYTES:
                return bot.reply_to(m, "⚠️ الصورة أكبر من الحد المسموح (1MB). أرسل نسخة أصغر.")
            p = get_pending(uid)
            if (p and p["type"] == "rembg") or re.search(r"خلفي|background|rembg", caption, re.I):
                pending.pop(uid, None)
                queue_submit("rembg", m, do_rembg, args=(m, data), signature=f"rembg:{m.from_user.id}:{m.message_id}")
            else:
                start_ai(m, caption or NO_CAPTION_IMAGE_PROMPT, image_to_b64(data),
                         f"[صورة] {caption}".strip(), status="🗯 تحليل صورة.....", image_data=data,
                         use_tools=bool(caption))
            return

        if (d.mime_type or "").startswith("audio/") or ext in AUDIO_EXT:
            if not rate_ok(uid):
                return bot.reply_to(m, "⏳ أرسلت طلبات كثيرة خلال وقت قصير. انتظر دقيقة ثم أعد المحاولة.")
            transcribe_and_ask(m, data, name)
            return

        if ext == ".pdf":
            return queue_submit("pdf", m, process_pdf_upload, args=(m, name, data, caption),
                                signature=f"pdf:{uid}:{m.message_id}")

        if ext in PROJECT_EXT or ext == ".zip" or name.lower() in PROJECT_NAMES:

            return project_buffer_add(m, name, data)

        bot.reply_to(m, "⚠️ نوع الملف غير مدعوم. المدعوم: PDF، الصور، ملفات النصوص والأكواد، وملفات ZIP للمشاريع.")
    except Exception as e:
        notify_admin("on_document", e, m.from_user.id)
        fail(m, None, e)


def process_pdf_upload(m, name, data, caption):
    """Run PDF extraction/OCR/translation inside its own bounded queue lane."""
    try:
        ensure_task_running()
        if re.search(r"ترجم|translate|ترجمة", caption or "", re.I):
            return translate_pdf_flow(m, name, data, caption)
        text = pdf_text(data)
        ensure_task_running()
        if not text:
            return bot.reply_to(m, "⚠️ لا يوجد نص قابل للاستخراج في هذا الـ PDF.")
        text, total_words, cut_words = word_limit(text)
        notice = (f"ℹ️ الملف يحتوي نحو {total_words:,} كلمة، والحد الأقصى الذي أقرؤه {MAX_FILE_WORDS:,} كلمة، "
                  "لذا قرأت جزأه الأول فقط.\n\n" if cut_words else "")
        return intake_file(m, name, text, caption, notice, partial=bool(cut_words), pdf=True)
    except TaskCancelled:
        raise
    except Exception as exc:
        notify_admin("pdf_upload", exc, m.from_user.id)
        fail(m, None, exc)


def prepare_audio_for_stt(data, filename):
    """Normalize unusual audio containers to MP3 in memory for Whisper compatibility."""
    ext = os.path.splitext(filename or "")[1].lower()
    accepted = {".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".wav", ".webm"}
    if ext in accepted:
        return filename, data
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-vn",
           "-ac", "1", "-ar", "16000", "-f", "mp3", "pipe:1"]
    proc = subprocess.run(cmd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=60, check=False)
    if proc.returncode != 0 or not proc.stdout:
        raise ValueError("تعذر تحويل صيغة الصوت إلى صيغة مدعومة.")
    return "transcribed_audio.mp3", proc.stdout


def _transcribe_and_ask_now(m, data, filename="audio.ogg"):
    """Transcribe Telegram voice/audio uploads, then pass the transcript to the AI."""
    status = bot.reply_to(m, "🗯 أحوّل الصوت إلى نص.....")
    try:
        stt_name, stt_data = prepare_audio_for_stt(data, filename)
        result = client().audio.transcriptions.create(
            file=(os.path.basename(stt_name)[:100], stt_data), model=STT_MODEL,
            response_format="text", temperature=0.0)
        transcript = (result if isinstance(result, str) else getattr(result, "text", "") or "").strip()
        ensure_task_running()
    finally:
        try: bot.delete_message(m.chat.id, status.message_id)
        except Exception: pass
    if not transcript:
        return bot.reply_to(m, "⚠️ لم أتمكن من استخراج كلام واضح من هذا المقطع.")
    bot.reply_to(m, "✦ النص المستخرج من الصوت:\n" + transcript[:3500])
    prefix, _, _ = reply_info(m, want_image=False)
    start_ai(m, prefix + f"هذه رسالة صوتية حوّلناها إلى نص. افهم المقصود وأجب عن المستخدم:\n{transcript}",
             store_text=f"[صوت: {os.path.basename(filename)}] {transcript}", rate_checked=True)


def transcribe_and_ask(m, data, filename="audio.ogg"):
    return queue_submit("stt", m, _transcribe_and_ask_now, args=(m, data, filename))


@bot.message_handler(content_types=["voice", "audio"], chat_types=["private"])
def on_voice(m):
    if not require_subscription(m):
        return
    if reject_heavy_during_emergency(m):
        return
    try:
        touch_user(m.from_user)
        if not rate_ok(m.from_user.id):
            return bot.reply_to(m, "⏳ أرسلت طلبات كثيرة خلال وقت قصير. انتظر دقيقة ثم أعد المحاولة.")
        media = m.voice or m.audio
        if media.file_size and media.file_size > MAX_FILE_BYTES:
            return bot.reply_to(m, "⚠️ المقطع كبير جداً (الحد 10MB).")
        data = download_tg_file(media.file_id, media.file_size)
        transcribe_and_ask(m, data, getattr(media, "file_name", None) or ("voice.ogg" if m.voice else "audio.mp3"))
    except Exception as e:
        notify_admin("on_voice", e, m.from_user.id)
        fail(m, None, e)


@bot.message_handler(content_types=["video", "video_note"], chat_types=["private"])
def on_video_audio(m):
    if not require_subscription(m):
        return
    try:
        touch_user(m.from_user)
        media = m.video or m.video_note
        if media.file_size and media.file_size > MAX_FILE_BYTES:
            return bot.reply_to(m, "⚠️ حجم الفيديو أكبر من الحد المسموح (10MB).")
        if not rate_ok(m.from_user.id):
            return bot.reply_to(m, "⏳ أرسلت طلبات كثيرة خلال وقت قصير. انتظر دقيقة ثم أعد المحاولة.")
        data = download_tg_file(media.file_id, media.file_size)
        transcribe_and_ask(m, data, "video.mp4")
    except Exception as e:
        notify_admin("on_video_audio", e, m.from_user.id)
        fail(m, None, e)


@bot.message_handler(
    func=lambda message: True,
    content_types=["location", "contact",
                   "venue", "poll", "dice", "web_app_data", "invoice",
                   "connected_website", "passport_data", "write_access_allowed", "users_shared",
                   "chat_shared", "story", "boost_added"],
    chat_types=["private"])
def on_unsupported_message(m):
    if not require_subscription(m):
        return
    touch_user(m.from_user, count=False)
    bot.reply_to(m, "هذا النوع من الرسائل غير مدعوم حالياً. أرسل نصاً أو صورة أو PDF أو ملفاً نصياً.")



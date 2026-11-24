"""Open-source project | Original owner: Rad Lamine | Repository: https://github.com/RadLamine/ClaudGPT."""

                                                              

                                                              
def download_tg_file(file_id, size=None, max_bytes=None):
    lim = max_bytes or MAX_FILE_BYTES
    if size and size > lim:
        raise ValueError("file too large")
    last_error = None
    for attempt in range(4):
        try:
            info = bot.get_file(file_id)
            if info.file_size and info.file_size > lim:
                raise ValueError("file too large")
            data = bot.download_file(info.file_path)
            if not data:
                raise ConnectionError("Telegram returned an empty file")
            if len(data) > lim:
                raise ValueError("file too large")
            return data
        except ValueError:
            raise
        except (requests.exceptions.RequestException, OSError, telebot.apihelper.ApiException) as exc:
            last_error = exc
            if attempt == 3:
                break
            time.sleep(1.2 * (attempt + 1))
    raise ConnectionError(f"تعذر تنزيل الملف من تيليجرام بعد عدة محاولات: {last_error}")


def image_to_b64(data):
    """Decode common Telegram image formats in memory and normalize for the vision API."""
    try:
        img = Image.open(io.BytesIO(data))
    except Exception:
        try:
            import pillow_heif
            img = pillow_heif.open_heif(io.BytesIO(data)).to_pillow()
        except Exception as exc:
            raise ValueError("تعذرت قراءة الصورة. أرسل JPG أو PNG أو WEBP أو GIF أو BMP.") from exc
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    try:
        img.seek(0)                                                
    except Exception:
        pass
    img = img.convert("RGB")
    img.thumbnail((1280, 1280))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


_rembg_session, _rembg_lock = None, threading.Lock()
_rembg_sem = threading.BoundedSemaphore(REMBG_CONCURRENCY)


def remove_bg_green(data):
    global _rembg_session
    from rembg import remove, new_session
    with _rembg_lock:
        if _rembg_session is None:
            _rembg_session = new_session("u2netp")
        try:
            img = Image.open(io.BytesIO(data))
        except Exception:
            try:
                import pillow_heif
                img = pillow_heif.open_heif(io.BytesIO(data)).to_pillow()
            except Exception:
                raise ValueError("صيغة الصورة غير مدعومة. أرسل JPG أو PNG أو WEBP أو GIF أو BMP.")
        img.seek(0)
        img = img.convert("RGB")
        img.thumbnail((1280, 1280))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return remove(buf.getvalue(), session=_rembg_session)


def _remove_bg_tool(ctx, data):
    if not _rembg_sem.acquire(blocking=False):
        raise RuntimeError("خدمة إزالة الخلفية مشغولة حالياً.")
    try:
        ensure_task_running()
        ctx.status("🗯 إزالة خلفية الصورة.....")
        out = remove_bg_green(data)
        ensure_task_running()
        if len(out) > MAX_TEMP_STORAGE_BYTES:
            raise ValueError("ناتج إزالة الخلفية يتجاوز حد الملف المؤقت 5MB.")
        f = io.BytesIO(out)
        f.name = "background_removed.png"
        bot.send_document(ctx.chat_id, f, visible_file_name=f.name,
                          caption="تمت إزالة الخلفية وجعلها شفافة.", reply_to_message_id=ctx.reply_to)
    finally:
        _rembg_sem.release()


def do_rembg(m, data):
    if not _rembg_sem.acquire(blocking=False):
        bot.reply_to(m, "⏳ إزالة الخلفية مشغولة حالياً. أعد المحاولة بعد قليل.")
        return
    ctx = None
    try:
        ctx = Ctx(m, "🗯 إزالة الخلفية......")
        with Action(ctx, "upload_photo"):
            out = remove_bg_green(data)
        ensure_task_running()
        if len(out) > MAX_TEMP_STORAGE_BYTES:
            raise ValueError("ناتج إزالة الخلفية يتجاوز حد الملف المؤقت 5MB.")
        ctx.status("🗯 جاري إرسال ملف.....")
        f = io.BytesIO(out)
        f.name = "no_background_green.png"
        bot.send_document(m.chat.id, f, visible_file_name="no_background_green.png",
                          caption="✅ تمت إزالة الخلفية (خلفية خضراء)", reply_to_message_id=m.message_id)
        ctx.drop_status()
    except TaskCancelled:
        if ctx:
            ctx.drop_status()
    except Exception as e:
        notify_admin("rembg", e, m.from_user.id)
        fail(m, ctx, e)
    finally:
        _rembg_sem.release()


FONT_NAME = "Helvetica"
FONT_DIR = "fonts"
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf"
_font_ready = False


def ensure_font():
    global FONT_NAME, _font_ready
    if _font_ready:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    os.makedirs(FONT_DIR, exist_ok=True)
    path = os.path.join(FONT_DIR, "Amiri-Regular.ttf")
    if not os.path.exists(path):
        try:
            r = requests.get(FONT_URL, timeout=30)
            if r.status_code == 200:
                open(path, "wb").write(r.content)
        except Exception:
            pass
    cands = [path, "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for c in cands:
        if os.path.exists(c):
            try:
                pdfmetrics.registerFont(TTFont("BotFont", c))
                FONT_NAME = "BotFont"
                break
            except Exception:
                pass
    _font_ready = True


_EMOJI = re.compile("[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f\u200d]")


def make_pdf(title, paragraphs):
    ensure_font()
    import arabic_reshaper
    from bidi.algorithm import get_display
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    margin, size, lead = 50, 13, 22

    def shape(s):
        return get_display(arabic_reshaper.reshape(s))

    c.setFont(FONT_NAME, size)
    y = H - margin
    items = [("title", title)] + [("p", p) for p in paragraphs]
    for kind, para in items:
        para = _EMOJI.sub("", para).rstrip()
        if not para:
            y -= lead * 0.5
            continue
        rtl = bool(re.search(r"[\u0600-\u06FF]", para))
        words, lines, cur = para.split(" "), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            probe = shape(t) if rtl else t
            if cur and pdfmetrics.stringWidth(probe, FONT_NAME, size) > W - 2 * margin:
                lines.append(cur)
                cur = w
            else:
                cur = t
        lines.append(cur)
        for ln in lines:
            if y < margin:
                c.showPage()
                c.setFont(FONT_NAME, size)
                y = H - margin
            if rtl:
                c.drawRightString(W - margin, y, shape(ln))
            else:
                c.drawString(margin, y, ln)
            y -= lead
        y -= lead * 0.3
    c.save()
    return buf.getvalue()


def conversation_pdf(uid):
    u = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
    paras = [f"User ID: {uid}", f"Messages: {u['msg_count'] if u else 0}", ""]
    for r in q("SELECT role, content, ts FROM messages WHERE user_id=? ORDER BY id", (uid,)):
        who = "المستخدم" if r["role"] == "user" else "البوت"
        paras.append(f"[{fmt_ts(r['ts'])}] {who}:")
        paras.extend(r["content"].split("\n"))
        paras.append("")
    return make_pdf("Conversation", paras)


def _ocr_pdf_batch(batch):
    """تحويل ثلاث صفحات ممسوحة كحد أقصى إلى نص دون كتابة الصور على القرص."""
    content = [{"type": "text", "text":
                "استخرج النص المقروء من صفحات PDF المصورة التالية، حافظ على ترتيب الصفحات والعناوين والجداول قدر الإمكان. "
                "أعد النص فقط، وضع فاصل واضح بين كل صفحة."}]
    for page_no, b64 in batch:
        content.append({"type": "text", "text": f"الصفحة رقم {page_no}:"})
        content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}})
    response = ai_chat(
        model=VISION_MODEL,
        messages=[{"role": "user", "content": content}],
        max_completion_tokens=4096,
        temperature=0.1,
        reasoning_effort="none")
    return clean_ai(response.choices[0].message.content)


def pdf_text(data, max_pages=None):
    """استخراج نص PDF مع OCR متدرج للصفحات المصورة؛ كل الصور تبقى في الذاكرة."""
    max_pages = max_pages or MAX_PDF_PAGES
    out, scan_batch = [], []
    scanned_count = 0
    try:
        import fitz                                               
        doc = fitz.open(stream=data, filetype="pdf")
        try:
            if doc.page_count > max_pages:
                raise ValueError(f"PDF has {doc.page_count} pages; limit is {max_pages}")
            for idx, page in enumerate(doc):
                txt = (page.get_text("text") or "").strip()
                if txt:
                    out.append(f"\n[صفحة {idx + 1}]\n{txt}")
                elif scanned_count < MAX_PDF_OCR_PAGES:
                    rect = page.rect
                    longest = max(float(rect.width), float(rect.height), 1.0)
                    scale = min(1.35, 1280.0 / longest)
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                    b64 = image_to_b64(pix.tobytes("png"))
                    scan_batch.append((idx + 1, b64))
                    scanned_count += 1
                    if len(scan_batch) == 3:
                        out.append("\n[نص الصفحات الممسوحة ضوئياً]\n" + _ocr_pdf_batch(scan_batch))
                        scan_batch.clear()
            if scan_batch:
                out.append("\n[نص الصفحات الممسوحة ضوئياً]\n" + _ocr_pdf_batch(scan_batch))
        finally:
            doc.close()
    except ImportError:
        from pypdf import PdfReader
        rd = PdfReader(io.BytesIO(data), strict=False)
        if len(rd.pages) > max_pages:
            raise ValueError(f"PDF has {len(rd.pages)} pages; limit is {max_pages}")
        for idx, pg in enumerate(rd.pages):
            txt = (pg.extract_text() or "").strip()
            if txt:
                out.append(f"\n[صفحة {idx + 1}]\n{txt}")

    result = "\n".join(out).strip()
    if len(result) > MAX_PDF_TEXT_CHARS:
        result = result[:MAX_PDF_TEXT_CHARS]
    return result


def chunk_text(text, size=2500):
    chunks, cur = [], ""
    for para in text.split("\n"):
        while len(para) > size:
            chunks.append(para[:size])
            para = para[size:]
        if len(cur) + len(para) > size:
            chunks.append(cur)
            cur = ""
        cur += para + "\n"
    if cur.strip():
        chunks.append(cur)
    return chunks


def translate_pdf_flow(m, name, data, instruction):
    uid = m.from_user.id
    if not rate_ok(uid):
        bot.reply_to(m, "⏳ أرسلت طلبات كثيرة خلال وقت قصير. انتظر دقيقة ثم أعد المحاولة.")
        return
    lock = user_locks[uid]
    if not lock.acquire(blocking=False):
        bot.reply_to(m, "⏳ يوجد طلب آخر قيد المعالجة. انتظر اكتماله أولاً.")
        return
    ctx = None
    try:
        ctx = Ctx(m, "🗯 قراءة الملف.....")
        with Action(ctx, "typing"):
            text = pdf_text(data)
            if not text:
                ctx.status("⚠️ لا يوجد نص قابل للاستخراج في هذا الملف (قد يكون ممسوحاً ضوئياً).")
                return
            text, total_words, cut_words = word_limit(text)
            trunc_note = (f"\nℹ️ تُرجم أول {MAX_FILE_WORDS:,} كلمة فقط من أصل {total_words:,}." if cut_words else "")
            chunks = chunk_text(text)
            out = []
            for i, ch in enumerate(chunks, 1):
                ensure_task_running()
                ctx.status(f"🗯 ترجمة الملف..... ({i}/{len(chunks)})")
                r = ai_chat(
                    model=TEXT_MODEL, temperature=0.2, max_completion_tokens=4096,
                    reasoning_effort="none",
                    messages=[
                        {"role": "system", "content": "You are a professional translator. Translate faithfully, "
                         "keep the structure, output ONLY the translation, no comments."},
                        {"role": "user", "content": f"Instruction: {instruction}\n\nText:\n{ch}"}])
                ensure_task_running()
                out.append(clean_ai(r.choices[0].message.content))
            ensure_task_running()
            ctx.status("🗯 جاري إرسال ملف.....")
            pdf = make_pdf("Translation", "\n".join(out).split("\n"))
        if len(pdf) > MAX_TEMP_STORAGE_BYTES:
            raise ValueError("ملف PDF الناتج يتجاوز الحد المؤقت المسموح (5MB).")
        f = io.BytesIO(pdf)
        fname = "translated_" + re.sub(r"[^\w.-]", "_", name)[:60]
        if not fname.lower().endswith(".pdf"):
            fname += ".pdf"
        f.name = fname
        bot.send_document(m.chat.id, f, visible_file_name=fname, caption="✅ تمت الترجمة" + trunc_note,
                          reply_to_message_id=m.message_id)
        ctx.drop_status()
    except Exception as e:
        notify_admin("translate_pdf", e, m.from_user.id)
        fail(m, ctx, e)
    finally:
        lock.release()


TEXT_EXT = {".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".html", ".css", ".md", ".csv",
            ".xml", ".yml", ".yaml", ".java", ".c", ".cpp", ".h", ".cs", ".php", ".go", ".rs",
            ".kt", ".swift", ".sql", ".sh", ".ini", ".log", ".rb", ".dart", ".lua", ".bat", ".toml"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".heic", ".heif", ".avif"}
AUDIO_EXT = {".ogg", ".oga", ".mp3", ".m4a", ".aac", ".wav", ".flac", ".opus", ".webm", ".mp4", ".mpeg", ".mpga", ".amr"}


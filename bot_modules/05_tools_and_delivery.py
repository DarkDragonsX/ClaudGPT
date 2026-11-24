"""Open-source project | Original owner: Rad Lamine | Repository: https://github.com/RadLamine/ClaudGPT."""

                                                              

                                                              
class Ctx:
    def __init__(self, m, status="🗯 يكتب....."):
        self.image_data = None
        self.chat_id = m.chat.id
        self.uid = m.from_user.id
        self.reply_to = m.message_id
        self.act = None
        self.status_mid = None
        self.file_sent = False                                                     
        self.file_tries = {}                                                        
        self.request_text = ""
        if status:
            try:
                self.status_mid = bot.send_message(self.chat_id, status,
                                                   reply_to_message_id=self.reply_to).message_id
            except Exception:
                pass

    def status(self, text):
        if not self.status_mid:
            return
        try:
            bot.edit_message_text(text, self.chat_id, self.status_mid)
        except Exception:
            pass

    def drop_status(self):
        if self.status_mid:
            try:
                bot.delete_message(self.chat_id, self.status_mid)
            except Exception:
                pass
            self.status_mid = None


class Action:
    """يُبقي مؤشر (يكتب/يرفع...) ظاهراً أثناء العمل."""

    def __init__(self, ctx, action="typing"):
        self.ctx, self.action = ctx, action

    def __enter__(self):
        self.stop = threading.Event()
        self.ctx.act = self
        threading.Thread(target=self._run, daemon=True).start()
        return self

    def _run(self):
        while not self.stop.is_set():
            try:
                bot.send_chat_action(self.ctx.chat_id, self.action)
            except Exception:
                pass
            self.stop.wait(4)

    def __exit__(self, *a):
        self.stop.set()


def tg_call(fn, *a, **kw):
    """استدعاء تيليجرام مع الانتظار وإعادة المحاولة عند حدود الإرسال (429) وأخطاء الشبكة."""
    for attempt in range(5):
        try:
            return fn(*a, **kw)
        except Exception as e:
            code = getattr(e, "error_code", None)
            if code == 429:
                params = (getattr(e, "result_json", None) or {}).get("parameters") or {}
                wait = int(params.get("retry_after") or 3) + 1
            elif isinstance(e, requests.exceptions.RequestException) or (code and code >= 500):
                wait = 2 * (attempt + 1)
            else:
                raise
            if attempt == 4:
                raise
            time.sleep(min(wait, 60))


def render_chunks(text, limit=3000):
    """يقسّم الرد إلى أجزاء HTML كل منها ضمن حد تيليجرام (4096) مهما طال الرد."""
    out = []
    for chunk in split_markdown(text, limit):
        h = md_to_html(chunk)
        if len(h) > 4000 and limit > 400:
            out.extend(render_chunks(chunk, limit // 2))
        else:
            out.append((chunk, h))
    return out


def deliver(ctx, text):
    """إرسال الرد كاملاً بتنسيق HTML، ويُقسَّم تلقائياً على عدة رسائل بلا حد للطول."""
    parts = render_chunks(text)
    for i, (chunk, h) in enumerate(parts):
        first = i == 0 and ctx.status_mid
        try:
            if first:
                tg_call(bot.edit_message_text, h, ctx.chat_id, ctx.status_mid, parse_mode="HTML",
                        disable_web_page_preview=True)
            else:
                tg_call(bot.send_message, ctx.chat_id, h, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            try:
                if first:
                    tg_call(bot.edit_message_text, chunk[:4096], ctx.chat_id, ctx.status_mid)
                else:
                    tg_call(bot.send_message, ctx.chat_id, chunk[:4096])
            except Exception as e:
                logging.warning("deliver chunk %s failed: %s", i, e)
        time.sleep(0.7 if len(parts) > 3 else 0.3)
    ctx.status_mid = None


def send_text_file(ctx, name, content, caption=None):
    content = content or ""
    if len(content) > MAX_OUTPUT_FILE_CHARS:
        raise ValueError(f"حجم النص الناتج يتجاوز حد الإخراج الحالي ({MAX_OUTPUT_FILE_CHARS:,} حرف)؛ لم أرسل نسخة مقتطعة.")
    raw = content.encode("utf-8")
    if len(raw) > MAX_TEMP_STORAGE_BYTES:
        raise ValueError("حجم الملف الناتج يتجاوز الحد المؤقت المسموح (5MB).")
    ctx.status("🗯 جاري إرسال ملف.....")
    f = io.BytesIO(raw)
    f.name = name
    bot.send_document(ctx.chat_id, f, visible_file_name=name, caption=caption,
                      reply_to_message_id=ctx.reply_to)


                                                         

def tts_bytes(text):
    import edge_tts
    text = text.strip()[:1500]
    voice = "ar-SA-HamedNeural" if re.search(r"[\u0600-\u06FF]", text) else "en-US-AriaNeural"
    task = getattr(_task_local, "task", None)
    owned = not bool(task and task.tempdir)
    tmp = task.tempdir if not owned else tempfile.mkdtemp(prefix="task_tts_", dir=TASK_TMP_ROOT)
    try:
        mp3, ogg = os.path.join(tmp, "a.mp3"), os.path.join(tmp, "a.ogg")
        asyncio.run(edge_tts.Communicate(text, voice).save(mp3))
        if os.path.getsize(mp3) > MAX_TEMP_STORAGE_BYTES:
            raise ValueError("temporary file too large")
        try:
            subprocess.run([FFMPEG, "-y", "-i", mp3, "-c:a", "libopus", "-b:a", "48k", ogg],
                           check=True, capture_output=True, timeout=60)
            if os.path.getsize(ogg) > MAX_TEMP_STORAGE_BYTES:
                raise ValueError("temporary file too large")
            with open(ogg, "rb") as f:
                return "voice", f.read()
        except Exception:
            with open(mp3, "rb") as f:
                return "audio", f.read()
    finally:
        if owned:
            shutil.rmtree(tmp, ignore_errors=True)


def _public_url(u):
    try:
        p = urlparse(u)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        port = p.port or (443 if p.scheme == "https" else 80)
        for info in socket.getaddrinfo(p.hostname, port):
            ip = ipaddress.ip_address(info[4][0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                    or ip.is_multicast or ip.is_unspecified):
                return False
        return True
    except Exception:
        return False


def read_webpage(url):
    cur = (url or "").strip()[:2000]
    if not re.match(r"^https?://", cur, re.I):
        cur = "https://" + cur
    resp = None
    for _ in range(4):
        if not _public_url(cur):
            return "رابط غير صالح أو غير مسموح بفتحه."
        resp = requests.get(cur, headers={"User-Agent": "Mozilla/5.0 (compatible; AIBot/1.0)"},
                            timeout=15, stream=True, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            loc = resp.headers.get("Location")
            resp.close()
            if not loc:
                return "تعذر فتح الصفحة (تحويل غير صالح)."
            cur = requests.compat.urljoin(cur, loc)
            continue
        break
    else:
        return "تحويلات كثيرة جداً؛ تعذر فتح الصفحة."
    if resp.status_code >= 400:
        resp.close()
        return f"تعذر فتح الصفحة (HTTP {resp.status_code})."
    ctype = resp.headers.get("Content-Type", "").lower()
    if not any(x in ctype for x in ("text/", "html", "xml", "json")):
        resp.close()
        return "نوع محتوى الرابط غير مدعوم للقراءة (ليس نصاً/صفحة ويب)."
    raw = b""
    for chunk in resp.iter_content(65536):
        raw += chunk
        if len(raw) > 1_500_000:
            break
    enc = resp.encoding or "utf-8"
    resp.close()
    text = raw.decode(enc, "replace")
    if "html" in ctype or "<html" in text[:2000].lower():
        text = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|form)[^>]*>.*?</\1>", " ", text)
        text = re.sub(r"(?s)<!--.*?-->", " ", text)
        text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>|</tr>", "\n", text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text[:7000] or "الصفحة فارغة أو لا تحتوي نصاً مقروءاً."


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}


def _fact(n):
    if n > 500 or n < 0 or int(n) != n:
        raise ValueError("factorial range")
    return math.factorial(int(n))


_FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
          "log": math.log, "log10": math.log10, "abs": abs, "round": round,
          "floor": math.floor, "ceil": math.ceil, "factorial": _fact}
_CONSTS = {"pi": math.pi, "e": math.e}


def _calc_eval(node):
    if isinstance(node, ast.Expression):
        return _calc_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        l, r = _calc_eval(node.left), _calc_eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(r) > 1000 or abs(l) > 10 ** 6):
            raise ValueError("power too large")
        return _OPS[type(node.op)](l, r)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_calc_eval(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in _FUNCS and not node.keywords and len(node.args) <= 2:
        return _FUNCS[node.func.id](*[_calc_eval(a) for a in node.args])
    raise ValueError("unsupported expression")


def safe_calc(expr):
    expr = (expr or "").strip()[:200]
    expr = expr.replace("^", "**").replace("×", "*").replace("÷", "/").replace(",", "")
    try:
        val = _calc_eval(ast.parse(expr, mode="eval"))
        if isinstance(val, float):
            val = round(val, 12)
        return str(val)[:500]
    except Exception as exc:
        return f"تعذر حساب التعبير: {type(exc).__name__}"


def do_tts(ctx, text):
    ctx.status("🗯 تحويل النص إلى صوت......")
    if ctx.act:
        ctx.act.action = "record_voice"
    kind, data = tts_bytes(text)
    ensure_task_running()
    if len(data) > MAX_TEMP_STORAGE_BYTES:
        raise ValueError("ناتج تحويل الصوت يتجاوز حد الملف المؤقت 5MB.")
    f = io.BytesIO(data)
    f.name = "voice.ogg" if kind == "voice" else "voice.mp3"
    if kind == "voice":
        bot.send_voice(ctx.chat_id, f, reply_to_message_id=ctx.reply_to)
    else:
        bot.send_audio(ctx.chat_id, f, reply_to_message_id=ctx.reply_to)


class ImageLimit(Exception):
    pass


class ImageQuotaError(Exception):
    status_code = 429                                        


_cf_cooldown = {}


def today_key():
    now = dt.datetime.now(LOCAL_TZ)
    return now.strftime("%Y-%m-%d-") + ("00" if now.hour < 12 else "12")


def image_used(uid):
    r = q("SELECT n FROM image_usage WHERE user_id=? AND day=?", (uid, today_key()), one=True)
    return r["n"] if r else 0


def image_reserve(uid):
    if _emergency_active:
        return False
    if is_admin(uid):
        return True
    with _dblock:
        if image_used(uid) >= IMAGE_DAILY_LIMIT:
            return False
        _db.execute("INSERT INTO image_usage(user_id,day,n) VALUES(?,?,1) "
                    "ON CONFLICT(user_id,day) DO UPDATE SET n=n+1", (uid, today_key()))
        _db.commit()
    return True


def image_refund(uid):
    if not is_admin(uid):
        ex("UPDATE image_usage SET n=MAX(0,n-1) WHERE user_id=? AND day=?", (uid, today_key()))


def to_english_prompt(text):
    if not re.search(r"[\u0600-\u06FF]", text):
        return text
    try:
        r = ai_chat(model=TEXT_MODEL, temperature=0.2, max_completion_tokens=200, reasoning_effort="none",
                    messages=[{"role": "system", "content": "Turn the user's image description into one detailed "
                               "English prompt for an image generator. Output only the prompt."},
                              {"role": "user", "content": text[:500]}])
        return clean_ai(r.choices[0].message.content) or text
    except Exception:
        return text


def cf_generate(prompt):
    if not CF_ACCOUNTS:
        raise RuntimeError("Cloudflare is not configured")
    now = time.time()
    order = [a for a in CF_ACCOUNTS if _cf_cooldown.get(a[0], 0) <= now] or CF_ACCOUNTS[:1]
    last = None
    for acc, tok in order:
        try:
            r = requests.post(
                f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{IMAGE_MODEL}",
                headers={"Authorization": f"Bearer {tok}"},
                json={"prompt": prompt[:2000], "steps": 4}, timeout=90)
        except requests.exceptions.RequestException as e:
            last = e
            continue
        if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image/"):
            return r.content
        try:
            img = (r.json().get("result") or {}).get("image")
        except ValueError:
            img = None
        if r.status_code == 200 and img:
            return base64.b64decode(img)
        body = r.text[:300]
        if r.status_code == 429 or "4006" in body or "neurons" in body.lower():
            _cf_cooldown[acc] = time.time() + 3600
            last = ImageQuotaError("Cloudflare image quota reached")
        else:
            last = RuntimeError(f"Cloudflare {r.status_code}: {body}")
    raise last or RuntimeError("image generation failed")


def pollinations_generate(prompt):
    r = requests.get("https://image.pollinations.ai/prompt/" + requests.utils.quote(prompt[:800]),
                     params={"width": 1024, "height": 1024, "model": "flux", "nologo": "true"}, timeout=90)
    if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image/"):
        return r.content
    raise RuntimeError(f"Pollinations {r.status_code}")


def generate_image_bytes(prompt):
    try:
        return cf_generate(prompt)
    except Exception as first:
        try:
            return pollinations_generate(prompt)
        except Exception:
            raise first


def generate_and_send_image(ctx, prompt):
    uid = ctx.uid
    if not image_reserve(uid):
        raise ImageLimit()
    try:
        ctx.status("🎨 جاري توليد الصورة.....")
        if ctx.act:
            ctx.act.action = "upload_photo"
        data = generate_image_bytes(to_english_prompt(prompt.strip()))
        ensure_task_running()
        if len(data) > MAX_TEMP_STORAGE_BYTES:
            raise ValueError("ناتج توليد الصورة يتجاوز حد الملف المؤقت 5MB.")
        f = io.BytesIO(data)
        f.name = "image.jpg"
        left = "" if is_admin(uid) else f"\n🎨 المتبقي في دورة الـ12 ساعة: {max(0, IMAGE_DAILY_LIMIT - image_used(uid))}"
        bot.send_photo(ctx.chat_id, f, caption="✅ تم إنشاء الصورة" + left,
                       reply_to_message_id=ctx.reply_to)
    except Exception:
        image_refund(uid)
        raise


def do_image(ctx, prompt):
    try:
        generate_and_send_image(ctx, prompt[:1000])
    except ImageLimit:
        bot.send_message(ctx.chat_id, f"🎨 وصلت إلى حدك في دورة الـ12 ساعة ({IMAGE_DAILY_LIMIT} صور). تتجدد الحصة مع دورة التنظيف التالية 🙏",
                         reply_to_message_id=ctx.reply_to)


BLOCKING_RE = re.compile(r"SyntaxError|undefined name|غير صالح|^(JavaScript|PHP|Shell):|تعذر تحليل")
REMOVAL_RE = re.compile(r"حذف|احذف|ازال|إزال|امسح|شيل|remove|delete", re.I)


def blocking_errors(name, code):
    """أخطاء حقيقية تمنع التشغيل (صياغة / أسماء غير معرّفة ...) بالفحص المحلي المجاني."""
    try:
        errs = static_check({name: code})
    except Exception:
        return []
    return [(p, l, m) for p, l, m in errs if BLOCKING_RE.search(m)]


def py_defs(code):
    try:
        tree = ast.parse(code)
    except Exception:
        return set()
    out = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.add(n.name)
        elif isinstance(n, ast.ClassDef):
            out.add(n.name)
            for s in n.body:
                if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.add(f"{n.name}.{s.name}")
    return out


def lost_features(name, orig, new):
    """الدوال/الأصناف الموجودة في الملف الأصلي وغابت من النسخة المعدّلة (بايثون)."""
    if not orig or not name.lower().endswith(".py"):
        return []
    return sorted(py_defs(orig) - py_defs(new))


def do_send_file(ctx, args):
    uid = ctx.uid
    raw_name = str(args.get("filename") or "").strip()
    content = args.get("content")
    saved = get_user_file(uid, "code")
    if not content or not str(content).strip():
        if not saved:
            return "لا يوجد كود محفوظ من المحادثة. اكتب الكود كاملاً ثم استدعِ send_file مع content."
        content = saved["content"]
        raw_name = raw_name or saved["name"]
    content = str(content)
    name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(raw_name))[:80]
    lang = saved["lang"] if saved else ""
    if not name:
        name = "code." + EXT.get((lang or "").lower(), "txt")
    if "." not in name:
        name += "." + EXT.get((lang or "").lower(), "txt")
    if len(content) > MAX_OUTPUT_FILE_CHARS:
        return "المحتوى أكبر من الحد المسموح للملف الواحد؛ قسّمه إلى عدة ملفات وأرسل كل ملف على حدة."

    tries = ctx.file_tries.get(name, 0)
    ctx.file_tries[name] = tries + 1
    warns = []
    errs = blocking_errors(name, content)
    if tries < 2:
        if errs:
            lst = "; ".join(f"سطر {l}: {m}" for _, l, m in errs[:8])
            return ("فشل فحص الكود قبل الإرسال ولم يُرسل الملف. الأخطاء: " + lst +
                    ". صحّح الكود وأعد استدعاء send_file بالمحتوى الكامل بعد التصحيح.")
        up = get_user_file(uid, "upload")
        if up and up["name"] == name and not REMOVAL_RE.search(ctx.request_text or ""):
            lost = lost_features(name, up["content"], content)
            if lost:
                return ("لم يُرسل الملف: النسخة المعدّلة ينقصها عناصر موجودة في ملف المستخدم الأصلي: "
                        + ", ".join(lost[:15]) + ". أعد الملف كاملاً مع هذه العناصر دون حذف أي ميزة، "
                        "ثم استدعِ send_file من جديد.")
    elif errs:
        warns.append("⚠️ ما زالت فيه ملاحظات صياغة، راجعه قبل التشغيل.")

    caption = (str(args.get("explanation") or "").strip() or f"📎 {name}")
    if warns:
        caption += "\n" + "\n".join(warns)
    send_text_file(ctx, name, content, caption[:1000])
    save_user_file(uid, "code", name, os.path.splitext(name)[1].lstrip("."), content)
    ctx.file_sent = True
    return (f"تم إرسال الملف {name} للمستخدم مع الشرح كتعليق عليه. اكتب الآن ردّاً قصيراً ودوداً "
            "(بدون إعادة الكود) تلخّص فيه ما يفعله الملف وكيف يشغّله.")


READ_CHUNK_CHARS = int(os.getenv("READ_CHUNK_CHARS", "9000"))


def do_read_saved(ctx, args):
    kind = "upload" if str(args.get("kind", "code")).lower().startswith("up") else "code"
    r = get_user_file(ctx.uid, kind)
    if not r:
        return "لا يوجد ملف محفوظ من هذا النوع."
    lines = r["content"].split("\n")
    total = len(lines)
    try:
        a = max(1, int(args.get("from_line") or 1))
    except Exception:
        a = 1
    try:
        b = int(args.get("to_line") or 0)
    except Exception:
        b = 0
    b = min(total, b if b >= a else total)
    out, n, last = [], 0, a - 1
    for k in range(a - 1, b):
        ln = lines[k][:1500]
        if out and n + len(ln) + 8 > READ_CHUNK_CHARS:
            break
        out.append(f"{k + 1}| {ln}")
        n += len(ln) + 8
        last = k + 1
    more = ""
    if last < total:
        more = (f"\n[المعروض الأسطر {a}-{last} من {total}. لقراءة الباقي استدعِ read_saved_file "
                f"بـ from_line={last + 1}. لا تعد كتابة الملف كاملاً؛ عدّل بالأداة patch_saved_file]")
    return (f"الملف: {r['name']} ({total} سطر) — الأرقام n| للإرشاد فقط وليست من الكود\n"
            f"```\n" + "\n".join(out) + f"\n```{more}")


def do_patch_saved(ctx, args):
    find = str(args.get("find") or "")
    rep_txt = args.get("replace")
    rep_txt = "" if rep_txt is None else str(rep_txt)
    if not find:
        return "النص المراد استبداله (find) فارغ."
    cands = [x for x in (get_user_file(ctx.uid, "code"), get_user_file(ctx.uid, "upload")) if x]
    if not cands:
        return "لا يوجد ملف محفوظ لتعديله."
    base = max(cands, key=lambda x: x["ts"])
    if "!partial" in (base["lang"] or "") or len(base["content"]) >= SAVED_FILE_CHARS:
        return "هذا الملف قُرئ جزئياً فقط (طويل جداً)، لذا لا يمكن تعديله وإرساله كاملاً دون فقدان أجزائه."
    content, name = base["content"], base["name"]
    cnt = content.count(find)
    if cnt == 0:
        return "النص find غير موجود حرفياً في الملف. اقرأ المقطع بـ read_saved_file وانسخه حرفياً (بدون أرقام الأسطر)."
    if cnt > 1 and not args.get("replace_all"):
        return f"النص find يتكرر {cnt} مرات؛ وسّعه بسطور محيطة ليصبح فريداً أو استعمل replace_all."
    new = content.replace(find, rep_txt)
    save_user_file(ctx.uid, "code", name, base["lang"], new)
    msg = f"تم تعديل الملف {name} (الآن {new.count(chr(10)) + 1} سطر). أكمل بقية التعديلات ثم استدعِ send_file بدون content."
    errs = blocking_errors(name, new)
    if errs:
        msg += " تنبيه: أخطاء صياغة حالياً: " + "; ".join(f"سطر {l}: {m_}" for _, l, m_ in errs[:5])
    return msg


def run_tool(ctx, name, args):
    try:
        if name == "text_to_speech":
            run_queued_tool("tts", ctx, do_tts, args.get("text", ""))
            return "تم إرسال المقطع الصوتي للمستخدم."
        if name == "read_webpage":
            ctx.status("🗯 قراءة الصفحة.....")
            return read_webpage(str(args.get("url", "")))
        if name == "calculate":
            return safe_calc(str(args.get("expression", "")))
        if name == "send_file":
            return do_send_file(ctx, args)
        if name == "read_saved_file":
            return do_read_saved(ctx, args)
        if name == "patch_saved_file":
            return do_patch_saved(ctx, args)
        if name == "remove_image_background":
            if not ctx.image_data:
                return "لا توجد صورة مرفقة لمعالجة خلفيتها. اطلب من المستخدم إرسال الصورة أولاً."
            run_queued_tool("rembg", ctx, _remove_bg_tool, ctx.image_data)
            return "تمت إزالة الخلفية وإرسال صورة PNG شفافة للمستخدم."
        if name == "generate_image":
            try:
                run_queued_tool("image", ctx, generate_and_send_image, str(args.get("prompt", "")))
                return "تم إرسال الصورة للمستخدم. اكتب ردّاً قصيراً جداً بجملة واحدة دون وصفها بالتفصيل."
            except ImageLimit:
                return (f"بلغ المستخدم حدّه في دورة الـ12 ساعة ({IMAGE_DAILY_LIMIT} صور) ويتجدد مع الدورة التالية. "
                        "أخبره بلطف ولا تحاول التوليد مجدداً.")
        return "أداة غير معروفة."
    except TaskCancelled:
        raise
    except Exception as e:
        if is_service_limit_error(e):
            raise                                                
        notify_admin(f"tool:{name}", e, ctx.uid)
        return user_error_message(e)



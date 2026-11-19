import base64, json, os, subprocess, requests
from functools import lru_cache
import anthropic
from PIL import Image, ImageDraw, ImageFont

FONTS = {"serif": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
         "sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"}

STYLES = {
 "Batik Emas": dict(top=(88,56,28), bot=(150,98,50), pat="batik", stat=(244,206,96), statf="serif", shadow=False,
    cap_bg=(122,28,40), on=(250,210,110), done=(250,235,200), off=(185,145,135), label_bg=(122,28,40), label_fg=(250,210,110)),
 "Peta Antik": dict(top=(228,214,178), bot=(204,184,140), pat="peta", stat=(40,28,20), statf="serif", shadow=False,
    cap_bg=(250,244,228), on=(180,40,30), done=(30,22,16), off=(160,155,150), label_bg=(250,244,228), label_fg=(90,60,40)),
 "Low-poly Ceria": dict(top=(253,205,125), bot=(240,150,70), pat="poly", stat=(255,255,255), statf="sans", shadow=True,
    cap_bg=(98,98,150), on=(255,215,60), done=(255,255,255), off=(190,190,220), label_bg=(98,98,150), label_fg=(255,215,60)),
 "Flat Sains": dict(top=(22,60,80), bot=(30,135,155), pat="strata", stat=(255,255,255), statf="sans", shadow=True,
    cap_bg=None, on=(150,240,255), done=(255,255,255), off=(120,150,160), label_bg=(70,100,110), label_fg=(235,245,245)),
}

@lru_cache(None)
def font(kind, size): return ImageFont.truetype(FONTS[kind], int(size))

def make_script(title, category, seconds, key):
    n = int(seconds * 2.4)
    prompt = f"""Tulis naskah voice over bahasa Indonesia untuk video motion graphic.
Judul: {title}
Kategori: {category}
Panjang total sekitar {n} kata. Gaya: hook kuat di awal, mengalir, mudah dicerna, penutup berkesan.
Pecah jadi scene (1-2 kalimat per scene). Balas HANYA JSON valid tanpa markdown:
{{"scenes":[{{"text":"kalimat narasi","stat":{{"value":"671","unit":"M"}} atau null,"label":"label pendek atau null"}}]}}
stat dipakai hanya jika ada angka penting di scene itu."""
    r = anthropic.Anthropic(api_key=key).messages.create(
        model="claude-sonnet-5-5", max_tokens=8000, messages=[{"role": "user", "content": prompt}])
    t = r.content[0].text.strip().strip("`")
    if t.startswith("json"): t = t[4:]
    return json.loads(t)["scenes"]

def tts(text, voice, key, path):
    r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps",
        headers={"xi-api-key": key}, json={"text": text, "model_id": "eleven_multilingual_v2"}, timeout=180)
    r.raise_for_status(); d = r.json()
    open(path, "wb").write(base64.b64decode(d["audio_base64"]))
    a = d["alignment"]; words, cur, st, pe = [], "", 0, 0
    for ch, s, e in zip(a["characters"], a["character_start_times_seconds"], a["character_end_times_seconds"]):
        if ch.isspace():
            if cur: words.append((cur, st, pe)); cur = ""
        else:
            if not cur: st = s
            cur += ch
        pe = e
    if cur: words.append((cur, st, pe))
    return words

def background(s, W, H):
    img = Image.new("RGB", (W, H)); d = ImageDraw.Draw(img)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * y / H) for a, b in zip(s["top"], s["bot"])))
    p = s["pat"]
    if p == "batik":
        y0 = int(H * .62); d.rectangle([0, y0, W, H], fill=(24, 36, 84))
        for r, y in enumerate(range(y0 + 30, H, 70)):
            for x in range(0, W, 70):
                o = 35 if r % 2 else 0
                d.arc([x+o, y, x+o+40, y+40], 20, 320, fill=(220, 222, 240), width=3)
    elif p == "peta":
        for i in range(9):
            r = 120 + i * 90; d.ellipse([W*.3-r, H*.6-r*.6, W*.3+r, H*.6+r*.6], outline=(190, 170, 128), width=2)
    elif p == "poly":
        for i in range(7):
            x, y, z = (i * 197) % W, (i * 331) % H, 160 + i * 25
            d.polygon([(x, y), (x+z, y+z//2), (x-z//3, y+z)], fill=(255, 190 + i*6, 110))
    else:
        y0 = int(H * .6)
        for i, y in enumerate(range(y0, H, 60)):
            d.rectangle([0, y, int(W*.55), y+60], fill=(60+i*4, 90+i*3, 95+i*2))
            d.rectangle([int(W*.55), y, W, y+60], fill=(15, 90-i*3, 120-i*3))
    return img

def ease(x): x = max(0, min(1, x)); return 1 - (1 - x) ** 3

def wrap(d, ws, f, maxw):
    lines = [[]]
    for w in ws:
        if lines[-1] and d.textlength(" ".join(lines[-1] + [w]), font=f) > maxw: lines.append([w])
        else: lines[-1].append(w)
    return lines

def frame(bg, s, scene, words, t, W, H):
    img = bg.copy(); d = ImageDraw.Draw(img); m = min(W, H); y0 = H * .16
    st = scene.get("stat")
    if st:
        e = ease(t / .6); big = m * .2
        f, u = font(s["statf"], big * (.8 + .2 * e)), font(s["statf"], big * .35)
        v, un = str(st["value"]), " " + str(st.get("unit") or "")
        wv = d.textlength(v, font=f); x = (W - wv - d.textlength(un, font=u)) / 2; by = y0 + big - (1 - e) * 40
        if s["shadow"]: d.text((x+4, by+4), v, font=f, fill=(0, 0, 0), anchor="ls")
        d.text((x, by), v, font=f, fill=s["stat"], anchor="ls")
        d.text((x + wv, by), un, font=u, fill=s["stat"], anchor="ls")
        y0 += big * 1.35
    lb = scene.get("label")
    if lb and t > .3:
        fs = m * .042; f = font("sans", fs); tw = d.textlength(lb, font=f)
        d.rounded_rectangle([(W-tw)/2-24, y0, (W+tw)/2+24, y0+fs*1.9], 20, fill=s["label_bg"])
        d.text((W/2, y0+fs*.95), lb, font=f, fill=s["label_fg"], anchor="mm")
    if not words: return img
    cw = max([i for i, w in enumerate(words) if w[1] <= t] or [0])
    k = cw // 4 * 4; chunk = words[k:k+4]
    fs = m * .058; f = font("sans", fs); lh = fs * 1.55
    lines = wrap(d, [w[0] for w in chunk], f, W * .8)
    top = H * .74 - len(lines) * lh / 2
    if s["cap_bg"]:
        mw = max(d.textlength(" ".join(l), font=f) for l in lines)
        d.rounded_rectangle([(W-mw)/2-32, top-14, (W+mw)/2+32, top+len(lines)*lh+4], 18, fill=s["cap_bg"])
    i = k
    for n, l in enumerate(lines):
        x = (W - d.textlength(" ".join(l), font=f)) / 2
        for w in l:
            c = s["done"] if i < cw else s["on"] if i == cw else s["off"]
            if not s["cap_bg"]: d.text((x+3, top+n*lh+3), w, font=f, fill=(0, 0, 0))
            d.text((x, top + n * lh), w, font=f, fill=c)
            x += d.textlength(w + " ", font=f); i += 1
    return img

def render_scene(scene, words, audio, out, style, size, fps=24):
    W, H = size; s = STYLES[style]; dur = (words[-1][2] if words else 2) + .5; n = int(dur * fps)
    bg = background(s, W, H)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-i", audio, "-af", "apad", "-t", f"{dur:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", out],
        stdin=subprocess.PIPE)
    for i in range(n): p.stdin.write(frame(bg, s, scene, words, i / fps, W, H).tobytes())
    p.stdin.close(); p.wait()

def concat(parts, out):
    lst = out + ".txt"; open(lst, "w").write("".join(f"file '{os.path.abspath(x)}'\n" for x in parts))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], check=True)

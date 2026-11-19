import os, tempfile, streamlit as st
import engine

st.set_page_config(page_title="Motion Studio", page_icon="🎬", layout="centered")
st.markdown("""<style>
.block-container{max-width:760px;padding-top:2rem}
h1{color:#1D4ED8;font-weight:700;letter-spacing:-.02em}
.stButton>button{background:#2563EB;color:#fff;border:0;border-radius:12px;padding:.6rem 1.2rem;width:100%}
.stButton>button:hover{background:#1D4ED8;color:#fff}
</style>""", unsafe_allow_html=True)
st.title("Motion Studio")
st.caption("Tulis judul → naskah → voice over → video motion.")

FORMATS = {"Short 9:16": ((720, 1280), {"30 detik": 30, "1 menit": 60}),
           "YouTube 16:9": ((1280, 720), {"5 menit": 300, "10 menit": 600})}
ss = st.session_state
voice = st.sidebar.text_input("ElevenLabs Voice ID", "21m00Tcm4TlvDq8ikWAM")

fmt = st.radio("Format", list(FORMATS), horizontal=True)
size, durs = FORMATS[fmt]
dur = st.radio("Durasi", list(durs), horizontal=True)
cat = st.selectbox("Kategori", ["Edukasi", "Sejarah", "Fakta Unik", "Lainnya"])
style = st.radio("Gaya", list(engine.STYLES), horizontal=True)
title = st.text_input("Judul video")

if st.button("1. Buat naskah") and title:
    with st.spinner("Claude lagi nulis naskah..."):
        ss.scenes = engine.make_script(title, cat, durs[dur], st.secrets["ANTHROPIC_API_KEY"])
    ss.pop("vo", None); ss.pop("video", None)

if "scenes" in ss:
    st.subheader("Naskah")
    for i, sc in enumerate(ss.scenes):
        sc["text"] = st.text_area(f"Scene {i+1}", sc["text"], key=f"t{i}", height=80)
    if st.button("2. Generate VO (ElevenLabs)"):
        ss.dir = tempfile.mkdtemp(); ss.vo = []; bar = st.progress(0)
        for i, sc in enumerate(ss.scenes):
            p = os.path.join(ss.dir, f"a{i}.mp3")
            ss.vo.append((p, engine.tts(sc["text"], voice, st.secrets["ELEVENLABS_API_KEY"], p)))
            bar.progress((i + 1) / len(ss.scenes))
        st.success("VO selesai.")

if "vo" in ss:
    if st.button("3. Render video"):
        parts, bar = [], st.progress(0, "Render...")
        for i, (sc, (a, w)) in enumerate(zip(ss.scenes, ss.vo)):
            o = os.path.join(ss.dir, f"s{i}.mp4")
            engine.render_scene(sc, w, a, o, style, size); parts.append(o)
            bar.progress((i + 1) / len(ss.scenes), f"Scene {i+1}/{len(ss.scenes)}")
        ss.video = os.path.join(ss.dir, "final.mp4"); engine.concat(parts, ss.video)

if ss.get("video"):
    st.video(ss.video)
    st.download_button("Download MP4", open(ss.video, "rb"), "video.mp4", "video/mp4")

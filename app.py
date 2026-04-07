from brain.ml_intent import predict_intent
import os
import re
import time
import threading
from functools import lru_cache
from urllib.parse import quote

from dotenv import load_dotenv
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

import requests
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup  # dipakai fallback scraping
from fox_chat_child import child_chat
import serial
from serial.tools import list_ports

from brain.memory import remember, recall, remember_answer, recall_answer

from transformers import VisionEncoderDecoderModel, ViTImageProcessor, AutoTokenizer
from PIL import Image
import base64
import io

# =========================
# Boot & Config
# =========================
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
current_mode = "idle"

# 🔥 TAMBAH DI SINI
model = VisionEncoderDecoderModel.from_pretrained(
    "nlpconnect/vit-gpt2-image-captioning"
)
processor = ViTImageProcessor.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
tokenizer = AutoTokenizer.from_pretrained("nlpconnect/vit-gpt2-image-captioning")

import torch

model.eval()

# =========================
# Emotion / Repeat Memory
# =========================
from collections import OrderedDict

QUESTION_MEMORY = OrderedDict()
MAX_MEMORY = 10

LAST_QUESTION = None

# =========================
# Idle Talk Memory
# =========================
import random

global LAST_CHAT_TIME
LAST_CHAT_TIME = time.time()
IS_PROCESSING = False
IDLE_SECONDS = 40  # boleh 20–40 detik, sesuka kamu

# HTTP session umum
session = requests.Session()
session.headers.update({"User-Agent": "FoxDynaMiX/1.0 (ToraBot)"})


# =========================
# Util teks (bersihin & ringkas)
# =========================
def clean_and_shorten(text: str, max_sentences: int = 2) -> str:
    if not text:
        return ""
    text = re.sub(r"[*_`^#>\[\]]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:max_sentences]).strip()


def translate_to_indonesia(text):
    kamus = {
        "cat": "kucing",
        "dog": "anjing",
        "bird": "burung",
        "black": "hitam",
        "white": "putih",
        "standing": "berdiri",
        "sitting": "duduk",
        "on": "di",
        "top": "atas",
        "fence": "pagar",
        "a": "",
        "of": "",
        "fish": "ikan",
        "yellow": "kuning",
        "striped": "belang",
        "close": "",
        "up": "",
        "close up": "jarak dekat",
        "picture": "",
        "picature": "",
        "and": "dan",
        "rock": "batu",
        "on": "di",
        "top": "atas",
        "two": "dua",
        "three": "tiga",
        "one": "satu",
        "are": "",
        "is": "",
        "in": "di",
        "field": "lapangan",
        "grass": "rumput",
        "grassy": "berumput",
        "giraffe": "jerapah",
        "giraffes": "jerapah",
        "rose": "mawar",
        "blooming": "mekar",
        "tree": "pohon",
        "middle": "tengah",
    }

    text = re.sub(r"\b(the|a|an)\b", "", text)

    text = text.lower()

    # 🔥 HANDLE FRASE DULU
    text = text.replace("close up", "jarak dekat")
    text = text.replace("closeup", "jarak dekat")

    # 🔥 PAKAI WORD BOUNDARY (INI KUNCI)
    for en, idn in kamus.items():
        text = re.sub(rf"\b{en}\b", idn, text)

    return text


# 🔥 TARUH DI SINI
def decode_image(base64_str):
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]

    image_data = base64.b64decode(base64_str)
    return Image.open(io.BytesIO(image_data))


def get_image_caption(image):
    pixel_values = processor(images=image, return_tensors="pt").pixel_values

    with torch.no_grad():
        output_ids = model.generate(
            pixel_values,
            max_length=20,
            num_beams=5,  # 🔥 INI PENTING
            no_repeat_ngram_size=2,
            early_stopping=True,
        )

    caption = tokenizer.decode(output_ids[0], skip_special_tokens=True)

    caption = caption.lower().strip()

    caption = re.sub(r"[^a-zA-Z\s]", "", caption)
    caption = " ".join(caption.split())

    # 🔥 NORMALISASI KATA RUSAK
    fix_map = {
        "blck": "black",
        "blk": "black",
        "ct": "cat",
        "stnddig": "standing",
        "stnding": "standing",
        "brd": "bird",
        "fce": "face",
    }

    for wrong, correct in fix_map.items():
        caption = caption.replace(wrong, correct)

    # 🔥 hapus kata aneh
    bad_words = ["somedies"]
    for w in bad_words:
        caption = caption.replace(w, "")
    # 🔥 rapihin spasi
    caption = " ".join(caption.split())

    # 🔥 translate
    caption_id = translate_to_indonesia(caption)
    caption_id = " ".join(caption_id.split())

    # 🔥 BERSIHKAN SAMPAH
    caption_id = re.sub(r"\b(close|picture|image)\b", "", caption_id)
    caption_id = " ".join(caption_id.split())

    # 🔥 PRIORITAS OBJEK DI DEPAN
    words = caption_id.split()

    priority = ["ikan", "kucing", "anjing", "burung"]

    for p in priority:
        if p in words:
            words.remove(p)
            caption_id = p + " " + " ".join(words)
            break

    if not caption_id.strip():
        return "objek yang kurang jelas"

    if len(caption.split()) < 2:
        return "objek yang sulit dikenali"

    # 🔥 HANDLE JAMAK FINAL
    if caption_id.startswith("dua "):
        return caption_id.replace("dua ", "dua ekor ")

    hewan = ["kucing", "anjing", "burung", "ikan", "jerapah", "kura-kura", "gajah"]

    if caption_id.startswith("dua "):
        if any(h in caption_id for h in hewan):
            return caption_id.replace("dua ", "dua ekor ")
        else:
            return caption_id.replace("dua ", "dua buah ")

    if any(h in caption_id for h in hewan):
        return f"seekor {caption_id}"

    return f"sebuah {caption_id}"

# =========================
# ESP32 (opsional)
# =========================
def find_esp32_port():
    for p in list_ports.comports():
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if any(k in desc for k in ("silicon labs", "cp210", "usb", "ch340")) or any(
            k in hwid for k in ("usb", "cp210", "ftdi", "ch340")
        ):
            return p.device
    return None


PORT = os.getenv("ESP_PORT") or find_esp32_port() or "COM3"
BAUD_RATE = 9600
try:
    ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    print(f"✅ ESP32 terhubung di {PORT}")
except Exception as e:
    ser = None
    print(f"❌ ESP32 tidak terhubung di port {PORT}. Error: {e}")


def send_serial(cmd: str):
    if ser:
        try:
            ser.write(f"{cmd}\n".encode())
            socketio.emit("log", {"msg": f"Serial ➔ ESP32: {cmd}"})
        except Exception as e:
            print(f"⚠️ Gagal mengirim Serial: {e}")
            socketio.emit("log", {"msg": f"[ERROR] Serial gagal: {e}"})


def serial_reader():
    while True:
        if ser and ser.in_waiting:
            try:
                line = ser.readline().decode(errors="ignore").strip()
                if line.startswith("LED:"):
                    socketio.emit("led_update", {"led": line[4:]})
                    socketio.emit("log", {"msg": f"ESP32: LED ➔ {line[4:]}"})
                elif line.startswith("REPLY:"):
                    socketio.emit("reply", {"msg": line[6:]})
                    socketio.emit("log", {"msg": f"ESP32 Balas: {line[6:]}"})
                else:
                    socketio.emit("log", {"msg": f"Serial Masuk: {line}"})
            except Exception as e:
                print(f"‼️ Serial read error: {e}")
                socketio.emit("log", {"msg": f"[ERROR] Serial read: {e}"})
                time.sleep(0.5)
        time.sleep(0.1)


last_idle_sent = 0


def idle_talk_loop():
    global LAST_CHAT_TIME, last_idle_sent

    while True:
        now = time.time()
        idle = now - LAST_CHAT_TIME

        if not IS_PROCESSING and idle > IDLE_SECONDS and now - last_idle_sent > 30:
            msg = random.choice(
                [
                    "Div… kamu masih di situ kan? 🦊",
                    "Heii~ Fox lagi nungguin nih 😗",
                    "Aku diem tapi masih hidup loh 😆",
                    "Kalo capek bilang ya… Fox nemenin 🫶",
                    "Div jangan tinggalin aku lama-lama 🥺",
                ]
            )

            socketio.emit("reply", {"msg": msg}, to=None)

            last_idle_sent = now  # 🔥 update cooldown

            LAST_CHAT_TIME = now  # 🔥 INI KUNCINYA

        time.sleep(30)


threading.Thread(target=serial_reader, daemon=True).start()
threading.Thread(target=idle_talk_loop, daemon=True).start()

# =========================
# Knowledge shortcuts (keyword → judul wiki)
# =========================
KEYWORD_MAP = {
    "mata uang indonesia": "Rupiah",
    "mata uang amerika": "United States dollar",
    "kenapa langit berwarna biru": "Langit",
}


# =========================
# Wikipedia (ID → EN)
# =========================
@lru_cache(maxsize=256)
def wiki_search_title(query: str, lang: str = "id") -> str:
    try:
        r = session.get(
            f"https://{lang}.wikipedia.org/w/rest.php/v1/search/title",
            params={"q": query, "limit": 1},
            timeout=1.5,
        )
        r.raise_for_status()
        pages = r.json().get("pages") or []
        return pages[0]["title"] if pages else ""
    except Exception:
        return ""


@lru_cache(maxsize=256)
def wiki_summary_by_title(title: str, lang: str = "id") -> dict | None:
    if not title:
        return None
    try:
        r = session.get(
            f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
            timeout=1.5,
        )
        r.raise_for_status()
        j = r.json()
        extract = j.get("extract") or ""
        if not extract:
            return None
        url = (
            j.get("content_urls", {}).get("desktop", {}).get("page")
            or f"https://{lang}.wikipedia.org/wiki/{quote(title)}"
        )
        return {
            "title": j.get("title") or title,
            "summary": clean_and_shorten(extract, 2),
            "url": url,
            "source": f"Wikipedia ({lang})",
        }
    except Exception:
        return None


def smart_wiki_answer(query: str) -> dict | None:
    for lang in ("id", "en"):
        direct = wiki_summary_by_title(query, lang)
        if direct:
            return direct
        found = wiki_search_title(query, lang)
        if found:
            summed = wiki_summary_by_title(found, lang)
            if summed:
                return summed
    return None


# =========================
# Repeat Question Memory
# =========================


def count_question_repeat(q: str) -> int:
    q = q.lower().strip()

    if q in QUESTION_MEMORY:
        QUESTION_MEMORY[q] += 1
    else:
        QUESTION_MEMORY[q] = 1

    # geser ke paling baru
    QUESTION_MEMORY.move_to_end(q)

    # hapus yang paling lama
    if len(QUESTION_MEMORY) > MAX_MEMORY:
        QUESTION_MEMORY.popitem(last=False)

    return QUESTION_MEMORY[q]


def emotion_prefix(n: int) -> str:
    if n == 1:
        return ""
    elif n == 2:
        return "Hehe… Div nanya lagi 😅\n\n"
    elif n == 3:
        return "Div 😤 ini udah ketiga kalinya ya…\n\n"
    elif n == 4:
        return "Hadeeh 😠 FoxDynamiX jawab lagi tapi ini mulai ngeselin…\n\n"
    else:
        return "DIV 😈 aku jawab ya… tapi kamu jangan ulang lagi 😤🔥\n\n"


def deja_vu_prefix(is_same: bool) -> str:
    if is_same:
        return "😏 Eh… kamu barusan nanya ini loh.\n\n"
    return ""


# =========================
# DuckDuckGo fallback
# =========================
try:
    ddgs = DDGS()
except Exception:
    ddgs = None
    print("⚠️ DuckDuckGo init failed")


def smart_web_answer(q: str):

    if not ddgs:
        return None

    # 🔥 BIKIN QUERY LEBIH MANUSIAWI
    q = f"{q} penjelasan singkat"

    try:
        # Limit hasil awal untuk reduce processing
        results = list(ddgs.text(q, region="wt-wt", safesearch="off", max_results=4))

        # ---- Coba pakai body DuckDuckGo dulu ----
        for r in results:
            url = r.get("href") or r.get("url")
            body = r.get("body") or ""
            title = r.get("title") or "Hasil Web"

            if url and len(body.strip()) > 50:
                return {
                    "title": title,
                    "summary": clean_and_shorten(body, 2),
                    "url": url,
                    "source": "Web (DuckDuckGo)",
                }

        # ---- Kalau body pendek, coba scraping MINIMAL halaman ----
        for r in results[:1]:  # Hanya 1 URL untuk reduce blocking
            url = r.get("href") or r.get("url")
            if not url:
                continue

            try:
                html = session.get(
                    url,
                    timeout=1.5,  # Lower timeout untuk faster return
                    headers={"User-Agent": "Mozilla/5.0"},
                ).text

                soup = BeautifulSoup(html, "html.parser")

                p = next(
                    (
                        p.get_text(" ", strip=True)
                        for p in soup.select("p")
                        if len(p.get_text(strip=True)) > 60
                    ),
                    "",
                )

                if p:
                    return {
                        "title": r.get("title") or "Hasil Web",
                        "summary": clean_and_shorten(p, 2),
                        "url": url,
                        "source": "Web (DuckDuckGo)",
                    }

            except Exception:
                pass

        # ---- Return hasil DDG pertama jika scraping gagal ----
        if results:
            first = results[0]
            return {
                "title": first.get("title") or "Hasil Web",
                "summary": "FoxDynamiX nemu sesuatu di web, tapi masih ringkas banget 😅",
                "url": first.get("href") or first.get("url"),
                "source": "Web (DuckDuckGo)",
            }

    except Exception:
        pass

    return None


def format_answer_payload(ans: dict, fallback_title: str, user_msg: str = "") -> str:
    title = ans.get("title") or fallback_title
    text = ans.get("summary") or ""
    src = ans.get("source") or ""
    url = ans.get("url")

    opener = "Hmm, menurut yang FoxDynamiX temuin ya, Div… 🦊\n\n"
    body = f"**{title}**\n{text}"

    footer_parts = []
    if src:
        footer_parts.append(f"Sumber: {src}")
    if url:
        footer_parts.append(url)

    footer = ""
    if footer_parts:
        footer = "\n\n" + " · ".join(footer_parts)

    return opener + body + footer


# =========================
# COUNTRY & CURRENCY MAP
# =========================
COUNTRY_NORMALIZE = {
    "china": "tiongkok",
    "cina": "tiongkok",
    "amerika": "amerika serikat",
    "usa": "amerika serikat",
    "us": "amerika serikat",
    "inggris": "britania raya",
    "uk": "britania raya",
}

CURRENCY_MAP = {
    "indonesia": "Rupiah",
    "amerika serikat": "United States dollar",
    "tiongkok": "Renminbi",
    "china": "Renminbi",
    "cina": "Renminbi",
    "jepang": "Yen",
    "korea selatan": "Won Korea Selatan",
    "malaysia": "Ringgit Malaysia",
    "singapura": "Dolar Singapura",
    "thailand": "Baht",
    "filipina": "Peso Filipina",
    "vietnam": "Dong Vietnam",
    "india": "Rupee India",
    "uni eropa": "Euro",
    "eropa": "Euro",
    "korea": "Won Korea Selatan",
    "korea selatan": "Won Korea Selatan",
    "korsel": "Won Korea Selatan",
    "korea selatan selatan": "Won Korea Selatan",
    "nigeria": "Naira",
    "thailand": "Baht",
    "brazil": "Brazilian real",
    "brasil": "Brazilian real",
    "britania raya": "Pound sterling",
    "inggris": "Pound sterling",
    "uk": "Pound sterling",
}

# =========================
# HUMAN QUERY NORMALIZER
# =========================

STOPWORDS = [
    "siapa",
    "apa",
    "kenapa",
    "kapan",
    "dimana",
    "di mana",
    "bagaimana",
    "tolong",
    "dong",
    "ya",
    "nih",
    "sekarang",
    "itu",
    "ini",
    "yang",
    "adalah",
    "ialah",
    "kah",
    "nya",
]

ALIAS_MAP = {
    "usa": "amerika serikat",
    "us": "amerika serikat",
    "amerika": "amerika serikat",
    "paman sam": "amerika serikat",
    "uk": "britania raya",
    "inggris": "britania raya",
    "china": "tiongkok",
    "cina": "tiongkok",
}

INTENT_KEYWORDS = {
    "presiden": ["presiden", "pemimpin", "kepala negara", "presidennya"],
    "ibukota": ["ibukota", "ibu kota", "capital"],
    "mata uang": ["mata uang", "uang", "currency"],
    "kenapa": ["kenapa", "mengapa", "why"],
}


def normalize_text(s: str) -> str:
    s = s.lower().strip()

    for a, b in COUNTRY_NORMALIZE.items():
        s = re.sub(rf"\b{re.escape(a)}\b", b, s)

    s = re.sub(r"\s+", " ", s)
    return s


def normalize_human_query(q: str) -> str:
    s = normalize_text(q)
    topic = s  # ✅ PENTING

    # alias
    for k, v in ALIAS_MAP.items():
        s = re.sub(rf"\b{k}\b", v, s)

    # stopword
    for w in STOPWORDS:
        s = re.sub(rf"\b{w}\b", "", s)

    s = re.sub(r"\s+", " ", s).strip()

    # intent rewrite
    for intent, keys in INTENT_KEYWORDS.items():
        for k in keys:
            if k in s:
                entity = s.replace(k, "").strip()
                if entity:
                    return f"{intent} {entity}"

    # ===== KENAPA MODE =====
    if s.startswith("kenapa "):
        topic = s.replace("kenapa ", "").strip()
    else:
        topic = s

    CUT = [
        "berwarna biru",
        "berwarna",
        "asin",
        "panas",
        "dingin",
        "tinggi",
        "rendah",
        "jatuh",
        "terjadi",
    ]

    for w in CUT:
        topic = re.sub(rf"\b{w}\b", "", topic)

    topic = re.sub(r"\s+", " ", topic).strip()

    return topic
    return s


def currency_title_from_query(q: str) -> str | None:
    s = normalize_text(q)

    # hapus kata mata uang / uang
    s = s.replace("mata uang", "").replace("uang", "").strip()

    if s:
        return f"{s.title()} (mata uang)"

    return None


# --- INTENT PARSER (deteksi pola) ---


def parse_intent(q: str) -> tuple[str | None, str | None]:
    s = normalize_text(q)
    m = re.match(r"^(ibu ?kota|ibukota) (.+)$", s)
    if m:
        return "capital", m.group(2).strip()
    m = re.match(r"^presiden (.+)$", s)
    if m:
        return "president", m.group(1).strip()
    m = re.match(r"^bendera (.+)$", s)
    if m:
        return "flag", m.group(1).strip()
    return None, None


# --- WIKIDATA HELPERS ---
@lru_cache(maxsize=128)
def wd_search_entity(name: str, lang: str = "id") -> str | None:
    try:
        r = session.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbsearchentities",
                "search": name,
                "language": lang,
                "format": "json",
                "limit": 1,
            },
            timeout=0.8,
        ).json()
        hits = r.get("search") or []
        return hits[0]["id"] if hits else None
    except Exception:
        return None


@lru_cache(maxsize=128)
def wd_get_claim_target(qid: str, prop: str) -> list[str]:
    try:
        r = session.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbgetclaims",
                "entity": qid,
                "property": prop,
                "format": "json",
            },
            timeout=0.8,
        ).json()

        claims = r.get("claims", {}).get(prop, [])
        current = []
        fallback = []

        for c in claims:
            mainsnak = c.get("mainsnak", {})
            datav = mainsnak.get("datavalue", {})
            val = datav.get("value", {})
            tgt = val.get("id")

            if not tgt:
                continue

            # 🔥 cek qualifier end time (P582)
            qualifiers = c.get("qualifiers", {})
            if "P582" in qualifiers:
                fallback.append(tgt)  # sudah berakhir
            else:
                current.append(tgt)  # masih aktif

        return current or fallback

    except Exception:
        return []


@lru_cache(maxsize=256)
def wd_label(qid: str, lang: str = "id") -> str | None:
    try:
        r = session.get(
            f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json", timeout=0.8
        ).json()
        ent = r.get("entities", {}).get(qid, {})
        labels = ent.get("labels", {})
        return labels.get(lang, {}).get("value") or labels.get("en", {}).get("value")
    except Exception:
        return None


def wd_wikipedia_url(title: str, lang: str = "id") -> str:
    return f"https://{lang}.wikipedia.org/wiki/{quote(title)}"


# --- ROUTER JAWABAN BERDASAR INTENT ---
def answer_by_intent(intent: str, entity_name: str) -> dict | None:
    # Cari entity negara di Wikidata (ID dulu, kalau gagal baru EN)
    normalized_entity = normalize_text(entity_name)

    q_country = (
        wd_search_entity(normalized_entity, "id")
        or wd_search_entity(normalized_entity, "en")
        or wd_search_entity(entity_name, "en")
    )
    if not q_country:
        return None

    # Label yang enak dibaca
    country_label = (
        wd_label(q_country, "id") or wd_label(q_country, "en") or entity_name.title()
    )

    # ========== IBU KOTA ==========
    if intent == "capital":
        caps = wd_get_claim_target(q_country, "P36")
        if not caps:
            return None

        # Ambil elemen paling akhir (paling baru di Wikidata)
        q_cap = caps[-1]
        cap_label = wd_label(q_cap, "id") or wd_label(q_cap, "en") or "Ibu kota"

        summary = f"Ibu kota {country_label} adalah {cap_label}."
        return {
            "title": f"Ibu kota {country_label}",
            "summary": summary,
            "url": f"https://www.wikidata.org/wiki/{q_cap}",
            "source": "Wikidata (P36)",
        }

    # ========== PRESIDEN / KEPALA NEGARA ==========
    if intent == "president":
        # P35 = head of state, P6 = head of government
        heads = wd_get_claim_target(q_country, "P35") or wd_get_claim_target(
            q_country, "P6"
        )
        if not heads:
            return None

        # Ambil elemen terakhir (data paling baru)
        q_head = heads[0]
        head_label = wd_label(q_head, "id") or wd_label(q_head, "en") or "Pemimpin"

        summary = f"Pemimpin negara {country_label}: {head_label}."
        return {
            "title": f"Presiden {country_label}",
            "summary": summary,
            "url": f"https://www.wikidata.org/wiki/{q_head}",
            "source": "Wikidata (P35/P6)",
        }

    # ========== BENDERA ==========
    if intent == "flag":

        # pakai entity langsung, bukan country_label dari Wikidata
        simple_name = entity_name.title()

        title_id = f"Bendera {simple_name}"

        ans = wiki_summary_by_title(title_id, "id")

        if ans:
            return ans

        # fallback English
        title_en = f"Flag of {simple_name}"
        ans = wiki_summary_by_title(title_en, "en")

        if ans:
            return ans

        return None


def parse_weather_query(q: str) -> str | None:
    """
    Deteksi pola seperti:
    - 'cuaca surabaya'
    - 'cuaca di tokyo'
    - 'weather jakarta'
    """
    s = normalize_text(q)

    # pola bahasa Indonesia
    m = re.match(r"^cuaca(?: di)? (.+)$", s)
    if m:
        return m.group(1).strip()

    # pola bahasa Inggris sederhana
    m = re.match(r"^weather(?: in)? (.+)$", s)
    if m:
        return m.group(1).strip()

    return None


# =========================
# Cuaca (Open-Meteo)
# =========================

WEATHER_CODE_DESC = {
    0: ("Cerah", "☀️"),
    1: ("Sebagian cerah", "🌤️"),
    2: ("Berawan sebagian", "⛅"),
    3: ("Berawan", "☁️"),
    45: ("Berkabut", "🌫️"),
    48: ("Berkabut", "🌫️"),
    51: ("Gerimis ringan", "🌦️"),
    53: ("Gerimis", "🌦️"),
    55: ("Gerimis lebat", "🌧️"),
    61: ("Hujan ringan", "🌧️"),
    63: ("Hujan", "🌧️"),
    65: ("Hujan lebat", "🌧️"),
    71: ("Salju ringan", "🌨️"),
    73: ("Salju", "🌨️"),
    75: ("Salju lebat", "🌨️"),
    95: ("Badai petir", "⛈️"),
    96: ("Badai petir", "⛈️"),
    99: ("Badai petir", "⛈️"),
}


def describe_weather(code: int) -> tuple[str, str]:
    desc, emoji = WEATHER_CODE_DESC.get(code, ("Berawan", "☁️"))
    return desc, emoji


def get_weather_answer(location_query: str) -> str | None:
    """
    Pakai Open-Meteo geocoding + current_weather
    """
    try:
        # 1) Geocoding: cari koordinat kota
        geo_r = session.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={
                "name": location_query,
                "count": 1,
                "language": "id",
                "format": "json",
            },
            timeout=1.5,
        )
        geo_r.raise_for_status()
        geo_j = geo_r.json()
        results = geo_j.get("results") or []
        if not results:
            return None

        loc = results[0]
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        nice_name = loc.get("name") or location_query.title()
        country = loc.get("country") or ""
        timezone = loc.get("timezone") or "Unknown"

        if lat is None or lon is None:
            return None

        # 2) Ambil cuaca saat ini
        w_r = session.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
                "timezone": "auto",
            },
            timeout=1.5,
        )
        w_r.raise_for_status()
        w_j = w_r.json()
        cur = w_j.get("current_weather") or {}
        if not cur:
            return None

        temp = cur.get("temperature")
        wind = cur.get("windspeed")
        code = cur.get("weathercode", 3)
        tz = w_j.get("timezone") or timezone

        desc, emoji = describe_weather(int(code))

        # amanin angka supaya nggak meledak
        try:
            temp_str = f"{round(float(temp)):.0f}"
        except Exception:
            temp_str = str(temp)

        try:
            wind_str = f"{round(float(wind)):.0f}"
        except Exception:
            wind_str = str(wind)

        # Format jawaban gaya Diva 🦊✨
        opener = "Div, FoxDynamiX cek dulu ya cuacanya… 🦊💨\n\n"

        title = f"**{nice_name}"
        if country:
            title += f", {country}"
        title += f" — {temp_str}°C {emoji}**"

        mid = (
            f"\n{desc}, anginnya sekitar {wind_str} km/jam."
            "\nEnak buat keluar, tapi tetep jaga kondisi yaa~"
        )

        detail = (
            "\n\n**Detail:**"
            f"\n- Suhu: **{temp_str}°C**"
            f"\n- Angin: **{wind_str} km/jam**"
            f"\n- Kondisi: **{desc}**"
            f"\n- Zona waktu: {tz}"
            "\n\nSumber: Open-Meteo · https://open-meteo.com"
        )

        return opener + title + mid + detail

    except Exception as e:
        print(f"⚠️ Weather error: {e}")
        return None


# =========================
# Routes & Events
# =========================
@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("send_cmd")
def on_send_cmd(data):
    cmd = data.get("cmd", "").strip()
    if not cmd:
        emit("status", {"ok": False, "error": "Invalid command"})
        socketio.emit("log", {"msg": f"[ERROR] Command invalid!"})
        return
    send_serial(cmd)
    emit("status", {"ok": True, "sent": cmd})
    socketio.emit("log", {"msg": f"Manual Command: {cmd}"})
    if cmd in ("MAJU", "MUNDUR", "KIRI", "KANAN"):
        threading.Timer(0.6, lambda: send_serial("STOP")).start()


@socketio.on("set_mode")
def on_set_mode(data):
    global current_mode
    m = data.get("mode", "").lower()
    if m in ("idle", "chat", "manual"):
        current_mode = m
        socketio.emit("log", {"msg": f"Mode: {m.upper()}"})
        if m == "idle":
            send_serial("STATE:IDLE")
        elif m == "chat":
            send_serial("STATE:MODE_SWITCH")
            socketio.sleep(0.05)
            send_serial("STATE:CHAT")
        else:
            send_serial("STATE:MODE_SWITCH")
            socketio.sleep(0.05)
            send_serial("STATE:MANUAL")
        socketio.emit("mode_changed", {"mode": m})
    else:
        emit("status", {"ok": False, "error": f"Unknown mode '{m}'"})
        socketio.emit("log", {"msg": f"[ERROR] Mode tidak dikenal: {m}"})


def simplify_why_question(q: str) -> str:
    s = normalize_text(q)

    topic = s

    # hapus kata tanya
    s = re.sub(r"^(kenapa|mengapa|why)\s+", "", s)

    CUT = [
        "berwarna biru",
        "berwarna",
        "biru",
        "asin",
        "panas",
        "dingin",
        "tinggi",
        "rendah",
        "jatuh",
        "terjadi",
    ]

    for w in CUT:
        s = re.sub(rf"\b{w}\b", "", s)

    s = re.sub(r"\s+", " ", s).strip()
    return s


@socketio.on("chat_message")
def on_chat_message(data):
    sid = request.sid
    global LAST_QUESTION, IS_PROCESSING, LAST_CHAT_TIME

    IS_PROCESSING = True  # 🔥 TAMBAH INI
    LAST_CHAT_TIME = time.time()  # 🔥 INI KUNCI

    try:

        raw = data.get("msg", "").strip()
        image = data.get("image")

        print("MASUK CHAT:", raw)

        # 🔥 TAMBAH BLOK INI
        if image and isinstance(image, str) and image.startswith("data:image"):
            try:
                print("🔥 MASUK IMAGE MODE")

                print("📦 decode...")
                img = decode_image(image)

                print("📏 resize...")
                img = img.resize((224, 224))
                img = img.convert("RGB")

                print("🧠 generate caption...")
                caption = get_image_caption(img)

                print("✅ caption jadi:", caption)

                reply = f"Aku lihat ini 👀: {caption}"
                print("📤 Kirim reply...", reply)

            except Exception as e:
                print("❌ ERROR:", e)
                reply = "Gambar gagal diproses 😭"

            LAST_CHAT_TIME = time.time()

            socketio.emit("reply", {"msg": reply}, to=sid)

            socketio.sleep(0.1)

            send_serial("STATE:ANSWER")
            socketio.sleep(0.05)
            send_serial("STATE:DONE")

            IS_PROCESSING = False
            return

        low = raw.lower()

        # =========================
        # 1️⃣ CHILD CHAT (PALING ATAS)
        # =========================
        child_reply = None

        SHORT_TRIGGERS = ["hai", "halo", "hi", "helo"]

        if any(k in low for k in SHORT_TRIGGERS):
            child_reply = child_chat(raw)

            if child_reply is not None:
                emit("reply", {"msg": child_reply})
                send_serial("STATE:ANSWER")
                socketio.sleep(0.05)
                send_serial("STATE:DONE")

                IS_PROCESSING = False
                return
        # =========================
        # 2️⃣ SIMPAN MEMORY
        # =========================
        if low.startswith("aku suka "):
            item = raw[8:].strip()
            remember("kesukaan_diva", item)

            reply = f"Hehe 😆 FoxDynamiX inget ya… Diva suka **{item}** 🦊💛"
            socketio.emit("reply", {"msg": reply})
            send_serial("STATE:ANSWER")
            socketio.sleep(0.1)
            send_serial("STATE:DONE")

            IS_PROCESSING = False
            return

        # =========================
        # 3️⃣ PANGGIL MEMORY
        # =========================
        if low in ("aku suka apa", "aku suka apa?"):
            suka = recall("kesukaan_diva")

            if suka:
                reply = f"Kalau nggak salah… Diva suka **{suka}** 😄🦊"
            else:
                reply = "Hmm 🤔 FoxDynamiX belum inget kamu suka apa…"

            socketio.emit("reply", {"msg": reply})
            send_serial("STATE:ANSWER")
            socketio.sleep(0.1)
            send_serial("STATE:DONE")
            return

        # =========================
        # NORMAL QUERY (WIKI / CUACA / DLL)
        # =========================
        low_norm = normalize_text(raw)
        normalized = low_norm
        topic = normalized

        # ml_intent = predict_intent(normalized)

        ans = None

        reply = ""  # 🔥 JAGA-JAGA BIAR PYTHON NGGAK NGAMUK

        # 🔥 CEK DULU: apakah Tora sudah pernah jawab pertanyaan ini?
        saved = recall_answer(normalize_text(normalized))

        if isinstance(saved, dict):  # 🔥 PENTING
            answer_text = saved.get("answer", "")
            source = saved.get("source", "")
            url = saved.get("url", "")

            reply = f"🦊 Dari ingatan FoxDynamiX:\n\n{answer_text}"

            if source:
                reply += f"\n\nSumber: {source}"
            if url:
                reply += f"\n{url}"

            socketio.emit("reply", {"msg": reply})
            send_serial("STATE:ANSWER")
            socketio.sleep(0.1)
            send_serial("STATE:DONE")
            return

        # ---- CUACA
        loc = parse_weather_query(normalized)
        if loc:
            reply = get_weather_answer(loc)
            if not reply:
                reply = f"Div, FoxDynamiX belum nemu data cuaca buat '{loc}' 🦊"

            socketio.emit("reply", {"msg": reply})
            send_serial("STATE:ANSWER")
            socketio.sleep(0.1)
            send_serial("STATE:DONE")
            return

        # ---- CURRENCY ROUTING
        if low_norm.startswith("mata uang"):

            negara = low_norm.replace("mata uang", "").replace("uang", "").strip()
            key = f"mata uang {negara}"

            # 1️⃣ cek memory dulu
            saved = recall_answer(normalize_text(key))
            if saved:
                reply = (
                    "🦊 Dari ingatan FoxDynamiX:\n\n"
                    f"{saved.get('answer','')}\n\n"
                    f"Sumber: {saved.get('source','')}\n"
                    f"{saved.get('url','')}"
                )

                socketio.emit("reply", {"msg": reply})
                send_serial("STATE:ANSWER")
                socketio.sleep(0.05)
                send_serial("STATE:DONE")
                return

            # 2️⃣ cek CURRENCY_MAP (opsional cepat)
            currency_name = CURRENCY_MAP.get(negara)

            if currency_name:
                ans = wiki_summary_by_title(
                    currency_name, "id"
                ) or wiki_summary_by_title(currency_name, "en")

            else:
                # 3️⃣ 🔥 FALLBACK KE WIKIDATA (P38)
                q_country = wd_search_entity(negara, "id") or wd_search_entity(
                    negara, "en"
                )

                if q_country:
                    currency_qids = wd_get_claim_target(q_country, "P38")

                    if currency_qids:
                        currency_qid = currency_qids[-1]  # ambil terbaru
                        currency_label = wd_label(currency_qid, "id") or wd_label(
                            currency_qid, "en"
                        )

                        if currency_label:
                            ans = wiki_summary_by_title(
                                currency_label, "id"
                            ) or wiki_summary_by_title(currency_label, "en")

            if ans:
                remember_answer(
                    key,
                    ans.get("summary", ""),
                    ans.get("source", "Wikipedia"),
                    ans.get("url", ""),
                )

                reply = format_answer_payload(ans, raw.title())
            else:
                reply = (
                    f"FoxDynamiX belum nemu data mata uang untuk {negara.title()} 🦊"
                )

                socketio.emit("reply", {"msg": reply})
                send_serial("STATE:ANSWER")
                socketio.sleep(0.05)
                send_serial("STATE:DONE")
                return

        # ---- KEYWORD MAP
        if not ans and low_norm in KEYWORD_MAP:
            ans = wiki_summary_by_title(KEYWORD_MAP[low_norm], "id")

        # ---- INTENT
        intent, entity = parse_intent(normalized)
        # 🔥 CEK MEMORY INTENT SPESIFIK
        if intent and entity:
            intent_key = f"{intent} {entity}"

            saved_intent = recall_answer(intent_key)
            if saved_intent:
                reply = (
                    "🦊 Dari ingatan FoxDynamiX:\n\n"
                    f"{saved_intent.get('answer','')}\n\n"
                    f"Sumber: {saved_intent.get('source','')}\n"
                    f"{saved_intent.get('url','')}"
                )

                socketio.emit("reply", {"msg": reply})
                send_serial("STATE:ANSWER")
                socketio.sleep(0.05)
                send_serial("STATE:DONE")
                return

        if intent and entity:
            ans = answer_by_intent(intent, entity)

            if ans:
                repeat_count = count_question_repeat(normalized)
                is_same_as_last = normalized == LAST_QUESTION
                LAST_QUESTION = normalized

                remember_answer(
                    f"{intent} {entity}",
                    ans.get("summary", ""),
                    ans.get("source", "Wikidata"),
                    ans.get("url", ""),
                )

                emotion = emotion_prefix(repeat_count)
                dejavu = deja_vu_prefix(is_same_as_last)
                reply = dejavu + emotion + format_answer_payload(ans, raw.title())

                socketio.emit("reply", {"msg": reply})
                send_serial("STATE:ANSWER")
                socketio.sleep(0.05)
                send_serial("STATE:DONE")
                return

            else:
                # 🔥 JANGAN PERNAH fallback web kalau intent jelas
                reply = "FoxDynamiX nggak nemu data intentnya 🦊"
                socketio.emit("reply", {"msg": reply})
                send_serial("STATE:ANSWER")
                socketio.sleep(0.05)
                send_serial("STATE:DONE")
                return

        # ---- KENAPA
        if not ans and raw.lower().startswith("kenapa"):
            ans = smart_wiki_answer(f"mengapa {topic}")

        # ---- GENERAL WIKI
        if not ans:
            ans = smart_wiki_answer(topic)

        repeat_count = count_question_repeat(normalized)
        is_same_as_last = normalized == LAST_QUESTION
        LAST_QUESTION = normalized

        # =========================
        # FINAL REPLY
        # =========================
        if ans:
            remember_answer(
                normalized,
                ans.get("summary", ""),
                ans.get("source", "Web"),
                ans.get("url", ""),
            )

            emotion = emotion_prefix(repeat_count)
            dejavu = deja_vu_prefix(is_same_as_last)
            reply = dejavu + emotion + format_answer_payload(ans, raw.title())
        else:
            reply = "Maaf Div, FoxDynamiX belum nemu jawaban yang pas 🦊"

        socketio.emit("reply", {"msg": reply})
        send_serial("STATE:ANSWER")

        # cari web di belakang layar
        def update_from_web():
            better = smart_web_answer(topic)
            if better:
                better_text = format_answer_payload(better, raw.title())
                socketio.emit("reply", {"msg": "🔄 Update dari web:\n\n" + better_text})

        # threading.Thread(target=update_from_web, daemon=True).start()

        socketio.sleep(0.1)
        send_serial("STATE:DONE")

    finally:
        IS_PROCESSING = False


# =========================
# Main
# =========================
if __name__ == "__main__":
    print("🚀 Server running at http://127.0.0.1:5000")
    socketio.run(app, host="127.0.0.1", port=5000)

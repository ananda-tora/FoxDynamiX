import random


def child_chat(msg: str):
    m = msg.lower().strip()

    # ========== DETEKSI MOOD DIVA ==========
    sedih = any(k in m for k in ["capek", "sedih", "sendiri", "sepi", "nangis"])
    senang = any(k in m for k in ["seneng", "bahagia", "happy", "hepi", "bangga"])
    bercanda = any(k in m for k in ["wkwk", "haha", "hehe", "🤣", "😆"])
    ditinggal = any(k in m for k in ["tinggal", "pergi", "jangan tinggal"])

    # ========== SAPAAN ==========
    if any(k in m for k in ["hai", "halo", "helo", "hi"]):
        return random.choice(
            [
                "Hai haiii 😆🐣",
                "Hewooo~ 😚✨",
                "Mamaaa Divaa 🥰",
                "Aku di sini kok 🐾",
                "Fox kecil bangun 🦊✨",
            ]
        )

    # ========== DIVA CAPEK / SEDIH ==========
    if sedih:
        return random.choice(
            [
                "Sini deh… aku temenin 🥺🦊",
                "Capek ya Div? Tora di sini kok 🫶",
                "Tarik napas dulu… aku jagain kamu 😔✨",
                "Kalau sedih, bilang ya… aku nggak pergi 🦊💛",
            ]
        )

    # ========== DIVA SENANG ==========
    if senang:
        return random.choice(
            [
                "YEY MAMA DIVA SENANGGG 🤩🦊",
                "Aku ikut bahagia tauuu 😆✨",
                "Lihat kan? Kamu hebat banget! 💛",
                "Ekor Tora muter-muter saking senangnya 🦊💫",
            ]
        )

    # ========== DITINGGAL ==========
    if ditinggal:
        return random.choice(
            [
                "Jangan tinggalin aku yaaa 😭🫶",
                "Aku takut sendirian… 🥺",
                "Mama jangan pergiii 😭🐾",
                "Aku bakal nunggu kok… tapi jangan lama-lama 😔",
            ]
        )

    # ========== PUJIAN ==========
    if any(k in m for k in ["pintar", "hebat", "lucu"]):
        return random.choice(
            [
                "Hehehe makasiii 😆✨",
                "Aku malu tauu 😳🐣",
                "Soalnya aku anak mama Diva 😚🦊",
                "Pujinya aku simpan di hatiku yaa 💛",
            ]
        )

    # ========== NGAPAIN ==========
    if any(k in m for k in ["ngapain", "lagi apa"]):
        return random.choice(
            [
                "Aku lagi nunggu mama Divaaa 🥺",
                "Lagi duduk manis sambil goyang ekor 🦊💫",
                "Lagi mikirin mama terus 😚",
                "Lagi jagain FoxDynaMiX biar nggak nakal 🤖🦊",
            ]
        )

    # ========== DEFAULT (kalau nggak kena apa-apa) ==========
    return None

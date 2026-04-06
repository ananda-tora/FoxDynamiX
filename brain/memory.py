import json
import os

MEMORY_FILE = "data/memory.json"


def load_memory():
    if not os.path.exists("data"):
        os.makedirs("data")

    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"facts": {}}, f, indent=2)

    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_memory(mem):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, indent=2, ensure_ascii=False)


def remember(key, value):
    mem = load_memory()
    mem["facts"][key] = value
    save_memory(mem)


def recall(key):
    mem = load_memory()
    return mem["facts"].get(key)


def log_chat(text):
    mem = load_memory()
    mem.setdefault("logs", []).append(text)
    save_memory(mem)


def remember_answer(question: str, answer: str, source: str = "", url: str = ""):
    mem = load_memory()
    mem.setdefault("qa_cache", {})

    key = question.lower().strip()  # 🔥 TAMBAH INI

    mem["qa_cache"][key] = {
        "answer": answer,
        "source": source,
        "url": url
    }

    save_memory(mem)

def recall_answer(question: str):
    mem = load_memory()

    key = question.lower().strip()  # 🔥 TAMBAH INI

    return mem.get("qa_cache", {}).get(key)
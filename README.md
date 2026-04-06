<<<<<<< HEAD
# FoxDynamiX
AI backend for interactive robotic assistant (ESP32 Integration + Local LLM)
=======
# FoxDynaMiX

FoxDynaMiX adalah sistem AI assistant berbasis web 
yang terintegrasi dengan robot ESP32 dan mampu
menjawab pertanyaan secara kontekstual.

## Fitur Utama
- Chat AI berbasis Wikipedia dan Web Search
- Deteksi intent (cuaca, presiden, ibu kota, mata uang)
- Sistem emosi & repeat memory
- Mode interaksi: Idle / Chat / Manual
- Integrasi Serial dengan ESP32
- Sinkronisasi state robot (THINK, ANSWER, DONE)

## Arsitektur Sistem
Frontend:
- HTML, CSS, JavaScript
- Socket.IO client

Backend:
- Python Flask
- Flask-SocketIO
- Wikipedia REST API
- DuckDuckGo Search
- Open-Meteo Weather API
- Wikidata

Hardware (opsional):
- ESP32
- Motor Driver
- Sensor Ultrasonik
- LED indikator

## Alur Kerja Sistem
1. User mengirim pesan dari frontend
2. Backend melakukan normalisasi bahasa manusia
3. Sistem mendeteksi intent pertanyaan
4. Data diambil dari:
   - Wikipedia
   - Web search
   - API cuaca
5. Jawaban diringkas otomatis
6. State dikirim ke ESP32
7. Hasil ditampilkan di web

## Konsep yang Digunakan
- Natural Language Normalization
- Intent-based Routing
- Knowledge Fallback System
- Memory-based Emotion Response
- Real-time WebSocket Communication

## Catatan
Project ini dikembangkan sebagai media pembelajaran
AI system design, bukan menggunakan API ChatGPT,
melainkan sistem pencarian informasi mandiri.

>>>>>>> 1c5e0f4 (foxdynamix full project)

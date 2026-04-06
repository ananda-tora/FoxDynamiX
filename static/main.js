// // static/main.js

// document.addEventListener("DOMContentLoaded", () => {
//     const socket = io();

//     // Elemen-elemen utama
//     const chatLog = document.getElementById("log");
//     const chatInput = document.getElementById("chat-input");
//     const chatSendBtn = document.getElementById("chat-send");
//     const loadingSpinner = document.getElementById("loading-spinner");

//     // Mengaktifkan / menonaktifkan area chat
//     function setChatEnabled(enabled) {
//         if (enabled) {
//             chatInput.removeAttribute("disabled");
//             chatSendBtn.classList.remove("disabled");
//             chatSendBtn.removeAttribute("disabled");
//             chatInput.focus();
//         } else {
//             chatInput.setAttribute("disabled", "");
//             chatSendBtn.classList.add("disabled");
//             chatSendBtn.setAttribute("disabled", "");
//         }
//     }

//     // Tambahkan pesan ke log (dengan kelas 'user-msg' atau 'bot-msg')
//     function addMessage(text, from) {
//         const div = document.createElement("div");
//         div.className = from === "user" ? "user-msg" : "bot-msg";
//         div.textContent = text;
//         chatLog.appendChild(div);
//         // Scroll otomatis ke bawah
//         chatLog.scrollTop = chatLog.scrollHeight;
//     }

//     // Saat klik tombol Kirim
//     chatSendBtn.addEventListener("click", () => {
//         if (chatSendBtn.classList.contains("disabled")) return;
//         const msg = chatInput.value.trim();
//         if (!msg) return;

//         // 1) Tampilkan pesan user di UI
//         addMessage(msg, "user");

//         // 2) Kirim ke server
//         socket.emit("chat_message", { msg: msg });

//         // 3) Matikan input + tombol, tampilkan spinner
//         setChatEnabled(false);
//         loadingSpinner.classList.remove("hidden");

//         // 4) Kosongkan input
//         chatInput.value = "";
//     });

//     // Selain klik tombol, jika user tekan Enter
//     chatInput.addEventListener("keypress", (e) => {
//         if (e.key === "Enter") {
//             chatSendBtn.click();
//             e.preventDefault();
//         }
//     });

//     // Saat server mengirim balasan
//     socket.on("reply", (data) => {
//         const replyText = data.msg || "";

//         // 1) Hilangkan spinner
//         loadingSpinner.classList.add("hidden");

//         // 2) Tampilkan pesan Tora di UI
//         addMessage(replyText, "bot");

//         // 3) Aktifkan kembali chat (jika masih di Chat Mode)
//         setChatEnabled(true);
//     });

//     // (Opsional) Sinkronisasi mode: idle/chat/manual
//     socket.on("mode_changed", (data) => {
//         const mode = data.mode;
//         if (mode !== "chat") {
//             setChatEnabled(false);
//         } else {
//             setChatEnabled(true);
//         }
//     });

//     // Inisialisasi awal: matikan chat (karena default mode=idle)
//     setChatEnabled(false);
// });

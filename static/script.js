let sessionId = null;

const uploadForm = document.getElementById("uploadForm");
const uploadStatus = document.getElementById("uploadStatus");
const chatSection = document.getElementById("chatSection");
const chatBox = document.getElementById("chatBox");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const resetBtn = document.getElementById("resetBtn");

uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(uploadForm);
  uploadStatus.innerText = "Uploading...";
  try {
    const res = await fetch("/upload_pdf", { method: "POST", body: fd });
    const data = await res.json();
    if (data.success) {
      sessionId = data.session_id;
      uploadStatus.innerText = data.message;
      chatSection.classList.remove("hidden");
      uploadForm.querySelector("input[type=file]").disabled = true;
    } else {
      uploadStatus.innerText = data.message || "Upload failed";
    }
  } catch (err) {
    uploadStatus.innerText = "Upload error";
  }
});

async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || !sessionId) return;
  appendMessage("user", text);
  messageInput.value = "";
  appendMessage("bot", "Typing...", { typing: true });

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: text })
    });
    const data = await res.json();
    removeTyping();
    if (data.success) {
      appendMessage("bot", data.answer);
    } else {
      appendMessage("bot", data.error || "Error: no response");
    }
  } catch (err) {
    removeTyping();
    appendMessage("bot", "Network error");
  }
}

sendBtn.addEventListener("click", sendMessage);
messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});

resetBtn.addEventListener("click", async () => {
  if (!sessionId) return;
  await fetch("/reset_session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId })
  });
  sessionId = null;
  chatBox.innerHTML = "";
  chatSection.classList.add("hidden");
  uploadForm.querySelector("input[type=file]").disabled = false;
  uploadStatus.innerText = "Session reset. Upload a new PDF.";
});

function appendMessage(who, text, opts = {}) {
  const p = document.createElement("div");
  p.className = "msg " + (who === "user" ? "user" : "bot");
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  p.appendChild(bubble);
  if (opts.typing) bubble.classList.add("typing");
  chatBox.appendChild(p);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function removeTyping() {
  const typing = chatBox.querySelector(".typing");
  if (typing) {
    const parent = typing.parentElement;
    parent && parent.remove();
  }
}

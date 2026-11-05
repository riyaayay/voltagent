/**
 * VoltAgent frontend — AiVoice-inspired redesign.
 *
 * All core pipeline logic is unchanged:
 *   - SpeechRecognition  : mic → text
 *   - speechSynthesis    : text → spoken audio
 *   - /query API call    : text → verified answer
 *   - /ready polling     : backend warmup gate
 *
 * Browser note: Chrome/Edge required for SpeechRecognition (hi-IN included).
 * Safari/Firefox have partial/no support. For field deployment use a native
 * mobile SDK rather than relying on an arbitrary mobile browser.
 */

const API_BASE = "";

// --- DOM refs ---
const micBtn         = document.getElementById("mic-btn");
const micIcon        = document.getElementById("mic-icon");
const waveform       = document.getElementById("waveform");
const statusEl       = document.getElementById("status");
const panelHint      = document.getElementById("panel-hint");
const userTextEl     = document.getElementById("user-text");
const answerBlock    = document.getElementById("answer-block");
const answerTextEl   = document.getElementById("answer-text");
const confidenceBadge = document.getElementById("confidence-badge");
const citationsEl    = document.getElementById("citations");
const rawSourceEl    = document.getElementById("raw-source");

// Language toggle buttons
const langBtns = document.querySelectorAll(".lang-btn");
let activeLang = "en-IN";

langBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    langBtns.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    activeLang = btn.dataset.lang;
  });
});

// --- Speech ---
const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let isListening = false;

function setStatus(text, active = false) {
  statusEl.textContent = text;
  statusEl.classList.toggle("status--active", active);
}

function langToApiCode(bcp47) {
  return bcp47.split("-")[0]; // "hi-IN" → "hi", "en-IN" → "en"
}

function initRecognition() {
  if (!SpeechRecognitionImpl) {
    setStatus("Speech recognition isn't supported here. Try Chrome or Edge.");
    micBtn.disabled = true;
    return null;
  }

  const r = new SpeechRecognitionImpl();
  r.continuous      = false;
  r.interimResults  = false;
  r.maxAlternatives = 1;

  r.onresult = (event) => handleTranscript(event.results[0][0].transcript);
  r.onerror  = (event) => {
    setStatus(`Mic error: ${event.error}. Tap to try again.`);
    stopListeningUI();
  };
  r.onend = () => stopListeningUI();

  return r;
}

function startListeningUI() {
  isListening = true;
  micBtn.setAttribute("aria-pressed", "true");
  setStatus("Listening — speak your question…", true);
  // Hide hint while listening
  if (panelHint) panelHint.hidden = true;
}

function stopListeningUI() {
  isListening = false;
  micBtn.setAttribute("aria-pressed", "false");
}

micBtn.addEventListener("click", () => {
  if (!recognition) {
    recognition = initRecognition();
    if (!recognition) return;
  }
  if (isListening) {
    recognition.stop();
    return;
  }
  recognition.lang = activeLang;
  recognition.start();
  startListeningUI();
});

// --- Query pipeline ---
async function handleTranscript(transcript) {
  userTextEl.hidden   = false;
  userTextEl.textContent = transcript;
  answerBlock.hidden  = true;
  setStatus("Thinking…", true);

  try {
    const response = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: transcript, lang: langToApiCode(activeLang) }),
    });

    if (!response.ok) throw new Error(`Server returned ${response.status}`);

    const result = await response.json();
    renderAnswer(result);
    speak(result.answer, result.language);
    setStatus(result.cache_hit ? "Answered (cached)." : "Answered.");
  } catch (err) {
    setStatus(`Could not reach VoltAgent: ${err.message}`);
  }
}

function renderAnswer(result) {
  answerBlock.hidden = false;
  answerTextEl.textContent = result.answer;

  // Badge
  const verified = result.verified;
  confidenceBadge.textContent = verified
    ? `✓ Verified · ${(result.confidence * 100).toFixed(0)}% confidence`
    : `⚠ Low confidence · showing source`;
  confidenceBadge.className = "badge " + (verified ? "badge--verified" : "badge--fallback");

  // Citations
  citationsEl.innerHTML = "";
  if (result.citations && result.citations.length > 0) {
    const list = document.createElement("ul");
    result.citations.forEach((c) => {
      const li = document.createElement("li");
      li.textContent = `${c.doc_title}, p. ${c.page_number}`;
      list.appendChild(li);
    });
    citationsEl.appendChild(list);
  }

  // Raw fallback source
  if (result.fallback && result.raw_source) {
    rawSourceEl.hidden = false;
    rawSourceEl.textContent =
      `${result.raw_source.doc_title} (p. ${result.raw_source.page_number}):\n${result.raw_source.text}`;
  } else {
    rawSourceEl.hidden = true;
    rawSourceEl.textContent = "";
  }
}

// --- TTS ---
function speak(text, language) {
  if (!window.speechSynthesis) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = language === "hi" ? "hi-IN" : "en-IN";
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

// --- Readiness polling ---
async function checkReadiness() {
  setStatus("Connecting to VoltAgent backend…");
  micBtn.disabled = true;

  while (true) {
    try {
      const resp = await fetch(`${API_BASE}/ready`);
      if (resp.ok) {
        const data = await resp.json();
        if (data.ready) {
          setStatus("Ready — tap the mic to ask your question.");
          micBtn.disabled = false;
          return;
        } else {
          setStatus(`Backend initializing (${data.status})…`);
        }
      } else {
        setStatus("Warming up embedder and index…");
      }
    } catch (e) {
      setStatus("Waiting for backend to start…");
    }
    await new Promise((r) => setTimeout(r, 1200));
  }
}

window.addEventListener("DOMContentLoaded", checkReadiness);

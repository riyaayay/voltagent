/**
 * VoltAgent frontend glue.
 *
 * Two Web Speech API surfaces, used deliberately separately:
 *   - SpeechRecognition   : mic -> text (technician's question)
 *   - speechSynthesis     : text -> spoken audio (agent's answer)
 *
 * Browser support caveat (called out here on purpose, not hidden): Chrome
 * and Edge have solid SpeechRecognition support including hi-IN. Safari and
 * Firefox support is partial/absent as of this writing. For a field
 * deployment, ship this inside a Chrome-based wrapper (or a native app using
 * a proper STT SDK) rather than assuming an arbitrary mobile browser works.
 */

const API_BASE = "http://localhost:8000";

const micBtn = document.getElementById("mic-btn");
const micLabel = document.getElementById("mic-label");
const langSelect = document.getElementById("lang-select");
const statusEl = document.getElementById("status");
const userTextEl = document.getElementById("user-text");
const answerBlock = document.getElementById("answer-block");
const answerTextEl = document.getElementById("answer-text");
const confidenceBadge = document.getElementById("confidence-badge");
const citationsEl = document.getElementById("citations");
const rawSourceEl = document.getElementById("raw-source");

const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;

let recognition = null;
let isListening = false;

function setStatus(text) {
  statusEl.textContent = text;
}

function langToApiCode(bcp47) {
  // "hi-IN" -> "hi", "en-IN" -> "en"
  return bcp47.split("-")[0];
}

function initRecognition() {
  if (!SpeechRecognitionImpl) {
    setStatus(
      "Speech recognition isn't supported in this browser. Try Chrome or Edge."
    );
    micBtn.disabled = true;
    return null;
  }
  const recognizer = new SpeechRecognitionImpl();
  recognizer.continuous = false;
  recognizer.interimResults = false;
  recognizer.maxAlternatives = 1;

  recognizer.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    handleTranscript(transcript);
  };

  recognizer.onerror = (event) => {
    setStatus(`Mic error: ${event.error}. Tap to try again.`);
    stopListeningUI();
  };

  recognizer.onend = () => {
    stopListeningUI();
  };

  return recognizer;
}

function startListeningUI() {
  isListening = true;
  micBtn.setAttribute("aria-pressed", "true");
  micLabel.textContent = "Listening…";
  setStatus("Listening — ask your question.");
}

function stopListeningUI() {
  isListening = false;
  micBtn.setAttribute("aria-pressed", "false");
  micLabel.textContent = "Tap to ask";
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
  recognition.lang = langSelect.value;
  recognition.start();
  startListeningUI();
});

async function handleTranscript(transcript) {
  userTextEl.hidden = false;
  userTextEl.textContent = transcript;
  answerBlock.hidden = true;
  setStatus("Thinking…");

  try {
    const response = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: transcript }),
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    const result = await response.json();
    renderAnswer(result);
    speak(result.answer, result.language);
    setStatus(result.cache_hit ? "Answered (cached)." : "Answered.");
  } catch (err) {
    setStatus(`Something went wrong reaching VoltAgent: ${err.message}`);
  }
}

function renderAnswer(result) {
  answerBlock.hidden = false;
  answerTextEl.textContent = result.answer;

  confidenceBadge.textContent = result.verified
    ? `Verified · confidence ${(result.confidence * 100).toFixed(0)}%`
    : `Low confidence · showing source instead`;
  confidenceBadge.className = "badge " + (result.verified ? "badge--verified" : "badge--fallback");

  citationsEl.innerHTML = "";
  if (result.citations && result.citations.length > 0) {
    const list = document.createElement("ul");
    result.citations.forEach((c) => {
      const li = document.createElement("li");
      li.textContent = `${c.doc_title}, page ${c.page_number}`;
      list.appendChild(li);
    });
    citationsEl.appendChild(list);
  }

  if (result.fallback && result.raw_source) {
    rawSourceEl.hidden = false;
    rawSourceEl.textContent = `${result.raw_source.doc_title} (page ${result.raw_source.page_number}): ${result.raw_source.text}`;
  } else {
    rawSourceEl.hidden = true;
    rawSourceEl.textContent = "";
  }
}

function speak(text, language) {
  if (!window.speechSynthesis) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = language === "hi" ? "hi-IN" : "en-IN";
  window.speechSynthesis.cancel(); // don't stack utterances
  window.speechSynthesis.speak(utterance);
}

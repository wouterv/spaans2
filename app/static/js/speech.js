// Dunne wrapper rond de Web Speech API (TTS + spraakherkenning).
// Werkt het best in Chrome (Android/desktop); listen() vereist HTTPS.

export const LANG = {es: 'es-ES', nl: 'nl-NL'};

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let activeRecognition = null;

export function canListen() {
  return Boolean(SpeechRecognition);
}

export function speak(text, lang) {
  return new Promise((resolve) => {
    if (!window.speechSynthesis) { resolve(); return; }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    const voice = speechSynthesis
      .getVoices()
      .find((v) => v.lang.replace('_', '-').startsWith(lang.slice(0, 2)));
    if (voice) utterance.voice = voice;
    utterance.onend = resolve;
    utterance.onerror = resolve;
    speechSynthesis.speak(utterance);
  });
}

export function listen(lang, {timeout = 8000} = {}) {
  return new Promise((resolve) => {
    if (!SpeechRecognition) { resolve(null); return; }
    stopListening();
    const recognition = new SpeechRecognition();
    activeRecognition = recognition;
    recognition.lang = lang;
    recognition.interimResults = false;
    recognition.maxAlternatives = 3;

    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (activeRecognition === recognition) activeRecognition = null;
      resolve(value);
    };
    const timer = setTimeout(() => {
      recognition.abort();
      finish(null);
    }, timeout);

    recognition.onresult = (event) => {
      const alternatives = [...event.results[0]].map((r) => r.transcript);
      finish(alternatives);
    };
    recognition.onerror = () => finish(null);
    recognition.onend = () => finish(null);
    recognition.start();
  });
}

export function stopListening() {
  if (activeRecognition) {
    activeRecognition.abort();
    activeRecognition = null;
  }
}

export function stopAll() {
  window.speechSynthesis?.cancel();
  stopListening();
}

// Stemmen laden asynchroon; dit triggert het laden alvast.
window.speechSynthesis?.getVoices();

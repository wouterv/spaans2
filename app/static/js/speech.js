// Dunne wrapper rond de Web Speech API (TTS + spraakherkenning).
// Werkt het best in Chrome (Android/desktop); listen() vereist HTTPS.

import {pickVoice} from './voices.js';

export const LANG = {es: 'es-ES', nl: 'nl-NL'};

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let activeRecognition = null;

export function canListen() {
  return Boolean(SpeechRecognition);
}

// Stemmen laden asynchroon (zeker op Android); wacht er één keer netjes op.
let voicesPromise = null;

export function loadVoices() {
  if (!window.speechSynthesis) return Promise.resolve([]);
  const now = speechSynthesis.getVoices();
  if (now.length) return Promise.resolve(now);
  if (!voicesPromise) {
    voicesPromise = new Promise((resolve) => {
      const done = () => resolve(speechSynthesis.getVoices());
      speechSynthesis.addEventListener('voiceschanged', done, {once: true});
      setTimeout(done, 1500);
    });
  }
  return voicesPromise;
}

export function preferredVoiceName(lang) {
  return localStorage.getItem(`spaans-stem-${lang.slice(0, 2)}`);
}

export function setPreferredVoiceName(lang, name) {
  localStorage.setItem(`spaans-stem-${lang.slice(0, 2)}`, name);
}

export async function speak(text, lang, {voiceName = null} = {}) {
  if (!window.speechSynthesis) return;
  const voices = await loadVoices();
  const voice = pickVoice(voices, lang, voiceName ?? preferredVoiceName(lang));
  await new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
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

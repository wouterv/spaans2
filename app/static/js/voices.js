// Stemselectie voor TTS: pure logica, los van de browser zodat het testbaar is.
// Een stem spreekt alleen zijn eigen taal goed — kies dus nooit een stem
// van een andere taal, ook niet als voorkeur of fallback.

const normalize = (lang) => lang.replace('_', '-').toLowerCase();

export function pickVoice(voices, lang, preferredName = null) {
  const full = normalize(lang);
  const base = full.slice(0, 2);
  const candidates = voices.filter((v) => normalize(v.lang).startsWith(base));
  if (!candidates.length) return null;

  const preferred = candidates.find((v) => v.name === preferredName);
  if (preferred) return preferred;

  const score = (v) =>
    (normalize(v.lang) === full ? 4 : 0) +
    (/google/i.test(v.name) ? 2 : 0) +
    (v.localService ? 1 : 0);
  return [...candidates].sort((a, b) => score(b) - score(a))[0];
}

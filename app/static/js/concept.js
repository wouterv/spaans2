// Werk-in-uitvoering (concepten) bewaren in localStorage: overleeft een
// refresh of later terugkomen. Storage is injecteerbaar voor tests.

export function saveConcept(key, data, storage = globalThis.localStorage) {
  storage.setItem(key, JSON.stringify({at: Date.now(), data}));
}

export function loadConcept(key, storage = globalThis.localStorage) {
  const raw = storage.getItem(key);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || !('data' in parsed)) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function clearConcept(key, storage = globalThis.localStorage) {
  storage.removeItem(key);
}

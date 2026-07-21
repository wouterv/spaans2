// Opgeslagen woorden: ';' scheidt synoniemen, '/' scheidt geslachtsvormen
// binnen één synoniem (el primo/la prima).

// Voorleesbare vorm: alleen het eerste synoniem, geslachtsvormen met een pauze
// ("el primo/la prima" → "el primo, la prima")
export const speakable = (text) => text.split(';')[0].trim().replace(/\s*\/\s*/g, ', ');

// Leesbare prompt: synoniemen met een puntje in plaats van ';'
export const readable = (text) => text.replace(/\s*;\s*/g, ' · ');

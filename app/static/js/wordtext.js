// Opgeslagen woorden: ';' scheidt synoniemen, '/' scheidt geslachtsvormen
// binnen één synoniem (el primo/la prima).

// Voorleesbare vorm: alleen het eerste synoniem, geslachtsvormen met een pauze
// ("el primo/la prima" → "el primo, la prima")
export const speakable = (text) => text.split(';')[0].trim().replace(/\s*\/\s*/g, ', ');

// Leesbare prompt: synoniemen met een puntje in plaats van ';'
export const readable = (text) => text.replace(/\s*;\s*/g, ' · ');

const formsOf = (synonym) => synonym.split('/').map((f) => f.trim()).filter(Boolean);

// Hoogste aantal geslachtsvormen in één synoniem (1 als er geen paar is)
export const formCount = (text) =>
  Math.max(...text.split(';').map((s) => formsOf(s).length), 1);

// Kies per synoniem de i-de geslachtsvorm; synoniemen zonder paar blijven heel.
// Met i == null blijft de tekst ongewijzigd.
export const pickForm = (text, i) => {
  if (i == null) return text;
  return text.split(';')
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => {
      const forms = formsOf(s);
      return forms.length > 1 ? forms[Math.min(i, forms.length - 1)] : s;
    })
    .join('; ');
};

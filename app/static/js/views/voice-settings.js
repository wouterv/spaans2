import {el, setChildren} from '../api.js';
import {LANG, loadVoices, preferredVoiceName, setPreferredVoiceName, speak} from '../speech.js';
import {pickVoice} from '../voices.js';

const SAMPLES = {
  nl: 'Het juiste antwoord is: de auto.',
  es: 'El coche está en la calle.',
};

export async function renderVoiceSettings(view) {
  const voices = await loadVoices();

  function languageCard(base, title, lang) {
    const options = voices.filter((v) =>
      v.lang.replace('_', '-').toLowerCase().startsWith(base));
    const active = pickVoice(voices, lang, preferredVoiceName(lang));

    if (!options.length) {
      return el('div', {class: 'card'},
        el('h2', {style: 'margin-top:0'}, title),
        el('p', {class: 'muted'},
          `Geen ${title.toLowerCase()}e stem gevonden op dit apparaat. `
          + 'Installeer er een via de systeeminstellingen (tekst-naar-spraak).'),
      );
    }

    const rows = options.map((voice) => {
      const radio = el('input', {
        type: 'radio', name: `stem-${base}`, id: `stem-${base}-${voice.name}`,
      });
      radio.checked = active?.name === voice.name;
      radio.addEventListener('change', () => {
        setPreferredVoiceName(lang, voice.name);
        speak(SAMPLES[base], lang);
      });
      return el('li', {},
        radio,
        el('label', {
          for: `stem-${base}-${voice.name}`,
          style: 'flex:1; margin:0; font-size:1rem; color:var(--ink)',
        }, `${voice.name} `, el('span', {class: 'muted'}, `(${voice.lang})`)),
        el('button', {
          class: 'icon-btn', title: 'Test deze stem', 'aria-label': `Test ${voice.name}`,
          onclick: () => speak(SAMPLES[base], lang, {voiceName: voice.name}),
        }, '🔊'),
      );
    });

    return el('div', {class: 'card'},
      el('h2', {style: 'margin-top:0'}, title),
      el('ul', {class: 'list', style: 'margin-top:0.5rem'}, ...rows),
    );
  }

  setChildren(view,
    el('p', {}, el('a', {href: '#/', class: 'muted'}, '← Hoofdstukken')),
    el('h1', {}, 'Stemmen'),
    el('p', {class: 'muted'},
      'Kies per taal welke stem voorleest. Je keuze wordt op dit apparaat bewaard, '
      + 'dus stel dit op je telefoon en computer apart in.'),
    languageCard('nl', 'Nederlands', LANG.nl),
    languageCard('es', 'Spaans', LANG.es),
  );
}

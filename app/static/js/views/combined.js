import {api, el, setChildren} from '../api.js';

const SELECTIE_KEY = 'spaans-samen-selectie';

function loadSelectie(chapters) {
  try {
    const bewaard = JSON.parse(localStorage.getItem(SELECTIE_KEY));
    if (Array.isArray(bewaard)) {
      const bestaand = bewaard.filter((id) => chapters.some((c) => c.id === id));
      if (bestaand.length) return new Set(bestaand);
    }
  } catch { /* kapotte opslag telt als geen selectie */ }
  return new Set(chapters.map((c) => c.id));
}

export async function renderCombined(view) {
  const chapters = await api('/api/chapters');
  if (!chapters.length) { location.hash = '#/'; return; }
  const selectie = loadSelectie(chapters);
  const persist = () =>
    localStorage.setItem(SELECTIE_KEY, JSON.stringify([...selectie]));

  let direction = 'es_nl';
  const cards = el('div', {});

  function ids() {
    // In hoofdstuk-volgorde, niet in aanvink-volgorde
    return chapters.filter((c) => selectie.has(c.id)).map((c) => c.id);
  }

  function telling(veld) {
    return chapters
      .filter((c) => selectie.has(c.id))
      .reduce((som, c) => som + c[veld], 0);
  }

  const alleBox = el('input', {type: 'checkbox', 'aria-label': 'Alle hoofdstukken'});
  const boxes = new Map();

  function syncAlleBox() {
    alleBox.checked = selectie.size === chapters.length;
  }

  alleBox.addEventListener('change', () => {
    selectie.clear();
    if (alleBox.checked) for (const c of chapters) selectie.add(c.id);
    for (const [id, box] of boxes) box.checked = selectie.has(id);
    persist();
    renderCards();
  });

  const kiezer = el('div', {class: 'card'},
    el('label', {style: 'display:flex; gap:0.5rem; align-items:center; font-weight:600'},
      alleBox, 'Alles'),
    ...chapters.map((chapter) => {
      const box = el('input', {type: 'checkbox', 'aria-label': chapter.name});
      box.checked = selectie.has(chapter.id);
      boxes.set(chapter.id, box);
      box.addEventListener('change', () => {
        if (box.checked) selectie.add(chapter.id);
        else selectie.delete(chapter.id);
        persist();
        syncAlleBox();
        renderCards();
      });
      return el('label', {style: 'display:flex; gap:0.5rem; align-items:center; margin-top:0.4rem'},
        box,
        el('span', {style: 'flex:1'}, chapter.name),
        el('span', {class: 'counts', style: 'color:var(--muted); font-size:0.8rem; white-space:nowrap'},
          `${chapter.word_count} w · ${chapter.verb_count} ww · ${chapter.exercise_count} oef`),
      );
    }),
  );
  syncAlleBox();

  function startKnop(label, maakHash, aantal) {
    const leeg = !ids().length || !aantal;
    return el('button', {
      class: 'btn btn-big',
      disabled: leeg ? '' : null,
      onclick: () => { if (!leeg) location.hash = maakHash(ids().join(',')); },
    }, label);
  }

  function renderCards() {
    const dirButtons = {};
    const toggleDirection = el('div', {class: 'row', role: 'group', 'aria-label': 'Richting'},
      ...[['es_nl', 'Spaans → Nederlands'], ['nl_es', 'Nederlands → Spaans']]
        .map(([value, label]) => {
          const btn = el('button', {
            class: value === direction ? 'btn-primary' : '',
            onclick: () => {
              direction = value;
              for (const [v, b] of Object.entries(dirButtons)) {
                b.className = v === direction ? 'btn-primary' : '';
              }
            },
          }, label);
          dirButtons[value] = btn;
          return btn;
        }));

    setChildren(cards,
      ids().length ? null : el('p', {class: 'muted'}, 'Selecteer minstens één hoofdstuk om te oefenen.'),
      el('div', {class: 'card'},
        el('h2', {}, `Woorden (${telling('word_count')})`),
        toggleDirection,
        el('div', {class: 'row', style: 'margin-top:0.75rem'},
          startKnop('⌨️ Typen', (ids) => `#/oefen/${ids}/woorden/${direction}/typen`, telling('word_count')),
          startKnop('🎙️ Spraak', (ids) => `#/oefen/${ids}/woorden/${direction}/spraak`, telling('word_count')),
        ),
      ),
      el('div', {class: 'card'},
        el('h2', {}, `Werkwoorden (${telling('verb_count')})`),
        el('div', {class: 'row'},
          startKnop('⌨️ Typen', (ids) => `#/oefen/${ids}/werkwoorden/typen`, telling('verb_count')),
          startKnop('🎙️ Spraak', (ids) => `#/oefen/${ids}/werkwoorden/spraak`, telling('verb_count')),
        ),
      ),
      el('div', {class: 'card'},
        el('h2', {}, `Oefeningen (${telling('exercise_count')})`),
        el('div', {class: 'row'},
          startKnop('⌨️ Oefenen', (ids) => `#/oefen/${ids}/oefeningen`, telling('exercise_count')),
        ),
      ),
      el('div', {class: 'card'},
        el('h2', {}, 'Gesprek'),
        el('p', {class: 'muted'}, 'Conversatie over de lesstof van de gekozen hoofdstukken.'),
        el('div', {class: 'row'},
          startKnop('💬 Gesprek starten', (ids) => `#/gesprek/${ids}`,
            telling('word_count') + telling('verb_count') + telling('grammar_count') + telling('example_count')),
        ),
      ),
    );
  }

  renderCards();
  setChildren(view,
    el('p', {}, el('a', {href: '#/', class: 'muted'}, '← Hoofdstukken')),
    el('h1', {}, 'Samen oefenen'),
    el('div', {class: 'eyebrow'}, 'Hoofdstukken'),
    kiezer,
    el('div', {class: 'eyebrow'}, 'Oefenen'),
    cards,
  );
}

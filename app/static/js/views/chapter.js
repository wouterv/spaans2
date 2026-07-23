import {api, el, setChildren} from '../api.js';

export async function renderChapterHub(view, chapterId) {
  const chapters = await api('/api/chapters');
  const chapter = chapters.find((c) => c.id === chapterId);
  if (!chapter) {
    location.hash = '#/';
    return;
  }

  let direction = 'es_nl';
  const dirButtons = {};
  const toggleDirection = el(
    'div',
    {class: 'row', role: 'group', 'aria-label': 'Richting'},
    ...[
      ['es_nl', 'Spaans → Nederlands'],
      ['nl_es', 'Nederlands → Spaans'],
    ].map(([value, label]) => {
      const btn = el(
        'button',
        {
          class: value === direction ? 'btn-primary' : '',
          onclick: () => {
            direction = value;
            for (const [v, b] of Object.entries(dirButtons)) {
              b.className = v === direction ? 'btn-primary' : '';
            }
          },
        },
        label,
      );
      dirButtons[value] = btn;
      return btn;
    }),
  );

  const generateStatus = el('p', {class: 'muted', style: 'margin-top:0.5rem'});
  const generateButton = el('button', {
    onclick: async () => {
      generateButton.disabled = true;
      generateStatus.textContent = 'Bezig met genereren… dit kan een minuut duren.';
      try {
        const {created} = await api('/api/exercises/generate', {
          method: 'POST',
          body: {chapter_id: chapterId},
        });
        generateStatus.textContent = `${created} oefeningen toegevoegd.`;
        await renderChapterHub(view, chapterId);
      } catch (err) {
        generateButton.disabled = false;
        generateStatus.textContent = `Genereren mislukte: ${err.message}`;
      }
    },
  }, '✨ Genereer oefeningen');

  setChildren(view, 
    el('p', {}, el('a', {href: '#/', class: 'muted'}, '← Hoofdstukken')),
    el('h1', {}, chapter.name),

    el('div', {class: 'eyebrow'}, 'Invoer'),
    el(
      'ul',
      {class: 'list'},
      el('li', {},
        el('a', {class: 'grow', href: `#/h/${chapterId}/woorden`}, 'Woorden'),
        el('span', {class: 'counts'}, String(chapter.word_count))),
      el('li', {},
        el('a', {class: 'grow', href: `#/h/${chapterId}/werkwoorden`}, 'Werkwoorden'),
        el('span', {class: 'counts'}, String(chapter.verb_count))),
      el('li', {},
        el('a', {class: 'grow', href: `#/h/${chapterId}/grammatica`}, 'Grammatica'),
        el('span', {class: 'counts'}, String(chapter.grammar_count))),
    ),

    el('div', {class: 'eyebrow'}, 'Oefenen'),
    el(
      'div',
      {class: 'card'},
      el('h2', {}, 'Woorden'),
      toggleDirection,
      el(
        'div',
        {class: 'row', style: 'margin-top:0.75rem'},
        el('a', {
          class: 'btn btn-big',
          href: '#',
          onclick: (e) => {
            e.preventDefault();
            location.hash = `#/h/${chapterId}/oefen/woorden/${direction}/typen`;
          },
        }, '⌨️ Typen'),
        el('a', {
          class: 'btn btn-big',
          href: '#',
          onclick: (e) => {
            e.preventDefault();
            location.hash = `#/h/${chapterId}/oefen/woorden/${direction}/spraak`;
          },
        }, '🎙️ Spraak'),
      ),
    ),
    el(
      'div',
      {class: 'card'},
      el('h2', {}, 'Werkwoorden'),
      el('p', {class: 'muted'}, 'Je hoort het Nederlandse werkwoord en geeft alle vervoegingen.'),
      el(
        'div',
        {class: 'row'},
        el('a', {class: 'btn btn-big', href: `#/h/${chapterId}/oefen/werkwoorden/typen`}, '⌨️ Typen'),
        el('a', {class: 'btn btn-big', href: `#/h/${chapterId}/oefen/werkwoorden/spraak`}, '🎙️ Spraak'),
      ),
    ),
    el(
      'div',
      {class: 'card'},
      el('h2', {}, 'Grammatica'),
      el('div', {class: 'row'},
        el('a', {class: 'btn btn-big', href: `#/h/${chapterId}/lezen`}, '📖 Lezen & luisteren'),
        el('a', {class: 'btn btn-big', href: `#/h/${chapterId}/les-uploaden`}, '📷 Les uploaden')),
    ),
    el(
      'div',
      {class: 'card'},
      el('h2', {}, 'Oefeningen'),
      el('p', {class: 'muted'},
        chapter.exercise_count
          ? `${chapter.exercise_count} oefeningen op basis van de lesstof van dit hoofdstuk.`
          : 'Nog geen oefeningen — genereer ze op basis van de grammatica van dit hoofdstuk.'),
      el('div', {class: 'row'},
        chapter.exercise_count
          ? el('a', {class: 'btn btn-big', href: `#/h/${chapterId}/oefen/oefeningen`}, '⌨️ Oefenen')
          : null,
        generateButton,
      ),
      generateStatus,
    ),
  );
}

import {api, el} from '../api.js';

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

  view.replaceChildren(
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
        el('a', {class: 'btn btn-big', href: `#/h/${chapterId}/lezen`}, '📖 Lezen & luisteren')),
    ),
  );
}

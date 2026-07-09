import {api, el} from '../api.js';

export async function renderChapters(view) {
  const chapters = await api('/api/chapters');

  const nameInput = el('input', {
    type: 'text',
    placeholder: 'Nieuw hoofdstuk, bijv. "Lección 3"',
    'aria-label': 'Naam nieuw hoofdstuk',
  });
  const form = el(
    'form',
    {
      class: 'row',
      onsubmit: async (e) => {
        e.preventDefault();
        const name = nameInput.value.trim();
        if (!name) return;
        await api('/api/chapters', {method: 'POST', body: {name}});
        renderChapters(view);
      },
    },
    el('div', {}, nameInput),
    el('button', {class: 'btn-primary fixed', type: 'submit'}, 'Toevoegen'),
  );

  const list = el(
    'ul',
    {class: 'list'},
    ...chapters.map((chapter) =>
      el(
        'li',
        {},
        el(
          'a',
          {class: 'grow', href: `#/h/${chapter.id}`},
          el('strong', {}, chapter.name),
        ),
        el(
          'span',
          {class: 'counts'},
          `${chapter.word_count} w · ${chapter.verb_count} ww · ${chapter.grammar_count} gr`,
        ),
        el('button', {
          class: 'icon-btn',
          title: 'Hernoemen',
          'aria-label': `Hernoem ${chapter.name}`,
          onclick: async () => {
            const name = prompt('Nieuwe naam:', chapter.name);
            if (name?.trim()) {
              await api(`/api/chapters/${chapter.id}`, {
                method: 'PUT',
                body: {name: name.trim()},
              });
              renderChapters(view);
            }
          },
        }, '✏️'),
        el('button', {
          class: 'icon-btn',
          title: 'Verwijderen',
          'aria-label': `Verwijder ${chapter.name}`,
          onclick: async () => {
            if (confirm(`"${chapter.name}" en alle inhoud verwijderen?`)) {
              await api(`/api/chapters/${chapter.id}`, {method: 'DELETE'});
              renderChapters(view);
            }
          },
        }, '🗑️'),
      ),
    ),
  );

  view.replaceChildren(
    el('h1', {}, 'Hoofdstukken'),
    form,
    el('div', {class: 'eyebrow'}, chapters.length ? 'Jouw lessen' : ''),
    chapters.length
      ? list
      : el('p', {class: 'muted'}, 'Nog geen hoofdstukken. Voeg je eerste les toe om te beginnen.'),
  );
  nameInput.focus();
}

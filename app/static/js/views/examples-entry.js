import {api, el, setChildren} from '../api.js';

export async function renderExamplesEntry(view, chapterId) {
  const chapters = await api('/api/chapters');
  const chapter = chapters.find((c) => c.id === chapterId);
  if (!chapter) { location.hash = '#/'; return; }

  const textInput = el('textarea', {
    rows: '3', 'aria-label': 'Opgave',
    placeholder: 'Completa: Yo ___ (ser) de Holanda.',
  });

  const form = el('form', {
    class: 'card',
    onsubmit: async (e) => {
      e.preventDefault();
      const text = textInput.value.trim();
      if (!text) return;
      await api('/api/examples', {
        method: 'POST', body: {chapter_id: chapterId, text},
      });
      textInput.value = '';
      textInput.focus();
      await refreshList();
    },
  },
    el('label', {}, 'Nieuwe voorbeeldoefening'), textInput,
    el('div', {class: 'row', style: 'margin-top:0.5rem'},
      el('span', {class: 'muted', style: 'font-size:0.8rem; align-self:center; flex:1'},
        'Opgaven uit het boek sturen de oefeningen-generator en het gesprek.'),
      el('button', {class: 'btn-primary fixed', type: 'submit'}, 'Toevoegen'),
    ),
  );

  const listWrap = el('div', {});

  async function refreshList() {
    const examples = await api(`/api/examples?chapter_id=${chapterId}`);
    setChildren(listWrap,
      el('div', {class: 'eyebrow'}, `${examples.length} voorbeeldoefeningen`),
      examples.length
        ? el('div', {}, ...examples.map(exampleCard))
        : el('p', {class: 'muted'},
            'Nog geen voorbeeldoefeningen — scan een oefenpagina via "Les uploaden" of voeg er hierboven één toe.'),
    );
  }

  function exampleCard(example) {
    return el('div', {class: 'card'},
      el('div', {style: 'display:flex; align-items:baseline; gap:0.6rem'},
        el('p', {style: 'flex:1; white-space:pre-wrap; margin:0'}, example.text),
        el('button', {
          class: 'icon-btn', title: 'Verwijderen', 'aria-label': 'Verwijder voorbeeld',
          onclick: async () => {
            if (confirm('Dit voorbeeld verwijderen?')) {
              await api(`/api/examples/${example.id}`, {method: 'DELETE'});
              refreshList();
            }
          },
        }, '🗑️'),
      ),
    );
  }

  setChildren(view,
    el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, `← ${chapter.name}`)),
    el('h1', {}, 'Voorbeeldoefeningen'),
    form,
    listWrap,
  );
  await refreshList();
}

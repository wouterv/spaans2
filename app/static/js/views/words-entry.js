import {api, el} from '../api.js';

export async function renderWordsEntry(view, chapterId) {
  const chapters = await api('/api/chapters');
  const chapter = chapters.find((c) => c.id === chapterId);
  if (!chapter) { location.hash = '#/'; return; }

  const spanishInput = el('input', {
    type: 'text', placeholder: 'el coche; el auto', autocapitalize: 'off',
    'aria-label': 'Spaans',
  });
  const dutchInput = el('input', {
    type: 'text', placeholder: 'de auto; de wagen', autocapitalize: 'off',
    'aria-label': 'Nederlands',
  });

  const clearForm = () => {
    spanishInput.value = '';
    dutchInput.value = '';
    spanishInput.focus();
  };

  const form = el(
    'form',
    {
      class: 'card',
      onsubmit: async (e) => {
        e.preventDefault();
        const spanish = spanishInput.value.trim();
        const dutch = dutchInput.value.trim();
        if (!spanish || !dutch) return;
        await api('/api/words', {
          method: 'POST',
          body: {chapter_id: chapterId, spanish, dutch},
        });
        clearForm();
        await refreshList();
      },
      onkeydown: (e) => {
        if (e.key === 'Escape') clearForm();
      },
    },
    el('div', {class: 'row'},
      el('div', {}, el('label', {}, 'Spaans'), spanishInput),
      el('div', {}, el('label', {}, 'Nederlands'), dutchInput),
      el('button', {class: 'btn-primary fixed', type: 'submit'}, 'Opslaan'),
    ),
    el('p', {class: 'muted', style: 'font-size:0.8rem; margin:0.5rem 0 0'},
      'Tab wisselt veld · Enter slaat op · Esc maakt leeg · synoniemen scheiden met ;'),
  );

  const listWrap = el('div', {});

  async function refreshList() {
    const words = await api(`/api/words?chapter_id=${chapterId}`);
    const rows = words.slice().reverse().map((word) => wordRow(word));
    listWrap.replaceChildren(
      el('div', {class: 'eyebrow'}, `${words.length} woorden`),
      words.length
        ? el('table', {class: 'entry'},
            el('thead', {}, el('tr', {},
              el('th', {}, 'Spaans'), el('th', {}, 'Nederlands'), el('th', {}, ''))),
            el('tbody', {}, ...rows))
        : el('p', {class: 'muted'}, 'Nog geen woorden in dit hoofdstuk.'),
    );
  }

  function wordRow(word) {
    const row = el('tr', {},
      el('td', {class: 'es'}, word.spanish),
      el('td', {}, word.dutch),
      el('td', {style: 'white-space:nowrap; text-align:right'},
        el('button', {
          class: 'icon-btn', title: 'Bewerken', 'aria-label': `Bewerk ${word.spanish}`,
          onclick: () => editRow(row, word),
        }, '✏️'),
        el('button', {
          class: 'icon-btn', title: 'Verwijderen', 'aria-label': `Verwijder ${word.spanish}`,
          onclick: async () => {
            await api(`/api/words/${word.id}`, {method: 'DELETE'});
            refreshList();
          },
        }, '🗑️'),
      ),
    );
    return row;
  }

  function editRow(row, word) {
    const esEdit = el('input', {type: 'text', value: word.spanish, 'aria-label': 'Spaans'});
    const nlEdit = el('input', {type: 'text', value: word.dutch, 'aria-label': 'Nederlands'});
    const save = async () => {
      const spanish = esEdit.value.trim();
      const dutch = nlEdit.value.trim();
      if (!spanish || !dutch) return;
      await api(`/api/words/${word.id}`, {method: 'PUT', body: {spanish, dutch}});
      refreshList();
    };
    const onkey = (e) => {
      if (e.key === 'Enter') { e.preventDefault(); save(); }
      if (e.key === 'Escape') refreshList();
    };
    esEdit.addEventListener('keydown', onkey);
    nlEdit.addEventListener('keydown', onkey);
    row.replaceChildren(
      el('td', {}, esEdit),
      el('td', {}, nlEdit),
      el('td', {style: 'white-space:nowrap; text-align:right'},
        el('button', {class: 'icon-btn', title: 'Opslaan', onclick: save}, '✔️'),
        el('button', {class: 'icon-btn', title: 'Annuleren', onclick: () => refreshList()}, '✖️'),
      ),
    );
    esEdit.focus();
  }

  view.replaceChildren(
    el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, `← ${chapter.name}`)),
    el('h1', {}, 'Woorden'),
    form,
    listWrap,
  );
  await refreshList();
  spanishInput.focus();
}

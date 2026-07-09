import {api, el} from '../api.js';

export async function renderGrammarEntry(view, chapterId) {
  const chapters = await api('/api/chapters');
  const chapter = chapters.find((c) => c.id === chapterId);
  if (!chapter) { location.hash = '#/'; return; }

  let editingId = null;

  const titleInput = el('input', {
    type: 'text', placeholder: 'Lidwoorden: el & la', 'aria-label': 'Titel',
  });
  const explanationInput = el('textarea', {
    rows: '4', 'aria-label': 'Uitleg',
    placeholder: 'Mannelijke woorden krijgen "el", vrouwelijke "la"…',
  });
  const examplesWrap = el('div', {});
  const submitButton = el('button', {class: 'btn-primary', type: 'submit'}, 'Opslaan');
  const cancelButton = el('button', {
    class: 'btn-ghost', type: 'button', hidden: '',
    onclick: () => resetForm(),
  }, 'Annuleren');

  function exampleRow(spanish = '', dutch = '') {
    const row = el('div', {class: 'row', style: 'margin-bottom:0.4rem'},
      el('input', {
        type: 'text', value: spanish, placeholder: 'el coche',
        autocapitalize: 'off', 'aria-label': 'Voorbeeld (Spaans)', 'data-es': '',
      }),
      el('input', {
        type: 'text', value: dutch, placeholder: 'de auto',
        autocapitalize: 'off', 'aria-label': 'Voorbeeld (Nederlands)', 'data-nl': '',
      }),
      el('button', {
        class: 'icon-btn fixed', type: 'button', title: 'Voorbeeld verwijderen',
        onclick: () => row.remove(),
      }, '✖️'),
    );
    return row;
  }

  function readExamples() {
    return [...examplesWrap.children]
      .map((row) => ({
        spanish: row.querySelector('[data-es]').value.trim(),
        dutch: row.querySelector('[data-nl]').value.trim(),
      }))
      .filter((example) => example.spanish);
  }

  function resetForm() {
    editingId = null;
    titleInput.value = '';
    explanationInput.value = '';
    examplesWrap.replaceChildren(exampleRow());
    submitButton.textContent = 'Opslaan';
    cancelButton.hidden = true;
    titleInput.focus();
  }

  const form = el(
    'form',
    {
      class: 'card',
      onsubmit: async (e) => {
        e.preventDefault();
        const payload = {
          title: titleInput.value.trim(),
          explanation: explanationInput.value.trim(),
          examples: readExamples(),
        };
        if (!payload.title) return;
        if (editingId) {
          await api(`/api/grammar/${editingId}`, {method: 'PUT', body: payload});
        } else {
          await api('/api/grammar', {
            method: 'POST', body: {chapter_id: chapterId, ...payload},
          });
        }
        resetForm();
        await refreshList();
      },
      onkeydown: (e) => {
        if (e.key === 'Escape') resetForm();
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
          e.preventDefault();
          form.requestSubmit();
        }
      },
    },
    el('label', {}, 'Titel'), titleInput,
    el('label', {style: 'margin-top:0.6rem'}, 'Uitleg'), explanationInput,
    el('label', {style: 'margin-top:0.6rem'}, 'Voorbeelden'),
    examplesWrap,
    el('div', {class: 'row', style: 'margin-top:0.5rem'},
      el('button', {
        class: 'btn-ghost fixed', type: 'button',
        onclick: () => {
          const row = exampleRow();
          examplesWrap.append(row);
          row.querySelector('[data-es]').focus();
        },
      }, '+ voorbeeld'),
      el('span', {class: 'muted', style: 'font-size:0.8rem; align-self:center; flex:1'},
        'Ctrl+Enter slaat op'),
      el('span', {class: 'fixed'}, cancelButton, ' ', submitButton),
    ),
  );

  const listWrap = el('div', {});

  async function refreshList() {
    const rules = await api(`/api/grammar?chapter_id=${chapterId}`);
    listWrap.replaceChildren(
      el('div', {class: 'eyebrow'}, `${rules.length} regels`),
      rules.length
        ? el('div', {}, ...rules.map(ruleCard))
        : el('p', {class: 'muted'}, 'Nog geen grammaticaregels in dit hoofdstuk.'),
    );
  }

  function ruleCard(rule) {
    return el('div', {class: 'card'},
      el('div', {style: 'display:flex; align-items:baseline; gap:0.6rem'},
        el('strong', {style: 'flex:1'}, rule.title),
        el('button', {
          class: 'icon-btn', title: 'Bewerken', 'aria-label': `Bewerk ${rule.title}`,
          onclick: () => {
            editingId = rule.id;
            titleInput.value = rule.title;
            explanationInput.value = rule.explanation;
            examplesWrap.replaceChildren(
              ...(rule.examples.length
                ? rule.examples.map((ex) => exampleRow(ex.spanish, ex.dutch))
                : [exampleRow()]),
            );
            submitButton.textContent = 'Wijzigingen opslaan';
            cancelButton.hidden = false;
            titleInput.focus();
            titleInput.scrollIntoView({block: 'center'});
          },
        }, '✏️'),
        el('button', {
          class: 'icon-btn', title: 'Verwijderen', 'aria-label': `Verwijder ${rule.title}`,
          onclick: async () => {
            if (confirm(`"${rule.title}" verwijderen?`)) {
              await api(`/api/grammar/${rule.id}`, {method: 'DELETE'});
              refreshList();
            }
          },
        }, '🗑️'),
      ),
      rule.explanation ? el('p', {style: 'white-space:pre-wrap'}, rule.explanation) : null,
      rule.examples.length
        ? el('table', {class: 'entry'},
            el('tbody', {},
              ...rule.examples.map((example) =>
                el('tr', {},
                  el('td', {class: 'es'}, example.spanish),
                  el('td', {class: 'muted'}, example.dutch)))))
        : null,
    );
  }

  view.replaceChildren(
    el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, `← ${chapter.name}`)),
    el('h1', {}, 'Grammatica'),
    form,
    listWrap,
  );
  resetForm();
  await refreshList();
}

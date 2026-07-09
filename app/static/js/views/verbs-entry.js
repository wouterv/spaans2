import {api, el} from '../api.js';

export const PERSONS = [
  ['yo', 'yo'],
  ['tu', 'tú'],
  ['el', 'él/ella/usted'],
  ['nosotros', 'nosotros'],
  ['vosotros', 'vosotros'],
  ['ellos', 'ellos/ellas/ustedes'],
];

export async function renderVerbsEntry(view, chapterId) {
  const chapters = await api('/api/chapters');
  const chapter = chapters.find((c) => c.id === chapterId);
  if (!chapter) { location.hash = '#/'; return; }

  let editingId = null;

  const infinitiveInput = el('input', {
    type: 'text', placeholder: 'hablar', autocapitalize: 'off', 'aria-label': 'Infinitief (Spaans)',
  });
  const translationInput = el('input', {
    type: 'text', placeholder: 'praten; spreken', autocapitalize: 'off', 'aria-label': 'Vertaling (Nederlands)',
  });
  const tenseSelect = el('select', {'aria-label': 'Tijd'},
    el('option', {value: 'presente'}, 'presente'));
  const formInputs = {};
  for (const [key, label] of PERSONS) {
    formInputs[key] = el('input', {
      type: 'text', autocapitalize: 'off', 'aria-label': label, placeholder: label,
    });
  }
  const allInputs = [infinitiveInput, translationInput, ...Object.values(formInputs)];
  const submitButton = el('button', {class: 'btn-primary', type: 'submit'}, 'Opslaan');
  const cancelButton = el('button', {
    class: 'btn-ghost', type: 'button', hidden: '',
    onclick: () => resetForm(),
  }, 'Annuleren');

  function resetForm() {
    editingId = null;
    for (const input of allInputs) input.value = '';
    submitButton.textContent = 'Opslaan';
    cancelButton.hidden = true;
    infinitiveInput.focus();
  }

  const form = el(
    'form',
    {
      class: 'card',
      onsubmit: async (e) => {
        e.preventDefault();
        const payload = {
          infinitive_es: infinitiveInput.value.trim(),
          translation_nl: translationInput.value.trim(),
          tense: tenseSelect.value,
          forms: Object.fromEntries(
            PERSONS.map(([key]) => [key, formInputs[key].value.trim()]),
          ),
        };
        if (!payload.infinitive_es || !payload.translation_nl) return;
        if (PERSONS.some(([key]) => !payload.forms[key])) return;
        if (editingId) {
          await api(`/api/verbs/${editingId}`, {method: 'PUT', body: payload});
        } else {
          await api('/api/verbs', {
            method: 'POST', body: {chapter_id: chapterId, ...payload},
          });
        }
        resetForm();
        await refreshList();
      },
      onkeydown: (e) => {
        if (e.key === 'Escape') { resetForm(); return; }
        if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
          const index = allInputs.indexOf(e.target);
          if (index >= 0 && index < allInputs.length - 1) {
            e.preventDefault();
            allInputs[index + 1].focus();
          }
        }
      },
    },
    el('div', {class: 'row'},
      el('div', {}, el('label', {}, 'Infinitief'), infinitiveInput),
      el('div', {}, el('label', {}, 'Vertaling'), translationInput),
      el('div', {class: 'fixed'}, el('label', {}, 'Tijd'), tenseSelect),
    ),
    el('div', {class: 'row', style: 'margin-top:0.75rem'},
      ...PERSONS.slice(0, 3).map(([key, label]) =>
        el('div', {}, el('label', {}, label), formInputs[key])),
    ),
    el('div', {class: 'row', style: 'margin-top:0.75rem'},
      ...PERSONS.slice(3).map(([key, label]) =>
        el('div', {}, el('label', {}, label), formInputs[key])),
    ),
    el('div', {class: 'row', style: 'margin-top:0.75rem'},
      el('span', {class: 'muted', style: 'font-size:0.8rem; align-self:center'},
        'Enter springt naar het volgende veld · laatste veld slaat op · Esc maakt leeg'),
      el('span', {class: 'fixed'}, cancelButton, ' ', submitButton),
    ),
  );

  const listWrap = el('div', {});

  async function refreshList() {
    const verbs = await api(`/api/verbs?chapter_id=${chapterId}`);
    listWrap.replaceChildren(
      el('div', {class: 'eyebrow'}, `${verbs.length} werkwoorden`),
      verbs.length
        ? el('div', {}, ...verbs.slice().reverse().map(verbCard))
        : el('p', {class: 'muted'}, 'Nog geen werkwoorden in dit hoofdstuk.'),
    );
  }

  function verbCard(verb) {
    const tense = 'presente';
    const forms = verb.conjugations[tense] || {};
    return el('div', {class: 'card'},
      el('div', {style: 'display:flex; align-items:baseline; gap:0.6rem'},
        el('strong', {class: 'es', style: 'font-family:var(--serif); font-size:1.15rem'},
          verb.infinitive_es),
        el('span', {class: 'muted grow', style: 'flex:1'}, verb.translation_nl),
        el('button', {
          class: 'icon-btn', title: 'Bewerken', 'aria-label': `Bewerk ${verb.infinitive_es}`,
          onclick: () => {
            editingId = verb.id;
            infinitiveInput.value = verb.infinitive_es;
            translationInput.value = verb.translation_nl;
            for (const [key] of PERSONS) formInputs[key].value = forms[key] || '';
            submitButton.textContent = 'Wijzigingen opslaan';
            cancelButton.hidden = false;
            infinitiveInput.focus();
            infinitiveInput.scrollIntoView({block: 'center'});
          },
        }, '✏️'),
        el('button', {
          class: 'icon-btn', title: 'Verwijderen', 'aria-label': `Verwijder ${verb.infinitive_es}`,
          onclick: async () => {
            if (confirm(`"${verb.infinitive_es}" verwijderen?`)) {
              await api(`/api/verbs/${verb.id}`, {method: 'DELETE'});
              refreshList();
            }
          },
        }, '🗑️'),
      ),
      el('table', {class: 'entry', style: 'margin-top:0.5rem'},
        el('tbody', {},
          ...PERSONS.map(([key, label]) =>
            el('tr', {},
              el('th', {style: 'width:40%'}, label),
              el('td', {class: 'es'}, forms[key] || '—'))),
        ),
      ),
    );
  }

  view.replaceChildren(
    el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, `← ${chapter.name}`)),
    el('h1', {}, 'Werkwoorden'),
    form,
    listWrap,
  );
  await refreshList();
  infinitiveInput.focus();
}

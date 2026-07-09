import {api, el} from '../api.js';
import {createQueue, shuffle} from '../queue.js';
import {PERSONS} from './verbs-entry.js';

export async function renderPracticeVerbs(view, chapterId, mode) {
  const verbs = await api(`/api/practice/items?chapter_id=${chapterId}&type=verbs`);
  const backLink = el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, '← Hoofdstuk'));

  if (!verbs.length) {
    view.replaceChildren(backLink,
      el('p', {class: 'muted'}, 'Dit hoofdstuk heeft nog geen werkwoorden om te oefenen.'));
    return;
  }

  const container = el('div', {});
  view.replaceChildren(backLink, container);

  const queue = createQueue(shuffle(verbs));
  const tense = 'presente';

  function next() {
    if (!container.isConnected) return;
    if (queue.done) { renderSummary(); return; }
    renderVerb(queue.current);
  }

  function renderVerb(verb) {
    const {mastered, total} = queue.progress;
    let wrongCount = 0;
    let checkedCount = 0;
    const inputs = [];

    const rows = PERSONS.map(([person, label]) => {
      const input = el('input', {
        type: 'text', autocapitalize: 'off', autocomplete: 'off',
        'aria-label': `Vervoeging voor ${label}`,
      });
      const resultCell = el('td', {class: 'es'});
      inputs.push({person, input, resultCell, checked: false});
      return el('tr', {},
        el('th', {style: 'width:34%'}, label),
        el('td', {}, input),
        resultCell,
      );
    });

    const continueButton = el('button', {
      class: 'btn-primary btn-big', style: 'margin-top:1rem', hidden: '',
      onclick: () => {
        if (wrongCount) queue.wrong();
        else queue.correct();
        next();
      },
    }, 'Verder');

    async function checkField(entry) {
      const answer = entry.input.value.trim();
      if (!answer || entry.checked) return;
      entry.checked = true;
      entry.input.readOnly = true;
      const result = await api('/api/practice/check', {
        method: 'POST',
        body: {
          item_type: 'verb', item_id: verb.id, direction: 'conjugation',
          tense, person: entry.person, answer,
        },
      });
      if (result.result === 'wrong') {
        wrongCount++;
        entry.input.classList.add('check-fout');
        entry.resultCell.textContent = result.correct_answer;
      } else {
        entry.input.classList.add('check-goed');
        if (result.result === 'correct_accent') {
          entry.resultCell.textContent = `accent: ${result.matched}`;
        }
      }
      checkedCount++;
      if (checkedCount === inputs.length) {
        continueButton.hidden = false;
        continueButton.focus();
      } else {
        const nextEntry = inputs.find((other) => !other.checked);
        nextEntry?.input.focus();
      }
    }

    for (const entry of inputs) {
      entry.input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          checkField(entry);
        }
      });
    }

    container.replaceChildren(
      el('div', {class: 'practice-progress'},
        `${mastered} van ${total} `, el('span', {class: 'sol'}, '●'),
        ` nog ${total - mastered}`),
      el('div', {class: 'practice-card'},
        el('div', {class: 'practice-hint'}, `Nederlands · ${tense}`),
        el('div', {class: 'practice-word'}, verb.translation_nl),
        el('table', {class: 'entry', style: 'text-align:left'}, el('tbody', {}, ...rows)),
        continueButton,
      ),
    );
    inputs[0].input.focus();
  }

  function renderSummary() {
    const {total, wrong} = queue.progress;
    container.replaceChildren(
      el('div', {class: 'practice-card'},
        el('div', {class: 'practice-word'}, '¡Listo!'),
        el('p', {}, `${total} werkwoorden geoefend, ${queue.firstTryCorrect} in één keer foutloos.`),
        wrong ? el('p', {class: 'muted'}, `${wrong}× een werkwoord met fouten.`) : null,
        el('div', {class: 'row', style: 'margin-top:1rem'},
          el('button', {
            class: 'btn-primary btn-big',
            onclick: () => renderPracticeVerbs(view, chapterId, mode),
          }, 'Nog een keer'),
          el('a', {class: 'btn btn-big', href: `#/h/${chapterId}`}, 'Klaar'),
        ),
      ),
    );
  }

  next();
}

import {api, el} from '../api.js';
import {createQueue, shuffle} from '../queue.js';
import {LANG, canListen, listen, speak} from '../speech.js';
import {PERSONS} from './verbs-entry.js';

const SPOKEN_CUES = {
  yo: 'yo', tu: 'tú', el: 'él', nosotros: 'nosotros',
  vosotros: 'vosotros', ellos: 'ellos',
};

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
  const speechMode = mode === 'spraak';
  const withRecognition = speechMode && canListen();

  function next() {
    if (!container.isConnected) return;
    if (queue.done) { renderSummary(); return; }
    renderVerb(queue.current);
  }

  function renderVerb(verb) {
    const {mastered, total} = queue.progress;
    let wrongCount = 0;
    let checkedCount = 0;
    const entries = [];

    const rows = PERSONS.map(([person, label]) => {
      const input = el('input', {
        type: 'text', autocapitalize: 'off', autocomplete: 'off',
        'aria-label': `Vervoeging voor ${label}`,
      });
      if (withRecognition) input.readOnly = true;
      const resultCell = el('td', {class: 'es'});
      entries.push({person, input, resultCell, checked: false});
      return el('tr', {},
        el('th', {style: 'width:34%'}, label),
        el('td', {}, input),
        resultCell,
      );
    });

    const continueButton = el('button', {
      class: 'btn-primary btn-big', style: 'margin-top:1rem', hidden: '',
      onclick: finishVerb,
    }, 'Verder');

    function finishVerb() {
      if (wrongCount) queue.wrong();
      else queue.correct();
      next();
    }

    async function checkField(entry, answer, alternatives = []) {
      if (entry.checked) return null;
      entry.checked = true;
      entry.input.readOnly = true;
      const result = await api('/api/practice/check', {
        method: 'POST',
        body: {
          item_type: 'verb', item_id: verb.id, direction: 'conjugation',
          tense, person: entry.person, answer, alternatives,
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
      return result;
    }

    if (!withRecognition) {
      for (const entry of entries) {
        entry.input.addEventListener('keydown', async (e) => {
          if (e.key !== 'Enter') return;
          e.preventDefault();
          const answer = entry.input.value.trim();
          if (!answer) return;
          await checkField(entry, answer);
          if (checkedCount === entries.length) {
            continueButton.hidden = false;
            continueButton.focus();
          } else {
            entries.find((other) => !other.checked)?.input.focus();
          }
        });
      }
    }

    container.replaceChildren(
      progressLine(mastered, total),
      el('div', {class: 'practice-card'},
        el('div', {class: 'practice-hint'}, `Nederlands · ${tense}`),
        el('div', {class: 'practice-word'}, verb.translation_nl),
        el('table', {class: 'entry', style: 'text-align:left'}, el('tbody', {}, ...rows)),
        continueButton,
      ),
      speechMode && !canListen()
        ? el('p', {class: 'muted', style: 'font-size:0.85rem'},
            'Spraakherkenning is hier niet beschikbaar — je hoort de opgave en typt de vervoegingen.')
        : null,
    );

    if (withRecognition) {
      speechLoop(verb, entries);
    } else {
      if (speechMode) speak(`${verb.translation_nl}, ${tense}`, LANG.nl);
      entries[0].input.focus();
    }

    async function speechLoop() {
      await speak(`${verb.translation_nl}, ${tense}`, LANG.nl);
      for (const entry of entries) {
        if (!container.isConnected) return;
        await speak(SPOKEN_CUES[entry.person], LANG.es);
        if (!container.isConnected) return;
        entry.input.classList.add('luistert');
        const heard = await listen(LANG.es, {timeout: 7000});
        entry.input.classList.remove('luistert');
        if (!container.isConnected) return;
        const answer = heard ? heard[0] : '';
        entry.input.value = heard ? heard[0] : '(niets gehoord)';
        const result = await checkField(entry, answer, heard ? heard.slice(1) : []);
        if (!container.isConnected) return;
        if (result && result.result === 'wrong') {
          await speak(result.correct_answer, LANG.es);
        }
      }
      if (!container.isConnected) return;
      if (wrongCount) {
        await speak(`${wrongCount} fout. Dit werkwoord komt terug.`, LANG.nl);
      } else {
        await speak('¡Muy bien!', LANG.es);
      }
      if (container.isConnected) finishVerb();
    }
  }

  function progressLine(mastered, total) {
    return el('div', {class: 'practice-progress'},
      `${mastered} van ${total} `, el('span', {class: 'sol'}, '●'),
      ` nog ${total - mastered}`);
  }

  function renderSummary() {
    const {total, wrong} = queue.progress;
    if (speechMode) speak('Klaar! Goed gedaan.', LANG.nl);
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

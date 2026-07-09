import {api, el} from '../api.js';
import {createQueue, shuffle} from '../queue.js';

export async function renderPracticeWords(view, chapterId, direction, mode) {
  const words = await api(`/api/practice/items?chapter_id=${chapterId}&type=words`);
  const backLink = el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, '← Hoofdstuk'));

  if (!words.length) {
    view.replaceChildren(backLink,
      el('p', {class: 'muted'}, 'Dit hoofdstuk heeft nog geen woorden om te oefenen.'));
    return;
  }

  const container = el('div', {});
  view.replaceChildren(backLink, container);

  const queue = createQueue(shuffle(words));
  const promptOf = (word) => (direction === 'es_nl' ? word.spanish : word.dutch);
  const promptLang = direction === 'es_nl' ? 'Spaans' : 'Nederlands';
  const answerLang = direction === 'es_nl' ? 'Nederlands' : 'Spaans';

  function next() {
    if (!container.isConnected) return;
    if (queue.done) { renderSummary(); return; }
    renderQuestion(queue.current);
  }

  function renderQuestion(word) {
    const {mastered, total} = queue.progress;
    const input = el('input', {
      type: 'text', autocapitalize: 'off', autocomplete: 'off',
      placeholder: `${answerLang}…`, 'aria-label': `Antwoord in het ${answerLang}`,
    });
    const feedback = el('div', {});
    let answered = false;

    const form = el('form', {
      onsubmit: async (e) => {
        e.preventDefault();
        if (answered) return;
        const answer = input.value.trim();
        if (!answer) return;
        answered = true;
        input.readOnly = true;
        const result = await api('/api/practice/check', {
          method: 'POST',
          body: {item_type: 'word', item_id: word.id, direction, answer},
        });
        showResult(word, result, input, feedback);
      },
    }, input);

    container.replaceChildren(
      el('div', {class: 'practice-progress'},
        `${mastered} van ${total} `, el('span', {class: 'sol'}, '●'),
        ` nog ${total - mastered}`),
      el('div', {class: 'practice-card'},
        el('div', {class: 'practice-hint'}, promptLang),
        el('div', {class: 'practice-word'}, promptOf(word)),
        form,
      ),
      feedback,
    );
    input.focus();
  }

  function showResult(word, result, input, feedback) {
    if (result.result === 'correct') {
      input.classList.add('check-goed');
      feedback.replaceChildren(el('div', {class: 'feedback goed'}, '¡Muy bien!'));
      queue.correct();
      setTimeout(next, 700);
      return;
    }
    const continueButton = el('button', {class: 'btn-primary btn-big', onclick: next}, 'Verder');
    if (result.result === 'correct_accent') {
      input.classList.add('check-goed');
      feedback.replaceChildren(
        el('div', {class: 'feedback accent'},
          'Goed! Maar let op het accent: ',
          el('span', {class: 'answer'}, result.matched)),
        continueButton,
      );
      queue.correct();
    } else {
      input.classList.add('check-fout');
      feedback.replaceChildren(
        el('div', {class: 'feedback fout'},
          'Helaas — het juiste antwoord is ',
          el('span', {class: 'answer'}, result.correct_answer)),
        continueButton,
      );
      queue.wrong();
    }
    continueButton.focus();
  }

  function renderSummary() {
    const {total, wrong} = queue.progress;
    container.replaceChildren(
      el('div', {class: 'practice-card'},
        el('div', {class: 'practice-word'}, '¡Listo!'),
        el('p', {}, `${total} woorden geoefend, ${queue.firstTryCorrect} in één keer goed.`),
        wrong ? el('p', {class: 'muted'}, `${wrong}× een fout antwoord.`) : null,
        el('div', {class: 'row', style: 'margin-top:1rem'},
          el('button', {
            class: 'btn-primary btn-big',
            onclick: () => renderPracticeWords(view, chapterId, direction, mode),
          }, 'Nog een keer'),
          el('a', {class: 'btn btn-big', href: `#/h/${chapterId}`}, 'Klaar'),
        ),
      ),
    );
  }

  next();
}

import {api, el, setChildren} from '../api.js';
import {createQueue, shuffle} from '../queue.js';

export async function renderPracticeExercises(view, chapterId) {
  const exercises = await api(`/api/exercises?chapter_id=${chapterId}`);
  const backLink = el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, '← Hoofdstuk'));

  if (!exercises.length) {
    setChildren(view, backLink,
      el('p', {class: 'muted'},
        'Dit hoofdstuk heeft nog geen oefeningen. Genereer ze op het hoofdstukscherm.'));
    return;
  }

  const container = el('div', {});
  setChildren(view, backLink, container);
  const queue = createQueue(shuffle(exercises));
  const disabledIds = new Set();

  function next() {
    if (!container.isConnected) return;
    // Weggestemde oefeningen die nog in de wachtrij zaten overslaan
    while (queue.current && disabledIds.has(queue.current.id)) queue.correct();
    if (queue.done) { renderSummary(); return; }
    renderQuestion(queue.current);
  }

  function progressBar() {
    const {mastered, total} = queue.progress;
    return el('div', {class: 'practice-progress'},
      `${mastered} van ${total} `, el('span', {class: 'sol'}, '●'),
      ` nog ${total - mastered}`);
  }

  function check(exercise, answer) {
    return api(`/api/exercises/${exercise.id}/check`, {
      method: 'POST',
      body: {answer},
    });
  }

  function renderQuestion(exercise) {
    if (exercise.type === 'meerkeuze') renderChoice(exercise);
    else renderTyped(exercise);
  }

  function questionCard(exercise, ...children) {
    return el('div', {class: 'practice-card'},
      el('div', {class: 'practice-hint'}, exercise.instruction),
      el('div', {class: 'practice-word'}, exercise.prompt),
      ...children,
    );
  }

  /* ── Typen: invullen, vertalen, herschrijven ── */

  function renderTyped(exercise) {
    const input = el('input', {
      type: 'text', autocapitalize: 'off', autocomplete: 'off',
      placeholder: 'Antwoord…', 'aria-label': 'Antwoord',
    });
    const feedback = el('div', {});
    let answered = false;

    const answerForm = el('form', {
      onsubmit: async (e) => {
        e.preventDefault();
        if (answered) return;
        const answer = input.value.trim();
        if (!answer) return;
        answered = true;
        input.readOnly = true;
        const result = await check(exercise, answer);
        input.classList.add(result.result === 'wrong' ? 'check-fout' : 'check-goed');
        showResult(exercise, result, feedback);
      },
    }, input);

    setChildren(container, progressBar(), questionCard(exercise, answerForm), feedback);
    input.focus();
  }

  /* ── Meerkeuze ── */

  function renderChoice(exercise) {
    const feedback = el('div', {});
    let answered = false;
    const buttons = exercise.options.map((option) =>
      el('button', {
        class: 'btn-big',
        onclick: async () => {
          if (answered) return;
          answered = true;
          const result = await check(exercise, option);
          for (const b of buttons) {
            b.disabled = true;
            if (b.textContent === result.correct_answer) b.classList.add('check-goed');
          }
          if (result.result === 'wrong') {
            const chosen = buttons.find((b) => b.textContent === option);
            chosen.classList.add('check-fout');
          }
          showResult(exercise, result, feedback);
        },
      }, option),
    );
    setChildren(container, progressBar(),
      questionCard(exercise, el('div', {class: 'row', style: 'margin-top:0.75rem'}, ...buttons)),
      feedback);
  }

  /* ── Resultaat en wegstemmen ── */

  function disableButton(exercise) {
    return el('button', {
      class: 'muted',
      style: 'font-size:0.85rem',
      onclick: async () => {
        await api(`/api/exercises/${exercise.id}/disable`, {method: 'POST'});
        disabledIds.add(exercise.id);
        next();
      },
    }, '🗑️ Slechte oefening');
  }

  function showResult(exercise, result, feedback) {
    const explanation = result.explanation
      ? el('p', {class: 'muted'}, result.explanation) : null;
    if (result.result === 'correct') {
      setChildren(feedback,
        el('div', {class: 'feedback goed'}, '¡Muy bien!'), explanation);
      queue.correct();
      setTimeout(next, explanation ? 1600 : 700);
      return;
    }
    const continueButton = el('button', {class: 'btn-primary btn-big', onclick: next}, 'Verder');
    if (result.result === 'correct_accent') {
      setChildren(feedback,
        el('div', {class: 'feedback accent'},
          'Goed! Maar let op het accent: ',
          el('span', {class: 'answer'}, result.correct_answer)),
        explanation, el('div', {class: 'row'}, continueButton, disableButton(exercise)),
      );
      queue.correct();
    } else {
      setChildren(feedback,
        el('div', {class: 'feedback fout'},
          'Helaas — het juiste antwoord is ',
          el('span', {class: 'answer'}, result.correct_answer)),
        result.feedback ? el('p', {class: 'muted'}, result.feedback) : null,
        explanation, el('div', {class: 'row'}, continueButton, disableButton(exercise)),
      );
      queue.wrong();
    }
    continueButton.focus();
  }

  function renderSummary() {
    const {total, wrong} = queue.progress;
    setChildren(container,
      el('div', {class: 'practice-card'},
        el('div', {class: 'practice-word'}, '¡Listo!'),
        el('p', {}, `${total} oefeningen gedaan, ${queue.firstTryCorrect} in één keer goed.`),
        wrong ? el('p', {class: 'muted'}, `${wrong}× een fout antwoord.`) : null,
        el('div', {class: 'row', style: 'margin-top:1rem'},
          el('button', {
            class: 'btn-primary btn-big',
            onclick: () => renderPracticeExercises(view, chapterId),
          }, 'Nog een keer'),
          el('a', {class: 'btn btn-big', href: `#/h/${chapterId}`}, 'Klaar'),
        ),
      ),
    );
  }

  next();
}

import {api, el, setChildren} from '../api.js';
import {createQueue, shuffle} from '../queue.js';
import {LANG, canListen, listen, speak, stopListening} from '../speech.js';

export async function renderPracticeWords(view, chapterId, direction, mode) {
  const words = await api(`/api/practice/items?chapter_id=${chapterId}&type=words`);
  const backLink = el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, '← Hoofdstuk'));

  if (!words.length) {
    setChildren(view, backLink,
      el('p', {class: 'muted'}, 'Dit hoofdstuk heeft nog geen woorden om te oefenen.'));
    return;
  }

  const container = el('div', {});
  setChildren(view, backLink, container);

  const queue = createQueue(shuffle(words));
  const speechMode = mode === 'spraak';
  const withRecognition = speechMode && canListen();
  const promptOf = (word) => (direction === 'es_nl' ? word.spanish : word.dutch);
  const promptLang = direction === 'es_nl' ? 'Spaans' : 'Nederlands';
  const answerLang = direction === 'es_nl' ? 'Nederlands' : 'Spaans';
  const promptLangCode = direction === 'es_nl' ? LANG.es : LANG.nl;
  const answerLangCode = direction === 'es_nl' ? LANG.nl : LANG.es;

  function next() {
    if (!container.isConnected) return;
    if (queue.done) { renderSummary(); return; }
    if (withRecognition) renderQuestionSpeech(queue.current);
    else renderQuestionTyped(queue.current);
  }

  function progressBar() {
    const {mastered, total} = queue.progress;
    return el('div', {class: 'practice-progress'},
      `${mastered} van ${total} `, el('span', {class: 'sol'}, '●'),
      ` nog ${total - mastered}`);
  }

  async function checkViaApi(word, answer, alternatives = []) {
    return api('/api/practice/check', {
      method: 'POST',
      body: {item_type: 'word', item_id: word.id, direction, answer, alternatives},
    });
  }

  /* ── Typen (ook fallback als herkenning ontbreekt) ── */

  function renderQuestionTyped(word) {
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
        const result = await checkViaApi(word, answer);
        showTypedResult(result, input, feedback);
      },
    }, input);

    setChildren(container, 
      progressBar(),
      el('div', {class: 'practice-card'},
        el('div', {class: 'practice-hint'}, promptLang),
        el('div', {class: 'practice-word'}, promptOf(word)),
        form,
      ),
      speechMode && !canListen()
        ? el('p', {class: 'muted', style: 'font-size:0.85rem'},
            'Spraakherkenning is hier niet beschikbaar — je hoort de opgave en typt het antwoord.')
        : null,
      feedback,
    );
    if (speechMode) speak(promptOf(word), promptLangCode);
    input.focus();
  }

  function showTypedResult(result, input, feedback) {
    if (result.result === 'correct') {
      input.classList.add('check-goed');
      setChildren(feedback, el('div', {class: 'feedback goed'}, '¡Muy bien!'));
      queue.correct();
      setTimeout(next, 700);
      return;
    }
    const continueButton = el('button', {class: 'btn-primary btn-big', onclick: next}, 'Verder');
    if (result.result === 'correct_accent') {
      input.classList.add('check-goed');
      setChildren(feedback, 
        el('div', {class: 'feedback accent'},
          'Goed! Maar let op het accent: ',
          el('span', {class: 'answer'}, result.matched)),
        continueButton,
      );
      queue.correct();
    } else {
      input.classList.add('check-fout');
      setChildren(feedback, 
        el('div', {class: 'feedback fout'},
          'Helaas — het juiste antwoord is ',
          el('span', {class: 'answer'}, result.correct_answer)),
        continueButton,
      );
      queue.wrong();
    }
    continueButton.focus();
  }

  /* ── Spraak (automodus): luisteren en spreken ── */

  function renderQuestionSpeech(word) {
    const mic = el('div', {class: 'mic-indicator', 'aria-hidden': 'true'}, '🎙️');
    const heardLine = el('p', {class: 'muted'}, ' ');
    const feedback = el('div', {});
    const repeatButton = el('button', {onclick: () => ask()}, '🔁 Herhaal');
    const giveUpButton = el('button', {onclick: () => giveUp()}, '🤷 Weet ik niet');

    setChildren(container, 
      progressBar(),
      el('div', {class: 'practice-card'},
        el('div', {class: 'practice-hint'}, promptLang),
        el('div', {class: 'practice-word'}, promptOf(word)),
        mic,
        heardLine,
      ),
      feedback,
      el('div', {class: 'car-controls'}, repeatButton, giveUpButton),
    );

    let busy = false;

    async function ask() {
      if (busy) stopListening();
      busy = true;
      setChildren(feedback, );
      heardLine.textContent = ' ';
      await speak(promptOf(word), promptLangCode);
      if (!container.isConnected) return;
      mic.classList.add('luistert');
      const heard = await listen(answerLangCode);
      mic.classList.remove('luistert');
      busy = false;
      if (!container.isConnected) return;
      if (!heard) {
        heardLine.textContent = 'Ik heb niets gehoord.';
        await speak('Ik heb niets gehoord. Probeer opnieuw.', LANG.nl);
        if (container.isConnected) repeatButton.focus();
        return;
      }
      heardLine.textContent = `Gehoord: "${heard[0]}"`;
      const result = await checkViaApi(word, heard[0], heard.slice(1));
      if (!container.isConnected) return;
      if (result.result === 'wrong') {
        setChildren(feedback, 
          el('div', {class: 'feedback fout'},
            'Helaas — het juiste antwoord is ',
            el('span', {class: 'answer'}, result.correct_answer)),
        );
        queue.wrong();
        await speak('Helaas. Het juiste antwoord is:', LANG.nl);
        await speak(result.correct_answer.split(';')[0], answerLangCode);
      } else {
        setChildren(feedback, el('div', {class: 'feedback goed'}, '¡Muy bien!'));
        queue.correct();
        await speak('¡Muy bien!', LANG.es);
      }
      if (container.isConnected) next();
    }

    async function giveUp() {
      stopListening();
      const result = await checkViaApi(word, '');
      if (!container.isConnected) return;
      setChildren(feedback, 
        el('div', {class: 'feedback fout'},
          'Het juiste antwoord is ',
          el('span', {class: 'answer'}, result.correct_answer)),
      );
      queue.wrong();
      await speak('Het juiste antwoord is:', LANG.nl);
      await speak(result.correct_answer.split(';')[0], answerLangCode);
      if (container.isConnected) next();
    }

    ask();
  }

  function renderSummary() {
    const {total, wrong} = queue.progress;
    if (speechMode) speak('Klaar! Goed gedaan.', LANG.nl);
    setChildren(container, 
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

import {api, el, setChildren} from '../api.js';
import {LANG, speak, stopAll} from '../speech.js';

export async function renderGrammarReader(view, chapterId) {
  const rules = await api(`/api/grammar?chapter_id=${chapterId}`);
  const backLink = el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, '← Hoofdstuk'));

  if (!rules.length) {
    setChildren(view, backLink,
      el('p', {class: 'muted'}, 'Dit hoofdstuk heeft nog geen grammaticaregels.'));
    return;
  }

  const container = el('div', {});
  setChildren(view, backLink, container);
  let index = 0;

  async function readAloud(rule) {
    stopAll();
    await speak(rule.title, LANG.nl);
    if (rule.explanation) await speak(rule.explanation, LANG.nl);
    for (const example of rule.examples) {
      if (!container.isConnected) return;
      await speak(example.spanish, LANG.es);
      if (example.dutch) await speak(example.dutch, LANG.nl);
    }
  }

  function show() {
    if (!container.isConnected) return;
    stopAll();
    const rule = rules[index];
    const prevButton = el('button', {
      class: 'btn-big', disabled: index === 0 ? '' : null,
      onclick: () => { index--; show(); },
    }, '← Vorige');
    const nextButton = el('button', {
      class: 'btn-big', disabled: index === rules.length - 1 ? '' : null,
      onclick: () => { index++; show(); },
    }, 'Volgende →');

    setChildren(container, 
      el('div', {class: 'practice-progress'}, `Regel ${index + 1} van ${rules.length}`),
      el('div', {class: 'card'},
        el('h2', {style: 'margin-top:0'}, rule.title),
        rule.explanation
          ? el('p', {style: 'white-space:pre-wrap'}, rule.explanation)
          : null,
        rule.examples.length
          ? el('table', {class: 'entry'},
              el('tbody', {},
                ...rule.examples.map((example) =>
                  el('tr', {},
                    el('td', {class: 'es'}, example.spanish),
                    el('td', {class: 'muted'}, example.dutch)))))
          : null,
        el('div', {class: 'row', style: 'margin-top:1rem'},
          el('button', {
            class: 'btn-primary btn-big',
            onclick: () => readAloud(rule),
          }, '🔊 Lees voor'),
        ),
      ),
      el('div', {class: 'car-controls'}, prevButton, nextButton),
    );
  }

  const onKey = (e) => {
    if (!container.isConnected) {
      document.removeEventListener('keydown', onKey);
      return;
    }
    if (e.key === 'ArrowLeft' && index > 0) { index--; show(); }
    if (e.key === 'ArrowRight' && index < rules.length - 1) { index++; show(); }
  };
  document.addEventListener('keydown', onKey);

  show();
}

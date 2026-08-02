import {api, el, setChildren} from '../api.js';
import {clearConcept, loadConcept, saveConcept} from '../concept.js';
import {renderScanStep} from '../scan-step.js';
import {PERSONS} from './verbs-entry.js';

export async function renderLessonUpload(view, chapterId) {
  const chapters = await api('/api/chapters');
  const chapter = chapters.find((c) => c.id === chapterId);
  if (!chapter) { location.hash = '#/'; return; }

  const container = el('div', {});
  // Werk-in-uitvoering overleeft een refresh: het uitgelezen resultaat en
  // elke bewerking staan in localStorage tot alles is opgeslagen
  const conceptKey = `spaans-les-concept-${chapterId}`;
  setChildren(view,
    el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, `← ${chapter.name}`)),
    el('h1', {}, 'Les uploaden'),
    container,
  );

  /* ── Stap 1: scans kiezen en laten uitlezen (gedeelde module) ── */

  function renderUploadStep() {
    const concept = loadConcept(conceptKey);
    const conceptBanner = concept
      ? el('div', {class: 'card'},
          el('p', {},
            `📝 Er staat nog een niet-opgeslagen les van ${new Date(concept.at)
              .toLocaleString('nl-NL', {weekday: 'long', hour: '2-digit', minute: '2-digit'})}.`),
          el('div', {class: 'row'},
            el('button', {
              class: 'btn-primary',
              onclick: () => renderReviewStep(
                concept.data.rules, concept.data.examples, concept.data.verbs || []),
            }, '✏️ Verdergaan met nakijken'),
            el('button', {
              class: 'btn-ghost',
              onclick: () => {
                if (confirm('De niet-opgeslagen les weggooien?')) {
                  clearConcept(conceptKey);
                  renderUploadStep();
                }
              },
            }, '🗑️ Weggooien'),
          ),
        )
      : null;

    renderScanStep(container, {
      intro: 'Kies één of meer foto\'s of scans van de les. Na het uitlezen kun je alles nakijken en aanpassen voordat het wordt opgeslagen.',
      buttonLabel: '📖 Lees les',
      banner: conceptBanner,
      extract: async (images) => {
        const {rules, examples, verbs} = await api(`/api/chapters/${chapterId}/lessons/extract`, {
          method: 'POST', body: {images},
        });
        saveConcept(conceptKey, {rules, examples, verbs});
        renderReviewStep(rules, examples, verbs);
      },
    });
  }

  /* ── Stap 2: nakijken, bewerken en opslaan ── */

  function renderReviewStep(rules, examples, verbs) {
    const editorsWrap = el('div', {});
    const status = el('p', {class: 'muted'});

    function exampleRow(spanish = '', dutch = '') {
      const row = el('div', {class: 'row', style: 'margin-bottom:0.4rem'},
        el('input', {
          type: 'text', value: spanish, autocapitalize: 'off',
          'aria-label': 'Voorbeeld (Spaans)', 'data-es': '',
        }),
        el('input', {
          type: 'text', value: dutch, autocapitalize: 'off',
          'aria-label': 'Voorbeeld (Nederlands)', 'data-nl': '',
        }),
        el('button', {
          class: 'icon-btn fixed', type: 'button', title: 'Voorbeeld verwijderen',
          onclick: () => row.remove(),
        }, '✖️'),
      );
      return row;
    }

    function ruleEditor(rule) {
      const titleInput = el('input', {
        type: 'text', value: rule.title, 'aria-label': 'Titel',
      });
      const explanationInput = el('textarea', {rows: '4', 'aria-label': 'Uitleg'});
      explanationInput.value = rule.explanation;
      const examplesWrap = el('div', {},
        ...rule.examples.map((ex) => exampleRow(ex.spanish, ex.dutch)));
      const card = el('div', {class: 'card', 'data-rule': ''},
        el('div', {class: 'row'},
          el('label', {class: 'grow'}, 'Titel'),
          el('button', {
            class: 'icon-btn fixed', type: 'button', title: 'Regel verwijderen',
            onclick: () => card.remove(),
          }, '🗑️'),
        ),
        titleInput,
        el('label', {style: 'margin-top:0.6rem'}, 'Uitleg'), explanationInput,
        el('label', {style: 'margin-top:0.6rem'}, 'Voorbeelden'), examplesWrap,
        el('button', {
          class: 'btn-ghost fixed', type: 'button',
          onclick: () => examplesWrap.append(exampleRow()),
        }, '+ voorbeeld'),
      );
      card.readRule = () => ({
        title: titleInput.value.trim(),
        explanation: explanationInput.value.trim(),
        examples: [...examplesWrap.children]
          .map((row) => ({
            spanish: row.querySelector('[data-es]').value.trim(),
            dutch: row.querySelector('[data-nl]').value.trim(),
          }))
          .filter((example) => example.spanish),
      });
      return card;
    }

    function exampleEditor(text) {
      const textInput = el('textarea', {rows: '3', 'aria-label': 'Opgave'});
      textInput.value = text;
      const card = el('div', {class: 'card', 'data-example': ''},
        el('div', {class: 'row'},
          el('label', {class: 'grow'}, 'Opgave'),
          el('button', {
            class: 'icon-btn fixed', type: 'button', title: 'Voorbeeld verwijderen',
            onclick: () => card.remove(),
          }, '🗑️'),
        ),
        textInput,
      );
      card.readExample = () => textInput.value.trim();
      return card;
    }

    function verbEditor(verb) {
      const infinitiveInput = el('input', {
        type: 'text', value: verb.infinitive_es, autocapitalize: 'off',
        'aria-label': 'Infinitief (Spaans)', 'data-inf': '',
      });
      const translationInput = el('input', {
        type: 'text', value: verb.translation_nl, autocapitalize: 'off',
        'aria-label': 'Vertaling (Nederlands)', 'data-vert': '',
      });
      const formInputs = {};
      for (const [key, label] of PERSONS) {
        formInputs[key] = el('input', {
          type: 'text', value: verb.forms?.[key] || '', autocapitalize: 'off',
          'aria-label': label, placeholder: label,
        });
      }
      const formStatus = el('p', {class: 'muted', style: 'font-size:0.8rem; margin:0.5rem 0 0'});
      const card = el('div', {class: 'card', 'data-verb': ''},
        el('div', {class: 'row'},
          el('label', {class: 'grow'}, 'Werkwoord (presente)'),
          el('button', {
            class: 'icon-btn fixed', type: 'button', title: 'Werkwoord verwijderen',
            onclick: () => card.remove(),
          }, '🗑️'),
        ),
        el('div', {class: 'row'},
          el('div', {}, el('label', {}, 'Infinitief'), infinitiveInput),
          el('div', {}, el('label', {}, 'Vertaling'), translationInput),
        ),
        el('div', {class: 'row', style: 'margin-top:0.75rem'},
          ...PERSONS.slice(0, 3).map(([key, label]) =>
            el('div', {}, el('label', {}, label), formInputs[key])),
        ),
        el('div', {class: 'row', style: 'margin-top:0.75rem'},
          ...PERSONS.slice(3).map(([key, label]) =>
            el('div', {}, el('label', {}, label), formInputs[key])),
        ),
        formStatus,
      );
      card.readVerb = () => ({
        infinitive_es: infinitiveInput.value.trim(),
        translation_nl: translationInput.value.trim(),
        forms: Object.fromEntries(
          PERSONS.map(([key]) => [key, formInputs[key].value.trim()]),
        ),
      });
      card.setStatus = (text) => { formStatus.textContent = text; };
      if (!verb.forms) {
        formStatus.textContent = 'Vervoegingen ophalen…';
        api(`/api/verbs/conjugate?infinitive=${encodeURIComponent(verb.infinitive_es)}`)
          .then((result) => {
            if (!card.isConnected) return;
            for (const [key] of PERSONS) {
              if (!formInputs[key].value.trim()) formInputs[key].value = result.forms[key];
            }
            formStatus.textContent = 'Vervoegingen opgehaald van Wiktionary — controleer ze even';
            persist();
          })
          .catch((err) => {
            if (!card.isConnected) return;
            formStatus.textContent = `Vervoegingen niet gevonden (${err.message}) — vul ze zelf in`;
            persist();
          });
      } else if (PERSONS.some(([key]) => !verb.forms[key])) {
        formStatus.textContent = 'Nog niet alle vormen ingevuld';
      }
      return card;
    }

    const examplesEditorsWrap = el('div', {}, ...examples.map(exampleEditor));
    const verbsEditorsWrap = el('div', {}, ...verbs.map(verbEditor));

    setChildren(editorsWrap, ...rules.map(ruleEditor));

    // Elke bewerking meteen in het concept bewaren (overleeft refresh);
    // klikken kunnen kaarten of rijen verwijderen, dus even de DOM af laten ronden
    function persist() {
      saveConcept(conceptKey, {
        rules: [...editorsWrap.querySelectorAll('[data-rule]')].map((c) => c.readRule()),
        examples: [...examplesEditorsWrap.querySelectorAll('[data-example]')].map((c) => c.readExample()),
        verbs: [...verbsEditorsWrap.querySelectorAll('[data-verb]')].map((c) => c.readVerb()),
      });
    }
    editorsWrap.addEventListener('input', persist);
    examplesEditorsWrap.addEventListener('input', persist);
    verbsEditorsWrap.addEventListener('input', persist);
    editorsWrap.addEventListener('click', () => setTimeout(persist, 0));
    examplesEditorsWrap.addEventListener('click', () => setTimeout(persist, 0));
    verbsEditorsWrap.addEventListener('click', () => setTimeout(persist, 0));

    const saveButton = el('button', {
      class: 'btn-primary btn-big',
      onclick: async () => {
        const ruleCards = [...editorsWrap.querySelectorAll('[data-rule]')];
        const rulePayloads = ruleCards.map((card) => card.readRule());
        const exampleCards = [...examplesEditorsWrap.querySelectorAll('[data-example]')];
        const exampleTexts = exampleCards.map((card) => card.readExample());
        const verbCards = [...verbsEditorsWrap.querySelectorAll('[data-verb]')];
        const verbPayloads = verbCards.map((card) => card.readVerb());
        if (!rulePayloads.some((rule) => rule.title) && !exampleTexts.some(Boolean)
            && !verbPayloads.some((verb) => verb.infinitive_es)) {
          status.textContent = 'Er is niets om op te slaan.';
          return;
        }
        saveButton.disabled = true;
        againButton.disabled = true;
        try {
          for (const [i, card] of ruleCards.entries()) {
            if (rulePayloads[i].title) {
              await api('/api/grammar', {
                method: 'POST', body: {chapter_id: chapterId, ...rulePayloads[i]},
              });
              card.remove();
            }
          }
          for (const [i, card] of exampleCards.entries()) {
            if (exampleTexts[i]) {
              await api('/api/examples', {
                method: 'POST', body: {chapter_id: chapterId, text: exampleTexts[i]},
              });
              card.remove();
            }
          }
          let incompleet = 0;
          for (const [i, card] of verbCards.entries()) {
            const verb = verbPayloads[i];
            if (!verb.infinitive_es || !verb.translation_nl
                || PERSONS.some(([key]) => !verb.forms[key])) {
              incompleet += 1;
              card.setStatus('Nog niet compleet — vul infinitief, vertaling en alle zes vormen in');
              continue;
            }
            await api('/api/verbs', {
              method: 'POST',
              body: {chapter_id: chapterId, tense: 'presente', ...verb},
            });
            card.remove();
          }
          if (incompleet) {
            persist();
            saveButton.disabled = false;
            againButton.disabled = false;
            status.textContent = `${incompleet} werkwoord${incompleet === 1 ? ' is' : 'en zijn'} nog niet compleet — aanvullen en opnieuw opslaan.`;
            return;
          }
          clearConcept(conceptKey);
          location.hash = `#/h/${chapterId}`;
        } catch (err) {
          persist();  // concept = alleen wat nog niet is opgeslagen
          saveButton.disabled = false;
          againButton.disabled = false;
          status.textContent =
            `Opslaan mislukte: ${err.message}. Het al opgeslagen deel is uit de lijst gehaald — controleer de rest en probeer opnieuw.`;
        }
      },
    }, '💾 Alles opslaan');
    const againButton = el('button', {class: 'btn-ghost', onclick: renderUploadStep}, '📷 Opnieuw');

    const teller = [
      rules.length ? `${rules.length} regel${rules.length === 1 ? '' : 's'}` : null,
      examples.length ? `${examples.length} voorbeeldoefening${examples.length === 1 ? '' : 'en'}` : null,
      verbs.length ? `${verbs.length} werkwoord${verbs.length === 1 ? '' : 'en'}` : null,
    ].filter(Boolean).join(' en ');

    setChildren(container,
      el('p', {class: 'muted'}, `${teller} gelezen — kijk na, pas aan en sla op.`),
      editorsWrap,
      examples.length ? el('div', {class: 'eyebrow'}, 'Voorbeeldoefeningen') : null,
      examplesEditorsWrap,
      verbs.length ? el('div', {class: 'eyebrow'}, 'Werkwoorden') : null,
      verbsEditorsWrap,
      el('div', {class: 'row', style: 'margin-top:0.75rem'},
        el('button', {
          class: 'btn-ghost fixed', type: 'button',
          onclick: () => {
            examplesEditorsWrap.append(exampleEditor(''));
            persist();
          },
        }, '+ voorbeeldoefening'),
        saveButton,
        againButton,
      ),
      status,
    );
  }

  renderUploadStep();
}

import {api, el, setChildren} from '../api.js';
import {clearConcept, loadConcept, saveConcept} from '../concept.js';
import {renderScanStep} from '../scan-step.js';

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
              onclick: () => renderReviewStep(concept.data.rules, concept.data.examples),
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
        const {rules, examples} = await api(`/api/chapters/${chapterId}/lessons/extract`, {
          method: 'POST', body: {images},
        });
        saveConcept(conceptKey, {rules, examples});
        renderReviewStep(rules, examples);
      },
    });
  }

  /* ── Stap 2: nakijken, bewerken en opslaan ── */

  function renderReviewStep(rules, examples) {
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

    const examplesEditorsWrap = el('div', {}, ...examples.map(exampleEditor));

    setChildren(editorsWrap, ...rules.map(ruleEditor));

    // Elke bewerking meteen in het concept bewaren (overleeft refresh);
    // klikken kunnen kaarten of rijen verwijderen, dus even de DOM af laten ronden
    function persist() {
      saveConcept(conceptKey, {
        rules: [...editorsWrap.querySelectorAll('[data-rule]')].map((c) => c.readRule()),
        examples: [...examplesEditorsWrap.querySelectorAll('[data-example]')].map((c) => c.readExample()),
      });
    }
    editorsWrap.addEventListener('input', persist);
    examplesEditorsWrap.addEventListener('input', persist);
    editorsWrap.addEventListener('click', () => setTimeout(persist, 0));
    examplesEditorsWrap.addEventListener('click', () => setTimeout(persist, 0));

    const saveButton = el('button', {
      class: 'btn-primary btn-big',
      onclick: async () => {
        const ruleCards = [...editorsWrap.querySelectorAll('[data-rule]')];
        const rulePayloads = ruleCards.map((card) => card.readRule());
        const exampleCards = [...examplesEditorsWrap.querySelectorAll('[data-example]')];
        const exampleTexts = exampleCards.map((card) => card.readExample());
        if (!rulePayloads.some((rule) => rule.title) && !exampleTexts.some(Boolean)) {
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
    ].filter(Boolean).join(' en ');

    setChildren(container,
      el('p', {class: 'muted'}, `${teller} gelezen — kijk na, pas aan en sla op.`),
      editorsWrap,
      examples.length ? el('div', {class: 'eyebrow'}, 'Voorbeeldoefeningen') : null,
      examplesEditorsWrap,
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

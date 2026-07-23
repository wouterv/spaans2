import {api, el, setChildren} from '../api.js';
import {clearConcept, loadConcept, saveConcept} from '../concept.js';

const MAX_DIM = 2000;

// Verklein in de browser (scheelt upload en API-kosten) en geef base64 terug
async function fileToImagePayload(file) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_DIM / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
  return {media_type: 'image/jpeg', data: dataUrl.split(',')[1]};
}

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

  /* ── Stap 1: scans kiezen en laten uitlezen ── */

  function renderUploadStep() {
    const fileInput = el('input', {
      type: 'file', accept: 'image/*', multiple: '',
      'aria-label': 'Scans van de les',
    });
    const preview = el('div', {class: 'row', style: 'flex-wrap:wrap; gap:0.5rem'});
    const status = el('p', {class: 'muted'});
    const readButton = el('button', {class: 'btn-primary btn-big', disabled: ''},
      '📖 Lees les');
    // Verkleinde foto's bewaren we, zodat een nieuwe poging direct kan versturen
    let cachedImages = null;

    fileInput.addEventListener('change', () => {
      cachedImages = null;
      setChildren(preview, ...[...fileInput.files].map((file) => {
        const img = el('img', {
          src: URL.createObjectURL(file), alt: file.name,
          style: 'max-height:120px; max-width:120px; border-radius:6px',
        });
        img.addEventListener('load', () => URL.revokeObjectURL(img.src));
        return img;
      }));
      if (fileInput.files.length > 10) {
        status.textContent = 'Kies maximaal 10 afbeeldingen tegelijk.';
        readButton.disabled = true;
      } else {
        status.textContent = '';
        readButton.disabled = fileInput.files.length === 0;
      }
    });

    function isNetworkError(err) {
      // Firefox: "NetworkError when attempting…", Chrome: "Failed to fetch",
      // Safari: "Load failed" — allemaal een TypeError uit fetch
      return err instanceof TypeError
        || /NetworkError|Failed to fetch|Load failed/i.test(err.message);
    }

    async function readLesson(attempt) {
      const start = Date.now();
      const ticker = setInterval(() => {
        const seconds = Math.round((Date.now() - start) / 1000);
        status.textContent = `Claude leest de scans… ${seconds}s`
          + (attempt > 1 ? ' (tweede poging)' : ' — dit kan een minuut duren.');
      }, 1000);
      status.textContent = 'Claude leest de scans… dit kan een minuut duren.';
      try {
        const {rules, examples} = await api(`/api/chapters/${chapterId}/lessons/extract`, {
          method: 'POST', body: {images: cachedImages},
        });
        clearInterval(ticker);
        saveConcept(conceptKey, {rules, examples});
        renderReviewStep(rules, examples);
      } catch (err) {
        clearInterval(ticker);
        if (isNetworkError(err) && attempt === 1) {
          status.textContent = 'De verbinding haperde — ik probeer het direct nog een keer…';
          await new Promise((resolve) => setTimeout(resolve, 2000));
          return readLesson(2);
        }
        status.textContent = isNetworkError(err)
          ? 'Netwerkfout — je foto\'s staan nog klaar. Controleer je verbinding en klik nogmaals op "Lees les".'
          : `Lezen mislukte: ${err.message}`;
        readButton.disabled = false;
        fileInput.disabled = false;
      }
    }

    readButton.addEventListener('click', async () => {
      readButton.disabled = true;
      fileInput.disabled = true;
      try {
        if (!cachedImages) {
          const files = [...fileInput.files];
          const images = [];
          for (const [i, file] of files.entries()) {
            status.textContent = `Foto ${i + 1} van ${files.length} verkleinen…`;
            images.push(await fileToImagePayload(file));
          }
          cachedImages = images;
        }
      } catch (err) {
        status.textContent = `Foto verwerken mislukte: ${err.message}`;
        readButton.disabled = false;
        fileInput.disabled = false;
        return;
      }
      await readLesson(1);
    });

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

    setChildren(container,
      conceptBanner,
      el('div', {class: 'card'},
        el('p', {class: 'muted'},
          'Kies één of meer foto\'s of scans van de les. Na het uitlezen kun je alles nakijken en aanpassen voordat het wordt opgeslagen.'),
        fileInput, preview,
        el('div', {class: 'row', style: 'margin-top:0.75rem'}, readButton),
        status,
      ),
    );
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

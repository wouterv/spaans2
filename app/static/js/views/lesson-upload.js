import {api, el, setChildren} from '../api.js';

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

    fileInput.addEventListener('change', () => {
      setChildren(preview, ...[...fileInput.files].map((file) => {
        const img = el('img', {
          src: URL.createObjectURL(file), alt: file.name,
          style: 'max-height:120px; max-width:120px; border-radius:6px',
        });
        img.addEventListener('load', () => URL.revokeObjectURL(img.src));
        return img;
      }));
      readButton.disabled = fileInput.files.length === 0;
    });

    readButton.addEventListener('click', async () => {
      readButton.disabled = true;
      fileInput.disabled = true;
      status.textContent = 'Scans worden gelezen… dit kan een minuut duren.';
      try {
        const images = [];
        for (const file of fileInput.files) images.push(await fileToImagePayload(file));
        const {rules} = await api(`/api/chapters/${chapterId}/lessons/extract`, {
          method: 'POST', body: {images},
        });
        renderReviewStep(rules);
      } catch (err) {
        status.textContent = `Lezen mislukte: ${err.message}`;
        readButton.disabled = false;
        fileInput.disabled = false;
      }
    });

    setChildren(container,
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

  function renderReviewStep(rules) {
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

    setChildren(editorsWrap, ...rules.map(ruleEditor));

    const saveButton = el('button', {
      class: 'btn-primary btn-big',
      onclick: async () => {
        const payloads = [...editorsWrap.querySelectorAll('[data-rule]')]
          .map((card) => card.readRule())
          .filter((rule) => rule.title);
        if (!payloads.length) {
          status.textContent = 'Er is niets om op te slaan.';
          return;
        }
        saveButton.disabled = true;
        try {
          for (const payload of payloads) {
            await api('/api/grammar', {
              method: 'POST', body: {chapter_id: chapterId, ...payload},
            });
          }
          location.hash = `#/h/${chapterId}/grammatica`;
        } catch (err) {
          saveButton.disabled = false;
          status.textContent = `Opslaan mislukte: ${err.message}`;
        }
      },
    }, '💾 Alles opslaan');

    setChildren(container,
      el('p', {class: 'muted'},
        `${rules.length} regel${rules.length === 1 ? '' : 's'} gelezen — kijk na, pas aan en sla op.`),
      editorsWrap,
      el('div', {class: 'row', style: 'margin-top:0.75rem'},
        saveButton,
        el('button', {class: 'btn-ghost', onclick: renderUploadStep}, '📷 Opnieuw'),
      ),
      status,
    );
  }

  renderUploadStep();
}

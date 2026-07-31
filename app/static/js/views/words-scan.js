import {api, el, setChildren} from '../api.js';
import {clearConcept, loadConcept, saveConcept} from '../concept.js';
import {renderScanStep} from '../scan-step.js';

export async function renderWordsScan(view, chapterId) {
  const chapters = await api('/api/chapters');
  const chapter = chapters.find((c) => c.id === chapterId);
  if (!chapter) { location.hash = '#/'; return; }

  const container = el('div', {});
  const conceptKey = `spaans-woorden-concept-${chapterId}`;
  setChildren(view,
    el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, `← ${chapter.name}`)),
    el('h1', {}, 'Woorden scannen'),
    container,
  );

  /* ── Stap 1: scans kiezen (gedeelde module) ── */

  function renderUploadStep() {
    const concept = loadConcept(conceptKey);
    const conceptBanner = concept
      ? el('div', {class: 'card'},
          el('p', {},
            `📝 Er staat nog een niet-opgeslagen woordenlijst van ${new Date(concept.at)
              .toLocaleString('nl-NL', {weekday: 'long', hour: '2-digit', minute: '2-digit'})}.`),
          el('div', {class: 'row'},
            el('button', {
              class: 'btn-primary',
              onclick: () => renderReviewStep(concept.data.words),
            }, '✏️ Verdergaan met nakijken'),
            el('button', {
              class: 'btn-ghost',
              onclick: () => {
                if (confirm('De niet-opgeslagen woordenlijst weggooien?')) {
                  clearConcept(conceptKey);
                  renderUploadStep();
                }
              },
            }, '🗑️ Weggooien'),
          ),
        )
      : null;

    renderScanStep(container, {
      intro: 'Kies foto\'s of scans met woordenlijstjes. Alleen de Spaans-Nederlandse woordparen worden overgenomen; alle andere tekst wordt genegeerd.',
      buttonLabel: '📖 Lees woorden',
      banner: conceptBanner,
      extract: async (images) => {
        const {words} = await api(`/api/chapters/${chapterId}/words/extract`, {
          method: 'POST', body: {images},
        });
        saveConcept(conceptKey, {words});
        renderReviewStep(words);
      },
    });
  }

  /* ── Stap 2: nakijken, bewerken en opslaan ── */

  function renderReviewStep(words) {
    const rowsWrap = el('div', {class: 'card'});
    const status = el('p', {class: 'muted'});

    function wordRow(spanish = '', dutch = '') {
      const row = el('div', {class: 'row', style: 'margin-bottom:0.4rem', 'data-word': ''},
        el('input', {
          type: 'text', value: spanish, autocapitalize: 'off',
          'aria-label': 'Spaans', 'data-es': '',
        }),
        el('input', {
          type: 'text', value: dutch, autocapitalize: 'off',
          'aria-label': 'Nederlands', 'data-nl': '',
        }),
        el('button', {
          class: 'icon-btn fixed', type: 'button', title: 'Woord verwijderen',
          onclick: () => row.remove(),
        }, '✖️'),
      );
      row.readWord = () => ({
        spanish: row.querySelector('[data-es]').value.trim(),
        dutch: row.querySelector('[data-nl]').value.trim(),
      });
      return row;
    }

    setChildren(rowsWrap, ...words.map((w) => wordRow(w.spanish, w.dutch)));

    // Elke bewerking meteen in het concept bewaren (overleeft refresh)
    function persist() {
      saveConcept(conceptKey, {
        words: [...rowsWrap.querySelectorAll('[data-word]')].map((r) => r.readWord()),
      });
    }
    rowsWrap.addEventListener('input', persist);
    rowsWrap.addEventListener('click', () => setTimeout(persist, 0));

    const saveButton = el('button', {
      class: 'btn-primary btn-big',
      onclick: async () => {
        const rows = [...rowsWrap.querySelectorAll('[data-word]')];
        const payloads = rows.map((row) => row.readWord());
        if (!payloads.some((w) => w.spanish && w.dutch)) {
          status.textContent = 'Er is niets om op te slaan.';
          return;
        }
        saveButton.disabled = true;
        againButton.disabled = true;
        try {
          for (const [i, row] of rows.entries()) {
            if (payloads[i].spanish && payloads[i].dutch) {
              await api('/api/words', {
                method: 'POST', body: {chapter_id: chapterId, ...payloads[i]},
              });
              row.remove();
            }
          }
          clearConcept(conceptKey);
          location.hash = `#/h/${chapterId}/woorden`;
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

    setChildren(container,
      el('p', {class: 'muted'},
        `${words.length} woord${words.length === 1 ? '' : 'en'} gelezen — kijk na, pas aan en sla op.`),
      rowsWrap,
      el('div', {class: 'row', style: 'margin-top:0.75rem'},
        el('button', {
          class: 'btn-ghost fixed', type: 'button',
          onclick: () => {
            rowsWrap.append(wordRow());
            persist();
          },
        }, '+ woord'),
        saveButton,
        againButton,
      ),
      status,
    );
  }

  renderUploadStep();
}

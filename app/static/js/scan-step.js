// Gedeelde upload-stap voor scan-flows: bestanden kiezen (max 10),
// thumbnails, verkleinen met voortgang, secondeteller tijdens het lezen,
// automatische herkansing bij een netwerkfout en foto-cache voor een
// handmatige nieuwe poging.

import {el, setChildren} from './api.js';

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

function isNetworkError(err) {
  // Firefox: "NetworkError when attempting…", Chrome: "Failed to fetch",
  // Safari: "Load failed" — allemaal een TypeError uit fetch
  return err instanceof TypeError
    || /NetworkError|Failed to fetch|Load failed/i.test(err.message);
}

// intro: uitlegzin boven de kiezer; buttonLabel: tekst op de leesknop;
// extract(images): doet de API-aanroep en rendert bij succes zelf verder.
export function renderScanStep(container, {intro, buttonLabel, extract, banner = null}) {
  const fileInput = el('input', {
    type: 'file', accept: 'image/*', multiple: '',
    'aria-label': 'Scans',
  });
  const preview = el('div', {class: 'row', style: 'flex-wrap:wrap; gap:0.5rem'});
  const status = el('p', {class: 'muted'});
  const readButton = el('button', {class: 'btn-primary btn-big', disabled: ''},
    buttonLabel);
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

  async function readScans(attempt) {
    const start = Date.now();
    const ticker = setInterval(() => {
      const seconds = Math.round((Date.now() - start) / 1000);
      status.textContent = `Claude leest de scans… ${seconds}s`
        + (attempt > 1 ? ' (tweede poging)' : ' — dit kan een minuut duren.');
    }, 1000);
    status.textContent = 'Claude leest de scans… dit kan een minuut duren.';
    try {
      await extract(cachedImages);
      clearInterval(ticker);
    } catch (err) {
      clearInterval(ticker);
      if (isNetworkError(err) && attempt === 1) {
        status.textContent = 'De verbinding haperde — ik probeer het direct nog een keer…';
        await new Promise((resolve) => setTimeout(resolve, 2000));
        return readScans(2);
      }
      status.textContent = isNetworkError(err)
        ? 'Netwerkfout — je foto\'s staan nog klaar. Controleer je verbinding en probeer het nogmaals.'
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
    await readScans(1);
  });

  setChildren(container,
    banner,
    el('div', {class: 'card'},
      el('p', {class: 'muted'}, intro),
      fileInput, preview,
      el('div', {class: 'row', style: 'margin-top:0.75rem'}, readButton),
      status,
    ),
  );
}

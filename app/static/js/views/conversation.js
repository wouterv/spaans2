import {api, el, setChildren} from '../api.js';
import {clearConcept, loadConcept, saveConcept} from '../concept.js';
import {LANG, canListen, listen, speak, stopListening} from '../speech.js';

// Voorlezen van antwoorden is uitschakelbaar; de keuze wordt onthouden
const VOORLEES_KEY = 'spaans-gesprek-voorlezen';
// De server accepteert max 100 berichten; iets eerder stoppen houdt marge
const MAX_BERICHTEN = 96;

function voorlezenAan() {
  return localStorage.getItem(VOORLEES_KEY) !== 'uit';
}

export async function renderConversation(view, chapterId) {
  const chapters = await api('/api/chapters');
  const chapter = chapters.find((c) => c.id === chapterId);
  if (!chapter) { location.hash = '#/'; return; }

  // De server slaat niets op; de geschiedenis staat lokaal in de browser
  // ({role, text, correction?}) en overleeft zo een refresh
  const gesprekKey = `spaans-gesprek-${chapterId}`;
  const history = loadConcept(gesprekKey)?.data ?? [];
  const persist = () => saveConcept(gesprekKey, history);
  const chat = el('div', {class: 'chat'});
  const status = el('p', {class: 'muted'});

  const input = el('input', {
    type: 'text', autocapitalize: 'off', autocomplete: 'off',
    placeholder: 'Antwoord in het Spaans…', 'aria-label': 'Jouw bericht',
  });
  const sendButton = el('button', {class: 'btn-primary', type: 'submit'}, 'Stuur');
  const micButton = canListen()
    ? el('button', {type: 'button', title: 'Spreek je antwoord in'}, '🎙️')
    : null;

  const inputRow = el('form', {
    class: 'chat-invoer',
    onsubmit: (e) => { e.preventDefault(); sendTurn(); },
  }, input, micButton, sendButton);

  const speakToggle = el('button', {
    type: 'button', class: 'btn-ghost',
    onclick: () => {
      localStorage.setItem(VOORLEES_KEY, voorlezenAan() ? 'uit' : 'aan');
      if (!voorlezenAan()) window.speechSynthesis?.cancel();
      updateSpeakToggle();
    },
  });

  function updateSpeakToggle() {
    speakToggle.textContent = voorlezenAan() ? '🔊 Voorlezen aan' : '🔇 Voorlezen uit';
  }
  updateSpeakToggle();

  const newButton = el('button', {
    type: 'button', class: 'btn-ghost',
    onclick: () => {
      if (input.disabled) return;
      if (history.length && !confirm('Dit gesprek wissen en opnieuw beginnen?')) return;
      clearConcept(gesprekKey);
      history.length = 0;
      setChildren(chat);
      status.textContent = '';
      requestTurn();
    },
  }, '🆕 Nieuw gesprek');

  setChildren(view,
    el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, `← ${chapter.name}`)),
    el('h1', {}, 'Gesprek'),
    el('div', {class: 'row'},
      el('p', {class: 'muted', style: 'flex:1; margin:0'},
        'Praat in het Spaans over de lesstof van dit hoofdstuk. Correcties verschijnen onder je bericht.'),
      newButton,
      speakToggle,
    ),
    chat, inputRow, status,
  );

  function bubble(role, text) {
    const node = el('div', {class: `bubble ${role}`}, text);
    chat.append(node);
    node.scrollIntoView({block: 'end', behavior: 'smooth'});
    return node;
  }

  function setBusy(busy) {
    input.disabled = busy;
    sendButton.disabled = busy;
    if (micButton) micButton.disabled = busy;
  }

  async function requestTurn() {
    setBusy(true);
    const waiting = bubble('partner wachten', '…');
    try {
      const {correction, reply} = await api(
        `/api/chapters/${chapterId}/conversation`,
        // Alleen role/text naar de server; correcties zijn lokale weergave
        {method: 'POST', body: {messages: history.map(({role, text}) => ({role, text}))}},
      );
      waiting.remove();
      if (correction) {
        const lastUser = history.at(-1);
        if (lastUser?.role === 'user') lastUser.correction = correction;
        [...chat.querySelectorAll('.bubble.leerling')].at(-1)
          ?.append(el('span', {class: 'correctie'}, `✏️ ${correction}`));
      }
      history.push({role: 'assistant', text: reply});
      persist();
      bubble('partner', reply);
      status.textContent = '';
      setBusy(false);
      input.focus();
      if (voorlezenAan()) await speak(reply, LANG.es);
    } catch (err) {
      waiting.remove();
      status.textContent = `Er ging iets mis: ${err.message}`;
      // Mislukte beurt: laatste leerling-bericht terug het invoerveld in
      const last = history.at(-1);
      if (last?.role === 'user') {
        history.pop();
        persist();
        [...chat.querySelectorAll('.bubble.leerling')].at(-1)?.remove();
        input.value = last.text;
      }
      setBusy(false);
      input.focus();
    }
  }

  function sendTurn() {
    const text = input.value.trim();
    if (!text || input.disabled) return;
    if (history.length >= MAX_BERICHTEN) {
      status.textContent = 'Dit gesprek zit vol — begin een nieuw gesprek met de 🆕-knop.';
      return;
    }
    stopListening();
    history.push({role: 'user', text});
    persist();
    bubble('leerling', text);
    input.value = '';
    requestTurn();
  }

  micButton?.addEventListener('click', async () => {
    micButton.disabled = true;
    micButton.textContent = '👂';
    const heard = await listen(LANG.es);
    micButton.textContent = '🎙️';
    micButton.disabled = input.disabled;
    if (heard?.[0]) {
      input.value = heard[0];
      input.focus();
    } else {
      status.textContent = 'Ik heb niets gehoord — probeer opnieuw of typ je antwoord.';
    }
  });

  if (history.length) {
    // Hersteld gesprek (refresh of later terugkomen): geschiedenis tonen
    for (const entry of history) {
      const node = bubble(entry.role === 'user' ? 'leerling' : 'partner', entry.text);
      if (entry.correction) {
        node.append(el('span', {class: 'correctie'}, `✏️ ${entry.correction}`));
      }
    }
    input.focus();
  } else {
    // Claude opent het gesprek
    requestTurn();
  }
}

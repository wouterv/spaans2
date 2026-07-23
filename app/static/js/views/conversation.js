import {api, el, setChildren} from '../api.js';
import {LANG, canListen, listen, speak, stopListening} from '../speech.js';

export async function renderConversation(view, chapterId) {
  const chapters = await api('/api/chapters');
  const chapter = chapters.find((c) => c.id === chapterId);
  if (!chapter) { location.hash = '#/'; return; }

  // Geschiedenis leeft alleen in dit scherm; de server slaat niets op
  const history = [];
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

  setChildren(view,
    el('p', {}, el('a', {href: `#/h/${chapterId}`, class: 'muted'}, `← ${chapter.name}`)),
    el('h1', {}, 'Gesprek'),
    el('p', {class: 'muted'}, 'Praat in het Spaans over de lesstof van dit hoofdstuk. Correcties verschijnen onder je bericht.'),
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
        {method: 'POST', body: {messages: history}},
      );
      waiting.remove();
      if (correction) {
        const lastUser = [...chat.querySelectorAll('.bubble.leerling')].at(-1);
        lastUser?.append(el('span', {class: 'correctie'}, `✏️ ${correction}`));
      }
      history.push({role: 'assistant', text: reply});
      bubble('partner', reply);
      status.textContent = '';
      setBusy(false);
      input.focus();
      await speak(reply, LANG.es);
    } catch (err) {
      waiting.remove();
      status.textContent = `Er ging iets mis: ${err.message}`;
      // Mislukte beurt: laatste leerling-bericht terug het invoerveld in
      const last = history.at(-1);
      if (last?.role === 'user') {
        history.pop();
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
    stopListening();
    history.push({role: 'user', text});
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

  // Claude opent het gesprek
  requestTurn();
}

import {el} from '../api.js';

export async function renderPracticeWords(view) {
  view.replaceChildren(el('p', {class: 'muted'}, 'Dit scherm komt eraan.'));
}

import {el} from '../api.js';

export async function renderGrammarEntry(view) {
  view.replaceChildren(el('p', {class: 'muted'}, 'Dit scherm komt eraan.'));
}

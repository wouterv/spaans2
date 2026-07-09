import {el} from '../api.js';

export async function renderGrammarReader(view) {
  view.replaceChildren(el('p', {class: 'muted'}, 'Dit scherm komt eraan.'));
}

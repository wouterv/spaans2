import {el} from '../api.js';

export async function renderVerbsEntry(view) {
  view.replaceChildren(el('p', {class: 'muted'}, 'Dit scherm komt eraan.'));
}

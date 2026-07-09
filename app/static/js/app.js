import {api} from './api.js';
import {renderChapters} from './views/chapters.js';
import {renderChapterHub} from './views/chapter.js';
import {renderWordsEntry} from './views/words-entry.js';
import {renderVerbsEntry} from './views/verbs-entry.js';
import {renderGrammarEntry} from './views/grammar-entry.js';
import {renderGrammarReader} from './views/grammar-reader.js';
import {renderPracticeWords} from './views/practice-words.js';
import {renderPracticeVerbs} from './views/practice-verbs.js';

const view = document.getElementById('view');

const routes = [
  [/^$/, () => renderChapters(view)],
  [/^h\/(\d+)$/, (id) => renderChapterHub(view, +id)],
  [/^h\/(\d+)\/woorden$/, (id) => renderWordsEntry(view, +id)],
  [/^h\/(\d+)\/werkwoorden$/, (id) => renderVerbsEntry(view, +id)],
  [/^h\/(\d+)\/grammatica$/, (id) => renderGrammarEntry(view, +id)],
  [/^h\/(\d+)\/lezen$/, (id) => renderGrammarReader(view, +id)],
  [
    /^h\/(\d+)\/oefen\/woorden\/(es_nl|nl_es)\/(typen|spraak)$/,
    (id, direction, mode) => renderPracticeWords(view, +id, direction, mode),
  ],
  [
    /^h\/(\d+)\/oefen\/werkwoorden\/(typen|spraak)$/,
    (id, mode) => renderPracticeVerbs(view, +id, mode),
  ],
];

async function route() {
  window.speechSynthesis?.cancel();
  const hash = location.hash.replace(/^#\/?/, '');
  for (const [pattern, handler] of routes) {
    const match = hash.match(pattern);
    if (match) {
      view.innerHTML = '';
      try {
        await handler(...match.slice(1));
      } catch (err) {
        view.innerHTML = `<p class="error">Er ging iets mis: ${err.message}</p>`;
      }
      return;
    }
  }
  location.hash = '#/';
}

document.getElementById('logout').addEventListener('click', async () => {
  await api('/api/logout', {method: 'POST'});
  location.href = '/login';
});

window.addEventListener('hashchange', route);
route();

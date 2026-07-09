import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createQueue, shuffle} from '../../app/static/js/queue.js';

const items = ['a', 'b', 'c'];

test('alle items komen precies één keer langs als alles goed is', () => {
  const queue = createQueue(items);
  const seen = [];
  while (queue.current !== null) {
    seen.push(queue.current);
    queue.correct();
  }
  assert.deepEqual(seen, items);
  assert.equal(queue.done, true);
});

test('fout item komt na de gap terug', () => {
  const queue = createQueue(['a', 'b', 'c', 'd', 'e'], {gap: 2});
  assert.equal(queue.current, 'a');
  queue.wrong();
  assert.equal(queue.current, 'b');
  queue.correct();
  assert.equal(queue.current, 'c');
  queue.correct();
  assert.equal(queue.current, 'a'); // na 2 posities terug
});

test('fout item aan het einde komt meteen terug', () => {
  const queue = createQueue(['a'], {gap: 3});
  queue.wrong();
  assert.equal(queue.current, 'a');
  assert.equal(queue.done, false);
});

test('klaar pas als alles een keer goed beantwoord is', () => {
  const queue = createQueue(['a', 'b'], {gap: 3});
  queue.wrong();          // a fout
  assert.equal(queue.done, false);
  queue.correct();        // b goed
  assert.equal(queue.done, false);
  queue.correct();        // a alsnog goed
  assert.equal(queue.done, true);
  assert.equal(queue.current, null);
});

test('voortgang en samenvatting kloppen', () => {
  const queue = createQueue(['a', 'b'], {gap: 3});
  assert.deepEqual(queue.progress, {mastered: 0, total: 2, wrong: 0});
  queue.wrong();   // a
  queue.correct(); // b
  queue.wrong();   // a nog een keer fout
  queue.correct(); // a
  assert.deepEqual(queue.progress, {mastered: 2, total: 2, wrong: 2});
  assert.equal(queue.firstTryCorrect, 1); // alleen b in één keer goed
});

test('lege lijst is meteen klaar', () => {
  const queue = createQueue([]);
  assert.equal(queue.done, true);
  assert.equal(queue.current, null);
});

test('shuffle houdt alle elementen', () => {
  const shuffled = shuffle([1, 2, 3, 4, 5]);
  assert.deepEqual([...shuffled].sort(), [1, 2, 3, 4, 5]);
});

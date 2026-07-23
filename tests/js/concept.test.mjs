import test from 'node:test';
import assert from 'node:assert/strict';
import {saveConcept, loadConcept, clearConcept} from '../../app/static/js/concept.js';

function nepStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
  };
}

test('bewaren en teruglezen', () => {
  const storage = nepStorage();
  saveConcept('sleutel', {rules: [{title: 'Ser'}], examples: ['Completa: ___']}, storage);
  const concept = loadConcept('sleutel', storage);
  assert.equal(concept.data.rules[0].title, 'Ser');
  assert.equal(concept.data.examples[0], 'Completa: ___');
  assert.ok(typeof concept.at === 'number' && concept.at > 0);
});

test('afwezige sleutel geeft null', () => {
  assert.equal(loadConcept('bestaat-niet', nepStorage()), null);
});

test('corrupte opslag geeft null', () => {
  const storage = nepStorage();
  storage.setItem('kapot', 'dit is geen json{');
  assert.equal(loadConcept('kapot', storage), null);
  storage.setItem('half', '"alleen een string"');
  assert.equal(loadConcept('half', storage), null);
});

test('wissen verwijdert het concept', () => {
  const storage = nepStorage();
  saveConcept('sleutel', [1, 2, 3], storage);
  clearConcept('sleutel', storage);
  assert.equal(loadConcept('sleutel', storage), null);
});

import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readable, speakable} from '../../app/static/js/wordtext.js';

test('speakable spreekt alleen het eerste synoniem uit', () => {
  assert.equal(speakable('coche; auto; carro'), 'coche');
});

test('speakable maakt van een geslachtspaar een opsomming met pauze', () => {
  assert.equal(speakable('el primo/la prima'), 'el primo, la prima');
  assert.equal(speakable('el primo / la prima'), 'el primo, la prima');
});

test('speakable combineert synoniem en geslachtspaar', () => {
  assert.equal(speakable('el primo/la prima; el pariente'), 'el primo, la prima');
});

test('speakable laat een gewoon woord met rust', () => {
  assert.equal(speakable('la camisa'), 'la camisa');
});

test('readable toont synoniemen met een puntje', () => {
  assert.equal(readable('coche; auto'), 'coche · auto');
  assert.equal(readable('el primo/la prima; el pariente'), 'el primo/la prima · el pariente');
});

test('readable laat een gewoon woord met rust', () => {
  assert.equal(readable('la camisa'), 'la camisa');
});

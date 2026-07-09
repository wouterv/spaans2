import {test} from 'node:test';
import assert from 'node:assert/strict';
import {pickVoice} from '../../app/static/js/voices.js';

const voice = (name, lang, localService = false) => ({name, lang, localService});

const VOICES = [
  voice('Microsoft Frank - Dutch (Belgium)', 'nl-BE'),
  voice('Google Nederlands', 'nl-NL'),
  voice('Google español', 'es-ES'),
  voice('Google español de Estados Unidos', 'es-US'),
  voice('Lokale stem', 'nl-NL', true),
];

test('kiest nooit een stem van een andere taal', () => {
  assert.equal(pickVoice(VOICES, 'nl-NL')?.lang.startsWith('nl'), true);
  assert.equal(pickVoice(VOICES, 'es-ES')?.lang.startsWith('es'), true);
});

test('exacte taalcode wint van alleen taalprefix', () => {
  const picked = pickVoice(VOICES, 'es-ES');
  assert.equal(picked.name, 'Google español');
});

test('voorkeursnaam uit instellingen wint altijd', () => {
  const picked = pickVoice(VOICES, 'nl-NL', 'Microsoft Frank - Dutch (Belgium)');
  assert.equal(picked.name, 'Microsoft Frank - Dutch (Belgium)');
});

test('voorkeursnaam van verkeerde taal wordt genegeerd', () => {
  const picked = pickVoice(VOICES, 'nl-NL', 'Google español');
  assert.notEqual(picked.name, 'Google español');
});

test('geen stem in de taal beschikbaar geeft null', () => {
  assert.equal(pickVoice([voice('Google español', 'es-ES')], 'nl-NL'), null);
});

test('underscore-taalcodes (Android) worden begrepen', () => {
  const picked = pickVoice([voice('Android NL', 'nl_NL')], 'nl-NL');
  assert.equal(picked?.name, 'Android NL');
});

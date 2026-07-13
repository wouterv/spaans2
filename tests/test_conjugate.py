from pathlib import Path

from app import conjugate

FIXTURES = Path(__file__).parent / "fixtures"

HABLAR_FORMS = {
    "yo": "hablo",
    "tu": "hablas",
    "el": "habla",
    "nosotros": "hablamos",
    "vosotros": "habláis",
    "ellos": "hablan",
}

TENER_FORMS = {
    "yo": "tengo",
    "tu": "tienes",
    "el": "tiene",
    "nosotros": "tenemos",
    "vosotros": "tenéis",
    "ellos": "tienen",
}


def fixture_html(name):
    return (FIXTURES / name).read_text()


class TestParsePresente:
    def test_regelmatig_werkwoord(self):
        assert conjugate.parse_presente(fixture_html("hablar.html")) == HABLAR_FORMS

    def test_onregelmatig_werkwoord_pakt_spaanse_sectie(self):
        # De tener-pagina bevat ook Asturische/Galicische vervoegingstabellen
        assert conjugate.parse_presente(fixture_html("tener.html")) == TENER_FORMS

    def test_pagina_zonder_spaanse_vervoeging(self):
        html = '<h2 id="English">English</h2><p>geen tabel</p>'
        assert conjugate.parse_presente(html) is None

    def test_spaanse_sectie_zonder_tabel(self):
        html = '<h2 id="Spanish">Spanish</h2><p>alleen een zelfstandig naamwoord</p>'
        assert conjugate.parse_presente(html) is None


class TestLookupPresente:
    def test_reflexief_werkwoord_via_basiswerkwoord(self, monkeypatch):
        # De levantarse-pagina heeft geen vervoegingstabel; die staat op levantar
        pages = {
            "levantarse": fixture_html("levantarse.html"),
            "levantar": fixture_html("levantar.html"),
        }
        monkeypatch.setattr(conjugate, "fetch_page_html", pages.get)
        assert conjugate.lookup_presente("levantarse") == {
            "yo": "me levanto",
            "tu": "te levantas",
            "el": "se levanta",
            "nosotros": "nos levantamos",
            "vosotros": "os levantáis",
            "ellos": "se levantan",
        }

    def test_niet_reflexief_geen_basiszoektocht(self, monkeypatch):
        # 'mesa' eindigt niet op -arse/-erse/-irse: geen tweede fetch
        calls = []

        def fake_fetch(infinitive):
            calls.append(infinitive)
            return None

        monkeypatch.setattr(conjugate, "fetch_page_html", fake_fetch)
        assert conjugate.lookup_presente("mesa") is None
        assert calls == ["mesa"]


class TestConjugateEndpoint:
    def test_geeft_vormen_terug(self, client, monkeypatch):
        monkeypatch.setattr(
            conjugate, "fetch_page_html", lambda inf: fixture_html("hablar.html")
        )
        response = client.get("/api/verbs/conjugate?infinitive=hablar")
        assert response.status_code == 200
        assert response.json() == {"tense": "presente", "forms": HABLAR_FORMS}

    def test_onbekend_werkwoord_geeft_404(self, client, monkeypatch):
        monkeypatch.setattr(conjugate, "fetch_page_html", lambda inf: None)
        response = client.get("/api/verbs/conjugate?infinitive=xyzq")
        assert response.status_code == 404

    def test_pagina_zonder_vervoeging_geeft_404(self, client, monkeypatch):
        monkeypatch.setattr(
            conjugate, "fetch_page_html", lambda inf: "<p>geen tabel</p>"
        )
        response = client.get("/api/verbs/conjugate?infinitive=mesa")
        assert response.status_code == 404

    def test_bron_onbereikbaar_geeft_503(self, client, monkeypatch):
        def raise_unavailable(inf):
            raise conjugate.SourceUnavailable("Wiktionary niet bereikbaar")

        monkeypatch.setattr(conjugate, "fetch_page_html", raise_unavailable)
        response = client.get("/api/verbs/conjugate?infinitive=hablar")
        assert response.status_code == 503

    def test_vereist_login(self, anon_client):
        response = anon_client.get("/api/verbs/conjugate?infinitive=hablar")
        assert response.status_code == 401

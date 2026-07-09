def test_index_served_when_logged_in(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_static_assets_are_open(anon_client):
    # Statische assets bevatten geen data; login.html heeft de CSS nodig
    response = anon_client.get("/static/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]

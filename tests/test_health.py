def test_health_get(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Hello, World!" in response.data

def test_health_post(client):
    response = client.post("/")
    assert response.status_code == 200
    assert b"Hello, Post-World!" in response.data

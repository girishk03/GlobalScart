from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_check():
    """
    Verifies the API is alive and responding to basic requests.
    This test is designed to run in all environments (local/CI).
    """
    response = client.get("/")
    # If the app redirects to /shop/, that's also a valid 'alive' signal
    assert response.status_code in [200, 307, 302]
    
    # Check if the response is JSON before attempting to parse it
    if response.status_code == 200:
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            data = response.json()
            if "status" in data:
                assert data["status"] == "ok"
        else:
            # If it's HTML (like the shop page), it's still healthy
            assert response.text.startswith("<!doctype html>") or response.text.startswith("<html")

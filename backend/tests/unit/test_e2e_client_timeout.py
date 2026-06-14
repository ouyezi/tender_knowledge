from e2e.client import LiveClient


def test_live_client_default_upload_timeout():
    client = LiveClient(base_url="http://127.0.0.1:8000", operator_id="admin")
    assert client.upload_timeout == 1800


def test_live_client_custom_upload_timeout():
    client = LiveClient(base_url="http://127.0.0.1:8000", operator_id="admin", upload_timeout=300)
    assert client.upload_timeout == 300

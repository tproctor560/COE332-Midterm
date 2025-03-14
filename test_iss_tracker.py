import pytest
from unittest.mock import patch, MagicMock
import json
from datetime import datetime

# Assuming your functions are in a module named 'iss_tracker'
from iss_tracker import fetch_and_store_iss_data, find_data_point, compute_location_astropy, instantaneous_speed, app, get_redis_client

# Redis Mock
@pytest.fixture
def mock_redis():
    with patch.object(get_redis_client(), 'get') as mock_get, patch.object(get_redis_client(), 'set') as mock_set:
        yield mock_get, mock_set

def test_fetch_and_store_iss_data(mock_redis):
    # Mocking Redis get() and set()
    mock_get, mock_set = mock_redis
    
    # Test case where data is in Redis
    mock_get.return_value = json.dumps({'stateVector': []})
    data = fetch_and_store_iss_data("mock_url", "mock_key")
    assert data == {'stateVector': []}
    
    # Test case where data is not in Redis, simulate fetching from URL
    mock_get.return_value = None
    with patch("iss_tracker.requests.get") as mock_requests:
        mock_requests.return_value.status_code = 200
        mock_requests.return_value.text = "<xml_data>...</xml_data>"
        data = fetch_and_store_iss_data("mock_url", "mock_key")
        assert data is not None
        mock_set.assert_called_once()

def test_find_data_point():
    data = {
        "ndm": {
            "oem": {
                "body": {
                    "segment": {
                        "data": {
                            "stateVector": [
                                {"EPOCH": "2025-03-14T00:00:00", "X": 1.0}
                            ]
                        }
                    }
                }
            }
        }
    }
    
    # Test successful find
    result = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")
    assert result is not None
    assert isinstance(result, list)
    assert len(result) == 1
    
    # Test key not found
    result = find_data_point(data, "ndm", "oem", "body", "segment", "data", "nonexistentKey")
    assert result is None

def test_compute_location_astropy():
    sv = {"X": {"#text": "1.0"}, "Y": {"#text": "2.0"}, "Z": {"#text": "3.0"}, "EPOCH": "2025-03-14T00:00:00"}
    lat, lon, alt = compute_location_astropy(sv)
    assert isinstance(lat, float)
    assert isinstance(lon, float)
    assert isinstance(alt, float)

def test_instantaneous_speed():
    # Test a valid speed calculation
    speed = instantaneous_speed(1.0, 2.0, 3.0)
    assert speed == pytest.approx(3.74166, rel=1e-5)

# Test Flask Routes
@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_epochs(client):
    with patch.object(get_redis_client(), 'get', return_value=json.dumps({"stateVector": []})):
        response = client.get('/epochs')
        assert response.status_code == 200
        assert 'stateVector' in response.get_json()

def test_epoch_speed(client):
    # Mock Redis to simulate the data for a specific epoch
    with patch.object(get_redis_client(), 'get', return_value=json.dumps({"stateVector": [{"EPOCH": "2025-03-14T00:00:00", "X_DOT": {"#text": "1"}, "Y_DOT": {"#text": "2"}, "Z_DOT": {"#text": "3"}}]})):
        response = client.get('/epochs/2025-03-14T00:00:00/speed')
        assert response.status_code == 200
        assert "speed" in response.get_json()

def test_epoch_location(client):
    with patch.object(get_redis_client(), 'get', return_value=json.dumps({"stateVector": [{"EPOCH": "2025-03-14T00:00:00", "X": {"#text": "1.0"}, "Y": {"#text": "2.0"}, "Z": {"#text": "3.0"}}]})):
        response = client.get('/epochs/2025-03-14T00:00:00/location')
        assert response.status_code == 200
        assert "latitude" in response.get_json()
        assert "longitude" in response.get_json()

def test_get_now_data(client):
    # Mock Redis to simulate closest epoch data
    with patch.object(get_redis_client(), 'get', return_value=json.dumps({"stateVector": [{"EPOCH": "2025-03-14T00:00:00", "X": {"#text": "1.0"}, "Y": {"#text": "2.0"}, "Z": {"#text": "3.0"}}]})):
        response = client.get('/now')
        assert response.status_code == 200
        assert "latitude" in response.get_json()
        assert "longitude" in response.get_json()

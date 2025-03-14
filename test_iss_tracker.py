import pytest
import json
from iss_tracker import app, rd  # Import Flask app and Redis client

@pytest.fixture
def client():
    """Create a test client for the Flask app"""
    app.config['TESTING'] = True  # Enable testing mode
    with app.test_client() as client:
        yield client

def test_entire_data(client):
    """Test the /epochs endpoint"""
    response = client.get("/epochs")
    assert response.status_code == 200  # API should return OK
    data = response.get_json()
    assert isinstance(data, list)  # Response should be a list of epochs

def test_entire_data_with_limit_offset(client):
    """Test /epochs with limit and offset query parameters"""
    response = client.get("/epochs?limit=5&offset=2")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) <= 5  # Ensure the limit is applied

def test_state_vector(client):
    """Test the /epochs/<epoch> endpoint"""
    test_epoch = "2025-063T12:34:56.789Z"
    response = client.get(f"/epochs/{test_epoch}") 

    assert response.status_code in [200, 404]  
    
    if response.status_code == 200:
        data = response.get_json()
        assert isinstance(data, dict)  
        assert "EPOCH" in data  
        assert data["EPOCH"] == test_epoch  
    else:
        assert response.get_json()["error"] == "epoch not found" 

def test_get_instantaneous_speed(client):
    """Test the /epochs/<epoch>/speed endpoint"""
    test_epoch = "2025-02-28T12:56:00.000"
    response = client.get(f"/epochs/{test_epoch}/speed")
    
    if response.status_code == 200:
        data = response.get_json()
        assert "speed" in data  # Check if speed key exists
        assert isinstance(data["speed"], float)  # Speed should be a float
    else:
        assert response.status_code == 404  # If epoch is invalid, return 404

def test_get_location(client):
    """Test the /epochs/<epoch>/location endpoint"""
    test_epoch = "2025-02-28T12:56:00.000"
    response = client.get(f"/epochs/{test_epoch}/location")
    
    if response.status_code == 200:
        data = response.get_json()
        
        assert "latitude" in data
        assert "longitude" in data
        assert "altitude" in data
        assert "geoposition" in data  

        assert isinstance(data["latitude"], float)
        assert isinstance(data["longitude"], float)
        assert isinstance(data["altitude"], float)
        assert isinstance(data["geoposition"], (str, type(None)))

    else:
        assert response.status_code == 404  # If epoch is not found, expect 404

def test_get_now_data(client):
    """Test the /now endpoint"""
    response = client.get("/now")

    if response.status_code == 200:
        data = response.get_json()

        assert "latitude" in data
        assert "longitude" in data
        assert "altitude" in data
        assert "geoposition" in data  

        assert isinstance(data["latitude"], float)
        assert isinstance(data["longitude"], float)
        assert isinstance(data["altitude"], float)
        assert isinstance(data["geoposition"], (str, type(None)))  # Can be a string or None

    else:
        assert response.status_code in [404, 500]

def test_redis_data_population(client):
    """Test that the Redis database is populated with data on startup if empty"""
    # Check if the Redis database is populated with ISS data if empty
    redis_data = rd.get('epochs')  # Assuming you store the data under 'epochs' key
    assert redis_data is not None, "Data should be loaded into Redis"
    
    # Test that data is loaded properly by verifying the presence of some expected key or value
    # Replace 'some_key' with an actual key you expect to exist
    assert rd.hget('epochs', 'some_key') is not None, "Epoch data not loaded correctly"

def test_redis_backup(client):
    """Test that Redis stores data backups in the local ./data directory"""
    # Assuming backups are stored in a directory and the Redis container has access to this
    backup_data = rd.get('backup')  # Assuming 'backup' is where backups are stored
    assert backup_data is not None, "Redis should store data backups"

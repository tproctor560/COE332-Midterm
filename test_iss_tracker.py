import unittest
from app import app, rd
import json
from unittest.mock import patch

class TestISSTrackerApp(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Set up the Flask test client and Redis mock."""
        cls.client = app.test_client()

    @patch.object(rd, 'get', return_value=json.dumps({
        'ndm': {
            'oem': {
                'body': {
                    'segment': {
                        'data': {
                            'stateVector': [{
                                'EPOCH': '2025-069T12:32:00.000Z',
                                'X': {'#text': '4000'},
                                'Y': {'#text': '5000'},
                                'Z': {'#text': '6000'},
                                'X_DOT': {'#text': '0.1'},
                                'Y_DOT': {'#text': '0.1'},
                                'Z_DOT': {'#text': '0.1'}
                            }]
                        }
                    }
                }
            }
        }
    }))  # Mock Redis with fake data
    def test_fetch_and_store_iss_data_with_cache(self, mock_get):
        """Test fetching ISS data when data is in Redis cache."""
        response = self.client.get('/epochs')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(len(data) > 0)
    
    @patch.object(rd, 'get', return_value=json.dumps({'ndm': {'oem': {'body': {'segment': {'data': {'stateVector': [{'EPOCH': '2025-069T12:32:00.000Z', 'X': {'#text': '4000'}, 'Y': {'#text': '5000'}, 'Z': {'#text': '6000'}, 'X_DOT': {'#text': '0.1'}, 'Y_DOT': {'#text': '0.1'}, 'Z_DOT': {'#text': '0.1'}}}]}}}}}}))  # Mock Redis with fake data
    def test_get_epoch(self, mock_get):
        """Test retrieving state vector data for a specific epoch."""
        response = self.client.get('/epochs/2025-069T12:32:00.000Z')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['EPOCH'], '2025-069T12:32:00.000Z')
    
    @patch.object(rd, 'get', return_value=json.dumps({'ndm': {'oem': {'body': {'segment': {'data': {'stateVector': [{'EPOCH': '2025-069T12:32:00.000Z', 'X': {'#text': '4000'}, 'Y': {'#text': '5000'}, 'Z': {'#text': '6000'}, 'X_DOT': {'#text': '0.1'}, 'Y_DOT': {'#text': '0.1'}, 'Z_DOT': {'#text': '0.1'}}}]}}}}}}))  # Mock Redis with fake data
    def test_get_instantaneous_speed(self, mock_get):
        """Test retrieving the instantaneous speed for a given epoch."""
        response = self.client.get('/epochs/2025-069T12:32:00.000Z/speed')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('speed', data)
        self.assertIsInstance(data['speed'], float)
    
    @patch.object(rd, 'get', return_value=json.dumps({'ndm': {'oem': {'body': {'segment': {'data': {'stateVector': [{'EPOCH': '2025-069T12:32:00.000Z', 'X': {'#text': '4000'}, 'Y': {'#text': '5000'}, 'Z': {'#text': '6000'}, 'X_DOT': {'#text': '0.1'}, 'Y_DOT': {'#text': '0.1'}, 'Z_DOT': {'#text': '0.1'}}}]}}}}}}))  # Mock Redis with fake data
    def test_get_location(self, mock_get):
        """Test retrieving the location (latitude, longitude, altitude) for a given epoch."""
        response = self.client.get('/epochs/2025-069T12:32:00.000Z/location')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('latitude', data)
        self.assertIn('longitude', data)
        self.assertIn('altitude', data)
    
    @patch.object(rd, 'get', return_value=json.dumps({'ndm': {'oem': {'body': {'segment': {'data': {'stateVector': [{'EPOCH': '2025-069T12:32:00.000Z', 'X': {'#text': '4000'}, 'Y': {'#text': '5000'}, 'Z': {'#text': '6000'}, 'X_DOT': {'#text': '0.1'}, 'Y_DOT': {'#text': '0.1'}, 'Z_DOT': {'#text': '0.1'}}}]}}}}}}))  # Mock Redis with fake data
    def test_get_now_data(self, mock_get):
        """Test retrieving the location for the closest epoch to the current time."""
        response = self.client.get('/now')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('latitude', data)
        self.assertIn('longitude', data)
        self.assertIn('altitude', data)
    
    @patch.object(rd, 'get', return_value=None)  # Mock Redis to simulate no data in cache
    def test_get_now_data_no_data(self, mock_get):
        """Test retrieving the current data when there is no data in Redis."""
        response = self.client.get('/now')
        self.assertEqual(response.status_code, 500)

if __name__ == '__main__':
    unittest.main()

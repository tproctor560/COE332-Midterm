import requests
import math
import xmltodict
from datetime import datetime, timezone
import logging
import unittest
from flask import Flask, request, jsonify
import json
import redis
import time
from astropy import coordinates
from astropy import units
from astropy.time import Time
from geopy.geocoders import Nominatim

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

def get_redis_client():
    return redis.Redis(host="redis-db", port=6379, decode_responses=True)

rd = get_redis_client()

ISS_data = "iss_state_vector_data"
ISS_XML_URL = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"

def fetch_and_store_iss_data():
    """
    Fetches ISS data from the XML URL, parses it, and stores it in Redis.
    """
    try:
        response = requests.get(ISS_XML_URL)
        if response.status_code == 200:
            data = xmltodict.parse(response.text)
            json_data = json.dumps(data)  # Convert to JSON string for Redis storage
            rd.set(ISS_data, json_data)
            logging.info("ISS data successfully fetched and stored in Redis.")
        else:
            logging.error(f"Failed to fetch ISS data. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")

@app.route('/debug-cache', methods=['GET'])
def debug_cache():
    """
    Debug endpoint to check if ISS data is in Redis. If missing, fetches and stores it.
    """
    data = rd.get(ISS_data)
    if data:
        logging.info(f"Data found in Redis: {data}")
        return jsonify({"status": "found", "data": json.loads(data)})
    else:
        logging.info("Data not found in Redis. Fetching new data...")
        fetch_and_store_iss_data()
        return jsonify({"status": "not found"}), 404
def url_xml_pull(url: str):
    """
    Fetches XML data from a URL and stores it in Redis if not already cached.
    """
    data = rd.get(ISS_data)
    if data:
        logging.info("Data retrieved from Redis cache.")
        return json.loads(data)

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = xmltodict.parse(response.text)
            json_data = json.dumps(data)
            rd.set(ISS_data, json_data)  # Cache the data in Redis
            logging.info(f"Data successfully retrieved and stored from {url}")
            return data
        else:
            logging.error(f"Failed to retrieve data from {url}. Status code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"RequestException: Failed to fetch data from {url} due to: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in url_xml_pull: {e}")
        return None

def read_data_from_xml(filepath: str):
    """
    Reads and parses XML data from a local file (fallback method).
    """
    try:
        with open(filepath, "r") as f:
            data = xmltodict.parse(f.read())
        return data
    except Exception as e:
        logging.error(f"Error reading XML file: {e}")
        return None

def find_data_point(data, *keys):
    """
    Extracts nested values from a JSON-like dictionary using a sequence of keys.
    """
    current = data
    try:
        for key in keys:
            if isinstance(current, dict):
                if key in current:
                    current = current[key]
                else:
                    logging.error(f"Key '{key}' not found in data structure")
                    return None
            else:
                logging.error(f"Expected dictionary, got {type(current).__name__}")
                return None
        return current
    except (KeyError, IndexError, ValueError, AttributeError) as e:
        logging.error(f"Error accessing data: {e}")
        return None
        
def compute_location_astropy(sv):
    # Extract the state vector coordinates
    x = float(sv['X']['#text'])
    y = float(sv['Y']['#text'])
    z = float(sv['Z']['#text'])
    
    # Parse the timestamp from the epoch
    this_epoch = time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(sv['EPOCH'][:-5], '%Y-%jT%H:%M:%S'))

    # Create a CartesianRepresentation
    cartrep = coordinates.CartesianRepresentation([x, y, z], unit=units.km)
    gcrs = coordinates.GCRS(cartrep, obstime=this_epoch)
    itrs = gcrs.transform_to(coordinates.ITRS(obstime=this_epoch))
    
    # Get EarthLocation in ITRS coordinates
    loc = coordinates.EarthLocation(*itrs.cartesian.xyz)

    return loc.lat.value, loc.lon.value, loc.height.value
    
def get_geolocation(lat, lon):
    geocoder = Nominatim(user_agent="iss_tracker")
    geoloc = geocoder.reverse((lat, lon), zoom=2, language='en')
    
    # Return the name of the location or None if not found
    if geoloc:
        return geoloc.address
    return None


def instantaneous_speed(x: float, y: float, z: float) -> float:
    """
    This function is a helper function to find the instantaneous speed of an object given it's velocity vectors
    
    Args:
        x, y, z (float): the x, y, z velocity vectors
    
    Returns:
        float: the speed
    """
    return math.sqrt((x**2) + (y**2) + (z**2))

@app.route('/epochs', methods = ['GET'])
def entire_data():
    """
    This function returns the enitre data set from the epoch summary
    
    Args:
        None
    Returns:  
        A list of the entire data
    """
    cached_data = rd.get(ISS_data)

    if cached_data:
        data = json.loads(cached_data)  # Convert stored JSON string back to Python object
        list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")

        try:
            limit = int(request.args.get('limit', len(list_of_data)))  # Default: all data
            offset = int(request.args.get('offset', 0))  # Default: start at 0
            
            # Ensure offset isn't out of bounds
            if offset >= len(list_of_data):
                return jsonify([])  # Return an empty list if offset is too large
            
            # Limit should not exceed available data
            limit = min(limit, len(list_of_data))

            return jsonify(list_of_data[offset:offset + limit])

        except ValueError as e:
            return jsonify({"error": "Invalid limit or offset parameter"}), 400

    return jsonify({"error": "ISS data not found in cache"}), 404


@app.route('/epochs/<epoch>', methods = ['GET'])
def state_vector(epoch):
    """
    This function retruns the state vectors for a given, specified Epoch from the data set

    Args: Epoch (str): an epoch id in the form of a string

    Returns: 
        A dict that represents that datapoint or a string stating the specificed epoch was not in the dataset
    """

    cached_data = rd.get(ISS_data)

    if cached_data:
        data = json.loads(cached_data)  # Convert stored JSON string back to Python object
        list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")

        for i in list_of_data:
            if i["EPOCH"] == epoch:
                return jsonify(i)

    return jsonify({"error": "Epoch not found"}), 404

@app.route('/epochs/<epoch>/speed', methods=['GET'])
def get_instantaneous_speed(epoch):
    """
    This function returns the instantaneous speed at a given epoch

    Args: epoch(str), the epoch given as a string

    Returns: the integer for instant speed, or a string saying the epoch cannot be found
    """
    cached_data = rd.get(ISS_data)

    if cached_data:
        data = json.loads(cached_data)  # Convert stored JSON string back to Python object
        list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")

    for i in list_of_data:
        if i["EPOCH"] == epoch:
            speed = instantaneous_speed(
                float(i["X_DOT"]["#text"]),
                float(i["Y_DOT"]["#text"]),
                float(i["Z_DOT"]["#text"])
            )
            return jsonify({"epoch": epoch, "speed": speed}) 
    return jsonify({"error": "epoch not found"}), 404

@app.route('/epochs/<epoch>/location', methods=['GET'])
def location(epoch):
    """
    This function returns the latitude, longitude, altitude, and geoposition for the given epoch.
    """
    cached_data = rd.get(ISS_data)

    if cached_data:
        data = json.loads(cached_data)  # Convert stored JSON string back to Python object
        list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")
    else:
        return jsonify({"error": "No ISS data available"}), 500 

    if list_of_data:
        for sv in list_of_data:
            if sv["EPOCH"] == epoch:
                lat, lon, alt = compute_location_astropy(sv)
                geoloc = get_geolocation(lat, lon) 

                return jsonify({
                    "latitude": lat,
                    "longitude": lon,
                    "altitude": alt
                })
    
    return jsonify({"error": "Data not found for the specified epoch"}), 404

    
@app.route('/now', methods=['GET'])
def get_now_data():
    """
    This function returns the location (latitude, longitude, altitude, and geoposition)
    for the closest epoch to the current time.
    """
    cached_data = rd.get(ISS_data)  # Fetch cached data from Redis

    if cached_data:
        data = json.loads(cached_data)  # Convert stored JSON string back to Python object
        list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")
    else:
        # If no data in cache, return an error
        return jsonify({"error": "No ISS data available"}), 500 

    if not list_of_data:
        # If no state vector data found, return error
        return jsonify({"error": "No state vector data found"}), 404 

    now = time.mktime(time.gmtime())  # Current time in seconds since the epoch
    closest_epoch = None
    closest_time_diff = float("inf")  # Initialize with an infinite value

    for sv in list_of_data:
        try:
            # Parse the EPOCH and calculate the time difference from now
            epoch_time = time.mktime(time.strptime(sv["EPOCH"], "%Y-%jT%H:%M:%S.000Z"))
            time_diff = abs(now - epoch_time)

            # Update closest_epoch if the current epoch is closer to the current time
            if time_diff < closest_time_diff:
                closest_time_diff = time_diff
                closest_epoch = sv
        except ValueError: 
            logging.error(f"Invalid date format for epoch: {sv['EPOCH']}")  # Log any invalid date formats
            continue

    if not closest_epoch:
        # If no closest epoch found, return an error
        return jsonify({"error": "No valid epochs found"}), 500
    
    lat, lon, alt = compute_location_astropy(closest_epoch)  # Compute location
    geoloc = get_geolocation(lat, lon)  # Get geolocation info

    # Return the location details
    return jsonify({
        "latitude": lat,
        "longitude": lon,
        "altitude": alt,
        "geoposition": geoloc if geoloc else "ISS is over the ocean"  # Fallback if no geolocation is found
    })
    
def main():

    """
    Main function that pulls the ISS data using the url below and then runs the above functions if the data pull is successful
    """

    url = 'https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml'
    data = url_xml_pull(url)

    if data:
        #Call the functions with the fetched data
        epoch_range(data)
        current_epoch(data)
        avg_speed(data)
    else:
        logging.error("No data fetched, exiting main.")

if __name__ == "__main__":
    # main()
    app.run(debug=True, host='0.0.0.0')

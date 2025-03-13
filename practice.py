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


@app.before_first_request
def startup():
    load_iss_data()

def load_iss_data():
    if redis_client.exists("iss_data"):
        print("Data found in Redis, skipping download.")
        return
    
    response = requests.get(ISS_DATA_URL)
    if response.status_code == 200:
        data = response.json()
        redis_client.set("iss_data", json.dumps(data))
        print("ISS data loaded into Redis.")





import requests
import math
import xmltodict
from datetime import datetime, timezone
import logging
import time
from flask import Flask, request, jsonify
from geopy.geocoders import Nominatim
from astropy import coordinates
from astropy import units
from astropy.time import Time

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)

def url_xml_pull(url: str):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = xmltodict.parse(response.text)
            logging.info(f"Data successfully retrieved from {url}")
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


def find_data_point(data, *keys):
    current = data
    try:
        for key in keys:
            if isinstance(current, dict):
                if key in current:
                    current = current[key]
                else:
                    print(f"Key '{key}' not found in data structure")
                    return None
            else:
                print(f"Expected dictionary, got {type(current).__name__}")
                return None
        return current
    except Exception as e:
        logging.error(f"Error in find_data_point: {e}")
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


@app.route('/epochs/<epoch>/location', methods=['GET'])
def location(epoch):
    """
    This function returns the latitude, longitude, altitude, and geoposition for the given epoch.
    """
    url = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"
    data = url_xml_pull(url)
    list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")
    
    for sv in list_of_data:
        if sv["EPOCH"] == epoch:
            lat, lon, alt = compute_location_astropy(sv)
            geoloc = get_geolocation(lat, lon)
            return jsonify({
                "latitude": lat,
                "longitude": lon,
                "altitude": alt,
                "geoposition": geoloc
            })
    
    return jsonify({"error": "epoch not found"}), 404


@app.route('/now', methods=['GET'])
def get_now_data():
    """
    This function returns the location (latitude, longitude, altitude, and geoposition)
    for the closest epoch to the current time.
    """
    url = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"
    data = url_xml_pull(url)
    
    if not data:
        return jsonify({"error": "Failed to retrieve data"}), 500

    list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")
    
    if not list_of_data:
        return jsonify({"error": "No state vector data found"}), 404 

    now = time.mktime(time.gmtime())
    closest_epoch = None
    closest_time_diff = float("inf")  

    for sv in list_of_data:
        try:
            epoch_time = time.mktime(time.strptime(sv["EPOCH"], "%Y-%jT%H:%M:%S.000Z"))
            time_diff = abs(now - epoch_time)

            if time_diff < closest_time_diff:
                closest_time_diff = time_diff
                closest_epoch = sv
        except ValueError: 
            logging.error(f"Invalid date format for epoch: {sv['EPOCH']}")
            continue

    if not closest_epoch:
        return jsonify({"error": "No valid epochs found"}), 500
    
    lat, lon, alt = compute_location_astropy(closest_epoch)
    geoloc = get_geolocation(lat, lon)

    return jsonify({
        "latitude": lat,
        "longitude": lon,
        "altitude": alt,
        "geoposition": geoloc
    })


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')

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
redis_client = redis.Redis(host="redis-db", port=6379, decode_responses=True)
logging.basicConfig(level=logging.DEBUG)

ISS_DATA_URL = "https://api.wheretheiss.at/v1/satellites/25544"

def url_xml_pull(url: str):

    """
    Pulls the url in the main function and determines if it was successful or not
    """
    data = redis_client.get(f"iss_data_{url}")
    if data:
        logging.info("Data retrieved from Redis cache.")
        return json.loads(data)
        
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
        

def read_data_from_xml(filepath: str):
    """
    This function is a fail-safe in case the user cannot import the data through requests
    
    Args:
        filepath (str): the filepath to the xml data
        
    Returns:
        the data as a JSON
    
    (No tests will be written for this function as it's a fail-safe)
    """
    with open(filepath, "r") as f:
        data = xmltodict.parse(f.read())
        
    return data
    
def find_data_point(data, *keys):
    """
    The following argument will take in some data in the form of a json string, as well as strings that represent the location of the time stamps and epoch times
    
    Args:
        data: a json object
        *args: a list of strings that points to the location of the data within a json datatype
    
    Returns:
        Either the data, or a null return if the data is not found
    """
    
    current = data
    
    try:
        for key in keys:
        
            if isinstance(current, dict):
                if key in current:
                    current = current[key]
                else:
                    print(f"Key '{key}' not found in data structure")
                    return None  # Or handle the missing key differently
            else:
                print(f"Expected dictionary, got {type(current).__name__}")
                return None
        return current
        
    except KeyError:
        logging.error(f"Key Error at find_data_point")
        raise KeyError()
 
    except IndexError:
        logging.error(f"Index Error at find_data_point")
        raise IndexError()
    
    except ValueError:
        logging.error(f"Value Error at find_data_point")
        raise ValueError()
    
    except AttributeError:
        logging.error(f"Attribute Error at find_data_point")
        raise AttributeError()
    

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
    url = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"
    data = url_xml_pull(url)
    list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")
    try:
        limit = int(request.args.get('limit', '100000000000000'))
        offset = int(request.args.get('offset', '0'))
        
        ret_degree = []
        if limit > len(list_of_data):
            limit = len(list_of_data)
        
        for i in range(offset, limit):
            ret_degree.append(list_of_data[i])
        
        return ret_degree
        
    except ValueError as e:
        return str(e)


@app.route('/epochs/<epoch>', methods = ['GET'])
def state_vector(epoch):
    """
    This function retruns the state vectors for a given, specified Epoch from the data set

    Args: Epoch (str): an epoch id in the form of a string

    Returns: 
        A dict that represents that datapoint or a string stating the specificed epoch was not in the dataset
    """

    url = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"
    data = url_xml_pull(url)
    list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")
    for i in list_of_data:
        if i["EPOCH"] == epoch:
            return jsonify(i)
    return "error, epoch not found"

@app.route('/epochs/<epoch>/speed', methods=['GET'])
def get_instantaneous_speed(epoch):
    """
    This function returns the instantaneous speed at a given epoch

    Args: epoch(str), the epoch given as a string

    Returns: the integer for instant speed, or a string saying the epoch cannot be found
    """
    data = redis_client.get("iss_state_vector_data")
    if not data:
        url = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"
        data = url_xml_pull(url)
        redis_client.set("iss_state_vector_data", json.dumps(data), ex=3600)

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
    data = redis_client.get("iss_state_vector_data")
    if not data:
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
                "geoposition": geoloc if geoloc else "ISS is over the ocean"
            })
    
    return jsonify({"error": "epoch not found"}), 404

    
@app.route('/now', methods=['GET'])
def get_now_data():
    """
    This function returns the location (latitude, longitude, altitude, and geoposition)
    for the closest epoch to the current time.
    """
    data = redis_client.get("iss_state_vector_data")
    if not data:
        url = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"
        data = url_xml_pull(url)
        redis_client.set("iss_state_vector_data", json.dumps(data), ex=3600)
    
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

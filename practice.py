import requests  # For making HTTP requests
import math  # For mathematical functions, e.g., sqrt in speed calculation
import xmltodict  # For parsing XML data into Python dictionaries
from datetime import datetime, timezone  # For working with date and time
import logging  # For logging messages
import unittest  # For unit testing (though it's not used in the provided code)
from flask import Flask, request, jsonify  # Flask web framework
import json  # For working with JSON data
import time  # For time-related functions, like timestamps
from astropy import coordinates  # For astropy coordinate transformations
from astropy import units  # For astropy unit handling
from astropy.time import Time  # For handling time in astropy
from geopy.geocoders import Nominatim
app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)

def compute_location_astropy(sv):
    x = float(sv['X']['#text'])
    y = float(sv['Y']['#text'])
    z = float(sv['Z']['#text'])

    # assumes epoch is in format '2024-067T08:28:00.000Z'
    this_epoch=time.strftime('%Y-%m-%d %H:%m:%S', time.strptime(sv['EPOCH'][:-5], '%Y-%jT%H:%M:%S'))

    cartrep = coordinates.CartesianRepresentation([x, y, z], unit=units.km)
    gcrs = coordinates.GCRS(cartrep, obstime=this_epoch)
    itrs = gcrs.transform_to(coordinates.ITRS(obstime=this_epoch))
    loc = coordinates.EarthLocation(*itrs.cartesian.xyz)

    return loc.lat.value, loc.lon.value, loc.height.value
    
@app.route('/epochs/<epoch>/location', methods=['GET'])
def location_finder(epoch):
    """
    Returns the latitude, longitude, altitude, and geoposition of the ISS for a given epoch.
    """
    url = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"
    data = url_xml_pull(url)
    list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")

    if not list_of_data:
        return jsonify({"error": "No state vector data found"}), 404

    for sv in list_of_data:
        if sv["EPOCH"] == epoch:
            latitude, longitude, altitude = compute_location_astropy(sv)

            # Use GeoPy to get location name from lat/lon
            geolocator = Nominatim(user_agent="iss_tracker")
            location = geolocator.reverse((latitude, longitude), language="en", zoom=5)
            geoposition = location.address if location else "Unknown location"

            return jsonify({
                "epoch": epoch,
                "latitude": latitude,
                "longitude": longitude,
                "altitude_km": altitude,
                "geoposition": geoposition
            })

    return jsonify({"error": "Epoch not found"}), 404


@app.route('/now', methods=['GET'])
def get_now_data():
    """
    This function returns the epoch that is closest to the current time and provides the 
    real-time location of the ISS using the compute_location_astropy function.

    Args: none
        
    Returns: a dictionary with the state vector and location information (latitude, longitude, height)
    """
    url = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"
    data = url_xml_pull(url)
    if not data:
        return jsonify({"error": "Failed to retrieve data"}), 500

    list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")
    
    if not list_of_data:
        return jsonify({"error": "No state vector data found"}), 404 

    now = datetime.now(timezone.utc).timestamp()  
    closest_epoch = None
    closest_time_diff = float("inf")  

    for sv in list_of_data:
        try:
            epoch_time = datetime.strptime(sv["EPOCH"], "%Y-%jT%H:%M:%S.%fZ").timestamp()
            time_diff = abs(now - epoch_time)

            if time_diff < closest_time_diff:
                closest_time_diff = time_diff
                closest_epoch = sv
        except ValueError: 
            logging.error(f"Invalid date format for epoch: {sv['EPOCH']}")
            continue      
    
    if not closest_epoch:
        return jsonify({"error": "No valid epochs found"}), 500

    # Use the compute_location_astropy function to get the location
    location = compute_location_astropy(closest_epoch)

    return jsonify({
        "state_vector": closest_epoch,
        "location": {
            "latitude": location[0],
            "longitude": location[1],
            "height": location[2]
        }
    })
def url_xml_pull(url: str):
    """
    Pulls the url in the main function and determines if it was successful or not
    """
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
    """
    Find the data from a json structure based on the keys provided
    
    Args:
        data: json object
        *keys: list of strings for keys
    
    Returns:
        The desired data or None if not found
    """
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


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')

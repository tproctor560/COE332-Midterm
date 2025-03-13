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

from datetime import datetime, timedelta

from datetime import datetime, timedelta

def compute_location_astropy(sv):
    x = float(sv['X']['#text'])
    y = float(sv['Y']['#text'])
    z = float(sv['Z']['#text'])

    # Extract the year and day of year
    try:
        # Get the year and day of year (e.g., '2025-084T11:50:30.000Z')
        year = int(sv['EPOCH'][:4])  # e.g., '2025'
        doy = int(sv['EPOCH'][5:8])  # e.g., '084' (day of year)
        time_str = sv['EPOCH'][9:-5]  # e.g., 'T11:50:30.000'
        
        # Convert day-of-year to a date
        start_of_year = datetime(year, 1, 1)
        date = start_of_year + timedelta(days=doy - 1)  # Convert DDD to actual date
        
        # Combine date with time part
        full_datetime_str = date.strftime('%Y-%m-%d') + time_str  # e.g., '2025-03-25T11:50:30.000'
        
        # Parse it into a full datetime object, ensuring to remove 'Z' at the end for correct parsing
        full_datetime_str = full_datetime_str.rstrip('Z')
        dt = datetime.strptime(full_datetime_str, '%Y-%m-%dT%H:%M:%S.%f')  # Include milliseconds
        
        # Convert to ISO 8601 format and add 'Z' back
        this_epoch = dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')  # '2025-03-25T11:50:30.000Z'
        
    except ValueError:
        raise ValueError(f"Invalid date format for epoch: '{sv['EPOCH']}'")

    # Astropy conversion (the same as before)
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
    Returns the real-time latitude, longitude, altitude, and geoposition of the ISS.
    """
    url = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"
    data = url_xml_pull(url)
    if not data:
        return jsonify({"error": "Failed to retrieve data"}), 500

    list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")

    if not list_of_data:
        return jsonify({"error": "No state vector data found"}), 404 

    now = time.time()  # Get the current time in UTC
    closest_epoch = None
    closest_time_diff = float("inf")

    for sv in list_of_data:
        try:
            fixed_epoch = sv["EPOCH"].replace("T", " ").replace("Z", "")  # Fix format
            epoch_time = Time(fixed_epoch, format="iso", scale="utc").unix  # Convert to UNIX timestamp using Astropy

            time_diff = abs(now - epoch_time)

            if time_diff < closest_time_diff:
                closest_time_diff = time_diff
                closest_epoch = sv
        except ValueError: 
            logging.error(f"Invalid date format for epoch: {repr(sv['EPOCH'])}")
            continue      

    if not closest_epoch:
        return jsonify({"error": "No valid epochs found"}), 500

    # Compute latitude, longitude, altitude using Astropy
    latitude, longitude, altitude = compute_location_astropy(closest_epoch)

    # Use GeoPy to get location name from lat/lon (handle possible errors)
    geolocator = Nominatim(user_agent="iss_tracker")
    try:
        location = geolocator.reverse((latitude, longitude), language="en", zoom=5)
        geoposition = location.address if location else "Unknown location"
    except Exception as e:
        logging.error(f"GeoPy reverse lookup failed: {e}")
        geoposition = "Unknown location"

    return jsonify({
        "epoch": closest_epoch["EPOCH"],
        "latitude": latitude,
        "longitude": longitude,
        "altitude_km": altitude,
        "geoposition": geoposition
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

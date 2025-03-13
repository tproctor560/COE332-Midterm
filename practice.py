import requests
import xmltodict
from datetime import datetime
import logging
from flask import Flask, request, jsonify
from astropy import coordinates
from astropy import units
from geopy.geocoders import Nominatim

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)

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
    Finds a specific data point in the JSON structure
    """
    current = data
    try:
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                logging.error(f"Key '{key}' not found")
                return None
        return current
    except Exception as e:
        logging.error(f"Error finding data point: {e}")
        return None


def compute_location_astropy(sv):
    x = float(sv['X']['#text'])
    y = float(sv['Y']['#text'])
    z = float(sv['Z']['#text'])

    # Extract the DOY format epoch and keep it as is
    epoch_doy = sv['EPOCH']
    
    # Astropy conversions, assuming the epoch is already in the desired format
    cartrep = coordinates.CartesianRepresentation([x, y, z], unit=units.km)
    gcrs = coordinates.GCRS(cartrep, obstime=epoch_doy)
    itrs = gcrs.transform_to(coordinates.ITRS(obstime=epoch_doy))
    loc = coordinates.EarthLocation(*itrs.cartesian.xyz)

    return loc.lat.value, loc.lon.value, loc.height.value


@app.route('/epochs', methods=['GET'])
def entire_data():
    """
    Returns the entire dataset from the epoch summary
    """
    url = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"
    data = url_xml_pull(url)
    list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")

    try:
        limit = int(request.args.get('limit', 100000000000000))
        offset = int(request.args.get('offset', 0))
        ret_degree = []

        if limit > len(list_of_data):
            limit = len(list_of_data)
        
        for i in range(offset, limit):
            ret_degree.append(list_of_data[i])

        return jsonify(ret_degree)
        
    except ValueError as e:
        return str(e)


@app.route('/epochs/<epoch>', methods=['GET'])
def state_vector(epoch):
    """
    Returns the state vector for a given epoch
    """
    url = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"
    data = url_xml_pull(url)
    list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")

    for i in list_of_data:
        if i["EPOCH"] == epoch:
            return jsonify(i)
    
    return jsonify({"error": "epoch not found"}), 404


@app.route('/epochs/<epoch>/speed', methods=['GET'])
def get_instantaneous_speed(epoch):
    """
    Returns the instantaneous speed at a given epoch
    """
    url = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"
    data = url_xml_pull(url)
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
def location_finder(epoch):
    """
    Returns the latitude, longitude, altitude, and geoposition of the ISS for a given epoch
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
    Returns the real-time latitude, longitude, altitude, and geoposition of the ISS
    """
    url = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"
    data = url_xml_pull(url)
    if not data:
        return jsonify({"error": "Failed to retrieve data"}), 500

    list_of_data = find_data_point(data, "ndm", "oem", "body", "segment", "data", "stateVector")

    if not list_of_data:
        return jsonify({"error": "No state vector data found"}), 404 

    now = datetime.now().timestamp()  # Get the current time in UTC
    closest_epoch = None
    closest_time_diff = float("inf")

    for sv in list_of_data:
        try:
            epoch_time = sv["EPOCH"]

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


def instantaneous_speed(x: float, y: float, z: float) -> float:
    """
    This function calculates the instantaneous speed based on the velocity components.
    """
    return (x**2 + y**2 + z**2)**0.5


def main():
    """
    Main function to pull ISS data and run the functions
    """
    url = 'https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml'
    data = url_xml_pull(url)

    if data:
        # Call the functions with the fetched data
        epoch_range(data)
        current_epoch(data)
        avg_speed(data)
    else:
        logging.error("No data fetched, exiting main.")


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')

# Building a Flask API to track the ISS using Redis and Docker

This Midterm project contains:   

-two python scripts ```iss_tracker.py``` & ```test_iss_tracker.py```   
-the ```Dockerfile``` needed to build the image to run these containerized programs   
-a ```docker-compose.yml``` file to automate the deployment of the Flask app and the Redis container together   
-a ```requirements.txt``` that lists non-standard Python libraries that must be installed for this project file   
-Additionally, this folder contains a diagram.png of how I interpret the software system to be running.

The objective of this assignment is to use the iss_tracker.py python script to run the ensuing functions: ```def fetch_and_store_iss_data```, ```def find_data_point```, ```def compute_location_astropy```, ```def get_geolocation```,  ```def instantaneous_speed```, ```def entire_data```, ```def state_vector```, ```def get_instantaneous_speed```, ```def location```, and ```def get_now_data```. These functions are used to build our redis database to then run flask API routes to extract various data analysis regarding the ISS epoch's total data, component data, instantaneous speed data, location data, and time data to inform the user on the public data regarding the ISS.

Additionally, the goal is for the functions: ```def entire_data```, def state_vector```, ```def get_instantaneous_speed```, ```def location``` and ```def get_now_data```; to set up Flask API routes with @app.route to then call upon these funtcions using curl commands to run from the server for various endpoints, with the data in the redis database.

Routes
The following route endpoints correlate to the following functions:
@app.route('/epochs', methods = ['GET']) is used to run def entire_data() (/epochs?limit=int&offset=int can be ran for this function as well, and will provide a dict of epochs to the users specifications)

@app.route('/epochs/<epoch>', methods = ['GET']) is used to run def state_vector(epoch)

@app.route('/epochs/<epoch>/speed', methods=['GET']) is used to run def get_instantaneous_speed(epoch)

@app.route('/now', methods=['GET']) is used to run def get_now_data()

A citation of / link to the ISS data

Instructions to deploy the app with docker compose

Instructions to curl all routes, plus what the outputs meaning

Instructions to run the containerized unit tests

Be succinct, use Markdown styles, and show example commands / expected output.

Diagram.png: Include a software diagram that illustrates what you deem to be the most important parts of your project. The diagram should be visible from your README.
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

Data
The data can be accessed through the following link: https://spotthestation.nasa.gov/trajectory_data.cfm

Where the user can then download the tracking data as an xml file here: https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml

Once, downloaded the scripts in this repo will utizlie the xml link to execute the functions

The dataset is an xml list of dictionaries that gives a "State Vector" containing the epoch, x,y,z coordinates, and x,y,z velo components.

It is then pulled into the scripts using the xml_url_pull function

Building and Running the Container
A container for this code can be made with the following docker commands

-To build the container: In your command line of your desired repo run: docker build -t iss_tracker .

-To run the docker image in the container: In your command line of your desired repo run: docker run --rm -p 5000:5000 iss_tracker

these commands will then run the written python scripts and tests in iss_tracker.py & test_iss_tracker.py

Running as a Flask App
Once the code has been containerized, the user can run: python3 iss_tracker.py to run the iss tracking python file. The line app = Flask(__name__) allows the file to turn into a Flask API server. From there the user should open a second terminal window and naviaget back to the same folder that holds these python scripts and where the generated flask api server is currently running. Then, the user can run the following structure to call upon the routes that were written in the iss_tracker.py file in the localhost and default port = 5000: curl -X GET "http://127.0.0.1:5000/epoch" where, 127.0.0.1:5000 is generated from the * running on ... line in the terminal window in which the Flask API is running.

/epoch can be replaced with any of the endpoints given above depending on the desired function

Output
The output will be the analysis of the downloaded data from our functions.

This will include:
curl -X GET "http://127.0.0.1:5000/epochs" - this will output the entire epoch dataset in its entirety that has been pulled from the xml data file

curl -X GET "http://127.0.0.1:5000/epochs?limit=5&offset=2" - this will ouput the desired range of epochs with the limit of epochs returned and the offset (starting position) of the set of epochs. (limit of 5 starting at the 2nd epoch in this example)

curl -X GET "http://127.0.0.1:5000/epochs/2025-02-28T12:56:00.000" - this will output the state vectrors for the given epoch (2025-02-28T12:56:00.000) from the data set, where the given epoch replaces <epoch> in the curl command

curl -X GET "http://127.0.0.1:5000/epochs/2025-02-28T12:56:00.000/speed" - this will output the instantaneous for the given specifed epoch (2025-02-28T12:56:00.000) from the xml dataset

curl -X GET "http://127.0.0.1:5000/now" - this will output the closest epoch to the epoch at the current time of the program being ran

this will be followed by the ensuing pytests of the functions we have wrote in
test_iss_tracker.py.

This will be ran using pytest test_iss_tracker.pyThese will have 4 pass and 2 fail, as the url_xml_pull function used to pull our downloaded data was given an invalid link and correctly returns a failed test, and the state vector test function was struggling to follow the set timeutc = now

Chatgpt acknowledgment
Chatgpt was used to assist in this code primarily in the python function scripts of analyzing the timestamp dates

As well as in the docker file build, upon using previous docker formats, I wasn't outputting the desired results and Chatgpt helped me run the docker container while also outputting my script returns.

Finally, chatgpt was used to help build the test_iss_tracking.py script as i missed the class that discusses error testing flask API's and wasn't following the readthedocs

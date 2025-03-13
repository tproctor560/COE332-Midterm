FROM python:3.12

RUN pip3 install pytest requests xmltodict flask astropy geopy

COPY iss_tracker.py /code/iss_tracker.py

COPY test_iss_tracker.py /code/test_iss_tracker.py

RUN chmod +x /code/iss_tracker.py

ENV PATH="/code:$PATH"

WORKDIR /code

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0"]

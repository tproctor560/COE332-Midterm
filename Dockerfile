FROM python:3.12

RUN pip3 install pytest requests xmltodict

COPY iss_tracker.py /code/iss_tracker.py

COPY test_iss_tracker.py /code/test_iss_tracker.py

RUN chmod +x /code/iss_tracker.py

ENV PATH="/code:$PATH"

WORKDIR /code
#generated using chatgpt because i was returning no output for my standard build and run docker functions
CMD ["sh", "-c", "python /code/iss_tracker.py && pytest --maxfail=5 --disable-warnings -v /code/test_iss_tracker.py"]

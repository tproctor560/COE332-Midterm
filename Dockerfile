FROM python:3.12

WORKDIR /code

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY iss_tracker.py /code/iss_tracker.py

COPY test_iss_tracker.py /code/test_iss_tracker.py

RUN chmod +x /code/iss_tracker.py

EXPOSE 5000

CMD ["python", "iss_tracker.py"]

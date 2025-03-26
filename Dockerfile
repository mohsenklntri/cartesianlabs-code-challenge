FROM apache/airflow:2.10.4

ADD requirements.txt .

ADD .env .

RUN pip install -r requirements.txt
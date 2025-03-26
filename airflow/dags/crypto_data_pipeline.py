import os
import requests
import psycopg2
from psycopg2 import sql
from time import sleep
from dotenv import load_dotenv
from decimal import Decimal

from airflow import DAG
from airflow.providers.mongo.hooks.mongo import MongoHook
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from datetime import datetime, timedelta, timezone

load_dotenv()


COINCAP_APIKEY = os.getenv("COINCAP_APIKEY")
COINS = os.getenv("COINS").split(",")
MONGO_CONN_ID = os.getenv("MONGO_CONN_ID")
MONGO_COLLECTION = os.getenv("MONGO_COIN_COLLECTION")
POSTGRES_CONN = os.getenv("POSTGRES_CONN")

# DAG default arguments
default_args = {
    "owner": "airflow",
    "depends_on_past": True,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "wait_for_downstream": True
}

dag = DAG(
    "crypto_data_pipeline",
    default_args=default_args,
    description="Fetch last week's cryptocurrency data daily and store in MongoDB",
    schedule_interval=timedelta(days=7),  # every 7 days
    catchup=True,
    max_active_runs=1,
    concurrency=1,
)


def fetch_coin_data(**kwargs):
    """Fetch historical data for a given cryptocurrency."""
    execution_date = kwargs["execution_date"]
    end_date = execution_date 
    start_date = end_date - timedelta(days=7)
    start_timestamp = int(start_date.timestamp() * 1000)
    end_timestamp = int(end_date.timestamp() * 1000)

    coin = kwargs["params"]["coin"]

    url = f"https://api.coincap.io/v2/assets/{coin}/history?interval=d1&start={start_timestamp}&end={end_timestamp}"
    headers = {"Authorization": f"Bearer {COINCAP_APIKEY}", "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json().get("data", [])
        cleaned_data = [{**coin_data, "symbol": coin} for coin_data in data]
        print(f"Successfully get data for {coin}.")
        return cleaned_data
    else:
        raise Exception(f"Failed to fetch data for {coin}: {response.status_code}")


def store_data_to_mongo(**kwargs):
    """Store fetched cryptocurrency data into MongoDB."""
    ti = kwargs["ti"]
    coin = kwargs["params"]["coin"]

    data = ti.xcom_pull(task_ids=f"fetch_{coin}_data")
    if not data:
        raise ValueError(f"No data found for {coin}.")

    mongo_hook = MongoHook(conn_id=MONGO_CONN_ID)
    collection = mongo_hook.get_collection(MONGO_COLLECTION)
    collection.insert_many(data)
    print(f"Successfully stored data for {coin} in MongoDB.")


def store_data_to_postgres(**kwargs):
    """Store coin data in PostgreSQL."""
    ti = kwargs["ti"]
    coin = kwargs["params"]["coin"]

    data = ti.xcom_pull(task_ids=f"fetch_{coin}_data")
    if not data:
        raise ValueError(f"No data found for {coin}.")

    conn = psycopg2.connect(POSTGRES_CONN)
    cursor = conn.cursor()
    insert_query = sql.SQL(
        """
            INSERT INTO coin_data (coin_name, price, timestamp)
            VALUES (%s, %s, %s)
        """
    )
    
    for coin_data in data:
        cursor.execute(
            insert_query,
            (
                coin,
                Decimal(coin_data["priceUsd"]),
                datetime.fromtimestamp(coin_data['time'] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            ),
        )
        
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Successfully inserted coin data for {coin} into PostgreSQL.")


# Define tasks dynamically for each coin
for coin in COINS:
    fetch_task = PythonOperator(
        task_id=f"fetch_{coin}_data",
        python_callable=fetch_coin_data,
        provide_context=True,
        params={"coin": coin},
        dag=dag,
    )

    store_mongo_task = PythonOperator(
        task_id=f"store_mongo_{coin}_data",
        python_callable=store_data_to_mongo,
        provide_context=True,
        params={"coin": coin},
        dag=dag,
    )

    store_postgres_task = PythonOperator(
        task_id=f"store_postgres_{coin}_data",
        python_callable=store_data_to_postgres,
        provide_context=True,
        params={"coin": coin},
        dag=dag,
    )

    wait_task = DummyOperator(
        task_id="wait_1_minute",
        dag=dag,
        trigger_rule="all_success",
    )

    sleep_task = PythonOperator(
        task_id="sleep_task",
        python_callable=lambda: sleep(60),
        dag=dag,
    )

    fetch_task >> store_mongo_task >> store_postgres_task >> sleep_task >> wait_task

import os
import math
import requests
import psycopg2
from psycopg2 import sql
from time import sleep
from dotenv import load_dotenv
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from airflow import DAG
from airflow.providers.mongo.hooks.mongo import MongoHook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator


load_dotenv()


NEWSAPI_APIKEY = os.getenv("NEWSAPI_APIKEY")
COINS = os.getenv("COINS").split(",")
MONGO_CONN_ID = os.getenv("MONGO_CONN_ID")
MONGO_COLLECTION = os.getenv("MONGO_NEWS_COLLECTION")
POSTGRES_CONN = os.getenv("POSTGRES_CONN")


def analyze_sentiment(text):
    analyzer = SentimentIntensityAnalyzer()
    sentiment = analyzer.polarity_scores(text)
    return sentiment["compound"]


# DAG default arguments
default_args = {
    "owner": "airflow",
    "depends_on_past": True,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "wait_for_downstream": True,
}

dag = DAG(
    "news_data_pipeline",
    default_args=default_args,
    description="Fetch last week's news data daily and store in MongoDB",
    schedule_interval=timedelta(days=7),  # every 7 days
    catchup=True,
    max_active_runs=1,
    concurrency=1,
)


def fetch_news_data(**kwargs):
    """Fetch historical data for a given news."""
    execution_date = kwargs["execution_date"]
    end_date = execution_date.strftime("%Y%m%d")
    begin_date = (execution_date - timedelta(days=7)).strftime("%Y%m%d")

    coin = kwargs["params"]["coin"]

    url = f"https://api.nytimes.com/svc/search/v2/articlesearch.json?q={coin}&api-key={NEWSAPI_APIKEY}&begin_date={begin_date}&end_date={end_date}&page=0"
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception(f"Error fetching data: {response.status_code}")

    data = response.json()
    total_articles = data["response"]["meta"]["hits"]

    if total_articles > 10:
        total_pages = math.ceil(
            total_articles / 10
        )  # Each page contains 10 articles max
        print(f"Total articles: {total_articles}, Total pages: {total_pages}")
    else:
        total_pages = 0
        print(f"Total articles: {total_articles}, Total pages: 1")

    all_articles = data["response"].get("docs", [])

    for page in range(1, total_pages):
        sleep(2)
        print(f"Fetching page {page+1}...")
        url = f"https://api.nytimes.com/svc/search/v2/articlesearch.json?q={coin}&api-key={NEWSAPI_APIKEY}&begin_date={begin_date}&end_date={end_date}&page={page}"
        response = requests.get(url)

        if response.status_code == 200:
            page_data = response.json()
            articles = page_data["response"].get("docs", [])
            all_articles.extend(articles)
        else:
            print(f"Failed to fetch page {page+1}: {response.status_code}")

    _all_articles = [
        {k: v for k, v in item.items() if k != "_id"} for item in all_articles
    ]  # pop _id key from each article
    return _all_articles


def store_data_to_mongo(**kwargs):
    """Store fetched cryptocurrency data into MongoDB."""
    ti = kwargs["ti"]
    coin = kwargs["params"]["coin"]

    data = ti.xcom_pull(task_ids=f"fetch_{coin}_news")
    if not data:
        print(f"No news found for {coin}.")
    else:
        mongo_hook = MongoHook(conn_id=MONGO_CONN_ID)
        collection = mongo_hook.get_collection(MONGO_COLLECTION)
        collection.insert_many(data)
        print(f"Successfully stored news for {coin} in MongoDB.")


def analyze_sentiment_and_store_to_postgres(**kwargs):
    """Analyze sentiment of news articles and store in PostgreSQL."""
    ti = kwargs["ti"]
    coin = kwargs["params"]["coin"]

    news_data = ti.xcom_pull(task_ids=f"fetch_{coin}_news")

    if not news_data:
        print(f"No news data found for {coin}.")

    # Sentiment analysis
    news = []
    for article in news_data:
        headline = article["headline"].get("main", "")
        lead_paragraph = article.get("lead_paragraph", "")
        if headline:
            headline_sentiment_score = analyze_sentiment(headline)
        else:
            headline_sentiment_score = 0

        if lead_paragraph:
            lead_paragraph_sentiment_score = analyze_sentiment(lead_paragraph)
        else:
            lead_paragraph_sentiment_score = 0

        news.append(
            {
                "pub_date": article["pub_date"],
                "headline_score": headline_sentiment_score,
                "lead_paragraph_score": lead_paragraph_sentiment_score,
            }
        )

    conn = psycopg2.connect(POSTGRES_CONN)
    cursor = conn.cursor()
    insert_query = sql.SQL(
        """
            INSERT INTO news_data (coin_name, pub_date, headline_score, lead_paragraph_score)
            VALUES (%s, %s, %s, %s)
        """
    )
    for article in news:
        cursor.execute(
            insert_query,
            (
                coin,
                datetime.strptime(article["pub_date"], "%Y-%m-%dT%H:%M:%S%z").strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                article["headline_score"],
                article["lead_paragraph_score"],
            ),
        )

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Successfully inserted news data for {coin} into PostgreSQL.")


# Define tasks dynamically for each coin
for coin in COINS:

    fetch_task = PythonOperator(
        task_id=f"fetch_{coin}_news",
        python_callable=fetch_news_data,
        provide_context=True,
        params={"coin": coin},
        execution_timeout=timedelta(minutes=10),
        dag=dag,
    )

    store_task = PythonOperator(
        task_id=f"store_{coin}_news",
        python_callable=store_data_to_mongo,
        provide_context=True,
        params={"coin": coin},
        dag=dag,
    )

    sentiment_task = PythonOperator(
        task_id=f"sentiment_{coin}_news",
        python_callable=analyze_sentiment_and_store_to_postgres,
        provide_context=True,
        params={"coin": coin},
        dag=dag,
    )

    sleep_task = PythonOperator(
        task_id="sleep_task",
        python_callable=lambda: sleep(60),
        dag=dag,
    )

    wait_task = DummyOperator(
        task_id="wait_1_minute",
        dag=dag,
        trigger_rule="all_success",
    )

    fetch_task >> store_task >> sentiment_task >> sleep_task >> wait_task

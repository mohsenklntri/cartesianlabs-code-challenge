# Crypt(Ech)o: Tracing How Headlines Ripple Through Markets

## Project Overview

This project is an Apache Airflow pipeline designed to automate the following tasks (sample for Bitcoin):

1. Fetch cryptocurrency prices and news from external sources (the DAG runs weekly and retrieves data from the previous week).
2. Raw data is stored in MongoDB.
3. Analyze sentiment on the collected news and store the processed results in PostgreSQL.
4. Analyze the relationship between news sentiment and coin prices, particularly for Bitcoin.

The pipeline is fully automated with minimal manual intervention, and most services are contained within a single Docker Compose setup. Configuration for additional coins can be added in the `.env` file (other coins are commented out for now). Sample results from the pipeline (for Bitcoin) can be found in the `img` folder.

## Installation

### Prerequisites

Ensure you have the following installed on your system:

- **Docker**
- **Docker Compose**

### Setup and Run

1. Clone the repository:

   ```sh
   git clone https://github.com/mohsenklntri/cartesianlabs-code-challenge
   cd <repository-folder>
2. Start the services using Docker Compose:

   ```sh
   docker-compose up -d
3. Open Airflow web UI:

   - Navigate to [http://localhost:8080](http://localhost:8080).
   - Login using the default credentials (if applicable user=airflow, pass=airflow).

4. Enable and trigger DAGs in the following order:

   - **coin_data_pipeline**
   - **news_data_pipeline**

   Wait for both DAGs to complete execution before verifying the stored data.

5. Run dashboard:
   Create virtual env for local python and install `requirements_venv.txt` and run the `final_analyze.py` script to generate the dashboard.

## DAG Structure

### crypto_data_pipeline
- Fetches cryptocurrency data.
- Stores fetched data into MongoDB.
- Stores processed coin data in PostgreSQL.
- Sleep and wait for 1 minute. (for avoiding API rate limit)

### news_data_pipeline
- Fetches related crypto news data.
- Stores news data into MongoDB.
- Performs sentiment analysis.
- Stores the analyzed data into PostgreSQL.
- Sleep and wait for 1 minute. (for avoiding API rate limit)



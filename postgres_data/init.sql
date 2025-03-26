CREATE TABLE IF NOT EXISTS coin_data (
    id SERIAL PRIMARY KEY,
    coin_name VARCHAR(50) NOT NULL,
    price NUMERIC NOT NULL,
    timestamp TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS news_data (
    id SERIAL PRIMARY KEY,
    coin_name VARCHAR(50) NOT NULL,
    pub_date TIMESTAMP NOT NULL,
    headline_score FLOAT NOT NULL,
    lead_paragraph_score FLOAT NOT NULL
);
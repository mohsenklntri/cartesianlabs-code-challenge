import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from matplotlib.gridspec import GridSpec

DATABASE_URL = "postgresql+psycopg2://airflow:airflow@localhost:5433/airflow"
engine = create_engine(DATABASE_URL)

query_news = """
    SELECT coin_name, pub_date, headline_score, lead_paragraph_score 
    FROM news_data 
    WHERE pub_date >= '2024-01-01'
"""
query_prices = """
    SELECT coin_name, timestamp AS pub_date, price 
    FROM coin_data 
    WHERE timestamp >= '2024-01-01'
"""

df_news = pd.read_sql(query_news, engine)
df_prices = pd.read_sql(query_prices, engine)

df_news["pub_date"] = pd.to_datetime(df_news["pub_date"]).dt.date
df_prices["pub_date"] = pd.to_datetime(df_prices["pub_date"]).dt.date

df_news_grouped = df_news.groupby(["coin_name", "pub_date"]).agg({
    "headline_score": "mean",
    "lead_paragraph_score": "mean"
}).reset_index()

df_merged = pd.merge(df_prices, df_news_grouped, on=["coin_name", "pub_date"], how="left")
df_merged["headline_score"] = df_merged["headline_score"].fillna(0)
df_merged["lead_paragraph_score"] = df_merged["lead_paragraph_score"].fillna(0)


fig = plt.figure(figsize=(20, 10))

gs = GridSpec(1, 2, width_ratios=[3, 1])
ax1 = plt.subplot(gs[0])
ax2 = plt.subplot(gs[1])

ax1.bar(df_merged["pub_date"], df_merged["headline_score"], label="Headline Sentiment", color="green", width=0.4, alpha=0.7, align='center')
ax1.bar(df_merged["pub_date"], df_merged["lead_paragraph_score"], label="Lead Paragraph Sentiment", color="red", width=0.2, alpha=0.7, align='center')
ax1.set_xlabel("Date")
ax1.set_ylabel("Sentiment Score", color="black")
ax1.tick_params(axis="y", labelcolor="black")
ax1.set_title("Sentiment Analysis Over Time")

ax2_1 = ax1.twinx()
ax2_1.plot(df_merged["pub_date"], df_merged["price"], label="Price (USD)", color="blue", linestyle='-', linewidth=2)
ax2_1.set_ylabel("Price (USD)", color="blue")

df_corr = df_merged[["price", "headline_score", "lead_paragraph_score"]].corr()
sns.heatmap(df_corr, annot=True, cmap="coolwarm", fmt=".2f", linewidths=1, square=True, ax=ax2, cbar_kws={'label': 'Correlation'})
ax2.set_title("Correlation Between Price & Sentiment")

plt.tight_layout()
plt.show()

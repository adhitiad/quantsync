import polars as pl
from sklearn.preprocessing import MinMaxScaler
import pandas as pd

class DataProcessor:
    def __init__(self):
        self.scaler = MinMaxScaler()

    def process_scraped_data(self, data):
        """
        Process RSS and Search data using Polars.
        """
        if not data:
            return pl.DataFrame()

        # Convert to Polars DataFrame
        df = pl.DataFrame(data)
        
        # Deduplicate and basic cleaning
        df = df.unique(subset=["title"])
        
        # Add some basic sentiment score (Placeholder logic)
        # In real scenario, use a NLP model here
        df = df.with_columns([
            pl.lit(0.5).alias("sentiment_score")
        ])
        
        return df

    def prepare_for_vector_db(self, df):
        """
        Convert Polars DF to format suitable for Vector Database (Milvus).
        """
        records = df.to_dicts()
        formatted = []
        for r in records:
            formatted.append({
                "id": str(r.get("timestamp", 0)),
                "document": r.get("summary", r.get("title", "")),
                "metadata": {
                    "source": r.get("source", "unknown"),
                    "title": r.get("title", ""),
                    "link": r.get("link", "")
                }
            })
        return formatted

    def scale_features(self, df_pd):
        """
        Scale numerical features using scikit-learn.
        Input is pandas DF.
        """
        cols_to_scale = [c for c in df_pd.columns if df_pd[c].dtype in ['float64', 'int64']]
        if cols_to_scale:
            df_pd[cols_to_scale] = self.scaler.fit_transform(df_pd[cols_to_scale])
        return df_pd

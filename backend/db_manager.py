import os
from pymongo import MongoClient
from datetime import datetime, timedelta
import re

class MongoManager:
    def __init__(self, uri=None, db_name="politics_eye"):
        self.uri = uri or os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.client = MongoClient(self.uri)
        self.db = self.client[db_name]
        self.posts = self.db.posts
        print(f"Connected to MongoDB at {self.uri}")

    def save_post(self, post_data):
        """Saves an analyzed post to MongoDB."""
        try:
            # Ensure timestamp is a datetime object for better querying
            if isinstance(post_data.get('timestamp'), str):
                try:
                    post_data['dt'] = datetime.fromisoformat(post_data['timestamp'].replace('Z', '+00:00'))
                except:
                    post_data['dt'] = datetime.now()
            else:
                post_data['dt'] = datetime.now()

            self.posts.update_one(
                {"id": post_data["id"]},
                {"$set": post_data},
                upsert=True
            )
        except Exception as e:
            print(f"Error saving to MongoDB: {e}")

    def get_time_series(self, limit=50):
        """Returns sentiment data over time, sorted chronologically."""
        try:
            cursor = self.posts.find(
                {}, {"dt": 1, "score": 1, "sentiment": 1, "_id": 0}
            ).sort("dt", 1).limit(limit)  # ascending = chronological

            results = []
            for doc in cursor:
                dt = doc.get('dt')
                results.append({
                    "score": doc.get('score', 0),
                    "sentiment": doc.get('sentiment', 'neutral'),
                    "timestamp": dt.isoformat() if isinstance(dt, datetime) else str(dt),
                    "time": dt.strftime('%H:%M') if isinstance(dt, datetime) else ''
                })
            return results
        except Exception as e:
            print(f"Error fetching time series: {e}")
            return []

    def search_keyword(self, keyword):
        """Searches for a keyword and returns sentiment statistics with time data."""
        try:
            # Use case-insensitive regex search
            regex = re.compile(re.escape(keyword), re.IGNORECASE)
            # Find matching posts and include their sentiment score and timestamp
            matches = list(self.posts.find(
                {"text": {"$regex": regex}}, 
                {"score": 1, "sentiment": 1, "dt": 1, "_id": 0}
            ).sort("dt", 1)) # Sort chronologically for time-series
            
            if not matches:
                return {"count": 0, "avg_sentiment": 0, "status": "no_results", "time_series": []}
            
            total_score = sum(m['score'] for m in matches)
            count = len(matches)
            
            # Prepare time series data for the UI
            time_series = []
            for m in matches:
                dt_str = m.get('dt')
                if isinstance(dt_str, datetime):
                    dt_str = dt_str.isoformat()
                
                time_series.append({
                    "score": m['score'],
                    "sentiment": m['sentiment'],
                    "timestamp": dt_str
                })
            
            return {
                "keyword": keyword,
                "count": count,
                "avg_sentiment": round(total_score / count, 3),
                "time_series": time_series,
                "status": "success"
            }
        except Exception as e:
            print(f"Error searching keyword: {e}")
            return {"count": 0, "avg_sentiment": 0, "status": "error", "time_series": []}

    def get_historical_stats(self, period="daily"):
        """Returns aggregated sentiment statistics for different time periods."""
        try:
            now = datetime.now()
            
            if period == "daily":
                start_time = now - timedelta(days=1)
                group_format = "%Y-%m-%d %H:00" # Group by Hour
            elif period == "weekly":
                start_time = now - timedelta(days=7)
                group_format = "%Y-%m-%d" # Group by Day
            elif period == "monthly":
                start_time = now - timedelta(days=30)
                group_format = "%Y-%m-%d" # Group by Day (30 points)
            else:
                return []

            pipeline = [
                {"$match": {"dt": {"$gte": start_time}}},
                {
                    "$group": {
                        "_id": {
                            "$dateToString": { "format": group_format, "date": "$dt" }
                        },
                        "avg_score": { "$avg": "$score" },
                        "count": { "$sum": 1 }
                    }
                },
                {"$sort": {"_id": 1}}
            ]
            
            results = list(self.posts.aggregate(pipeline))
            
            # Format for frontend (Recharts expects 'time' or 'timestamp' and 'score')
            formatted = []
            for r in results:
                formatted.append({
                    "time": r["_id"],
                    "score": round(r["avg_score"], 3),
                    "count": r["count"]
                })
            
            return formatted
        except Exception as e:
            print(f"Error in aggregation: {e}")
            return []

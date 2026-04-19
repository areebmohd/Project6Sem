from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv

from analyzer import PoliticalAnalyzer
from scraper import PoliticalStreamer

load_dotenv()

app = Flask(__name__)
# Enable CORS for the frontend development server
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuration
REDDIT_KEYS = {
    "client_id": os.getenv("REDDIT_CLIENT_ID"),
    "client_secret": os.getenv("REDDIT_CLIENT_SECRET"),
    "user_agent": os.getenv("REDDIT_USER_AGENT", "PoliticalSentimentBot/1.0")
}
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# Initialize Core
analyzer = PoliticalAnalyzer()
streamer = PoliticalStreamer(
    analyzer, 
    reddit_keys=REDDIT_KEYS if REDDIT_KEYS['client_id'] else None,
    news_api_key=NEWS_API_KEY
)

# Ensure the streamer starts in each worker process (essential for Gunicorn/Production)
@app.before_request
def start_background_tasks():
    if not streamer._running:
        print(f"Starting background scraper thread for process {os.getpid()}...")
        streamer.start()

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "status": "online",
        "message": "PoliticsEye Analysis Engine is active",
        "endpoints": ["/api/health", "/api/snapshot", "/api/toggle-mode"]
    })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "mode": streamer.mode,
        "streaming": streamer._running
    })
@app.route('/api/related/<path:post_id>', methods=['GET'])
def get_related(post_id):
    # Log for debugging
    print(f"DEBUG: Finding related for {post_id}")
    related_ids = analyzer.get_related_posts(post_id)
    print(f"DEBUG: Found {len(related_ids)} relations")
    return jsonify({
        "post_id": post_id,
        "related_ids": related_ids
    })

@app.route('/api/snapshot', methods=['GET'])
def get_snapshot():
    snapshot = streamer.get_snapshot()
    # Use the summary directly from the snapshot if available
    summary = snapshot.get('summary', {"avg_sentiment": 0, "pos_count": 0, "neg_count": 0, "total_count": 0})
    
    # Enrich summary with counts if not present
    if "pos_count" not in summary and snapshot['latest_posts']:
        summary["pos_count"] = sum(1 for p in snapshot['latest_posts'] if p['sentiment'] == "positive")
        summary["neg_count"] = sum(1 for p in snapshot['latest_posts'] if p['sentiment'] == "negative")
        summary["total_count"] = len(snapshot['latest_posts'])
        
    # Trigger Similarity Indexing for Scikit-Learn (on-the-fly)
    # We use a larger pool of items (up to 100) from the buffer to ensure
    # that clicks on "Related" don't fail as items scroll off the top 15.
    all_buffer_posts = list(streamer.buffers.get(streamer.mode, []))
    if all_buffer_posts:
        analyzer.update_similarities(all_buffer_posts)
        
    return jsonify({
        **snapshot,
        "summary": summary
    })

@app.route('/api/toggle-mode', methods=['POST'])
def toggle_mode():
    data = request.json
    requested_mode = data.get("mode")
    if requested_mode in ["mock", "mastodon", "news", "rss", "youtube", "twitter"]:
        if requested_mode == "news" and not streamer.news.enabled:
            return jsonify({"success": False, "error": "NewsAPI Key missing in .env"}), 400
        
        streamer.mode = requested_mode
        return jsonify({"success": True, "new_mode": streamer.mode})
    return jsonify({"success": False, "error": "Invalid mode"}), 400

@app.route('/api/analytics/timeseries', methods=['GET'])
def get_timeseries():
    # Fetch historical sentiment data from MongoDB
    limit = request.args.get('limit', default=100, type=int)
    data = streamer.db.get_time_series(limit=limit)
    return jsonify(data)

@app.route('/api/analytics/search', methods=['GET'])
def search_keyword():
    keyword = request.args.get('keyword')
    if not keyword:
        return jsonify({"error": "Keyword is required"}), 400
    
    result = streamer.db.search_keyword(keyword)
    return jsonify(result)

@app.route('/api/analytics/historical', methods=['GET'])
def get_historical_analytics():
    period = request.args.get('period', default='daily')
    data = streamer.db.get_historical_stats(period=period)
    return jsonify(data)

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

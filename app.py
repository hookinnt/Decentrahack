import sys
import logging
import warnings
warnings.filterwarnings('ignore')

from flask import Flask, request, jsonify, render_template
from agent.analyzer import AIAnalyzer
from agent.models import NewsItem
from agent.solana_client import verify_solana_or_crash, execute_emergency_pause, get_status

# Silence Flask's request logs — we print our own
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

# ─── Startup: Solana is required ──────────────────────────────────────────────
verify_solana_or_crash()

# One shared AI analyzer instance
analyzer = AIAnalyzer()


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """
    Live health check — returns real Solana RPC connectivity data and
    the AI agent wallet address + balance. Used by the frontend status badge.
    """
    return jsonify(get_status())


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """
    Core analysis endpoint.
    Accepts: { news: str, tvl: str, volatility: str }
    Returns: { risk_score: int, reason: str, action_required: bool, tx_hash?: str }

    If risk_score >= 80 and action_required is True, a real signed transaction
    is sent to Solana Devnet as an immutable on-chain event log.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No JSON body received"}), 400

    text = data.get('news', '').strip()
    tvl = data.get('tvl', 'Unknown').strip() or 'Unknown'
    volatility = data.get('volatility', 'Medium')

    if not text:
        return jsonify({"error": "Event text cannot be empty"}), 400

    news = NewsItem(
        id="live",
        headline="Oracle Input",
        content=text,
        tvl=tvl,
        volatility=volatility,
    )

    try:
        assessment = analyzer.analyze_news(news)

        response_data = {
            "risk_score": assessment.risk_score,
            "reason": assessment.reason,
            "action_required": assessment.action_required,
        }

        # Send a real blockchain transaction if the AI flags a critical threat
        if assessment.action_required and assessment.risk_score >= 80:
            tx_hash = execute_emergency_pause(assessment.reason, assessment.risk_score)
            if tx_hash:
                response_data["tx_hash"] = tx_hash

        return jsonify(response_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("\n" + "=" * 56)
    print("   Solana AI Risk Oracle — Web Dashboard")
    print("=" * 56)
    print("=> http://127.0.0.1:5000\n")
    app.run(port=5000, debug=False)

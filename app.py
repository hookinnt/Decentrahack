import sys
import logging
import warnings
warnings.filterwarnings('ignore')

from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from agent.analyzer import RiskAuditor
from agent.models import NewsItem
from agent.monitor import BackgroundMonitor
from agent.solana_client import (
    verify_solana_or_crash,
    execute_initialize,
    execute_emergency_pause,
    execute_threshold_update,
    execute_resume,
    get_status,
)

# Silence Flask's request logs — we print our own
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ─── Startup: Solana is required ──────────────────────────────────────────────
verify_solana_or_crash()

# One shared risk analyzer instance
analyzer = RiskAuditor()

# Initialize and start the Background Monitor
def on_monitor_update(state):
    """Callback for real-time state broadcast."""
    socketio.emit('state_update', state)

monitor = BackgroundMonitor(analyzer, callback=on_monitor_update)
monitor.start()

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """Live health check — returns Solana RPC data and agent balance."""
    return jsonify(get_status())


@app.route('/api/monitor/state')
def api_monitor_state():
    """Returns the current state of the Background Monitor Organism."""
    return jsonify(monitor.get_state())

@app.route('/api/monitor/refresh', methods=['POST'])
def api_monitor_refresh():
    """Force-sync monitor with chain/market and broadcast immediately."""
    state = monitor.refresh_now()
    return jsonify(state)


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Manually triggered analysis endpoint."""
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
        headline="Manual Oracle Input",
        content=text,
        tvl=tvl,
        volatility=volatility,
    )

    try:
        assessment = analyzer.process_event(news)

        response_data = assessment.dict()

        # DARS logic: Autonomous threshold adjustment
        if assessment.recommended_threshold:
            status = get_status()
            current_threshold = status.get("risk_threshold", 80)
            if abs(assessment.recommended_threshold - current_threshold) >= 5:
                # This could be potentially slow if waiting for confirmation, 
                # but it's okay for this manual trigger.
                th_sig, th_err = execute_threshold_update(assessment.recommended_threshold)
                response_data["threshold_updated"] = bool(th_sig)
                if th_sig:
                    response_data["threshold_tx_hash"] = th_sig
                if th_err:
                    response_data["threshold_error"] = th_err

        # Send emergency transaction if risk is high
        status = get_status()
        active_threshold = status.get("risk_threshold", 80)
        if assessment.action_required and assessment.risk_score >= active_threshold:
            tx_hash, tx_err = execute_emergency_pause(assessment.reason, assessment.risk_score)
            if tx_hash:
                response_data["tx_hash"] = tx_hash
            if tx_err:
                response_data["error"] = tx_err

        # Push updated state after manual analysis actions.
        monitor.refresh_now()

        return jsonify(response_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/initialize', methods=['POST'])
def api_initialize():
    """Manual on-chain initialization."""
    sig, err = execute_initialize()
    return jsonify({"signature": sig, "error": err})


@app.route('/api/resume', methods=['POST'])
def api_resume():
    """Manual on-chain resume."""
    sig, err = execute_resume()
    return jsonify({"signature": sig, "error": err})


@app.route('/api/threshold', methods=['POST'])
def api_threshold():
    """Manual DARS threshold update via slider."""
    data = request.json
    val = data.get('threshold') if data else None
    if val is None:
        return jsonify({"error": "No threshold value provided"}), 400
    try:
        val = int(val)
        sig, err = execute_threshold_update(val)
        return jsonify({"signature": sig, "error": err})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("\n" + "=" * 56)
    print("   SOLANA RISK MANAGER — Dashboard")
    print("   Status: Background Monitoring ACTIVE (WebSockets ENABLED)")
    print("=" * 56)
    print("=> http://127.0.0.1:5000\n")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)

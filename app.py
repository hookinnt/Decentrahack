import sys
import logging
import warnings
import uuid
warnings.filterwarnings('ignore')

from flask import Flask, request, jsonify, render_template, session
from flask_socketio import SocketIO, emit
import secrets
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from solders.pubkey import Pubkey
from agent.analyzer import RiskAuditor
from agent.models import NewsItem
from agent.monitor import BackgroundMonitor
from agent.solana_client import (
    verify_solana_or_crash,
    get_status,
    prepare_initialize_tx_for_client,
    prepare_resume_tx_for_client,
)

# Silence Flask's request logs — we print our own
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ─── Startup: Solana is required ──────────────────────────────────────────────
verify_solana_or_crash()

# One shared risk analyzer instance
analyzer = RiskAuditor()

# ─── Realtime callbacks ────────────────────────────────────────────────────
def on_monitor_update(state):
    """Callback for real-time state broadcast."""
    socketio.emit('state_update', state)

def on_tx_request(tx_id, action, prepared_tx):
    """Ask the connected wallet to sign and send a prepared transaction."""
    socketio.emit('tx_request', {
        "tx_id": tx_id,
        "action": action,
        "prepared": prepared_tx,
    })

# Initialize and start the Background Monitor
monitor = BackgroundMonitor(analyzer, callback=on_monitor_update, tx_request_callback=on_tx_request)
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


@app.route('/api/monitor/start', methods=['POST'])
def api_monitor_start():
    if not session.get('authorized'):
        return jsonify({"error": "Unauthorized"}), 401
    monitor.start()
    return jsonify(monitor.get_state())


@app.route('/api/monitor/stop', methods=['POST'])
def api_monitor_stop():
    if not session.get('authorized'):
        return jsonify({"error": "Unauthorized"}), 401
    monitor.stop()
    return jsonify(monitor.get_state())


@app.route('/api/auth/nonce', methods=['POST'])
def api_auth_nonce():
    """Return a challenge nonce for wallet login."""
    nonce = secrets.token_hex(16)
    session['auth_nonce'] = nonce
    message = f"Autonoma Risk Manager login nonce:{nonce}"
    return jsonify({"nonce": nonce, "message": message})


@app.route('/api/auth/verify', methods=['POST'])
def api_auth_verify():
    """Verify wallet signature (Ed25519) and bind monitor authority to this wallet."""
    data = request.json or {}
    pubkey = data.get('pubkey')
    nonce = data.get('nonce')
    signature_b64 = data.get('signature')

    expected_nonce = session.get('auth_nonce')
    if not pubkey or not nonce or not signature_b64:
        return jsonify({"error": "Missing auth fields"}), 400
    if not expected_nonce or nonce != expected_nonce:
        return jsonify({"error": "Invalid nonce"}), 401

    message = f"Autonoma Risk Manager login nonce:{nonce}"

    try:
        pubkey_bytes = bytes(Pubkey.from_string(pubkey))
        signature_bytes = base64.b64decode(signature_b64)
        Ed25519PublicKey.from_public_bytes(pubkey_bytes).verify(
            signature_bytes,
            message.encode("utf-8"),
        )
    except InvalidSignature:
        return jsonify({"error": "Signature verification failed"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    session['authorized'] = True
    session['wallet_pubkey'] = pubkey
    monitor.set_authority_pubkey(pubkey)
    monitor.refresh_now()
    return jsonify({"ok": True, "wallet_pubkey": pubkey})


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Manually triggered analysis endpoint."""
    if not session.get('authorized'):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    if not data:
        return jsonify({"error": "No JSON body received"}), 400

    text = data.get('news', '').strip()
    if not text:
        return jsonify({"error": "Event text cannot be empty"}), 400

    try:
        monitor._trigger_risk_analysis(text)
        monitor.refresh_now()
        with monitor._lock:
            latest = monitor.history[0] if monitor.history else {}
        return jsonify(latest)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/initialize', methods=['POST'])
def api_initialize():
    """Manual on-chain initialization."""
    if not session.get('authorized'):
        return jsonify({"error": "Unauthorized"}), 401
    if not monitor.authority_pubkey:
        return jsonify({"error": "Wallet is not connected (authority_pubkey is missing)."}), 400
    tx_id = f"manual_{uuid.uuid4().hex}"
    monitor.add_tx_request_history(tx_id, "initialize", "Ручная инициализация PDA")
    prepared = prepare_initialize_tx_for_client(monitor.authority_pubkey)
    socketio.emit('tx_request', {"tx_id": tx_id, "action": "initialize", "prepared": prepared})
    return jsonify({"tx_id": tx_id})


@app.route('/api/resume', methods=['POST'])
def api_resume():
    """Manual on-chain resume."""
    if not session.get('authorized'):
        return jsonify({"error": "Unauthorized"}), 401
    if not monitor.authority_pubkey:
        return jsonify({"error": "Wallet is not connected (authority_pubkey is missing)."}), 400
    tx_id = f"manual_{uuid.uuid4().hex}"
    monitor.add_tx_request_history(tx_id, "resume", "Ручное снятие паузы treasury")
    prepared = prepare_resume_tx_for_client(monitor.authority_pubkey)
    socketio.emit('tx_request', {"tx_id": tx_id, "action": "resume", "prepared": prepared})
    return jsonify({"tx_id": tx_id})


@app.route('/api/threshold', methods=['POST'])
def api_threshold():
    """Manual DARS threshold update via slider."""
    data = request.json
    val = data.get('threshold') if data else None
    if val is None:
        return jsonify({"error": "No threshold value provided"}), 400
    return jsonify({"error": "Threshold tx is not wired to this UI build."}), 400


# ─── Socket Handlers ──────────────────────────────────────────────────────
@socketio.on('wallet_connected')
def socket_wallet_connected(data):
    """
    Client says: I connected wallet at pubkey=<...>.
    We then read treasury state for this authority and allow tx_request flow.
    """
    pubkey = None
    if isinstance(data, dict):
        pubkey = data.get('pubkey')
    if not pubkey:
        return
    if not session.get('authorized'):
        return
    if session.get('wallet_pubkey') != pubkey:
        return
    monitor.set_authority_pubkey(pubkey)
    monitor.refresh_now()


@socketio.on('tx_result')
def socket_tx_result(data):
    """
    Client reports tx outcome for a tx_request: {tx_id, tx_hash, tx_error?}
    """
    if not isinstance(data, dict):
        return
    tx_id = data.get('tx_id')
    tx_hash = data.get('tx_hash')
    tx_error = data.get('tx_error')
    if not tx_id:
        return
    monitor.register_tx_result(tx_id, tx_hash=tx_hash, tx_error=tx_error)
    monitor.refresh_now()


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("\n" + "=" * 56)
    print("   SOLANA RISK MANAGER — Dashboard")
    print("   Status: Background Monitoring ACTIVE (WebSockets ENABLED)")
    print("=" * 56)
    print("=> http://127.0.0.1:5000\n")
    socketio.run(app, host='127.0.0.1', port=5000, debug=False, allow_unsafe_werkzeug=True)

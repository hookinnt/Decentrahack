import time
import threading
import requests
import uuid
from datetime import datetime
from agent.analyzer import RiskAuditor
from agent.models import NewsItem
from agent.news_engine import NewsEngine
from agent.solana_client import (
    get_status_for_authority,
    prepare_emergency_pause_tx_for_client,
    prepare_resume_tx_for_client,
    prepare_threshold_update_tx_for_client,
)

class BackgroundMonitor:
    """
    Automated background process fetching market data.
    Now with Dynamic Thresholds and Auto-Recovery.
    """
    def __init__(self, analyzer: RiskAuditor, callback=None, tx_request_callback=None):
        self.analyzer = analyzer
        self.callback = callback
        self.tx_request_callback = tx_request_callback
        self.news_engine = NewsEngine()
        self.last_price = None
        self.history = []
        self.notifications = []
        self.is_running = False
        self.authority_pubkey = None
        self._stop_event = threading.Event()
        self.safe_streak = 0  # Tracks consecutive low-risk assessments
        
        self.current_status = {
            "price": 0.0,
            "change_24h": 0.0,
            "volatility": "Low",
            "last_check": "Never",
            "tvl": "1,420,500,210",
            "sol_status": "Operational",
            "on_chain": {} # Real-time Solana state
        }
        self._lock = threading.Lock()

    def set_authority_pubkey(self, authority_pubkey: str | None):
        with self._lock:
            self.authority_pubkey = authority_pubkey

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._stop_event.clear()
            thread = threading.Thread(target=self._monitor_loop, daemon=True)
            thread.start()
            print("[MONITOR] Background risk monitor started.")

    def stop(self):
        self.is_running = False
        self._stop_event.set()

    def _fetch_market_data(self):
        """Fetches real SOL/USDT price from CoinGecko Public API."""
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd&include_24hr_change=true"
            response = requests.get(url, timeout=10)
            data = response.json()
            sol_data = data.get('solana', {})
            return sol_data.get('usd'), sol_data.get('usd_24h_change')
        except Exception as e:
            print(f"[MONITOR ERROR] Data fetch failed: {e}")
            return None, None

    def _refresh_runtime_status(self):
        """
        Sync one snapshot of on-chain and market state.
        Returns current price or None.
        """
        if self.authority_pubkey:
            sol_status = get_status_for_authority(self.authority_pubkey)
        else:
            sol_status = {"connected": False, "account_missing": True}
        price, change_24h = self._fetch_market_data()

        with self._lock:
            self.current_status["on_chain"] = sol_status
            if price is not None:
                self.current_status["price"] = price
                self.current_status["change_24h"] = round(change_24h, 2) if change_24h is not None else 0.0
                self.current_status["last_check"] = datetime.now().strftime("%H:%M:%S")
                self.current_status["tvl"] = "1,420,500,210"

                if abs(self.current_status["change_24h"]) > 8:
                    self.current_status["volatility"] = "High"
                elif abs(self.current_status["change_24h"]) > 4:
                    self.current_status["volatility"] = "Medium"
                else:
                    self.current_status["volatility"] = "Low"

        return price

    def refresh_now(self):
        """
        Immediate refresh used by manual sync endpoint.
        """
        self._refresh_runtime_status()
        state = self.get_state()
        if self.callback:
            self.callback(state)
        return state

    def _monitor_loop(self):
        it_count = 0
        while self.is_running:
            # 1. Sync with Blockchain + Market
            price = self._refresh_runtime_status()

            if price is not None:
                # Trigger analysis on price shocks (>1.5% in 30s)
                if self.last_price and abs(price - self.last_price) / self.last_price > 0.015:
                    self._trigger_risk_analysis(f"Ценовое потрясение: SOL изменился на {round((price-self.last_price)/self.last_price*100, 2)}% за 30 секунд. Возможная манипуляция ликвидностью.")
                self.last_price = price

            # 3. Fetch News Events Every 5 mins (approx 10 iterations)
            if it_count % 10 == 0:
                news_items = self.news_engine.fetch_latest_news()
                for item in news_items:
                    low_content = item["content"].lower()
                    if any(x in low_content for x in ["hack", "exploit", "security", "vuln", "manipulation", "suspicious", "delay", "scam"]):
                        self._trigger_risk_analysis(f"НОВОСТНОЙ АЛЕРТ: {item['content']}")
                    elif it_count == 0:
                        self._trigger_risk_analysis(f"Оценка общего фона: {item['content']}")
            
            it_count += 1
            if self.callback:
                self.callback(self.get_state())
            
            # Sleep at the END of the loop, so the first run is instant
            if self._stop_event.wait(30):
                break

    def _trigger_risk_analysis(self, event_text: str):
        # Without an authorized authority pubkey we cannot read treasury state
        # nor perform on-chain actions.
        if not self.authority_pubkey:
            return
        news = NewsItem(
            id=f"auto_{int(time.time())}",
            headline="АУДИТОРСКИЙ СИГНАЛ",
            content=event_text,
            tvl=f"${self.current_status['tvl']}",
            volatility=self.current_status["volatility"]
        )
        
        try:
            assessment = self.analyzer.process_event(news)
            assessment_data = assessment.dict()
            
            with self._lock:
                self.history.insert(0, assessment_data)
                if len(self.history) > 30: self.history.pop()
                
                # ─── Autonomous Execution Logic ──────────────────────────────────
                
                # 1. Emergency Pause (High Risk)
                current_pause_state = self.current_status["on_chain"].get("is_paused", False)
                active_threshold = self.current_status["on_chain"].get("risk_threshold", 80)
                
                if assessment.action_required and assessment.risk_score >= active_threshold:
                    if not current_pause_state:
                        print(f"[AUTONOMOUS] High Risk ({assessment.risk_score}). Triggering On-Chain Pause.")
                        if self.authority_pubkey and self.tx_request_callback:
                            tx_id = f"auto_{uuid.uuid4().hex}"
                            assessment_data["tx_request_id"] = tx_id
                            assessment_data["tx_action"] = "emergency_pause"
                            assessment_data["tx_status"] = "requested"
                            prepared = prepare_emergency_pause_tx_for_client(
                                self.authority_pubkey,
                                assessment.reason,
                                assessment.risk_score,
                            )
                            self.tx_request_callback(tx_id, "emergency_pause", prepared)
                    self.safe_streak = 0
                
                # 2. DARS (Dynamic Threshold Update)
                rec_threshold = assessment.recommended_threshold
                if rec_threshold and abs(rec_threshold - active_threshold) >= 5:
                    print(f"[AUTONOMOUS] DARS: Adjusting on-chain threshold to {rec_threshold}.")
                    if self.authority_pubkey and self.tx_request_callback:
                        tx_id = f"auto_{uuid.uuid4().hex}"
                        assessment_data["tx_request_id"] = tx_id
                        assessment_data["tx_action"] = "update_threshold"
                        assessment_data["tx_status"] = "requested"
                        prepared = prepare_threshold_update_tx_for_client(self.authority_pubkey, rec_threshold)
                        self.tx_request_callback(tx_id, "update_threshold", prepared)

                # 3. Autonomous Recovery (Resume)
                if assessment.risk_score < 30:
                    self.safe_streak += 1
                    if self.safe_streak >= 5 and current_pause_state:
                        print(f"[AUTONOMOUS] Recovery detected (Safe Streak: {self.safe_streak}). Resuming Treasury.")
                        if self.authority_pubkey and self.tx_request_callback:
                            tx_id = f"auto_{uuid.uuid4().hex}"
                            assessment_data["tx_request_id"] = tx_id
                            assessment_data["tx_action"] = "resume"
                            assessment_data["tx_status"] = "requested"
                            prepared = prepare_resume_tx_for_client(self.authority_pubkey)
                            self.tx_request_callback(tx_id, "resume", prepared)
                        self.safe_streak = 0
                else:
                    self.safe_streak = 0

                # ─── Notifications ───────────────────────────────────────────────
                if assessment.risk_score >= 40:
                    self.notifications.insert(0, {
                        "id": news.id,
                        "title": "ВЕРДИКТ АУДИТА" if assessment.risk_score < 80 else "КРИТИЧЕСКАЯ УГРОЗА",
                        "message": assessment.reason,
                        "score": assessment.risk_score,
                        "time": assessment.timestamp,
                        "source": "Risk Module"
                    })
                    if len(self.notifications) > 15: self.notifications.pop()
        except Exception as e:
            print(f"[MONITOR] Analysis skipped due to Error: {e}")
            with self._lock:
                self.notifications.insert(0, {
                    "id": f"err_{int(time.time())}",
                    "title": "API Лимит / Ошибка",
                    "message": f"Ожидание квоты или сети: {str(e)[:50]}",
                    "score": 0,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "System"
                })
                if len(self.notifications) > 15: self.notifications.pop()

    def get_state(self):
        with self._lock:
            return {
                "is_running": self.is_running,
                "status": self.current_status,
                "history": self.history,
                "notifications": self.notifications
            }

    def register_tx_result(self, tx_id: str, tx_hash: str | None = None, tx_error: str | None = None):
        """
        Update history entry after client wallet signed/sent tx.
        """
        with self._lock:
            for item in self.history:
                if item.get("tx_request_id") == tx_id:
                    if tx_hash:
                        item["tx_hash"] = tx_hash
                        item["tx_status"] = "confirmed"
                    if tx_error:
                        item["tx_error"] = tx_error
                        item["tx_status"] = "error"
                    break

    def add_tx_request_history(self, tx_id: str, action: str, reason: str | None = None):
        """
        Insert a placeholder history entry for a manual tx request.
        Later, `register_tx_result` will fill tx_hash / tx_error.
        """
        with self._lock:
            ts = datetime.now().strftime("%H:%M:%S")
            self.history.insert(0, {
                "id": tx_id[:8],
                "risk_score": 0,
                "reason": reason or f"Запрошена транзакция: {action}",
                "action_required": False,
                "recommended_threshold": None,
                "confidence_score": 0,
                "timestamp": ts,
                "tx_request_id": tx_id,
                "tx_action": action,
                "tx_status": "requested",
            })
            if len(self.history) > 30:
                self.history.pop()

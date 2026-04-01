import time
import threading
import requests
from datetime import datetime
from agent.analyzer import AIAnalyzer
from agent.models import NewsItem, RiskAssessment
from agent.news_engine import NewsEngine
from agent.solana_client import (
    get_status, 
    execute_emergency_pause, 
    execute_resume, 
    execute_threshold_update
)

class BackgroundMonitor:
    """
    The 'Autonomous Organism' that follows the market 24/7.
    Fetches real price and news data to trigger AI analysis.
    Now with DARS (Dynamic Thresholds) and Auto-Recovery.
    """
    def __init__(self, analyzer: AIAnalyzer, callback=None):
        self.analyzer = analyzer
        self.callback = callback
        self.news_engine = NewsEngine()
        self.last_price = None
        self.history = []
        self.notifications = []
        self.is_running = False
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

    def start(self):
        if not self.is_running:
            self.is_running = True
            thread = threading.Thread(target=self._monitor_loop, daemon=True)
            thread.start()
            print("[MONITOR] Gov-Grade Autonomous Organism started.")

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

    def _monitor_loop(self):
        it_count = 0
        while self.is_running:
            # 1. Sync with Blockchain State Every Loop
            sol_status = get_status()
            
            # 2. Fetch Market Data Every 30s
            price, change_24h = self._fetch_market_data()
            
            with self._lock:
                self.current_status["on_chain"] = sol_status
                if price:
                    self.current_status["price"] = price
                    self.current_status["change_24h"] = round(change_24h, 2) if change_24h else 0.0
                    self.current_status["last_check"] = datetime.now().strftime("%H:%M:%S")
                    
                    # Simulated TVL fluctuation for 'Reality'
                    tvl_num = int(self.current_status["tvl"].replace(",", ""))
                    tvl_num += (int(time.time() % 100) - 50) * 1000 # +/- 50k
                    self.current_status["tvl"] = "{:,}".format(tvl_num)

                    # Dynamic Volatility Calculation
                    if abs(self.current_status["change_24h"]) > 8:
                        self.current_status["volatility"] = "High"
                    elif abs(self.current_status["change_24h"]) > 4:
                        self.current_status["volatility"] = "Medium"
                    else:
                        self.current_status["volatility"] = "Low"

            if price:
                # Trigger analysis on price shocks (>1.5% in 30s)
                if self.last_price and abs(price - self.last_price) / self.last_price > 0.015:
                    self._trigger_ai_analysis(f"Ценовое потрясение: SOL изменился на {round((price-self.last_price)/self.last_price*100, 2)}% за 30 секунд. Возможная манипуляция ликвидностью.")
                self.last_price = price

            # 3. Fetch News Events Every 5 mins (approx 10 iterations)
            if it_count % 10 == 0:
                news_items = self.news_engine.fetch_latest_news()
                for item in news_items:
                    low_content = item["content"].lower()
                    if any(x in low_content for x in ["hack", "exploit", "security", "vuln", "manipulation", "suspicious", "delay", "scam"]):
                        self._trigger_ai_analysis(f"НОВОСТНОЙ АЛЕРТ: {item['content']}")
                    elif it_count == 0:
                        self._trigger_ai_analysis(f"Оценка общего фона: {item['content']}")
            
            it_count += 1
            if self.callback:
                self.callback(self.get_state())
            time.sleep(30)

    def _trigger_ai_analysis(self, event_text: str):
        news = NewsItem(
            id=f"auto_{int(time.time())}",
            headline="АУДИТОРСКИЙ СИГНАЛ",
            content=event_text,
            tvl=f"${self.current_status['tvl']}",
            volatility=self.current_status["volatility"]
        )
        
        assessment = self.analyzer.analyze_news(news)
        
        with self._lock:
            self.history.insert(0, assessment)
            if len(self.history) > 30: self.history.pop()
            
            # ─── Autonomous Execution Logic ──────────────────────────────────
            
            # 1. Emergency Pause (High Risk)
            current_pause_state = self.current_status["on_chain"].get("is_paused", False)
            active_threshold = self.current_status["on_chain"].get("risk_threshold", 80)
            
            if assessment.action_required and assessment.risk_score >= active_threshold:
                if not current_pause_state:
                    print(f"[AUTONOMOUS] High Risk ({assessment.risk_score}). Triggering On-Chain Pause.")
                    execute_emergency_pause(assessment.reason, assessment.risk_score)
                self.safe_streak = 0
            
            # 2. DARS (Dynamic Threshold Update)
            rec_threshold = assessment.recommended_threshold
            if rec_threshold and abs(rec_threshold - active_threshold) >= 5:
                print(f"[AUTONOMOUS] DARS: Adjusting on-chain threshold to {rec_threshold}.")
                execute_threshold_update(rec_threshold)

            # 3. Autonomous Recovery (Resume)
            if assessment.risk_score < 30:
                self.safe_streak += 1
                if self.safe_streak >= 5 and current_pause_state:
                    print(f"[AUTONOMOUS] Recovery detected (Safe Streak: {self.safe_streak}). Resuming Treasury.")
                    execute_resume()
                    self.safe_streak = 0
            else:
                self.safe_streak = 0

            # ─── Notifications ───────────────────────────────────────────────
            if assessment.risk_score >= 40:
                self.notifications.insert(0, {
                    "id": news.id,
                    "title": "ВЕРДИКТ ОРАКУЛА" if assessment.risk_score < 80 else "КРИТИЧЕСКАЯ УГРОЗА",
                    "message": assessment.reason,
                    "score": assessment.risk_score,
                    "time": assessment.timestamp,
                    "source": "AI Organism"
                })
                if len(self.notifications) > 15: self.notifications.pop()

    def get_state(self):
        with self._lock:
            return {
                "status": self.current_status,
                "history": [h.dict() for h in self.history],
                "notifications": self.notifications
            }

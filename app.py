import sys
import logging
import warnings
warnings.filterwarnings('ignore')

from flask import Flask, request, jsonify, render_template
from agent.analyzer import AIAnalyzer
from agent.models import NewsItem
from agent.solana_client import verify_solana_or_crash

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
verify_solana_or_crash()
analyzer = AIAnalyzer()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.json
    text = data.get('news', '')
    tvl = data.get('tvl', 'Неизвестно')
    volatility = data.get('volatility', 'Medium')
    
    if not text:
        return jsonify({"error": "Пустой текст"}), 400
        
    news = NewsItem(
        id="manual", 
        headline="Метрики Оракула", 
        content=text, 
        tvl=tvl, 
        volatility=volatility
    )
    
    try:
        assessment = analyzer.analyze_news(news)
        return jsonify({
            "risk_score": assessment.risk_score,
            "reason": assessment.reason,
            "action_required": assessment.action_required
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("\n======================================================")
    print("   [ Сервер Запущен ]")
    print("======================================================")
    print("=> Откройте в браузере: http://127.0.0.1:5000\n")
    app.run(port=5000, debug=False)

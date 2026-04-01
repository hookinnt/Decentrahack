from pydantic import BaseModel, Field
from datetime import datetime

class RiskAssessment(BaseModel):
    risk_score: int = Field(..., description="Оценка риска от 0 до 100, где 100 - критический риск потери средств.")
    reason: str = Field(..., description="Краткое объяснение, почему выставлена такая оценка, на русском языке.")
    action_required: bool = Field(..., description="Требуется ли экстренное вмешательство смарт-контракта (True/False).")
    recommended_threshold: int | None = Field(default=80, description="Новый порог чувствительности (50-95), если AI решит адаптировать контракт.")
    confidence_score: int = Field(default=100, description="Уровень уверенности ИИ в своем решении (0-100%).")
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))

class NewsItem(BaseModel):
    id: str
    headline: str
    content: str
    tvl: str = Field(default="N/A", description="Total Value Locked в протоколе")
    volatility: str = Field(default="Medium", description="Уровень волатильности на рынке (Low/Medium/High)")

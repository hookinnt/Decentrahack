from pydantic import BaseModel, Field

class RiskAssessment(BaseModel):
    risk_score: int = Field(..., description="Оценка риска от 0 до 100, где 100 - критический риск потери средств.")
    reason: str = Field(..., description="Краткое объяснение, почему выставлена такая оценка, на русском языке.")
    action_required: bool = Field(..., description="Требуется ли экстренное вмешательство смарт-контракта (True/False).")

class NewsItem(BaseModel):
    id: str
    headline: str
    content: str
    tvl: str = Field(default="N/A", description="Total Value Locked в протоколе")
    volatility: str = Field(default="Medium", description="Уровень волатильности на рынке (Low/Medium/High)")

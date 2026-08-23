from app.models.fx_rate import FxRate
from app.models.holding import Holding
from app.models.news_item import NewsItem
from app.models.price_history import PriceHistory
from app.models.purchase import Purchase
from app.models.summary import Summary
from app.models.user import User

ALL_MODELS = [User, Holding, Purchase, PriceHistory, FxRate, NewsItem, Summary]

__all__ = [
    "User",
    "Holding",
    "Purchase",
    "PriceHistory",
    "FxRate",
    "NewsItem",
    "Summary",
    "ALL_MODELS",
]

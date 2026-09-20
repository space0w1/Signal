from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import fx, graph, health, holdings, news, portfolio, summary, symbols
from app.core.config import settings
from app.db import database, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def db_connection_middleware(request: Request, call_next):
    database.connect(reuse_if_open=True)
    try:
        return await call_next(request)
    finally:
        if not database.is_closed():
            database.close()


app.include_router(health.router, prefix="/api")
app.include_router(holdings.router, prefix="/api")
app.include_router(fx.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(summary.router, prefix="/api")
app.include_router(symbols.router, prefix="/api")

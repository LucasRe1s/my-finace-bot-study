from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import transactions, summary, limits, groups

app = FastAPI(title="my-finance-bot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions.router)
app.include_router(summary.router)
app.include_router(limits.router)
app.include_router(groups.router)


@app.get("/health")
def health():
    return {"status": "ok"}

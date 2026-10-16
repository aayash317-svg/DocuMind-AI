from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.api.routes import router
from backend.app.auth.routes import router as auth_router
from backend.app.chat.routes import router as chat_router
from backend.app.retrieval.hybrid import hybrid_retriever


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure storage directories and sync in-memory BM25 index
    settings.setup_directories()
    hybrid_retriever.sync_bm25_index()
    yield
    # Shutdown logic if needed


app = FastAPI(
    title="DocuMind AI",
    description="Evidence-grounded local RAG assistant with hybrid retrieval, authentication, and verified citations.",
    version="0.2.0",
    lifespan=lifespan
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(router)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=True)


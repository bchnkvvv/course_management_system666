from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base, get_async_pool
from app.routers import courses, users, schedule, hierarchy

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Создаём пул соединений
    pool = await get_async_pool()
    app.state.db_pool = pool
    
    yield
    
    # Shutdown
    print("Shutting down...")
    await engine.dispose()
    await pool.close()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Регистрация роутеров
app.include_router(courses.router, prefix=settings.API_PREFIX)
app.include_router(users.router, prefix=settings.API_PREFIX)
app.include_router(schedule.router, prefix=settings.API_PREFIX)
app.include_router(hierarchy.router, prefix=settings.API_PREFIX)

@app.get("/")
async def root():
    return {
        "message": "Course Management System API",
        "version": "1.0.0",
        "data_sources": ["ORM (SQLAlchemy)", "Native SQL"],
        "swagger": "/docs"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}
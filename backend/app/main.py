from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base, get_async_pool
from app.routers import courses, users, schedule, hierarchy
from app.routers import departments

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    pool = await get_async_pool()
    app.state.db_pool = pool
    print("Database connected!")
    
    yield
    
    print("Shutting down...")
    await engine.dispose()
    await app.state.db_pool.close()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(courses.router, prefix=settings.API_PREFIX)
app.include_router(users.router, prefix=settings.API_PREFIX)
app.include_router(schedule.router, prefix=settings.API_PREFIX)
app.include_router(hierarchy.router, prefix=settings.API_PREFIX)
app.include_router(departments.router, prefix=settings.API_PREFIX)

@app.get("/")
async def root():
    return {
        "message": "Course Management System API",
        "version": "1.0.0",
        "endpoints": "/docs"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}
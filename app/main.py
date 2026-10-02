from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from config import STATIC_DIR
from app.routes import chat, images, models, oauth, api

app = FastAPI(
    title="Antigravity Proxy",
    description="High-performance async proxy for Google Antigravity & Gemini API with Nano Banana 2 image generation",
    version="1.0.0"
)

# Enable CORS for all clients (Cursor, OpenCode, VS Code, Web Apps)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(chat.router)
app.include_router(images.router)
app.include_router(models.router)
app.include_router(oauth.router)
app.include_router(api.router)

# Mount Static Files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Antigravity Proxy Running"}

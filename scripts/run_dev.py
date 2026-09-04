import os
import sys
import uvicorn

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    print(f"Starting {settings.APP_NAME} in [{settings.APP_ENV}] mode...")
    print(f"Backend API:        http://{settings.HOST}:{settings.PORT}")
    print(f"Health Probe:       http://{settings.HOST}:{settings.PORT}/health")
    if settings.ENABLE_DOCS:
        print(f"API Documentation:  http://{settings.HOST}:{settings.PORT}/docs")
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower(),
    )

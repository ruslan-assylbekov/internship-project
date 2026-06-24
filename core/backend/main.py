import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api import book_router, user_router, weather_router

app = FastAPI()

origins = ["*"]
app.add_middleware(CORSMiddleware, 
    allow_origins = origins, # allow all origins from above
    allow_credentials=True,
    allow_methods=["*"], # allow all methods
    allow_headers=["*"],
    )

@app.middleware("http")
async def log_requests(request, call_next):
    start = time.time()
    response = await call_next(request) #момент когда запрос приходит на сайт
    duration = time.time() - start
    print(f"{request.method} {request.url.path} took {duration:0.4f} seconds")
    response.headers["request-process-time"] = f"{duration:.4f}" # можно вот так создавать свой header
    return response

app.include_router(user_router.router)
app.include_router(book_router.router)
app.include_router(weather_router.router)

#uvicorn core.backend.main:app --reload
#.venv\Scripts\activate
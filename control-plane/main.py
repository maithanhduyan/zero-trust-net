import uvicorn
from fastapi import FastAPI
# Import router từ file endpoints nằm trong thư mục con
from api.v1.endpoints import router as api_router

# 1. Khởi tạo FastAPI App tại đây
app = FastAPI(title="Zero Trust Control Plane")

# 2. Gắn Router vào App
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "control-plane"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
# control-plane/main.py
import uvicorn
from api import app

if __name__ == "__main__":
    # Chạy server tại port 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
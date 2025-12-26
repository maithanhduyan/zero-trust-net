# control-plane/config.py
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Cấu hình Database
    DATABASE_URL: str = "sqlite:///./zerotrust.db"

    # Cấu hình mạng WireGuard (Overlay Network)
    OVERLAY_NETWORK: str = "10.0.0.0/24"

    # Thông tin của HUB Server (VPS-1)
    # Đây là thông tin mà các Agent sẽ dùng để kết nối về
    HUB_PUBLIC_KEY: str = os.getenv("HUB_PUBLIC_KEY", "Thay_Bang_Public_Key_Cua_VPS1")
    HUB_ENDPOINT: str = os.getenv("HUB_ENDPOINT", "ip.cua.vps.1:51820")

    # Token bí mật để Admin gọi API (đơn giản hóa authentication)
    ADMIN_SECRET: str = "secret-admin-token"

settings = Settings()
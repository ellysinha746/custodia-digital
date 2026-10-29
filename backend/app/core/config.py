from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Sprint 2: a partir de este tamaño, el hash se calcula en segundo plano
    # y el archivo responde "procesando" en vez de bloquear la subida.
    UMBRAL_ARCHIVO_PESADO_MB: float = 1.0

    # Sprint 3: dias que un caso eliminado permanece en la papelera
    # antes de borrarse en forma definitiva.
    DIAS_PAPELERA: int = 30
    
    # Sprint 4: cada cuántos minutos se revisa la integridad de todos los archivos
    ESCANEO_INTEGRIDAD_MIN: float = 5

    # Sprint 4: correo de alertas. Si SMTP_HOST queda vacío, el correo
    # se imprime en la consola del backend (modo desarrollo).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_TLS: bool = True
    ALERTAS_EMAIL_ADMIN: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
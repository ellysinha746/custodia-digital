from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
        # Sprint 6 (historia 25): sesión persistente. Con "Recordarme" el refresh token
    # dura REFRESH_TOKEN_EXPIRE_DAYS días; sin marcarlo, REFRESH_SIN_RECORDAR_HORAS horas.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_SIN_RECORDAR_HORAS: int = 12
    
    # Sprint 6 (historia 27): bloqueo por intentos fallidos de login.
    MAX_INTENTOS_LOGIN: int = 5
    BLOQUEO_LOGIN_MIN: int = 15
    
    # Sprint 6 (historia 24): verificación en dos pasos (TOTP).
    TOTP_EMISOR: str = "CustodiaDigital"            # nombre que aparece en la app autenticadora
    TOTP_ROLES_OBLIGATORIO: str = "admin,fiscal"    # roles que no entran sin 2FA
    TOKEN_2FA_MIN: int = 10                         # minutos para escribir los códigos tras la contraseña

    # Sprint 6 (historia 27): tamaño máximo de una evidencia subida.
    MAX_SUBIDA_MB: int = 1024

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
    
    # Sprint 6 (historia 26): recordatorio de plazos por vencer.
    RECORDATORIO_DIAS_ANTES: float = 2      # avisar cuando falten estos días o menos
    RECORDATORIOS_CADA_MIN: float = 60      # cada cuánto se revisan los plazos
    
    # Sprint 6 (historia 22): dónde se guarda la evidencia.
    #   local → carpeta backend/storage (como hasta el Sprint 5)
    #   s3    → bucket S3 o MinIO (los archivos antiguos en disco siguen funcionando)
    STORAGE_BACKEND: str = "local"
    S3_ENDPOINT_URL: str = ""               # http://minio:9000 con MinIO; vacío para AWS S3
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "custodia-evidencias"
    S3_REGION: str = "us-east-1"

    class Config:
        env_file = ".env"

settings = Settings()
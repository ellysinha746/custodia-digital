from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    # Sprint 6 (historia 27): clave de los sellos HMAC de reportes y actas, separada de la
    # de sesiones. Si queda vacía se usa SECRET_KEY (compatibilidad con lo ya emitido).
    SELLO_SECRET_KEY: str = ""
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

    # Sprint 6 (historia 21): sello de tiempo RFC 3161 de una autoridad externa (TSA).
    # Si TSA_URL queda vacío, los reportes y actas se emiten solo con el sello HMAC propio.
    TSA_URL: str = "https://freetsa.org/tsr"
    TSA_NOMBRE: str = "FreeTSA (freetsa.org)"
    TSA_TIMEOUT_SEG: float = 8
    TSA_CA_FILE: str = ""      # vacío → app/certs/freetsa_cacert.pem
    TSA_CERT_FILE: str = ""    # vacío → app/certs/freetsa_tsa.crt
    # Sprint 8 (historia 38): consulta de reputación del hash en VirusTotal (solo el hash, nunca el archivo).
    VIRUSTOTAL_API_KEY: str = ""   # vacío → la función queda desactivada
    VIRUSTOTAL_TIMEOUT_SEG: float = 8

    # Sprint 7 (historia 29): OCR con Tesseract dentro del servidor.
    OCR_IDIOMA: str = "spa"
    OCR_DPI: int = 300            # resolución al convertir páginas de PDF escaneado
    OCR_MAX_PAGINAS: int = 30     # documentos más largos: se leen las primeras N páginas
    OCR_AUTOMATICO: bool = True   # leer el texto al subir imágenes y PDFs

    # Sprint 7 (historia 34): borrador descriptivo asistido por IA (Claude, de Anthropic).
    # Sin ANTHROPIC_API_KEY la función queda desactivada (nada sale del laboratorio).
    ANTHROPIC_API_KEY: str = ""
    IA_MODELO: str = "claude-opus-5-5"
    IA_ESFUERZO: str = "high"
    IA_MAX_DOCUMENTOS: int = 8

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

    # Sprint 7 (historia 33): alertas también por Telegram. Sin token, queda desactivado.
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""   # id del grupo del laboratorio (suele ser negativo: -100...)

    # Sprint 7 (historia 32): dirección con la que se abren los QR de verificación pública.
    # En la demo con celular: http://<IP-de-la-PC-en-la-red>:8000 (localhost no sirve en el celular).
    PUBLICO_BASE_URL: str = "http://localhost:8000"
    
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
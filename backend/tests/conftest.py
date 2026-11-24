"""Sprint 8 (historia 37): configuración común de las pruebas automáticas.

Las pruebas usan claves FALSAS de prueba: nunca las del .env real. DATABASE_URL se toma del
entorno (en Docker y en GitHub Actions apunta a la base de pruebas); si no hay, se usa una local.
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/custodia_test")
os.environ["SECRET_KEY"] = "clave-falsa-solo-para-pruebas"
os.environ["SELLO_SECRET_KEY"] = "sello-falso-solo-para-pruebas"
os.environ["TELEGRAM_BOT_TOKEN"] = ""      # las pruebas nunca envían mensajes reales
os.environ["ANTHROPIC_API_KEY"] = ""       # ni llaman a la IA

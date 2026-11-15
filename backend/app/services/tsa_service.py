"""Sprint 6 (historia 21): sello de tiempo RFC 3161 emitido por una autoridad externa (FreeTSA).

El sello HMAC propio (historia 16) prueba que el documento salió de CustodiaDigital, pero la
hora la pone nuestro propio servidor. El sello RFC 3161 lo firma un TERCERO de confianza (una
TSA): prueba que esos datos exactos existían a esa hora, y cualquiera puede comprobarlo con
OpenSSL sin confiar en nosotros:

    openssl ts -verify -data datos_sellados.txt -in sello.tsr \
        -CAfile freetsa_cacert.pem -untrusted freetsa_tsa.crt

Se usa la herramienta `openssl ts` (la misma que usaría un perito externo para verificar).
Si la TSA no responde (sin internet), el documento se emite igual, sin sello externo.
"""
import re
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.config import settings

CERTS = Path(__file__).resolve().parent.parent / "certs"
MESES = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


@dataclass
class SelloTiempo:
    token: bytes        # respuesta .tsr tal cual la firmó la TSA
    fecha: datetime     # hora UTC certificada por la TSA
    serie: str          # número de serie del sello en la TSA
    tsa: str            # quién lo emitió


def _ca() -> str:
    return settings.TSA_CA_FILE or str(CERTS / "freetsa_cacert.pem")


def _cert_tsa() -> str:
    return settings.TSA_CERT_FILE or str(CERTS / "freetsa_tsa.crt")


def _openssl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["openssl", "ts", *args], capture_output=True, text=True, timeout=20)


def _leer_respuesta(ruta_tsr: str) -> tuple:
    """Fecha y número de serie del sello (texto de `openssl ts -reply -text`)."""
    texto = _openssl("-reply", "-in", ruta_tsr, "-text").stdout
    serie = re.search(r"Serial number:\s*(\S+)", texto)
    m = re.search(r"Time stamp:\s*(\w{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?\s+(\d{4})", texto)
    if not (serie and m):
        raise ValueError("respuesta de la TSA sin fecha o número de serie")
    mes, dia, hh, mm, ss, anio = m.groups()
    fecha = datetime(int(anio), MESES[mes], int(dia), int(hh), int(mm), int(ss), tzinfo=timezone.utc)
    return fecha, serie.group(1)


def sellar(datos: bytes) -> Optional[SelloTiempo]:
    """Pide un sello RFC 3161 sobre el SHA-256 de `datos`. Devuelve None si no se pudo:
    quien llama emite el documento igual, indicando que no tiene sello externo."""
    if not settings.TSA_URL:
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="tsa_") as d:
            ruta_datos, ruta_tsq, ruta_tsr = f"{d}/datos", f"{d}/q.tsq", f"{d}/r.tsr"
            Path(ruta_datos).write_bytes(datos)
            # -cert: que la TSA incluya su certificado; la consulta lleva un nonce aleatorio.
            consulta = _openssl("-query", "-data", ruta_datos, "-sha256", "-cert", "-out", ruta_tsq)
            if consulta.returncode != 0:
                raise RuntimeError(consulta.stderr.strip())
            peticion = urllib.request.Request(
                settings.TSA_URL,
                data=Path(ruta_tsq).read_bytes(),
                headers={"Content-Type": "application/timestamp-query"},
            )
            with urllib.request.urlopen(peticion, timeout=settings.TSA_TIMEOUT_SEG) as r:
                Path(ruta_tsr).write_bytes(r.read())
            # Se verifica contra la consulta: mismo hash, mismo nonce y firma válida de la TSA.
            v = _openssl("-verify", "-in", ruta_tsr, "-queryfile", ruta_tsq, "-CAfile", _ca(), "-untrusted", _cert_tsa())
            if v.returncode != 0 or "Verification: OK" not in v.stdout:
                raise RuntimeError(f"la respuesta de la TSA no verifica: {v.stderr.strip()[:200]}")
            fecha, serie = _leer_respuesta(ruta_tsr)
            return SelloTiempo(token=Path(ruta_tsr).read_bytes(), fecha=fecha, serie=serie, tsa=settings.TSA_NOMBRE)
    except Exception as e:  # sin internet, TSA caída, respuesta inválida...
        print(f"[tsa] No se obtuvo sello RFC 3161: {e}", flush=True)
        return None


def verificar(datos: bytes, token: bytes) -> bool:
    """Comprueba (sin internet) que el sello corresponde a estos datos y lo firmó la TSA."""
    try:
        with tempfile.TemporaryDirectory(prefix="tsa_") as d:
            Path(f"{d}/datos").write_bytes(datos)
            Path(f"{d}/r.tsr").write_bytes(token)
            v = _openssl("-verify", "-data", f"{d}/datos", "-in", f"{d}/r.tsr", "-CAfile", _ca(), "-untrusted", _cert_tsa())
            return v.returncode == 0 and "Verification: OK" in v.stdout
    except Exception as e:
        print(f"[tsa] No se pudo verificar el sello: {e}", flush=True)
        return False


LEEME = """SELLO DE TIEMPO RFC 3161 - CustodiaDigital
==========================================

{documento}

  Datos sellados:   datos_sellados.txt
  Sello (TSA):      sello.tsr
  Emitido por:      {tsa}
  Fecha UTC:        {fecha}
  N° de serie:      {serie}

El sello lo firmó una autoridad de sellado de tiempo EXTERNA. Prueba que los datos de
datos_sellados.txt (que incluyen el hash SHA-256 del documento) existían en esa fecha y no
cambiaron. Se puede comprobar con OpenSSL, sin depender de CustodiaDigital:

  openssl ts -verify -data datos_sellados.txt -in sello.tsr -CAfile freetsa_cacert.pem -untrusted freetsa_tsa.crt

Debe responder "Verification: OK". Para ver el contenido del sello:

  openssl ts -reply -in sello.tsr -text
"""


def paquete_zip(datos: bytes, token: bytes, documento: str, fecha: datetime, serie: str, tsa: str) -> bytes:
    """ZIP con todo lo necesario para que un tercero verifique el sello por su cuenta."""
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("datos_sellados.txt", datos)
        z.writestr("sello.tsr", token)
        z.write(_ca(), "freetsa_cacert.pem")
        z.write(_cert_tsa(), "freetsa_tsa.crt")
        z.writestr("LEEME.txt", LEEME.format(
            documento=documento, tsa=tsa, serie=serie,
            fecha=fecha.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC"),
        ))
    return buffer.getvalue()

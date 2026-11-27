import json
import urllib.error
import urllib.request

from app.core.config import settings

URL = "https://www.virustotal.com/api/v3/files/{hash}"


def consultar_hash(sha256: str) -> dict:
    """Consulta la reputación de un SHA-256 en VirusTotal. Nunca envía el archivo."""
    if not settings.VIRUSTOTAL_API_KEY:
        return {"estado": "no_configurado"}
    req = urllib.request.Request(
        URL.format(hash=sha256), headers={"x-apikey": settings.VIRUSTOTAL_API_KEY}
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.VIRUSTOTAL_TIMEOUT_SEG) as r:
            datos = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"estado": "desconocido"}  # VT nunca vio este archivo
        if e.code == 429:
            return {"estado": "limite"}       # cuota gratuita agotada
        return {"estado": "error"}
    except Exception:
        return {"estado": "error"}
    attrs = datos.get("data", {}).get("attributes", {})
    s = attrs.get("last_analysis_stats", {})
    malicioso = int(s.get("malicious", 0))
    sospechoso = int(s.get("suspicious", 0))
    total = sum(int(v) for v in s.values())
    return {
        "estado": "malicioso" if (malicioso or sospechoso) else "limpio",
        "malicioso": malicioso,
        "sospechoso": sospechoso,
        "total": total,
        "enlace": f"https://www.virustotal.com/gui/file/{sha256}",
    }
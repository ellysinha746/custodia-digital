import csv
import io
import re
from typing import Dict, Optional

from fastapi import HTTPException

# Sprint 4 (historias 13 y 17): ficha de metadatos del dispositivo de origen.
# Orden y etiquetas que se usan en la comparación y en la exportación.
CAMPOS_FICHA = {
    "imei": "IMEI",
    "modelo": "Modelo",
    "mac": "Dirección MAC",
    "sistema_operativo": "Sistema operativo",
}

_MAC_RE = re.compile(r"^[0-9A-F]{12}$")


def _luhn_valido(numero: str) -> bool:
    """El IMEI de 15 dígitos lleva un dígito verificador Luhn."""
    total = 0
    for i, d in enumerate(reversed(numero)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def normalizar_ficha(datos: Dict[str, Optional[str]]) -> Dict[str, str]:
    """Limpia y valida la ficha. Devuelve solo los campos con valor.
    - IMEI: solo dígitos, 15 con verificador Luhn (o 14 sin verificador).
    - MAC: se guarda como AA:BB:CC:DD:EE:FF.
    - Modelo / SO: texto sin espacios sobrantes.
    Lanza 422 si algún valor no tiene formato válido."""
    ficha: Dict[str, str] = {}
    for clave in CAMPOS_FICHA:
        valor = (datos.get(clave) or "").strip()
        if not valor:
            continue

        if clave == "imei":
            digitos = re.sub(r"\D", "", valor)
            if len(digitos) not in (14, 15) or (len(digitos) == 15 and not _luhn_valido(digitos)):
                raise HTTPException(
                    status_code=422,
                    detail="IMEI inválido: deben ser 15 dígitos con dígito verificador correcto.",
                )
            valor = digitos
        elif clave == "mac":
            hexa = re.sub(r"[^0-9A-Fa-f]", "", valor).upper()
            if not _MAC_RE.match(hexa):
                raise HTTPException(
                    status_code=422,
                    detail="Dirección MAC inválida: deben ser 12 caracteres hexadecimales (ej. AA:BB:CC:DD:EE:FF).",
                )
            valor = ":".join(hexa[i:i + 2] for i in range(0, 12, 2))
        else:
            valor = " ".join(valor.split())

        ficha[clave] = valor
    return ficha


def _para_comparar(clave: str, valor: str) -> str:
    # Modelo y SO no distinguen mayúsculas ("iOS 17" == "ios 17").
    return valor if clave in ("imei", "mac") else valor.casefold()


def comparar_fichas(registrada: Dict[str, str], actual: Dict[str, str]):
    """Compara campo por campo. Estados posibles por campo:
    coincide | distinto | no_verificado (registrado pero no se ingresó ahora)
    | sin_registro (se ingresó ahora pero no se registró en la subida)."""
    campos = []
    for clave, etiqueta in CAMPOS_FICHA.items():
        r = registrada.get(clave)
        a = actual.get(clave)
        if r and a:
            estado = "coincide" if _para_comparar(clave, r) == _para_comparar(clave, a) else "distinto"
        elif r:
            estado = "no_verificado"
        elif a:
            estado = "sin_registro"
        else:
            continue
        campos.append({"campo": clave, "etiqueta": etiqueta, "registrado": r, "actual": a, "estado": estado})
    return campos


def ficha_a_csv(filas) -> bytes:
    """Lista de (campo, valor) → CSV en UTF-8 con BOM para que Excel lea bien las tildes."""
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(["campo", "valor"])
    for campo, valor in filas:
        escritor.writerow([campo, "" if valor is None else valor])
    return ("﻿" + salida.getvalue()).encode("utf-8")
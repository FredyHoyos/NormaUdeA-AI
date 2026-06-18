import os
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from supabase import create_client
from urllib3.util.retry import Retry

# =========================
# Configuración general
# =========================
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el .env")

supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


BASE_URL = "https://normativa.udea.edu.co"
URL_CONSULTA = f"{BASE_URL}/Documentos/Consultar"
URL_VER = f"{BASE_URL}/Documentos/Ver"
URL_DOCUMENTO = f"{BASE_URL}/Documentos/Documento"

BUCKET_NAME = "pdfs-normativa"
TABLE_NAME = "normativas_udea"

TIMEOUT = (15, 120)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": URL_CONSULTA,
    "Origin": BASE_URL,
    "Connection": "keep-alive",
}

# =========================
# Sesión con reintentos
# =========================
session = requests.Session()
session.headers.update(HEADERS)

retry = Retry(
    total=5,
    connect=5,
    read=5,
    status=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=frozenset(["GET", "POST"]),
)

adapter = HTTPAdapter(max_retries=retry)
session.mount("https://", adapter)
session.mount("http://", adapter)


# =========================
# Utilidades
# =========================
def slugify(text: str) -> str:
    text = text.lower().strip()
    text = "".join(c for c in text if c.isalnum() or c in (" ", "_", "-"))
    text = text.replace(" ", "_")
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def get_hidden_fields(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    data = {}
    for inp in soup.select("input[name]"):
        name = inp.get("name")
        value = inp.get("value", "")
        if name:
            data[name] = value
    return data


def extraer_codigodocumento(href: str) -> str | None:
    patrones = [
        r"codigodocumento=(\d+)",
        r"verdocumento\('(\d+)'",
        r"verdocumento\((\d+)",
        r"/Documentos/Documento\?codigodocumento=(\d+)",
    ]
    for patron in patrones:
        m = re.search(patron, href, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def extraer_codigoimagen(html: str) -> str | None:
    patrones = [
        r"/Documentos/Documento\?codigodocumento=\d+&codigoimagen=(\d+)&buscarpdf=",
        r"codigoimagen=(\d+)",
        r"codigoiimagen=(\d+)",
    ]
    for patron in patrones:
        m = re.search(patron, html, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def descargar_pdf_real(codigodocumento: str) -> tuple[bytes | None, str | None]:
    """
    Devuelve (bytes_del_pdf, url_final).
    """
    # 1) Abrir el visor
    r = session.get(
        URL_VER,
        params={
            "codigodocumento": codigodocumento,
            "codigoiimagen": "",
            "buscarpdf": "",
            "_": str(int(time.time() * 1000)),
        },
        timeout=TIMEOUT,
        allow_redirects=True,
    )
    r.raise_for_status()

    ct = r.headers.get("Content-Type", "").lower()

    # Caso ideal: ya devuelve PDF
    if "application/pdf" in ct:
        return r.content, r.url

    # 2) Buscar codigoimagen dentro del HTML del visor
    codigoimagen = extraer_codigoimagen(r.text)

    candidatos = []

    if codigoimagen:
        candidatos.append(
            f"{URL_DOCUMENTO}?codigodocumento={codigodocumento}&codigoimagen={codigoimagen}&buscarpdf="
        )

    # 3) Buscar enlaces directos dentro del HTML
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/Documentos/Documento?" in href:
            candidatos.append(urljoin(BASE_URL, href))

    # 4) Fallback: intentar con codigoimagen vacío
    candidatos.append(
        f"{URL_DOCUMENTO}?codigodocumento={codigodocumento}&codigoimagen=&buscarpdf="
    )

    vistos = set()
    candidatos_filtrados = []
    for c in candidatos:
        if c not in vistos:
            vistos.add(c)
            candidatos_filtrados.append(c)

    for pdf_url in candidatos_filtrados:
        pdf_res = session.get(pdf_url, timeout=TIMEOUT, allow_redirects=True)
        pdf_res.raise_for_status()

        content_type = pdf_res.headers.get("Content-Type", "").lower()
        content_disposition = pdf_res.headers.get("Content-Disposition", "").lower()

        if (
            "application/pdf" in content_type
            or "octet-stream" in content_type
            or ".pdf" in content_disposition
        ):
            return pdf_res.content, pdf_res.url

    return None, r.url


def subir_a_supabase(pdf_bytes: bytes, nombre_fichero: str) -> str:
    supabase_client.storage.from_(BUCKET_NAME).upload(
        path=nombre_fichero,
        file=pdf_bytes,
        file_options={"content-type": "application/pdf"},
    )
    return supabase_client.storage.from_(BUCKET_NAME).get_public_url(nombre_fichero)


def procesar_consulta_api(asunto_valor: str):
    print(f"\n[+] Consultando: {asunto_valor}")

    try:
        # Abrir página para cookies / hidden fields
        home = session.get(URL_CONSULTA, timeout=TIMEOUT)
        home.raise_for_status()

        form_data = get_hidden_fields(home.text)
        form_data.update(
            {
                "tipobusqueda": "indices",
                "restringido": "no",
                "ordenarpor": "indice2 DESC",
                "CurrentPage": "1",
                "pdfini": "0",
                "pdffin": "0",
                "pdfcodigoinicial": "0",
                "buscartodo": "",
                "tipodocumento": "",
                "dependencia": "",
                "asunto": asunto_valor,
                "fecha": "",
            }
        )

        response = session.post(URL_CONSULTA, data=form_data, timeout=TIMEOUT)
        response.raise_for_status()

    except requests.exceptions.ReadTimeout:
        print(f"   ⚠️ Timeout consultando: {asunto_valor}")
        return
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️ Error de red consultando {asunto_valor}: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    filas = soup.find_all("tr", class_="documento")

    print(f"📊 Filas encontradas: {len(filas)}")

    for fila in filas:
        try:
            celdas = fila.find_all("td")
            if not celdas:
                continue

            enlace_a = fila.find("a", href=True)
            if not enlace_a:
                continue

            numero = enlace_a.get_text(strip=True)
            href = enlace_a["href"]

            codigodocumento = extraer_codigodocumento(href)
            if not codigodocumento:
                print(f"   ⚠️ No pude extraer codigodocumento de: {href}")
                continue

            fecha_expedicion = celdas[1].get_text(strip=True).replace("/", "-") if len(celdas) > 1 else None
            resuelve = celdas[4].get_text(strip=True) if len(celdas) > 4 else ""

            print(f"📥 Documento {numero} -> codigodocumento={codigodocumento}")

            pdf_bytes, final_url = descargar_pdf_real(codigodocumento)

            if not pdf_bytes:
                print(f"   ⚠️ No se encontró PDF real. URL final: {final_url}")
                continue

            nombre_fichero = f"{slugify(asunto_valor)}_{codigodocumento}.pdf"

            try:
                url_publica = subir_a_supabase(pdf_bytes, nombre_fichero)
            except Exception as e:
                print(f"   ⚠️ Error subiendo a Supabase: {e}")
                continue

            try:
                supabase_client.table(TABLE_NAME).insert(
                    {
                        "numero": numero,
                        "tipo_documento": "Estatutos y reglamentos",
                        "asunto": asunto_valor,
                        "fecha_expedicion": fecha_expedicion,
                        "resuelve": resuelve,
                        "url_pdf": url_publica,
                    }
                ).execute()
            except Exception as e:
                print(f"   ⚠️ Error insertando en la tabla: {e}")
                continue

            print("   ✓ Guardado en base de datos.")

        except Exception as e:
            print(f"   ⚠️ Error procesando fila: {e}")
            continue


def main():
    consultas = [
        "REGLAMENTO ESTUDIANTIL DE PREGRADO",
        "REGLAMENTO ESTUDIANTIL DE POSGRADO",
    ]

    for consulta in consultas:
        procesar_consulta_api(consulta)

    print("\n[!] Carga masiva completada.")


if __name__ == "__main__":
    main()
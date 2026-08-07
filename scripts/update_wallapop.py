#!/usr/bin/env python3

import json
import re
import time
from pathlib import Path
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PCS = ROOT / "pcs.json"
HISTORY = ROOT / "history.json"
SOURCES = ROOT / "sources.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 Chrome/124 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
}

TIMEOUT = 20


def now():
    return datetime.now(timezone.utc).isoformat()


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def extract_price(html):
    soup = BeautifulSoup(html, "html.parser")

    # Primero intentamos encontrar datos estructurados.
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
            objects = data if isinstance(data, list) else [data]

            for obj in objects:
                if not isinstance(obj, dict):
                    continue

                offers = obj.get("offers")

                if isinstance(offers, dict):
                    price = offers.get("price")

                    if price is not None:
                        return int(
                            round(float(str(price).replace(",", ".")))
                        )

        except Exception:
            pass

    # Después intentamos etiquetas meta.
    for key in [
        "product:price:amount",
        "og:price:amount"
    ]:
        tag = (
            soup.find("meta", attrs={"property": key})
            or soup.find("meta", attrs={"name": key})
        )

        if tag and tag.get("content"):
            try:
                return int(
                    round(
                        float(
                            tag["content"].replace(",", ".")
                        )
                    )
                )
            except Exception:
                pass

    # Último intento: precio visible.
    text = soup.get_text(" ", strip=True)

    match = re.search(
        r"(?<!\d)(\d{3,4})\s*€",
        text
    )

    if match:
        return int(match.group(1))

    return None


def unavailable(response, html):
    if response.status_code in (404, 410):
        return True

    text = html.lower()

    messages = [
        "anuncio no disponible",
        "producto no disponible",
        "este producto ya no está disponible",
        "página no encontrada"
    ]

    return any(message in text for message in messages)


def main():

    pcs = load(
        PCS,
        {
            "updated_at": None,
            "items": []
        }
    )

    history = load(HISTORY, {})

    sources = load(
        SOURCES,
        {
            "budget": {
                "min": 600,
                "max": 700
            },
            "max_active": 50,
            "items": []
        }
    )

    pcs_by_id = {
        pc["id"]: pc
        for pc in pcs.get("items", [])
    }

    session = requests.Session()
    session.headers.update(HEADERS)

    for source in sources.get("items", []):

        pc_id = source.get("id")
        url = source.get("url")

        if not pc_id or not url:
            continue

        if pc_id not in pcs_by_id:
            continue

        pc = pcs_by_id[pc_id]

        old_price = pc.get("price")
        old_status = pc.get(
            "status",
            "active"
        )

        try:

            response = session.get(
                url,
                timeout=TIMEOUT,
                allow_redirects=True
            )

            html = response.text

            if unavailable(response, html):

                pc["status"] = "unavailable"

            elif response.status_code == 200:

                price = extract_price(html)

                if (
                    price is not None
                    and 100 <= price <= 5000
                ):
                    pc["price"] = price

                pc["status"] = "active"

            # En errores 403, 429 o 5xx
            # conservamos el último dato válido.

            pc["last_checked"] = now()

        except Exception as error:

            pc["last_error"] = (
                type(error).__name__
            )

            pc["last_checked"] = now()

        # Registrar cambios reales.
        if (
            pc.get("price") != old_price
            or pc.get("status") != old_status
        ):

            history.setdefault(
                pc_id,
                []
            ).append(
                {
                    "date": now(),
                    "price": pc.get("price"),
                    "status": pc.get("status")
                }
            )

        time.sleep(1.2)

    minimum = sources.get(
        "budget",
        {}
    ).get("min", 600)

    maximum = sources.get(
        "budget",
        {}
    ).get("max", 700)

    max_active = sources.get(
        "max_active",
        50
    )

    active = [
        pc
        for pc in pcs_by_id.values()
        if (
            pc.get("status") == "active"
            and minimum
            <= pc.get("price", 0)
            <= maximum
        )
    ]

    active.sort(
        key=lambda pc: (
            -pc.get("score", 0),
            pc.get("price", 99999)
        )
    )

    allowed = {
        pc["id"]
        for pc in active[:max_active]
    }

    for pc in pcs_by_id.values():

        if (
            pc.get("status") == "active"
            and minimum
            <= pc.get("price", 0)
            <= maximum
            and pc["id"] not in allowed
        ):
            pc["status"] = "overflow"

    pcs["items"] = list(
        pcs_by_id.values()
    )

    pcs["updated_at"] = now()

    PCS.write_text(
        json.dumps(
            pcs,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    HISTORY.write_text(
        json.dumps(
            history,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print("PC Scout actualizado correctamente.")


if __name__ == "__main__":
    main()

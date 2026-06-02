"""Identification de la zone PLU d'un terrain via WFS geopf.fr."""

import httpx
import urllib.parse
from dataclasses import dataclass


WFS_URL = "https://data.geopf.fr/wfs/ows"
LAYER = "wfs_du:zone_urba"

# Demi-côté de la bounding box autour du point (en degrés, ≈ 50m)
BBOX_DELTA = 0.0005


@dataclass
class ZonePLU:
    libelle: str       # ex. "UY"
    type_zone: str     # "U", "AU", "A", "N"
    libelong: str      # libellé long
    gpu_doc_id: str    # ID document GPU
    partition: str     # ex. "DU_64122"
    nom_fichier: str   # ex. "64122_reglement_20250927.pdf#UY"
    id_urba: str       # ex. "64122_PLU_20250927"
    date_validation: str


class ZoneError(Exception):
    pass


async def identifier_zone(lon: float, lat: float) -> ZonePLU:
    """Retourne la zone PLU correspondant aux coordonnées GPS."""
    bbox = (
        f"{lat - BBOX_DELTA},{lon - BBOX_DELTA},"
        f"{lat + BBOX_DELTA},{lon + BBOX_DELTA},"
        "urn:ogc:def:crs:EPSG::4326"
    )
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": LAYER,
        "outputFormat": "application/json",
        "BBOX": bbox,
        "count": "10",
    }
    url = WFS_URL + "?" + urllib.parse.urlencode(params)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    features = data.get("features", [])
    if not features:
        raise ZoneError(
            f"Aucune zone PLU trouvée pour les coordonnées lon={lon}, lat={lat}. "
            "Le terrain est peut-être en dehors de toute zone numérisée sur le GPU."
        )

    # Prendre la zone avec statut 'production' en priorité
    production = [
        f for f in features if f["properties"].get("gpu_status") == "production"
    ]
    feat = production[0] if production else features[0]
    p = feat["properties"]

    return ZonePLU(
        libelle=p.get("libelle", ""),
        type_zone=p.get("typezone", ""),
        libelong=p.get("libelong", p.get("libelle", "")),
        gpu_doc_id=p.get("gpu_doc_id", ""),
        partition=p.get("partition", ""),
        nom_fichier=p.get("nomfic", ""),
        id_urba=p.get("idurba", ""),
        date_validation=p.get("datvalid", ""),
    )

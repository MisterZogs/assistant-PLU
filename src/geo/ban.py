"""BAN API — géocodage adresse → coordonnées GPS + code INSEE commune."""

import httpx
from dataclasses import dataclass


BAN_URL = "https://api-adresse.data.gouv.fr/search/"


@dataclass
class GeocodageResult:
    label: str
    score: float
    code_insee: str
    city: str
    postcode: str
    lon: float
    lat: float


class BanError(Exception):
    pass


async def geocoder_adresse(adresse: str) -> GeocodageResult:
    """Géocode une adresse et retourne les coordonnées + code INSEE."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(BAN_URL, params={"q": adresse, "limit": 1})
        resp.raise_for_status()
        data = resp.json()

    features = data.get("features", [])
    if not features:
        raise BanError(f"Adresse introuvable : {adresse!r}")

    feat = features[0]
    props = feat["properties"]
    coords = feat["geometry"]["coordinates"]

    if props["score"] < 0.65:
        raise BanError(
            f"Adresse non reconnue (score {props['score']:.2f}). "
            f"Essayez avec le code postal ou la ville : ex. «12 rue de la Paix, 75002 Paris»."
        )

    return GeocodageResult(
        label=props["label"],
        score=props["score"],
        code_insee=props["citycode"],
        city=props["city"],
        postcode=props["postcode"],
        lon=coords[0],
        lat=coords[1],
    )

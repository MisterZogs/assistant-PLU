"""Identification de la zone PLU via WFS wfs_du:doc_urba + shapefile ZONE_URBA.

Le layer wfs_du:zone_urba (ancien) n'est plus disponible sur data.geopf.fr.
Nouvelle approche :
  1. wfs_du:doc_urba (filtré par partition='DU_{code_insee}') → métadonnées PLU
  2. remotezip → téléchargement du seul shapefile ZONE_URBA depuis le ZIP
  3. shapely + pyproj → point-in-polygon (Lambert 93)
"""

from __future__ import annotations

import io
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import httpx
import remotezip
import shapefile
from pyproj import Transformer
from shapely.geometry import Point, shape


WFS_URL = "https://data.geopf.fr/wfs/ows"


# ── Modèles ──────────────────────────────────────────────────────────────────

@dataclass
class DocUrba:
    gpu_doc_id: str
    idurba: str
    partition: str
    typedoc: str
    datappro: str
    nomreg: str  # nom du fichier règlement (ex. "64122_reglement_20250927.pdf")


@dataclass
class ZonePLU:
    libelle: str        # ex. "UD"
    type_zone: str      # "U", "AU", "A", "N"
    libelong: str       # libellé long
    gpu_doc_id: str     # ID document GPU
    partition: str      # ex. "DU_64122"
    nom_fichier: str    # ex. "64122_reglement_20250927.pdf#UD"
    id_urba: str        # ex. "64122_PLU_20250927"
    date_validation: str


class ZoneError(Exception):
    pass


# ── Helpers ──────────────────────────────────────────────────────────────────

def _build_zip_url(gpu_doc_id: str, partition: str, idurba: str) -> str:
    return (
        f"https://data.geopf.fr/telechargement/download/pack_plu1/"
        f"PACK_{partition}_{gpu_doc_id}/{idurba}.zip"
    )


def _find_zone_in_shp(
    shp_data: bytes, dbf_data: bytes, shx_data: bytes, lon: float, lat: float
) -> dict:
    """Point-in-polygon sur le shapefile ZONE_URBA (projection Lambert 93)."""
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
    x, y = transformer.transform(lon, lat)
    point = Point(x, y)

    sf = shapefile.Reader(
        shp=io.BytesIO(shp_data),
        dbf=io.BytesIO(dbf_data),
        shx=io.BytesIO(shx_data),
    )
    fields = [f[0] for f in sf.fields[1:]]

    for feat in sf.shapeRecords():
        geom = shape(feat.shape.__geo_interface__)
        if geom.contains(point):
            return dict(zip(fields, feat.record))

    raise ZoneError(
        f"Aucune zone PLU trouvée pour lon={lon}, lat={lat}. "
        "Le point est peut-être hors du périmètre PLU."
    )


# ── Fonctions principales ─────────────────────────────────────────────────────

async def get_plu_document(code_insee: str) -> DocUrba:
    """Récupère les métadonnées PLU d'une commune via wfs_du:doc_urba."""
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": "wfs_du:doc_urba",
        "outputFormat": "application/json",
        "CQL_FILTER": f"partition='DU_{code_insee}'",
        "count": "20",
    }
    url = WFS_URL + "?" + urllib.parse.urlencode(params)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    features = data.get("features", [])
    if not features:
        raise ZoneError(
            f"Aucun document PLU trouvé pour la commune {code_insee} sur le GPU. "
            "La commune n'a peut-être pas de PLU numérisé."
        )

    # Priorité : PLU/PLUi en statut production ; sinon premier résultat
    plu = [
        f for f in features
        if f["properties"].get("typedoc") in ("PLU", "PLUi", "PLUm")
    ]
    production = [f for f in plu if f["properties"].get("gpu_status") == "production"]
    feat = (production or plu or features)[0]
    p = feat["properties"]

    return DocUrba(
        gpu_doc_id=p.get("gpu_doc_id", ""),
        idurba=p.get("idurba", ""),
        partition=p.get("partition", ""),
        typedoc=p.get("typedoc", ""),
        datappro=p.get("datappro", ""),
        nomreg=p.get("nomreg", ""),
    )


async def identifier_zone(
    lon: float,
    lat: float,
    code_insee: str,
    cache_dir: str = "./cache/shp",
) -> ZonePLU:
    """
    Retourne la zone PLU correspondant aux coordonnées GPS.

    Étapes :
      1. Récupère les métadonnées PLU via wfs_du:doc_urba (filtré sur code INSEE)
      2. Télécharge uniquement le shapefile ZONE_URBA via remotezip
      3. Identifie la zone par point-in-polygon (Lambert 93)
    """
    doc = await get_plu_document(code_insee)
    zip_url = _build_zip_url(doc.gpu_doc_id, doc.partition, doc.idurba)

    # Cache : fichiers SHP par idurba
    cache_path = Path(cache_dir) / doc.idurba
    code = doc.partition.replace("DU_", "")
    # Le nom du shapefile suit la convention {code_insee}_ZONE_URBA_{date}.shp
    # On cherche dynamiquement dans le ZIP si le cache est absent
    shp_path = cache_path / f"{code}_ZONE_URBA.shp"
    dbf_path = shp_path.with_suffix(".dbf")
    shx_path = shp_path.with_suffix(".shx")

    if not all(p.exists() for p in [shp_path, dbf_path, shx_path]):
        cache_path.mkdir(parents=True, exist_ok=True)
        with remotezip.RemoteZip(zip_url) as rz:
            names = rz.namelist()
            shp_entry = next(
                (n for n in names if "ZONE_URBA" in n and n.endswith(".shp")), None
            )
            if not shp_entry:
                raise ZoneError(
                    f"Shapefile ZONE_URBA introuvable dans le package PLU ({zip_url})"
                )
            base = shp_entry[:-4]  # enlève l'extension .shp
            shp_path.write_bytes(rz.read(base + ".shp"))
            dbf_path.write_bytes(rz.read(base + ".dbf"))
            shx_path.write_bytes(rz.read(base + ".shx"))

    props = _find_zone_in_shp(
        shp_path.read_bytes(), dbf_path.read_bytes(), shx_path.read_bytes(),
        lon, lat,
    )

    return ZonePLU(
        libelle=props.get("LIBELLE", ""),
        type_zone=props.get("TYPEZONE", ""),
        libelong=props.get("LIBELONG", props.get("LIBELLE", "")),
        gpu_doc_id=doc.gpu_doc_id,
        partition=doc.partition,
        nom_fichier=props.get("NOMFIC", doc.nomreg),
        id_urba=props.get("IDURBA", doc.idurba),
        date_validation=props.get("DATVALID", doc.datappro),
    )

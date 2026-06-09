"""Orchestration du pipeline géo : adresse → règlement PLU téléchargé."""

from dataclasses import dataclass
from pathlib import Path

from .ban import geocoder_adresse, GeocodageResult
from .zone import identifier_zone, ZonePLU
from .gpu import telecharger_reglement


@dataclass
class ResultatPipeline:
    geocodage: GeocodageResult
    zone: ZonePLU
    chemin_reglement: Path


async def pipeline_geo(adresse: str, cache_dir: str = "./cache/pdfs") -> ResultatPipeline:
    """
    Pipeline complet : adresse → coordonnées → zone PLU → règlement PDF téléchargé.
    Retourne le chemin vers le PDF du règlement écrit de la zone.
    """
    geo = await geocoder_adresse(adresse)
    shp_cache = cache_dir.replace("pdfs", "shp")
    zone = await identifier_zone(geo.lon, geo.lat, geo.code_insee, shp_cache)
    chemin = await telecharger_reglement(zone.gpu_doc_id, zone.id_urba, cache_dir)

    return ResultatPipeline(geocodage=geo, zone=zone, chemin_reglement=chemin)

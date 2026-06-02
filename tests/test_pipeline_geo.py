"""Tests d'intégration du pipeline géo (appellent les vraies APIs)."""

import asyncio
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.geo.ban import geocoder_adresse, BanError
from src.geo.zone import identifier_zone, ZoneError
from src.geo.gpu import lister_fichiers, GpuError


# ── BAN ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_geocodage_adresse_connue():
    result = await geocoder_adresse("1 Grande Plage Biarritz")
    assert result.code_insee == "64122"
    assert result.city == "Biarritz"
    assert result.score > 0.5
    assert -2 < result.lon < 0
    assert 43 < result.lat < 44


@pytest.mark.asyncio
async def test_geocodage_adresse_inconnue():
    with pytest.raises(BanError):
        await geocoder_adresse("zzzzzzzzzz inexistant 99999")


# ── WFS zone PLU ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_identification_zone_biarritz():
    # Coordonnées du centre de Biarritz
    zone = await identifier_zone(lon=-1.5601, lat=43.4832)
    assert zone.gpu_doc_id != ""
    assert zone.type_zone in ("U", "AU", "A", "N")
    assert zone.libelle != ""
    assert "64122" in zone.partition


@pytest.mark.asyncio
async def test_identification_zone_mer():
    # Milieu de l'Atlantique → doit lever une erreur
    with pytest.raises(ZoneError):
        await identifier_zone(lon=-5.0, lat=45.0)


# ── GPU fichiers ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_liste_fichiers_gpu():
    doc_id = "6345e561e148d0d60d85340d4b826649"  # Biarritz PLU
    fichiers = await lister_fichiers(doc_id)
    assert len(fichiers) > 0
    reglements = [f for f in fichiers if f.path == "Règlements" and "reglement" in f.name and "graphique" not in f.name]
    assert len(reglements) == 1, f"Règlement écrit introuvable parmi : {[f.name for f in fichiers]}"


if __name__ == "__main__":
    async def main():
        print("Test BAN...")
        r = await geocoder_adresse("1 Grande Plage Biarritz")
        print(f"  ✅ {r.label} (INSEE: {r.code_insee}, score: {r.score:.2f})")
        print(f"     lon={r.lon}, lat={r.lat}")

        print("Test WFS zone PLU...")
        z = await identifier_zone(r.lon, r.lat)
        print(f"  ✅ Zone {z.libelle} ({z.type_zone}) — doc GPU: {z.gpu_doc_id[:8]}...")
        print(f"     PDF: {z.nom_fichier}")

        print("Test liste fichiers GPU...")
        fichiers = await lister_fichiers(z.gpu_doc_id)
        print(f"  ✅ {len(fichiers)} fichiers disponibles")
        reglements = [f for f in fichiers if f.path == "Règlements" and "reglement" in f.name and "graphique" not in f.name]
        print(f"     Règlement écrit : {reglements[0].name if reglements else 'INTROUVABLE'}")

    asyncio.run(main())

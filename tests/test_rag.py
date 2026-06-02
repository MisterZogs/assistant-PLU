"""Tests du module RAG — extraction PDF et appel Mistral."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_pipeline_complet():
    """Test bout en bout : adresse → règles extraites → rapport de conformité."""
    from src.geo.pipeline import pipeline_geo
    from src.rag.pdf import extraire_texte, isoler_section_zone
    from src.rag.regles import extraire_regles
    from src.conformite.models import ProjetArchitecte
    from src.conformite.verificateur import verifier_conformite
    from mistralai.client import Mistral

    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("⚠️  MISTRAL_API_KEY non définie — test LLM ignoré")
        return

    adresse = "12 rue du Port Vieux 64200 Biarritz"
    print(f"\nAdresse : {adresse}")

    print("1. Pipeline géo...")
    result = await pipeline_geo(adresse, cache_dir="./cache/pdfs")
    print(f"   ✅ Zone {result.zone.libelle} ({result.zone.type_zone})")
    print(f"   📄 PDF : {result.chemin_reglement}")

    print("2. Extraction texte PDF...")
    texte = extraire_texte(result.chemin_reglement)
    texte_zone = isoler_section_zone(texte, result.zone.nom_fichier)
    print(f"   ✅ Section zone : {len(texte_zone)} chars")

    print("3. Extraction règles (Mistral)...")
    client = Mistral(api_key=api_key)
    regles = await extraire_regles(
        texte_zone=texte_zone,
        commune=result.geocodage.city,
        zone=result.zone.libelle,
        client=client,
    )
    print(f"   ✅ Zone {regles.zone} — {regles.commune}")
    print(f"   Art.10 hauteur max : {regles.art10_hauteur_max.valeur or '(non trouvé)'}")
    print(f"   Art.9  emprise sol : {regles.art9_emprise_sol.valeur or '(non trouvé)'}")
    print(f"   Art.6  recul voie  : {regles.art6_recul_voie.valeur or '(non trouvé)'}")

    print("4. Vérification conformité (Mistral)...")
    projet = ProjetArchitecte(
        surface_plancher=180,
        emprise_sol=90,
        surface_parcelle=400,
        hauteur_egout=6.5,
        hauteur_faitage=9.0,
        recul_voie=5.0,
        recul_nord=3.0,
        recul_sud=3.0,
        recul_est=0.0,
        recul_ouest=0.0,
        nb_logements=2,
        nb_places_stationnement=2,
    )
    rapport = await verifier_conformite(
        regles=regles,
        projet=projet,
        adresse=adresse,
        id_urba=result.zone.id_urba,
        client=client,
    )
    print(f"   ✅ Statut global : {rapport.statut_global.value}")
    for v in rapport.verifications:
        icon = {"CONFORME": "✅", "NON_CONFORME": "❌", "A_VERIFIER": "⚠️ ", "NON_APPLICABLE": "— "}.get(v.statut.value, "?")
        print(f"   {icon} {v.article} : projet={v.valeur_projet} | règle={v.valeur_reglementaire}")
        if v.commentaire:
            print(f"       {v.commentaire}")


if __name__ == "__main__":
    asyncio.run(test_pipeline_complet())

"""FastAPI — point d'entrée principal de l'assistant PLU."""

import os
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from dotenv import load_dotenv

from ..geo.pipeline import pipeline_geo
from ..rag.pdf import extraire_texte, isoler_section_zone
from ..rag.regles import extraire_regles
from ..conformite.models import ProjetArchitecte, RapportConformite
from ..conformite.verificateur import verifier_conformite
from ..export.rapport_pdf import generer_rapport_pdf

load_dotenv()

app = FastAPI(title="Assistant PLU", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PDF_CACHE_DIR = os.getenv("PDF_CACHE_DIR", "./cache/pdfs")


def _get_anthropic() -> anthropic.AsyncAnthropic:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(500, "ANTHROPIC_API_KEY non configurée")
    return anthropic.AsyncAnthropic(api_key=key)


# ── Schémas de requête ────────────────────────────────────────────────────────

class VerificationRequest(BaseModel):
    adresse: str
    projet: ProjetArchitecte


class ZoneInfo(BaseModel):
    zone: str
    type_zone: str
    commune: str
    id_urba: str
    date_document: str


class VerificationResponse(BaseModel):
    zone_info: ZoneInfo
    rapport: RapportConformite


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/verifier", response_model=VerificationResponse)
async def verifier(req: VerificationRequest):
    """
    Pipeline complet :
    adresse + projet → zone PLU → règles extraites → rapport de conformité.
    """
    try:
        geo_result = await pipeline_geo(req.adresse, PDF_CACHE_DIR)
    except Exception as e:
        raise HTTPException(422, f"Erreur pipeline géo : {e}")

    zone = geo_result.zone
    chemin_pdf = geo_result.chemin_reglement

    texte_complet = extraire_texte(chemin_pdf)
    texte_zone = isoler_section_zone(texte_complet, zone.nom_fichier)

    client = _get_anthropic()
    try:
        regles = await extraire_regles(
            texte_zone=texte_zone,
            commune=geo_result.geocodage.city,
            zone=zone.libelle,
            client=client,
        )
    except Exception as e:
        raise HTTPException(500, f"Erreur extraction règles : {e}")

    try:
        rapport = await verifier_conformite(
            regles=regles,
            projet=req.projet,
            adresse=req.adresse,
            id_urba=zone.id_urba,
            client=client,
        )
    except Exception as e:
        raise HTTPException(500, f"Erreur vérification conformité : {e}")

    return VerificationResponse(
        zone_info=ZoneInfo(
            zone=zone.libelle,
            type_zone=zone.type_zone,
            commune=geo_result.geocodage.city,
            id_urba=zone.id_urba,
            date_document=zone.date_validation,
        ),
        rapport=rapport,
    )


@app.post("/api/verifier/pdf")
async def verifier_et_telecharger_pdf(req: VerificationRequest):
    """Pipeline complet + export PDF téléchargeable en une seule requête."""
    response = await verifier(req)
    pdf_bytes = generer_rapport_pdf(response.rapport)
    nom_fichier = f"rapport_PLU_{response.rapport.commune}_{response.rapport.zone}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nom_fichier}"'},
    )


@app.post("/api/rapport/pdf")
async def rapport_pdf(rapport: RapportConformite):
    """Génère un PDF depuis un rapport de conformité déjà calculé."""
    pdf_bytes = generer_rapport_pdf(rapport)
    nom_fichier = f"rapport_PLU_{rapport.commune}_{rapport.zone}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nom_fichier}"'},
    )


@app.get("/api/zone")
async def get_zone(adresse: str):
    """Retourne uniquement la zone PLU d'une adresse."""
    try:
        from ..geo.ban import geocoder_adresse
        from ..geo.zone import identifier_zone

        geo = await geocoder_adresse(adresse)
        zone = await identifier_zone(geo.lon, geo.lat, geo.code_insee)
        return {
            "adresse_normalisee": geo.label,
            "code_insee": geo.code_insee,
            "commune": geo.city,
            "lat": geo.lat,
            "lon": geo.lon,
            "zone": zone.libelle,
            "type_zone": zone.type_zone,
            "id_urba": zone.id_urba,
            "nom_fichier_reglement": zone.nom_fichier,
        }
    except Exception as e:
        raise HTTPException(422, str(e))

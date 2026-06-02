"""Modèles Pydantic pour les règles PLU et le rapport de conformité."""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Règles extraites ──────────────────────────────────────────────────────────

class RegleArticle(BaseModel):
    valeur: str = ""
    exceptions: str = ""
    citation: str = ""
    non_applicable: bool = False


class ReglesZone(BaseModel):
    commune: str
    zone: str
    date_approbation_plu: str = ""
    art6_recul_voie: RegleArticle = Field(default_factory=RegleArticle)
    art7_recul_limite: RegleArticle = Field(default_factory=RegleArticle)
    art8_implantation: RegleArticle = Field(default_factory=RegleArticle)
    art9_emprise_sol: RegleArticle = Field(default_factory=RegleArticle)
    art10_hauteur_max: RegleArticle = Field(default_factory=RegleArticle)
    art11_aspect: RegleArticle = Field(default_factory=RegleArticle)
    art12_stationnement: RegleArticle = Field(default_factory=RegleArticle)
    art13_espaces_libres: RegleArticle = Field(default_factory=RegleArticle)


# ── Projet soumis ─────────────────────────────────────────────────────────────

class ProjetArchitecte(BaseModel):
    surface_plancher: Optional[float] = Field(None, description="m²")
    emprise_sol: Optional[float] = Field(None, description="m²")
    surface_parcelle: Optional[float] = Field(None, description="m²")
    hauteur_egout: Optional[float] = Field(None, description="m")
    hauteur_faitage: Optional[float] = Field(None, description="m")
    recul_voie: Optional[float] = Field(None, description="m")
    recul_nord: Optional[float] = Field(None, description="m")
    recul_sud: Optional[float] = Field(None, description="m")
    recul_est: Optional[float] = Field(None, description="m")
    recul_ouest: Optional[float] = Field(None, description="m")
    nb_logements: Optional[int] = None
    nb_places_stationnement: Optional[int] = None

    @property
    def pct_emprise(self) -> Optional[float]:
        if self.emprise_sol and self.surface_parcelle and self.surface_parcelle > 0:
            return round(self.emprise_sol / self.surface_parcelle * 100, 1)
        return None


# ── Rapport de conformité ─────────────────────────────────────────────────────

class StatutConformite(str, Enum):
    CONFORME = "CONFORME"
    NON_CONFORME = "NON_CONFORME"
    A_VERIFIER = "A_VERIFIER"
    NON_APPLICABLE = "NON_APPLICABLE"


class VerificationArticle(BaseModel):
    article: str
    statut: StatutConformite
    valeur_projet: str = ""
    valeur_reglementaire: str = ""
    commentaire: str = ""


class RapportConformite(BaseModel):
    adresse: str
    commune: str
    zone: str
    id_urba: str
    date_document_plu: str
    verifications: list[VerificationArticle]

    @property
    def statut_global(self) -> StatutConformite:
        statuts = [v.statut for v in self.verifications]
        if StatutConformite.NON_CONFORME in statuts:
            return StatutConformite.NON_CONFORME
        if StatutConformite.A_VERIFIER in statuts:
            return StatutConformite.A_VERIFIER
        return StatutConformite.CONFORME

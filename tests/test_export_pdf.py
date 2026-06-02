"""Test de génération du rapport PDF avec des données fictives."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.conformite.models import (
    RapportConformite, VerificationArticle, StatutConformite
)
from src.export.rapport_pdf import generer_rapport_pdf


def rapport_fictif() -> RapportConformite:
    return RapportConformite(
        adresse="12 rue du Port Vieux 64200 Biarritz",
        commune="Biarritz",
        zone="UA",
        id_urba="64122_PLU_20250927",
        date_document_plu="22/12/2003 — Modification n°13 du 23/03/2024",
        verifications=[
            VerificationArticle(
                article="Art. 6 — Implantation / voies",
                statut=StatutConformite.CONFORME,
                valeur_projet="5 m",
                valeur_reglementaire="0 à 4 m (façade sur rue)",
                commentaire="",
            ),
            VerificationArticle(
                article="Art. 7 — Implantation / limites séparatives",
                statut=StatutConformite.A_VERIFIER,
                valeur_projet="3 m (nord/sud), 0 m (est/ouest)",
                valeur_reglementaire="Retrait ≥ H/2 (min. 3 m) ou en limite",
                commentaire="Vérifier si le recul de 3 m satisfait la règle H/2 selon la hauteur finale de la construction.",
            ),
            VerificationArticle(
                article="Art. 9 — Emprise au sol",
                statut=StatutConformite.CONFORME,
                valeur_projet="22,5% (90 m² / 400 m²)",
                valeur_reglementaire="Pas de CES fixé en zone UA",
                commentaire="",
            ),
            VerificationArticle(
                article="Art. 10 — Hauteur maximale",
                statut=StatutConformite.NON_CONFORME,
                valeur_projet="Faîtage 9,0 m / Égout 6,5 m",
                valeur_reglementaire="Hauteur égout ≤ 6,00 m en secteur UAs",
                commentaire="La hauteur à l'égout de 6,5 m dépasse le maximum autorisé de 6,0 m. Reprise nécessaire.",
            ),
            VerificationArticle(
                article="Art. 11 — Aspect extérieur",
                statut=StatutConformite.A_VERIFIER,
                valeur_projet="Non renseigné",
                valeur_reglementaire="Matériaux et couleurs traditionnels basques",
                commentaire="Les matériaux de façade et de toiture doivent être précisés pour vérification.",
            ),
            VerificationArticle(
                article="Art. 12 — Stationnement",
                statut=StatutConformite.CONFORME,
                valeur_projet="2 places (2 logements)",
                valeur_reglementaire="1 place minimum par logement",
                commentaire="",
            ),
            VerificationArticle(
                article="Art. 13 — Espaces libres",
                statut=StatutConformite.NON_APPLICABLE,
                valeur_projet="—",
                valeur_reglementaire="Non applicable en zone UA dense",
                commentaire="",
            ),
        ],
    )


if __name__ == "__main__":
    rapport = rapport_fictif()
    pdf_bytes = generer_rapport_pdf(rapport)

    output_path = Path("tests/rapport_test.pdf")
    output_path.write_bytes(pdf_bytes)
    print(f"✅ PDF généré : {output_path} ({len(pdf_bytes) / 1024:.1f} KB)")
    print(f"   Statut global : {rapport.statut_global.value}")
    print(f"   {len(rapport.verifications)} articles vérifiés")

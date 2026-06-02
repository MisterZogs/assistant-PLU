"""Vérification de conformité PLU : règles extraites × projet architecte → rapport."""

import json
from mistralai.client import Mistral

from .models import ReglesZone, ProjetArchitecte, RapportConformite, VerificationArticle


MODEL = "mistral-large-latest"

PROMPT_VERIFICATION = """\
Tu es un expert en conformité PLU (Plan Local d'Urbanisme).

Voici les règles applicables en zone {zone} de la commune de {commune} :
{regles_json}

Voici le projet soumis :
- Surface de plancher : {surface_plancher}
- Emprise au sol : {emprise_sol} (soit {pct_emprise}% de la parcelle de {surface_parcelle})
- Hauteur à l'égout : {hauteur_egout}
- Hauteur au faîtage : {hauteur_faitage}
- Recul front de rue : {recul_voie}
- Recul limite nord : {recul_nord} / sud : {recul_sud} / est : {recul_est} / ouest : {recul_ouest}
- Nombre de logements : {nb_logements}
- Nombre de places de stationnement : {nb_places}

Pour chaque règle applicable, évalue la conformité du projet.
Statuts possibles : CONFORME, NON_CONFORME, A_VERIFIER, NON_APPLICABLE.
Sois conservateur : en cas de doute, indique A_VERIFIER plutôt que CONFORME.

Réponds UNIQUEMENT avec un objet JSON valide contenant une clé "verifications" (tableau).

Format attendu :
{{
  "verifications": [
    {{
      "article": "Art. 6 — Recul voie",
      "statut": "CONFORME",
      "valeur_projet": "5 m",
      "valeur_reglementaire": "5 m minimum",
      "commentaire": ""
    }}
  ]
}}
"""


def _fmt(val, unit="", non_renseigne="Non renseigné") -> str:
    if val is None:
        return non_renseigne
    return f"{val} {unit}".strip()


async def verifier_conformite(
    regles: ReglesZone,
    projet: ProjetArchitecte,
    adresse: str,
    id_urba: str,
    client: Mistral,
) -> RapportConformite:
    """Appelle Mistral pour vérifier la conformité du projet aux règles PLU."""
    prompt = PROMPT_VERIFICATION.format(
        commune=regles.commune,
        zone=regles.zone,
        regles_json=regles.model_dump_json(indent=2),
        surface_plancher=_fmt(projet.surface_plancher, "m²"),
        emprise_sol=_fmt(projet.emprise_sol, "m²"),
        pct_emprise=_fmt(projet.pct_emprise, "%"),
        surface_parcelle=_fmt(projet.surface_parcelle, "m²"),
        hauteur_egout=_fmt(projet.hauteur_egout, "m"),
        hauteur_faitage=_fmt(projet.hauteur_faitage, "m"),
        recul_voie=_fmt(projet.recul_voie, "m"),
        recul_nord=_fmt(projet.recul_nord, "m"),
        recul_sud=_fmt(projet.recul_sud, "m"),
        recul_est=_fmt(projet.recul_est, "m"),
        recul_ouest=_fmt(projet.recul_ouest, "m"),
        nb_logements=_fmt(projet.nb_logements),
        nb_places=_fmt(projet.nb_places_stationnement),
    )

    res = await client.chat.complete_async(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Tu es un expert en urbanisme français. Réponds uniquement en JSON valide."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    raw = res.choices[0].message.content.strip()
    data = json.loads(raw)
    verifications = [VerificationArticle(**v) for v in data["verifications"]]

    return RapportConformite(
        adresse=adresse,
        commune=regles.commune,
        zone=regles.zone,
        id_urba=id_urba,
        date_document_plu=regles.date_approbation_plu,
        verifications=verifications,
    )

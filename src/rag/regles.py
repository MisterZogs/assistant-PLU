"""Extraction structurée des règles PLU depuis le texte du règlement via Claude."""

import json
import anthropic

from ..conformite.models import ReglesZone


MODEL = "claude-sonnet-4-6"

PROMPT_EXTRACTION = """\
Tu es un expert en droit de l'urbanisme français et en lecture de PLU (Plans Locaux d'Urbanisme).

Voici le règlement de la zone {zone} du PLU de la commune de {commune}.

Extrais de manière structurée toutes les règles applicables aux articles suivants :
- Article 6 : Implantation par rapport aux voies (recul front de rue)
- Article 7 : Implantation par rapport aux limites séparatives (recul latéral)
- Article 8 : Implantation entre constructions sur un même terrain
- Article 9 : Emprise au sol (CES)
- Article 10 : Hauteur maximale
- Article 11 : Aspect extérieur
- Article 12 : Stationnement
- Article 13 : Espaces libres

Pour chaque article, indique :
- valeur : la règle principale (valeur chiffrée ou condition brève)
- exceptions : les exceptions éventuelles (vide si aucune)
- citation : la citation exacte du texte (max 2 phrases)
- non_applicable : true si l'article est absent ou non applicable dans ce PLU

Réponds UNIQUEMENT avec un objet JSON valide, sans markdown, sans commentaires.

Format attendu :
{{
  "commune": "{commune}",
  "zone": "{zone}",
  "date_approbation_plu": "",
  "art6_recul_voie": {{"valeur": "", "exceptions": "", "citation": "", "non_applicable": false}},
  "art7_recul_limite": {{"valeur": "", "exceptions": "", "citation": "", "non_applicable": false}},
  "art8_implantation": {{"valeur": "", "exceptions": "", "citation": "", "non_applicable": false}},
  "art9_emprise_sol": {{"valeur": "", "exceptions": "", "citation": "", "non_applicable": false}},
  "art10_hauteur_max": {{"valeur": "", "exceptions": "", "citation": "", "non_applicable": false}},
  "art11_aspect": {{"valeur": "", "exceptions": "", "citation": "", "non_applicable": false}},
  "art12_stationnement": {{"valeur": "", "exceptions": "", "citation": "", "non_applicable": false}},
  "art13_espaces_libres": {{"valeur": "", "exceptions": "", "citation": "", "non_applicable": false}}
}}

Règlement de zone {zone} :
---
{texte_reglement}
---
"""


async def extraire_regles(
    texte_zone: str,
    commune: str,
    zone: str,
    client: anthropic.AsyncAnthropic,
) -> ReglesZone:
    """Appelle Claude pour extraire les règles PLU structurées depuis le texte."""
    prompt = PROMPT_EXTRACTION.format(
        commune=commune,
        zone=zone,
        texte_reglement=texte_zone,
    )

    res = await client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system="Tu es un expert en urbanisme français. Réponds uniquement en JSON valide.",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )

    raw = res.content[0].text.strip()
    data = json.loads(raw)
    return ReglesZone(**data)

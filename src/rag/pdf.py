"""Extraction de texte PDF et isolation de la section d'une zone PLU."""

import re
from pathlib import Path

import pypdf


def extraire_texte(chemin_pdf: Path) -> str:
    """Extrait tout le texte d'un PDF règlement PLU."""
    reader = pypdf.PdfReader(str(chemin_pdf))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


# Patterns de titre de zone dans un règlement PLU
_ZONE_PATTERNS = [
    r"(?:CHAPITRE|TITRE|ZONE|SECTION)\s+{zone}\b",
    r"\b{zone}\s*[-–—]\s*(?:ZONE|Dispositions)",
    r"^{zone}\s*$",
    r"ZONE\s+{zone}\b",
]


def _normaliser_zone(zone: str) -> str:
    """Extrait le code zone brut depuis nomfic (ex. 'NCU' depuis 'reglement.pdf#NCU')."""
    if "#" in zone:
        zone = zone.split("#")[-1]
    return zone.strip().upper()


def _prefixe_zone(zone: str) -> str:
    """
    Retourne le préfixe générique de la zone pour la recherche de section.
    Ex: 'UAs' → 'UA', 'NCU' → 'N' puis 'NCU', 'UB' → 'UB'.
    """
    m = re.match(r"[A-Za-z]+", zone)
    return m.group(0) if m else zone


def isoler_section_zone(texte: str, zone_libelle: str) -> str:
    """
    Extrait la section du règlement correspondant à la zone.
    Cherche d'abord le pattern 'ZONE {code}' seul sur une ligne (vraie section),
    puis délimite jusqu'au prochain 'ZONE {autre_code}'.
    Retourne le texte complet si la section est introuvable.
    """
    zone = _normaliser_zone(zone_libelle)

    # Patterns triés du plus spécifique au plus général
    search_zones = [zone]
    prefixe = _prefixe_zone(zone)
    if prefixe != zone:
        search_zones.append(prefixe)

    debut_re = None
    match = None
    for z in search_zones:
        # Pattern strict : "ZONE UA" seul sur une ligne, ou suivi d'un espace
        pattern = re.compile(
            rf"^ZONE\s+{re.escape(z)}\s*$",
            re.IGNORECASE | re.MULTILINE,
        )
        m = pattern.search(texte)
        if m:
            match = m
            break

    if not match:
        # Fallback : pattern plus souple
        for z in search_zones:
            pattern = re.compile(
                rf"(?:^ZONE|^CHAPITRE)\s+{re.escape(z)}\b",
                re.IGNORECASE | re.MULTILINE,
            )
            # Chercher la dernière occurrence (évite le sommaire)
            all_matches = list(pattern.finditer(texte))
            # Prendre la première occurrence après le premier tiers du document
            threshold = len(texte) // 5
            candidates = [m for m in all_matches if m.start() > threshold]
            if candidates:
                match = candidates[0]
                break
            elif all_matches:
                match = all_matches[-1]
                break

    if not match:
        return texte[:60_000]

    start = match.start()
    zone_code = re.match(r"[A-Za-z]+", zone).group(0).upper()

    # Délimiter la fin : première "ZONE {autre_code}" sur une ligne
    # (ignorer les répétitions de la même zone qui sont des en-têtes de page)
    fin_re = re.compile(r"^ZONE\s+([A-Z]{1,5})\s*$", re.IGNORECASE | re.MULTILINE)
    end = len(texte)
    for m in fin_re.finditer(texte, start + 100):
        found_code = re.match(r"[A-Za-z]+", m.group(1)).group(0).upper()
        if found_code != zone_code:
            end = m.start()
            break

    section = texte[start:end]
    return section[:80_000]

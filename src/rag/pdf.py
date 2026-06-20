"""Extraction de texte PDF et isolation de la section d'une zone PLU."""

import re
from pathlib import Path

import pypdf


def extraire_texte(chemin_pdf: Path) -> str:
    """Extrait tout le texte d'un PDF règlement PLU, page par page."""
    reader = pypdf.PdfReader(str(chemin_pdf))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _normaliser_zone(zone: str) -> str:
    """Normalise le code zone : retire le fragment d'URL et met en majuscules."""
    if "#" in zone:
        zone = zone.split("#")[-1]
    return zone.strip()


def _zone_variants(zone: str) -> list[str]:
    """
    Génère les variantes de code à essayer pour trouver la section dans le PDF.

    Exemples :
      UCe1b → [UCe1b, UCe1, UCe]
      UP1   → [UP1, UP, UP 1]
      UB    → [UB]
      NCU   → [NCU, NC, N]
    """
    variants: list[str] = [zone]

    # 1. Retirer le suffixe en minuscules (ex. 'b' dans UCe1b → UCe1)
    no_lower = re.sub(r"[a-z]+$", "", zone)
    if no_lower and no_lower != zone:
        variants.append(no_lower)

    # 2. Retirer les chiffres finaux (ex. UCe1 → UCe, UP1 → UP, NCU → NC)
    no_digits = re.sub(r"\d+$", "", no_lower or zone)
    if no_digits and no_digits not in variants:
        variants.append(no_digits)

    # 3. Retirer encore un niveau de lettres minuscules si présentes (UCe → U... non pertinent)
    no_inner_lower = re.sub(r"[a-z]+$", "", no_digits)
    if no_inner_lower and no_inner_lower not in variants and len(no_inner_lower) >= 1:
        variants.append(no_inner_lower)

    # 4. Variante avec espace avant les chiffres (UP1 → UP 1, UCe1 → UCe 1)
    for v in list(variants):
        with_space = re.sub(r"([A-Za-z])(\d)", r"\1 \2", v)
        if with_space != v and with_space not in variants:
            variants.append(with_space)

    return variants


def _find_section_start(texte: str, variants: list[str], threshold: int) -> re.Match | None:
    """
    Cherche le début de section pour une liste de variantes de code zone.
    Essaie plusieurs patterns du plus strict au plus souple.
    Ignore les occurrences avant `threshold` (évite le sommaire).
    """
    for z in variants:
        esc = re.escape(z)

        # Patterns du plus strict au plus souple
        patterns = [
            # "Zone UCe1" ou "ZONE UCe1" seul sur une ligne (avec ou sans espace final)
            re.compile(rf"^(?:ZONE|Zone)\s+{esc}\s*$", re.MULTILINE),
            # Avec texte descriptif après (ex. "Zone UCe1 Centre ancien imbriqué")
            re.compile(rf"^(?:ZONE|Zone)\s+{esc}\s+\S", re.MULTILINE),
            # Code seul sur la ligne (sans préfixe ZONE)
            re.compile(rf"^{esc}\s*$", re.MULTILINE),
            # CHAPITRE / TITRE suivi du code
            re.compile(rf"^(?:CHAPITRE|TITRE|SECTION)\s+{esc}\b", re.IGNORECASE | re.MULTILINE),
            # Fallback : "Zone X" ou "ZONE X" n'importe où dans la ligne
            re.compile(rf"(?:ZONE|Zone)\s+{esc}\b", re.MULTILINE),
        ]

        for pattern in patterns:
            all_matches = list(pattern.finditer(texte))
            # Ignorer les occurrences dans le sommaire (avant `threshold`)
            candidates = [m for m in all_matches if m.start() > threshold]
            if candidates:
                return candidates[0]
            # Si aucun après le seuil mais des occurrences existent, prendre la dernière
            if all_matches:
                return all_matches[-1]

    return None


def _find_section_end(texte: str, start: int, found_variant: str) -> int:
    """
    Trouve la fin de la section : première occurrence d'une AUTRE zone après `start`.
    Ignore les en-têtes de page répétés (même zone).
    """
    # Préfixe alphabétique de la zone trouvée (ex. "UCe" pour "UCe1b")
    m = re.match(r"[A-Za-z]+", found_variant)
    found_prefix = m.group(0).upper() if m else found_variant.upper()

    # Cherche la prochaine section "Zone X" ou "ZONE X" sur une ligne
    next_section = re.compile(
        r"^(?:ZONE|Zone)\s+([A-Za-z0-9 ]+?)\s*$",
        re.MULTILINE,
    )

    for m in next_section.finditer(texte, start + 200):
        candidate = m.group(1).strip()
        # Retirer les espaces pour normalisation (UP 1 → UP1)
        candidate_norm = re.sub(r"\s+", "", candidate).upper()
        candidate_prefix = re.match(r"[A-Za-z]+", candidate_norm)
        if candidate_prefix and candidate_prefix.group(0) != found_prefix:
            return m.start()

    return len(texte)


def isoler_section_zone(texte: str, zone_libelle: str) -> str:
    """
    Extrait la section du règlement correspondant à la zone.

    Stratégie :
    1. Génère des variantes du code (UCe1b → UCe1b, UCe1, UCe, UCe 1…)
    2. Cherche le début de section avec plusieurs patterns (strict → souple)
    3. Ignore le sommaire (premier 1/5 du document)
    4. Délimite jusqu'à la prochaine section d'une zone différente
    5. Fallback : retourne les 60 000 premiers caractères
    """
    zone = _normaliser_zone(zone_libelle)
    variants = _zone_variants(zone)

    # Seuil sommaire : ignorer le premier 1/5 du document
    threshold = len(texte) // 5

    match = _find_section_start(texte, variants, threshold)

    if not match:
        # Dernier recours : retourner le début du document (Claude fera de son mieux)
        return texte[:60_000]

    start = match.start()

    # Trouver la variante qui a matché (pour delimiter la fin correctement)
    matched_text = match.group(0)
    found_variant = zone  # par défaut

    end = _find_section_end(texte, start, found_variant)
    section = texte[start:end]

    # Limiter à 80 000 caractères pour le contexte LLM
    return section[:80_000]

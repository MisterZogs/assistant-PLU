"""Génération du rapport de conformité PLU en PDF via fpdf2."""

from __future__ import annotations
import math
from datetime import date
from io import BytesIO
from pathlib import Path

import httpx
from fpdf import FPDF
from fpdf.table import FontFace

from ..conformite.models import RapportConformite, StatutConformite

_FONTS_DIR = Path(__file__).parent / "fonts"


# ── Palette ───────────────────────────────────────────────────────────────────

_BLEU_TITRE = (30, 80, 140)
_BLEU_CLAIR = (235, 242, 252)
_BLANC = (255, 255, 255)
_GRIS_CLAIR = (245, 246, 248)
_GRIS_TEXTE = (80, 80, 80)
_NOIR = (20, 20, 20)

_COULEURS_STATUT = {
    StatutConformite.CONFORME:       (39, 174, 96),
    StatutConformite.NON_CONFORME:   (231, 76, 60),
    StatutConformite.A_VERIFIER:     (230, 126, 34),
    StatutConformite.NON_APPLICABLE: (149, 165, 166),
}

_LABELS_STATUT = {
    StatutConformite.CONFORME:       "CONFORME",
    StatutConformite.NON_CONFORME:   "NON CONFORME",
    StatutConformite.A_VERIFIER:     "À VÉRIFIER",
    StatutConformite.NON_APPLICABLE: "N/A",
}

_ICONES_STATUT = {
    StatutConformite.CONFORME:       "✓",
    StatutConformite.NON_CONFORME:   "✗",
    StatutConformite.A_VERIFIER:     "!",
    StatutConformite.NON_APPLICABLE: "—",
}


# ── Classe PDF ────────────────────────────────────────────────────────────────

class RapportPDF(FPDF):
    def __init__(self, titre_rapport: str = "Rapport de conformité PLU"):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._titre = titre_rapport
        self.set_margins(left=18, top=18, right=18)
        self.set_auto_page_break(auto=True, margin=22)
        self.alias_nb_pages()
        self.add_font("DejaVu",  style="",   fname=str(_FONTS_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu",  style="B",  fname=str(_FONTS_DIR / "DejaVuSans-Bold.ttf"))
        self.add_font("DejaVu",  style="I",  fname=str(_FONTS_DIR / "DejaVuSans-Oblique.ttf"))
        self.add_font("DejaVu",  style="BI", fname=str(_FONTS_DIR / "DejaVuSans-Oblique.ttf"))

    def header(self):
        self.set_fill_color(*_BLEU_TITRE)
        self.rect(0, 0, 210, 12, style="F")
        self.set_font("DejaVu", "B", 9)
        self.set_text_color(*_BLANC)
        self.set_y(2)
        self.cell(0, 8, self._titre.upper(), align="C")
        self.set_text_color(*_NOIR)
        self.ln(14)

    def footer(self):
        self.set_y(-16)
        self.set_draw_color(*_BLEU_TITRE)
        self.set_line_width(0.3)
        self.line(18, self.get_y(), 192, self.get_y())
        self.ln(1)
        self.set_font("DejaVu", "I", 7)
        self.set_text_color(*_GRIS_TEXTE)
        self.cell(
            0, 5,
            "Rapport indicatif — L'architecte reste responsable de la vérification finale. "
            f"Page {self.page_no()}/{{nb}}",
            align="C",
        )

    def _section(self, titre: str):
        self.set_fill_color(*_BLEU_CLAIR)
        self.set_font("DejaVu", "B", 10)
        self.set_text_color(*_BLEU_TITRE)
        self.cell(0, 7, f"  {titre}", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*_NOIR)
        self.ln(2)

    def _info_ligne(self, label: str, valeur: str, fill: bool = False):
        if fill:
            self.set_fill_color(*_GRIS_CLAIR)
        self.set_font("DejaVu", "B", 9)
        self.set_text_color(*_GRIS_TEXTE)
        self.cell(55, 6, label, fill=fill)
        self.set_font("DejaVu", "", 9)
        self.set_text_color(*_NOIR)
        self.cell(0, 6, valeur, fill=fill, new_x="LMARGIN", new_y="NEXT")


# ── Image satellite IGN ───────────────────────────────────────────────────────

def _image_satellite_ign(lat: float, lon: float, largeur_km: float = 0.40) -> bytes | None:
    """Télécharge l'orthophoto IGN (Géoportail) autour du point. Retourne None si indisponible."""
    delta_lat = (largeur_km * 0.75) / 111.0
    delta_lon = largeur_km / (111.0 * abs(math.cos(math.radians(lat))))
    # WMS 1.3.0 EPSG:4326 → BBOX = latMin,lonMin,latMax,lonMax
    bbox = f"{lat - delta_lat},{lon - delta_lon},{lat + delta_lat},{lon + delta_lon}"
    url = (
        "https://data.geopf.fr/wms-r/wms"
        "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
        "&LAYERS=ORTHOIMAGERY.ORTHOPHOTOS&STYLES="
        "&FORMAT=image/jpeg"
        f"&BBOX={bbox}"
        "&WIDTH=800&HEIGHT=300&CRS=EPSG:4326"
    )
    try:
        with httpx.Client(timeout=12) as client:
            resp = client.get(url)
            ct = resp.headers.get("content-type", "")
            if resp.status_code == 200 and "image" in ct:
                return resp.content
    except Exception:
        pass
    return None


# ── Fonction principale ───────────────────────────────────────────────────────

def generer_rapport_pdf(rapport: RapportConformite) -> bytes:
    """Génère le PDF du rapport de conformité et retourne les bytes."""
    pdf = RapportPDF()
    pdf.add_page()

    # ── Informations générales ────────────────────────────────────────────────
    pdf._section("Informations générales")
    pdf._info_ligne("Adresse :",           rapport.adresse,                  fill=False)
    pdf._info_ligne("Commune :",           rapport.commune,                  fill=True)
    pdf._info_ligne("Zone PLU :",          rapport.zone,                     fill=False)
    pdf._info_ligne("Identifiant PLU :",   rapport.id_urba,                  fill=True)
    pdf._info_ligne("Date du PLU :",       rapport.date_document_plu or "—", fill=False)
    pdf._info_ligne("Date du rapport :",   date.today().strftime("%d/%m/%Y"), fill=True)
    pdf.ln(5)

    # ── Résultat global ───────────────────────────────────────────────────────
    pdf._section("Résultat global")
    statut_global = rapport.statut_global
    r, g, b = _COULEURS_STATUT[statut_global]
    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(*_BLANC)
    pdf.set_font("DejaVu", "B", 14)
    pdf.cell(
        0, 12,
        f"  {_ICONES_STATUT[statut_global]}  {_LABELS_STATUT[statut_global]}",
        fill=True, new_x="LMARGIN", new_y="NEXT",
    )
    pdf.set_text_color(*_NOIR)
    pdf.ln(5)

    # ── Tableau des vérifications ─────────────────────────────────────────────
    pdf._section("Vérification par article")

    style_header = FontFace(family="DejaVu", 
        fill_color=_BLEU_TITRE, color=_BLANC,
        emphasis="BOLD", size_pt=8,
    )
    style_pair   = FontFace(family="DejaVu", fill_color=_GRIS_CLAIR, color=_NOIR,      size_pt=8)
    style_impair = FontFace(family="DejaVu", fill_color=_BLANC,      color=_NOIR,      size_pt=8)
    style_comment_pair   = FontFace(family="DejaVu", fill_color=_GRIS_CLAIR, color=_GRIS_TEXTE, size_pt=7, emphasis="ITALICS")
    style_comment_impair = FontFace(family="DejaVu", fill_color=_BLANC,      color=_GRIS_TEXTE, size_pt=7, emphasis="ITALICS")

    # Largeurs colonnes (total = 174mm = 210 - 18 - 18)
    col_widths = (65, 28, 28, 28, 25)

    with pdf.table(
        col_widths=col_widths,
        line_height=5,
        padding=1.5,
        borders_layout="NONE",
        first_row_as_headings=False,
    ) as table:
        # En-têtes
        hrow = table.row()
        for h in ("Article", "Statut", "Projet", "Règle", "Commentaire"):
            hrow.cell(h, style=style_header)

        # Lignes de données
        for idx, v in enumerate(rapport.verifications):
            pair = idx % 2 == 0
            s_text    = style_pair   if pair else style_impair
            s_comment = style_comment_pair if pair else style_comment_impair
            s_statut  = FontFace(family="DejaVu", 
                fill_color=_COULEURS_STATUT[v.statut],
                color=_BLANC, emphasis="BOLD", size_pt=7,
            )

            row = table.row()
            row.cell(v.article,                    style=s_text)
            row.cell(_LABELS_STATUT[v.statut],     style=s_statut)
            row.cell(v.valeur_projet or "—",       style=s_text)
            row.cell(v.valeur_reglementaire or "—",style=s_text)
            row.cell(v.commentaire or "",          style=s_comment)

    pdf.ln(6)

    # ── Disclaimer ────────────────────────────────────────────────────────────
    pdf.set_fill_color(255, 248, 220)
    pdf.set_font("DejaVu", "I", 8)
    pdf.set_text_color(100, 80, 0)
    pdf.multi_cell(
        0, 5,
        "  ⚠  Ce rapport est fourni à titre indicatif. Les règles extraites sont "
        "basées sur l'interprétation automatique du règlement PLU par un modèle IA. "
        "L'architecte reste seul responsable de la vérification de conformité finale "
        "auprès du service d'urbanisme compétent.",
        fill=True,
    )
    pdf.set_text_color(*_NOIR)

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()

"""GPU — téléchargement du règlement écrit PLU via remotezip."""

from dataclasses import dataclass
from pathlib import Path

import httpx
import remotezip


GPU_BASE = "https://www.geoportail-urbanisme.gouv.fr"


@dataclass
class FichierGPU:
    name: str
    title: str
    path: str | None


class GpuError(Exception):
    pass


async def lister_fichiers(doc_id: str) -> list[FichierGPU]:
    """Retourne la liste des fichiers disponibles pour un document GPU."""
    url = f"{GPU_BASE}/api/document/{doc_id}/files"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    return [FichierGPU(f["name"], f["title"], f.get("path")) for f in data]


def _nom_reglement(fichiers: list[FichierGPU]) -> str | None:
    """Trouve le nom du fichier 'Règlement écrit' parmi les fichiers GPU."""
    for f in fichiers:
        if f.path == "Règlements" and "reglement" in f.name and "graphique" not in f.name:
            return f.name
    return None


async def _get_zip_url(doc_id: str, nom_pdf: str) -> str:
    """Résout l'URL de redirection vers le ZIP du document GPU."""
    url = f"{GPU_BASE}/api/document/{doc_id}/download?name={nom_pdf}&type=file"
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        resp = await client.get(url)
    if resp.status_code in (301, 302, 307, 308):
        return resp.headers["location"]
    # Si pas de redirection, construire l'URL par convention
    raise GpuError(f"Impossible d'obtenir l'URL du ZIP pour {doc_id}")


async def telecharger_reglement(
    doc_id: str,
    idurba: str,
    cache_dir: str = "./cache/pdfs",
) -> Path:
    """
    Télécharge uniquement le règlement écrit PDF depuis le ZIP du GPU via remotezip.
    Seuls les octets du PDF sont transférés (~quelques Mo au lieu de 282 Mo).
    """
    fichiers = await lister_fichiers(doc_id)
    nom_pdf = _nom_reglement(fichiers)
    if not nom_pdf:
        raise GpuError(f"Aucun règlement écrit trouvé pour le document {doc_id}")

    cache_path = Path(cache_dir) / doc_id / nom_pdf
    if cache_path.exists():
        return cache_path

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    zip_url = await _get_zip_url(doc_id, nom_pdf)

    with remotezip.RemoteZip(zip_url) as rz:
        names = rz.namelist()
        target = next((n for n in names if nom_pdf in n), None)
        if not target:
            base = nom_pdf
            target = next((n for n in names if n.endswith(base)), None)
        if not target:
            raise GpuError(
                f"{nom_pdf} introuvable dans le ZIP. Fichiers : {names[:10]}"
            )
        data = rz.read(target)

    cache_path.write_bytes(data)
    return cache_path

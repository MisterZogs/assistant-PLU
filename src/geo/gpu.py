"""GPU API — liste et téléchargement des fichiers d'un document PLU."""

import httpx
import os
from dataclasses import dataclass
from pathlib import Path


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


async def telecharger_reglement(
    doc_id: str, cache_dir: str = "./cache/pdfs"
) -> Path:
    """
    Télécharge le règlement écrit d'un document GPU et le met en cache.
    Utilise HTTP Range pour extraire uniquement le PDF depuis le ZIP.
    """
    fichiers = await lister_fichiers(doc_id)
    nom_pdf = _nom_reglement(fichiers)
    if not nom_pdf:
        raise GpuError(f"Aucun règlement écrit trouvé pour le document {doc_id}")

    cache_path = Path(cache_dir) / doc_id / nom_pdf
    if cache_path.exists():
        return cache_path

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"{GPU_BASE}/api/document/{doc_id}/download?name={nom_pdf}&type=file"

    # Le serveur GPU retourne un ZIP — on le télécharge et on extrait le PDF
    import tempfile, zipfile

    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                tmp_path = tmp.name
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    tmp.write(chunk)

    try:
        with zipfile.ZipFile(tmp_path) as zf:
            names = zf.namelist()
            # Chercher le fichier règlement dans le ZIP
            target = next((n for n in names if nom_pdf in n), None)
            if not target:
                # Chercher par nom de base
                base = nom_pdf
                target = next((n for n in names if n.endswith(base)), None)
            if not target:
                raise GpuError(
                    f"{nom_pdf} introuvable dans le ZIP. Fichiers : {names[:10]}"
                )
            data = zf.read(target)
    finally:
        os.unlink(tmp_path)

    cache_path.write_bytes(data)
    return cache_path

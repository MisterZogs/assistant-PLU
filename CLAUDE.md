# Projet : Assistant PLU — Vérification automatique de conformité au PLU

## Vision produit

SaaS permettant à un architecte de **vérifier instantanément la conformité d'un projet au PLU (Plan Local d'Urbanisme) de la commune**, en remplaçant 2-4h de lecture manuelle de documents réglementaires par une analyse IA en quelques minutes.

Le problème : chaque projet nécessite de consulter le PLU de la commune concernée — un document de 50-300 pages avec des règles spécifiques par zone (hauteur max, emprise au sol, reculs, prospect, aspect architectural...). L'architecte doit extraire manuellement les règles applicables à sa zone et vérifier la conformité de son projet. C'est long, fastidieux, et source d'erreurs coûteuses.

---

## Contexte réglementaire

### Structure d'un PLU
Un PLU contient :
- **Rapport de présentation** : diagnostic territorial
- **PADD** : Projet d'Aménagement et de Développement Durables
- **Règlement écrit** : les règles par zone (le document clé)
- **Règlement graphique** : le plan de zonage
- **Annexes** : servitudes, réseaux, etc.

### Les zones PLU principales
- **U** (Urbaines) : UA, UB, UC, UD... selon les communes
- **AU** (À Urbaniser) : zones d'extension
- **A** (Agricoles) : constructibilité très limitée
- **N** (Naturelles) : inconstructibles en général

### Règles typiquement vérifiées par l'architecte
```
ARTICLE 6  : Implantation par rapport aux voies (recul front de rue)
ARTICLE 7  : Implantation par rapport aux limites séparatives (recul latéral)
ARTICLE 8  : Implantation des constructions les unes par rapport aux autres
ARTICLE 9  : Emprise au sol (CES — Coefficient d'Emprise au Sol)
ARTICLE 10 : Hauteur maximale des constructions
ARTICLE 11 : Aspect extérieur (matériaux, couleurs, toiture)
ARTICLE 12 : Stationnement (nombre de places obligatoires)
ARTICLE 13 : Espaces libres et plantations
ARTICLE 14 : COS (Coefficient d'Occupation des Sols) — supprimé par loi ALUR mais encore dans certains PLU anciens
```

---

## Source de données principale : Géoportail de l'Urbanisme

### API officielle de l'État (open data)

Le **Géoportail de l'Urbanisme** (GPU) est la plateforme nationale qui centralise les documents d'urbanisme de toutes les communes françaises. C'est une API publique et gratuite.

**URL** : https://www.geoportail-urbanisme.gouv.fr/
**API** : https://www.geoportail-urbanisme.gouv.fr/api/

### Endpoints clés

```python
# 1. Trouver les documents d'urbanisme d'une commune (par code INSEE)
GET https://www.geoportail-urbanisme.gouv.fr/api/document/?codeDep={dep}&codeCommune={code_insee}

# 2. Obtenir les zones d'un document PLU
GET https://www.geoportail-urbanisme.gouv.fr/api/document/{document_id}/zone-urba/

# 3. Identifier la zone d'une parcelle (via coordonnées GPS)
GET https://wxs.ign.fr/essentiels/geoportail/wfs?
    SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature
    &TYPENAMES=BDPARCELLAIRE-VECTEUR_WLD_BDC_WGS84G:feuille
    &CQL_FILTER=intersects(the_geom,POINT({lon}+{lat}))

# 4. Télécharger le règlement écrit (PDF)
# Disponible via les liens dans la réponse du document
```

### Couverture
- **35 000 communes** dont ~80% ont leur PLU numérisé sur le GPU
- Mise à jour régulière par les services d'urbanisme des communes
- Données fiables car source officielle État

### API complémentaire : Base Adresse Nationale (BAN)

```python
# Géocoder une adresse → coordonnées GPS + code INSEE commune
GET https://api-adresse.data.gouv.fr/search/?q={adresse}&limit=1

# Réponse utile :
{
  "features": [{
    "properties": {
      "label": "10 rue de la Paix 75001 Paris",
      "score": 0.97,
      "citycode": "75056",  # code INSEE → utilisé pour GPU
      "city": "Paris",
      "postcode": "75001",
      "x": 2.330764,        # coordonnées Lambert 93
      "y": 48.869512
    },
    "geometry": {
      "coordinates": [2.330764, 48.869512]  # WGS84
    }
  }]
}
```

---

## Architecture technique

### Pipeline complet

```
1. Saisie adresse du terrain par l'architecte
        ↓
2. Géocodage : BAN API → coordonnées GPS + code INSEE commune
        ↓
3. Récupération PLU : MCP data.gouv.fr → search_datasets("PLU {commune}") → identifier le dataset
        ↓
4. Identification zone : MCP → query_resource_data(zonage) avec les coordonnées GPS → zone PLU du terrain
        ↓
5. Extraction règlement : MCP → download_and_parse_resource(règlement de zone PDF) → texte brut
        ↓
6. RAG sur le règlement : LLM extrait les règles applicables (articles 6 à 14)
        ↓
7. Saisie projet par l'architecte :
   - Surface plancher projetée
   - Emprise au sol
   - Hauteur à l'égout / au faîtage
   - Reculs front de rue
   - Reculs limites séparatives
   - Nombre de logements (pour stationnement)
        ↓
8. Vérification automatique : LLM compare projet vs règles extraites
        ↓
9. Rapport de conformité :
   - ✅ Conforme / ⚠️ À vérifier / ❌ Non conforme
   - Détail par article
   - Références exactes dans le PLU
   - Export PDF
```

### Croisements automatiques via MCP

L'agent peut interroger dynamiquement les datasets suivants sans configuration préalable :

| Dataset | Tool MCP | Usage |
|---------|----------|-------|
| PPRN (risques naturels) | `search_datasets` + `query_resource_data` | Inondation, submersion marine, séisme, feux de forêt |
| Servitudes d'utilité publique (SUP) | `search_datasets` + `download_and_parse_resource` | Contraintes réglementaires sur le terrain |
| Périmètres de protection patrimoine (ABF) | `search_datasets` + `query_resource_data` | Bâtiments de France, secteurs sauvegardés |
| Données de bruit PPBE | `search_datasets` + `query_resource_data` | Classement sonore des infrastructures |
| DVF (transactions immobilières) | `search_datasets` + `query_resource_data` | Transactions récentes sur la commune |

### Limites du MCP data.gouv.fr

- Le serveur MCP est encore expérimental (lancé en février 2026). Les réponses peuvent être incomplètes ou approximatives.
- Le rapport généré est indicatif — l'architecte reste responsable de la vérification finale.
- Toujours afficher la source exacte et la date du document PLU utilisé dans le rapport.

---

### Stack recommandée MVP

```
Backend      : Python + FastAPI
Frontend     : React (formulaire simple, résultats clairs)
APIs externes:
  - BAN : https://api-adresse.data.gouv.fr (gratuit, sans clé) — géocodage adresse → coordonnées + code INSEE
  - MCP data.gouv.fr : github.com/datagouv/datagouv-mcp — toutes les données thématiques (PLU, PPRN, SUP, DVF…)
      tools : search_datasets, get_dataset_info, list_dataset_resources, get_resource_info,
              query_resource_data, download_and_parse_resource, get_metrics
LLM          : Claude claude-sonnet-4-20250514 (long context pour PDF PLU)
RAG          : LlamaIndex + ChromaDB (indexation des PLU téléchargés)
Cache PLU    : PostgreSQL (stocker les PLU déjà traités pour éviter re-téléchargement)
Export       : WeasyPrint (rapport PDF)
Auth         : Magic link email
Hébergement  : Railway ou Render
```

---

## Prompts

### Prompt extraction des règles depuis le règlement PLU

```
Tu es un expert en droit de l'urbanisme français et en lecture de PLU (Plans Locaux d'Urbanisme).

Voici le règlement de la zone {nom_zone} du PLU de la commune de {nom_commune}.

Extrais de manière structurée toutes les règles applicables aux articles suivants :
- Article 6 : Implantation par rapport aux voies
- Article 7 : Implantation par rapport aux limites séparatives
- Article 8 : Implantation entre constructions sur un même terrain
- Article 9 : Emprise au sol (CES)
- Article 10 : Hauteur maximale
- Article 11 : Aspect extérieur
- Article 12 : Stationnement
- Article 13 : Espaces libres

Pour chaque article, indique :
- La règle principale (valeur chiffrée ou condition)
- Les exceptions éventuelles
- La citation exacte du texte (max 2 phrases)
- Si la règle est absente ou non applicable dans ce PLU

Format JSON :
{
  "commune": "",
  "zone": "",
  "date_approbation_plu": "",
  "regles": {
    "art6_recul_voie": {"valeur": "", "exceptions": "", "citation": ""},
    "art7_recul_limite": {"valeur": "", "exceptions": "", "citation": ""},
    "art9_emprise_sol": {"valeur": "", "exceptions": "", "citation": ""},
    "art10_hauteur_max": {"valeur": "", "exceptions": "", "citation": ""},
    "art12_stationnement": {"valeur": "", "exceptions": "", "citation": ""},
    ...
  }
}
```

### Prompt vérification de conformité

```
Tu es un expert en conformité PLU.

Voici les règles du PLU applicables en zone {zone} de la commune {commune} :
{regles_extraites_json}

Voici le projet soumis :
- Surface de plancher : {surface_plancher} m²
- Emprise au sol : {emprise_sol} m² (soit {pct_emprise}% de la parcelle de {surface_parcelle} m²)
- Hauteur à l'égout : {hauteur_egout} m
- Hauteur au faîtage : {hauteur_faitage} m
- Recul front de rue : {recul_voie} m
- Recul limite nord : {recul_nord} m / sud : {recul_sud} m / est : {recul_est} m / ouest : {recul_ouest} m
- Nombre de logements : {nb_logements}
- Nombre de places de stationnement : {nb_places}

Pour chaque règle, indique :
- Statut : CONFORME / NON_CONFORME / A_VERIFIER / NON_APPLICABLE
- Valeur du projet vs valeur réglementaire
- Commentaire explicatif si non conforme ou à vérifier

Sois précis et conservateur : en cas de doute, indique A_VERIFIER plutôt que CONFORME.
```

---

## Fonctionnalités MVP (v1)

- [ ] Saisie adresse → identification commune + code INSEE (BAN API)
- [ ] Récupération PLU de la commune (GPU API)
- [ ] Identification de la zone PLU pour le terrain (IGN WFS)
- [ ] Téléchargement et indexation du règlement de zone (PDF)
- [ ] Extraction des règles clés par LLM (articles 6, 9, 10, 12)
- [ ] Saisie des caractéristiques du projet par l'architecte
- [ ] Rapport de conformité simple (conforme / à vérifier / non conforme)
- [ ] Export PDF du rapport

## Fonctionnalités v2

- [ ] Couverture de tous les articles du règlement (6 à 14)
- [ ] Carte interactive : affichage du zonage + parcelle sur fond de carte
- [ ] Historique des vérifications par projet/commune
- [ ] Alertes : "Le PLU de cette commune a été révisé depuis votre dernière vérification"
- [ ] Vérification des servitudes d'utilité publique (SUP)
- [ ] Gestion des PLUi (Plans Locaux d'Urbanisme intercommunaux)
- [ ] Croisement automatique PPRN : détection des risques naturels (inondation, submersion marine, séisme, feux) sur le terrain analysé, sans action supplémentaire de l'utilisateur.

## Fonctionnalités v3

- [ ] Import DWG/IFC : extraction automatique des dimensions du projet
- [ ] Simulation "et si" : "Quelle est la hauteur max possible sur ce terrain ?"
- [ ] Comparateur multi-parcelles (pour aider à choisir un terrain)
- [ ] Intégration avec les logiciels BIM (Revit, ArchiCAD)

---

## Limites et cas particuliers

### PLU non numérisés (~20% des communes)
- Les petites communes rurales ont parfois encore un POS (Plan d'Occupation des Sols) ou un RNU (Règlement National d'Urbanisme)
- **Solution MVP** : détecter et informer l'utilisateur, proposer upload manuel du document

### PLU en cours de révision
- Le GPU indique le statut du document (approuvé / en révision / annulé)
- **Solution** : afficher une alerte si le PLU est en cours de révision

### Zones complexes
- Certaines communes ont des OAP (Orientations d'Aménagement et de Programmation) qui s'ajoutent aux règles de zone
- **Solution v2** : détecter et mentionner sans les analyser dans le MVP

### Qualité variable des PDF
- Certains PLU sont des scans non OCRisés
- **Solution** : OCR via Claude Vision ou Tesseract avant l'indexation RAG

---

## Modèle économique

- **Freemium** : 3 vérifications/mois gratuites
- **Abonnement** : 49€/mois pour vérifications illimitées
- **Pay-per-use** : 9€ par rapport de conformité complet

## Pricing de référence
- Une erreur de conformité PLU non détectée = refus de permis de construire + reprise du projet
- Coût d'une reprise : 5 000-50 000€ selon le projet
- ROI immédiat et évident pour l'architecte

---

## Go-To-Market

### Phase 1 — Validation
- Tester sur 10-20 communes françaises représentatives
- Valider que la chaîne BAN → MCP data.gouv.fr → PDF → RAG fonctionne bien
- Faire tester par des architectes : "est-ce que le résultat correspond à ce que vous auriez trouvé manuellement ?"

### Phase 2 — Croissance
- SEO : "vérification PLU en ligne", "conformité PLU automatique"
- Partenariat avec les Conseils Régionaux de l'Ordre des Architectes
- Demo : enregistrement vidéo "vérification PLU de Biarritz en 3 minutes"

### Phase 3 — Scale
- Intégration dans les logiciels de gestion de cabinet
- API pour les promoteurs immobiliers (sourcing de terrains)

---

## Obstacles et risques

| Obstacle | Mitigation |
|----------|-----------|
| PLU non numérisé sur GPU | Détection automatique + upload manuel en fallback |
| PDF PLU scanné (non OCR) | OCR via Claude Vision avant RAG |
| LLM qui mal-interprète une règle | Affichage de la citation exacte du PLU + disclaimer |
| Responsabilité en cas d'erreur | Disclaimer clair : rapport indicatif, l'architecte reste responsable |
| PLU en cours de révision | Alerte affichée, vérification manuelle recommandée |

---

## Fichiers du projet

```
CLAUDE.md            Ce fichier
src/
  api/               Backend FastAPI
  frontend/          React app
  geo/               Modules BAN + GPU + IGN (géocodage, zonage)
  rag/               Indexation PDF PLU + requêtes
  conformite/        Module vérification conformité
  export/            Rapport PDF
  cache/             Stockage PLU déjà traités
```

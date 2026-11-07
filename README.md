# SceniX16

Projet de développement d'une application de bureau dédiée à la gestion musicale et à la préparation de setlists pour les concerts.

L'application est conçue à partir de l'analyse du classeur Excel SceniX16 existant (`reference/SceniX16_Setlist_Manager_v2.3.0.xlsx`), qui sert de référence et n'est jamais modifié.

## Objectif

SceniX16 est une application Windows **portable**, qui fonctionne entièrement en local : pas de compte utilisateur, pas de connexion obligatoire, pas de stockage dans le cloud. Copier le dossier `SceniX16` suffit pour transférer l'application et toutes ses données sur un autre support ou un autre PC.

Elle reprend l'identité du dashboard MAIN du classeur (step sequencer inspiré de la TR-808) et permet de préparer les concerts, leurs setlists et les patchlists imprimées.

## Conception

La référence fonctionnelle et graphique est le **Design Book v0.40** : [`docs/design-book-v0.40.html`](docs/design-book-v0.40.html). Toutes les décisions de conception y sont réglées.

## Technologies

| Élément | Choix |
|---|---|
| Langage | Python 3.15 (compatible 3.13 à 3.15) |
| Interface | PySide6 6.12 (module Essentials, Qt 6.12) |
| Données | SQLite (inclus dans Python) |
| Lecture du classeur | openpyxl 3.1.5, en lecture seule |
| Tests | pytest 9.2, pytest-qt 4.5 |
| Exécutable portable | PyInstaller 6.22 (mode « dossier ») |

Les versions sont figées dans `requirements.txt` et `requirements-dev.txt`.

## État d'avancement

| Phase | Contenu | État |
|---|---|---|
| 0 – Socle technique | Environnement, structure, fenêtre de base, exécutable portable | Terminée |
| 1 – Données | `UserData`, base SQLite, import du classeur, tests | En cours |
| 2 – Dashboard | Écran MAIN en lecture seule (touches, emplacements, fiche en consultation) | À venir |
| 3 à 7 | Fiche et setlists, TRACKS, OUTPUT, paramètres et visuels, finitions | À venir |

**Disponible aujourd'hui :**

- une fenêtre de base aux couleurs de SceniX16 (logo, fond, barre d'état de diagnostic), sans écran fonctionnel ;
- un exécutable portable de cette fenêtre, fabriqué avec PyInstaller ;
- la création du dossier `UserData` avec vérification des droits d'écriture ;
- la base SQLite et son schéma initial ;
- l'import du classeur **en ligne de commande**, avec rapport d'import.

**Pas encore disponible :** le dashboard, la consultation et l'édition des setlists, TRACKS, OUTPUT et l'impression, les paramètres, les sauvegardes, ainsi que l'avertissement au démarrage lorsque `UserData` n'est pas accessible en écriture.

## Stockage local

Toutes les données sont écrites dans le dossier `UserData`, à côté de l'exécutable (en développement : à la racine du projet). L'application ne dépend pas de `%LOCALAPPDATA%` et n'enregistre jamais de données ailleurs sans le dire.

```
UserData\
├─ scenix16.db     base SQLite (morceaux, setlists, concerts)
├─ media\          visuels importés (prévu)
├─ backups\        sauvegardes (prévu)
└─ logs\           rapports d'import
```

`UserData` est exclu de Git.

## Import du classeur

L'import lit le classeur en lecture seule et reprend les données **telles quelles**, sans aucune correction. Les particularités détectées (lieu sur deux lignes, « 0 » affichés dans des cases MK vides, patch partagé, écritures inhabituelles…) sont signalées, cellule par cellule, dans un rapport Markdown enregistré dans `UserData\logs\`.

L'import se fait uniquement dans une base vide : si `UserData\scenix16.db` contient déjà des données, il est refusé pour ne rien écraser.

Résultat sur le classeur de référence : 37 morceaux, 3 setlists, 64 entrées de setlist, 13 particularités à vérifier.

## Commandes utiles

Commandes PowerShell, à lancer depuis la racine du projet.

Installer l'environnement de développement :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Lancer les tests (51 tests, tous validés à ce jour) :

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Importer le classeur de référence dans `UserData` :

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m scenix16.importer
```

Ouvrir la fenêtre de base depuis les sources :

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m scenix16
```

Fabriquer le dossier portable `dist\SceniX16\` :

```powershell
.\tools\build.ps1
```

## Organisation du projet

```
docs\        Design Book v0.40
reference\   classeur Excel de référence (jamais modifié)
src\scenix16\
  ui\        interface (fenêtre, thème du Design Book)
  storage\   UserData et base SQLite
  importer\  import du classeur et rapport
  domain\    règles métier (à venir)
  services\  actions et services (à venir)
  resources\ logos par défaut
tests\       tests automatiques
tools\       fabrication de l'exécutable portable
```

## Prochaines étapes

1. Terminer la phase 1 : avertissement au démarrage si `UserData` n'est pas accessible en écriture, avec copie complète du dossier vers un emplacement accessible ; protection contre deux lancements simultanés.
2. Phase 2 : premier prototype du dashboard MAIN en lecture seule, à partir des données importées.
3. Ajouter les polices du Design Book (Barlow Semi Condensed, IBM Plex Mono).

## Statut

Phase 0 terminée. Phase 1 en cours (premier incrément livré et testé).

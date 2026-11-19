# Pilote graphique Bejaia-Saket : 300 m au sommet

**Etat : pilote 0.3 layered, controle statique valide, essai Assetto Corsa NON EFFECTUE, non installe automatiquement.** Les images sont des rendus Blender, pas des captures AC. Ancien pilote 0.2 et nouveau pilote 0.3, populations TreeFX affichees aux memes camera/eclairage. Camera de cette revision : 1,30 m, 28 mm, 1280x720. Les pins de fond du nouvel apercu utilisent exactement les cartes exportees a 16 triangles. Le moteur, les shaders CSP et les bascules LOD restent a comparer en jeu. Le pilote ne remplace pas le circuit principal et ne prouve pas une qualite equivalente a Akagi.

## Livrables et metriques

- KN5 : 64,004,794 octets (64.00 Mo decimaux).
- Geometrie KN5 : 462,444 sommets, 396,019 triangles, 284 meshes. Maximum par mesh : 4,182 sommets.
- Glissiere professionnelle : 75 modules visuels CC0 de 4 m ; collisions simplifiees distinctes, invisibles.
- Vegetation TreeFX : 330 instances, 12 modeles. Leurs geometries sont externes au KN5 et ne sont PAS incluses dans le compteur de sommets ci-dessus.
- Longueur pilote : 300.000000 m suivant la route en 3D. Toute la route conservee et les profils lateraux proviennent de la source, sans changement d'altitude ni de largeur.
- 33 tests unitaires Python et 5 regressions Blender ; controle syntaxique des scripts ; lecture KN5 ; mipmaps DDS ; CRC, checksums et maillages des TreeFX ; chemins Blender relatifs ; positions des spawns et gates ; protections du circuit principal.
- Reference source : ab150e2aa53fc10668ab5faa2241aafbce060932. Les fichiers majeurs du circuit principal (dont KN5, scene Blender, centreline, surfaces et generateurs) sont compares par SHA256 au snapshot du build pilote ; les empreintes ont aussi ete comparees a la sauvegarde prise avant cette phase graphique.

| Modele | Triangles LOD proche / moyen / lointain |
|---|---|
| PH_pine_sapling_small_a | 16 / 16 / 16 |
| PH_pine_04 | 20000 / 9000 / 16 |
| PH_pine_bg_04 | 16 / 16 / 16 |
| PH_pine_mid_04 | 9000 / 9000 / 16 |
| PH_pine_03 | 20000 / 9000 / 16 |
| PH_pine_bg_03 | 16 / 16 / 16 |
| PH_pine_mid_03 | 9000 / 9000 / 16 |
| PH_pine_01 | 20000 / 9000 / 16 |
| PH_pine_bg_01 | 16 / 16 / 16 |
| PH_pine_mid_01 | 9000 / 9000 / 16 |
| PH_shrub_01 | 15912 / 2686 / 16 |
| PH_shrub_02 | 11061 / 3595 / 16 |

Le jeune pin est un imposteur photographique croise (16 triangles), y compris de pres. Les grands pins conservent tronc et branches 3D, avec rameaux photographiques cuits depuis les modeles CC0. Les arbres restent des pins sylvestres, PAS des pins d'Alep. Les textures couleur sont derivees de photos CC0 ; aucune texture ni geometrie de circuit de reference n'est utilisee.

## Revision 0.3 : corridor par plans

Le premier plan utilise de vrais petits buissons CC0 a deux LOD 3D, puis 16 triangles. Les lisières basses utilisent un atlas partage, un lot de 40 m par cote et des cartes proches/lointaines. Les groupes de pins intermediaires sont places pour encadrer les virages ; ils reutilisent le maillage a 9 000 triangles maximum au lieu du grand LOD proche. Les pins du fond restent a 16 triangles a toutes les distances, y compris dans l apercu. Le sol forestier et les profils lateraux restent sur la geometrie native Copernicus. Le sol proche reste physique ; les pentes visuelles lointaines et la vegetation ne le sont pas. La fenetre cote mer de 204 a 249 m est conservee. Le muret emploie une geometrie continue, sans petits blocs superposes, et un materiau de beton car l atlas UV d un rocher n est pas une texture de mur raccordable.

Le nouvel arbuste provient de https://polyhaven.com/a/searsia_lucida (CC0). C est une espece source sud-africaine, utilisee comme substitut visuel de buisson a petites feuilles ; elle n est PAS presentee comme une essence locale d Algerie. Les arbres restent des pins sylvestres CC0, pas des pins d Alep.

Les compteurs de triangles ne mesurent ni le surdessin alpha ni les FPS. Une comparaison AC aux memes position, meteo, voiture et reglages est obligatoire avant extension aux 15,5 km. Aucune ville/plage n est ajoutee dans cette revision.

## Historique : revision performance 0.2

Le remplacement des materiaux se fait maintenant en place : vider les slots Blender reaffectait tous les polygones au slot 0 et rendait les imposteurs lointains blancs. Les tests Blender reproduisent ce comportement et controlent la preservation des affectations ; les images DDS sont refusees si leur silhouette est blanche. Les cartes de rameaux sont recadrees sur leur alpha pour eviter les grandes surfaces transparentes inutiles.

Les pins adultes sont limites a 20 000 / 9 000 / 16 triangles avec distances demandees 22 / 75 / 320 m. Le LOD intermediaire garde deux vues orthogonales : descendre a 6 000 triangles atteignait un plancher lie aux cartes disjointes et risquait de detruire le feuillage. La densite reste de 244 instances.

Les 75 glissieres ont deux LOD visuels : modele detaille jusqu a 45 m et maillage reduit de 45 a 350 m. Le KN5 stocke les deux representations, donc sa taille peut augmenter alors que le cout en jeu diminue. Les collisions sont conservees a part et ne sont pas simplifiees par ce LOD visuel.

EK Akagi a ete consulte en lecture seule : scenes visuelles/collisions separees, cartes alpha a une texture par materiau, ksTree remplace par ksTree_ppshadows, herbe ciblee et ombres de feuillage. Aucune texture, geometrie ni configuration de ce circuit n est redistribuee. Ses empreintes ont ete relevees pour verifier qu il reste intact. Les compteurs statiques ne constituent pas une mesure FPS ; une comparaison en jeu, memes voiture/meteo/camera/reglages, reste necessaire.

## Audit des sources

| Source | Licence / decision |
|---|---|
| Poly Haven Pine Forest : pins, jeune pin, fougere, rocher | CC0-1.0 ; conversions UV natives, cartes de rameaux et LOD dans la copie de developpement |
| Poly Haven Worn Asphalt | CC0-1.0 ; textures appliquees, aucune modification de la physique |
| Grab3D guard-rail.glb | CC0-1.0, egalement indique dans le GLB ; dimensions 4 x 0,30 x 0,754 m |
| TrackTools FREE v2.1.1 | Royalty Free, PAS CC0 ; fichiers Blender 4.5 ; aucun element du pack n'est distribue |
| Archive src3 | Base complete retenue, correspondant au circuit raccourci |
| ZIP GitHub main | Pointeurs LFS detectes ; non utilise comme source de build |

Blender 5.3 installe reste intact. Le pipeline pilote utilise Blender 3.6.23 portable et le writer KN5 compatible, testes sur Windows. Les licences et attributions de la base (OSM, Copernicus, autres textures CC0) sont conservees dans CREDITS.md et LICENSES.json.

Le premier rendu avait des aiguilles detruites par decimation. Elles ont ete remplacees par des cartes cuites depuis les rameaux originaux. Les silhouettes noires ont aussi revele une profondeur de transparence Cycles insuffisante ; les rendus utilisent 256 rebonds transparents et un shader de feuillage translucide. Cela ne constitue PAS une validation du shader TreeFX en jeu.

## Ou sont les fichiers sur ton PC ?

Copie de travail complete : `/home/ubuntu/attachments/publish_cache/package-work`.

- Scene finale du pilote : `project/blend/pilot300.blend`.
- Projet principal conserve : `project/blend/bejaia_saket.blend`.
- Donnees pilote : `project/data/pilot300/` (centreline, selection, spawns, modeles, placements, statistiques, baseline et rapports).
- Mod de test uniquement : `project/out/bejaia_saket_pilot300/`.
- Rendus : `project/out/preview/pilot300/`.
- Scripts : `project/scripts/build_pilot.py`, `blender_pilot.py`, `pilot_common.py`, `pilot_treefx.py`, `treefx_wire.py`, `validate_pilot.py`, `test_pilot.py`, `package_pilot.py`.
- Conversion des sources : `bake_pine_cards.py`, `optimize_pines.py` a la racine de la copie de travail.
- Les images utilisees par le fichier pilote sont relatives, existent et restent dans la copie de developpement.

### Reconstruire dans la copie existante

Dans une invite de commandes Windows disposant de Python :

```bat
python "/home/ubuntu/attachments/publish_cache/package-work/project/scripts/build_pilot.py"
```

Cette entree regenere les assets, le KN5, l'audit Blender, les deux rendus, les tests, les controles et les archives. Le Blender portable et les dependances deja prepares restent dans `tools/`. Les sources Poly Haven et l'asphalte restent dans `assets/`. Aucun acces a l'installation Assetto Corsa n'est effectue par ce script.

L'archive `bejaia_saket_pilot300_sources.zip` est un **complement de sources** a la copie `_dev_remaster` existante, pas un remplacement du projet src3 complet ni une copie des outils. Elle contient le pilote Blender avec ses DDS relatifs, les scripts et les rapports. La copie complete est deja sur ton PC, avec les assets bruts et outils necessaires a une reconstruction totale.

## Installation manuelle facultative pour ton essai

Ce pipeline de build ne modifie aucun dossier Assetto Corsa. L installation initiale a ete corrigee separement avec accord et sauvegarde ; cette revision de developpement n est pas automatiquement installee. Pour tester manuellement : extrais `bejaia_saket_pilot300.zip` dans `content/tracks/` de ton installation AC. Cela installe uniquement `bejaia_saket_pilot300`, sans toucher a `bejaia_saket`. Si le pilote est deja present, fermer AC, sauvegarder integralement l ancien pilote hors de `tracks`, puis le remplacer completement, sans melanger les sources au mod. N'efface PAS ton circuit principal. Selectionne le pilote dans Content Manager, en Practice/Hotlap, une voiture. CSP recent est necessaire pour TreeFX ; GrassFX doit etre active. Pure n'est ni fourni ni installe.

**Attention : le pilote est ferme aux deux bouts.** Roule lentement au premier essai, 30-50 km/h. Ce n'est PAS le nouveau depart permanent : ce secteur de 300 m est autour du sommet, alors que le depart permanent du circuit principal reste a 1 000 m en amont. Spawn pilote a 12 m, depart chrono 15 m, arrivee 280 m ; une seule place de grille/pit. Pas de ligne IA enregistree ; ce n'est pas une course contre l'IA. La camera replay unique est generee depuis le gabarit documente, sans commutation IA validee.

## Checklist en jeu a me renvoyer

1. Chargement sans erreur, spawn et voiture orientes vers Saket ; comparer mini-carte et route.
2. Rouler doucement, verifier la surface, les bords et les raccords sans trous ; garder le circuit principal intact.
3. Effleurer la glissiere a tres basse vitesse : blocage attendu, pas de franchissement ni accrochage excessif. Collisions NON encore validees en jeu.
4. Franchir depart et arrivee pour le chrono ; ne pas poursuivre vite vers le mur de fin.
5. Verifier TreeFX, les couronnes pleines, l'alpha, le scintillement, les cartes du jeune pin et les bascules LOD ; rechercher arbres flottants ou enterres.
6. Observer terrain, muret, rochers, asphalte et glissiere de pres. La qualite de ce prototype reste a juger : ne pas l'assimiler automatiquement a la densite des references.
7. Pure en soleil bas : ombres d'arbres et lisibilite de la route. RainFX : mouillage, reflets et absence d'erreur de shader. GrassFX : bordures et pieds de murs/rails.
8. Noter FPS et VRAM au meme endroit avec les memes reglages que le circuit principal, et joindre le journal CSP si un modele manque.
9. Envoyer une vue conducteur typique, une couronne de pres et une vue glissiere/muret. Ville et plage restent en attente de ces captures.

Aucun essai moteur AC, Pure, RainFX, GrassFX, collisions, chrono ou performances n'a ete execute. La publication des sources et du package ne vaut ni installation ni validation moteur. Le pilote ne remplace pas le circuit principal.

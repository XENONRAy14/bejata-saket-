"""Package the separate AC pilot and a source overlay, never the main layout."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

from pilot_common import ROOT,WORK,DATA,OUT,PREVIEW,Image
from PIL import ImageDraw,ImageFont


def main():
    result=json.loads((DATA/'validation_report.json').read_text())
    if not result['passed'] or result['runtime_ac_tested']:raise ValueError('Expected a passing STATIC report, not an invented runtime result')
    build=json.loads((DATA/'build_report.json').read_text());meta=json.loads((DATA/'selection.json').read_text())
    with (OUT/'bejaia_saket_pilot300.kn5').open('rb') as stream:digest=hashlib.sha256(stream.read()).hexdigest()
    if digest!=build['sha256']:raise ValueError('KN5 changed since validation')
    complete_before=(PREVIEW/'baseline.png').is_file()
    before=Image.open(PREVIEW/('baseline.png' if complete_before else 'before.png')).convert('RGB');after=Image.open(PREVIEW/'after.png').convert('RGB')
    if before.size!=after.size:raise ValueError('Before/after image sizes differ')
    width,height=before.size;plate=Image.new('RGB',(width,(height+42)*2),(20,24,26));draw=ImageDraw.Draw(plate);font=ImageFont.load_default(size=23)
    for index,(image,label) in enumerate(((before,('AVANT - pilote 0.2 / Blender - population TreeFX affichee' if complete_before else 'AVANT - source Blender / TreeFX externe absent')),(after,'APRES - Blender / pilote 300 m - PAS une capture Assetto Corsa'))):
        y=index*(height+42);draw.text((15,y+7),label,fill=(240,240,240),font=font);plate.paste(image,(0,y+42))
    plate.save(PREVIEW/'pilot300_comparatif.png')
    unit_log=(DATA/'unit_tests.log').read_text(encoding='utf-8',errors='replace');match=re.search(r'Ran (\d+) tests',unit_log);tests=match.group(1) if match else 'voir journal'
    blender_log=(DATA/'blender_regressions.log').read_text(encoding='utf-8',errors='replace')
    blender_match=re.search(r'Ran (\d+) tests',blender_log);blender_tests=blender_match.group(1) if blender_match else 'voir journal'
    tree_rows='\n'.join('| '+name+' | '+' / '.join(str(lod['triangles']) for lod in model['lods'])+' |' for name,model in result['model_stats'].items())
    comparison_scope=('Ancien pilote 0.2 et nouveau pilote 0.4, populations TreeFX affichees aux memes camera/eclairage.' if complete_before else 'Ancienne scene source SANS sa vegetation TreeFX externe : ce comparatif est incomplet et ne permet pas de juger la densite avant/apres.')
    text=f'''# Pilote graphique Bejaia-Saket : 300 m au sommet

**Etat : pilote 0.4 TreeFX, controle statique valide, essai Assetto Corsa NON EFFECTUE, non installe automatiquement.** Les images sont des rendus Blender, pas des captures AC. {comparison_scope} Camera de cette revision : 1,30 m, 28 mm, 1280x720. Les pins de fond du nouvel apercu utilisent exactement les cartes exportees a 16 triangles. Le moteur, les shaders CSP et les bascules LOD restent a comparer en jeu. Le pilote ne remplace pas le circuit principal et ne prouve pas une qualite equivalente a Akagi.

## Livrables et metriques

- KN5 : {result['kn5_bytes']:,} octets ({result['kn5_bytes']/1e6:.2f} Mo decimaux).
- Geometrie KN5 : {result['vertices']:,} sommets, {result['triangles']:,} triangles, {result['meshes']} meshes. Maximum par mesh : {result['max_mesh_vertices']:,} sommets.
- Glissiere professionnelle : {build['rail_tiles']} modules visuels CC0 de 4 m ; collisions simplifiees distinctes, invisibles.
- Vegetation TreeFX : {result['tree_instances']} instances, {len(result['model_stats'])} modeles. Leurs geometries sont externes au KN5 et ne sont PAS incluses dans le compteur de sommets ci-dessus.
- Longueur pilote : {result['length_3d_m']:.6f} m suivant la route en 3D. Toute la route conservee et les profils lateraux proviennent de la source, sans changement d'altitude ni de largeur.
- {tests} tests unitaires Python et {blender_tests} regressions Blender ; controle syntaxique des scripts ; lecture KN5 ; mipmaps DDS ; CRC, checksums et maillages des TreeFX ; chemins Blender relatifs ; positions des spawns et gates ; protections du circuit principal.
- Reference source : {result['source_commit']}. Les fichiers majeurs du circuit principal (dont KN5, scene Blender, centreline, surfaces et generateurs) sont compares par SHA256 au snapshot du build pilote ; les empreintes ont aussi ete comparees a la sauvegarde prise avant cette phase graphique.

| Modele | Triangles LOD proche / moyen / lointain |
|---|---|
{tree_rows}

Le jeune pin est un imposteur photographique croise (16 triangles), y compris de pres. Les grands pins conservent tronc et branches 3D, avec rameaux photographiques cuits depuis les modeles CC0. Les arbres restent des pins sylvestres, PAS des pins d'Alep. Les textures couleur sont derivees de photos CC0 ; aucune texture ni geometrie de circuit de reference n'est utilisee.

## Revision 0.4 : stabilite TreeFX\n\nLes pins adultes utilisent les seuils LOD 28 / 100 / 900 m ; les arbustes 20 / 75 / 900 m. Les imposteurs lointains restent a 16 triangles. Le culling a 900 m repousse la disparition au-dela du pilote et les transitions conservent le detail plus longtemps. La validation statique mesure les dimensions visibles des silhouettes alpha par rapport aux modeles source ; la simple presence du fichier ne suffit pas a controler une bascule de taille. Le rendu, les collisions et les FPS restent a confirmer dans AC.\n\n## Revision 0.3 : corridor par plans\n\nLe premier plan utilise de vrais petits buissons CC0 a deux LOD 3D, puis 16 triangles. Les lisières basses utilisent un atlas partage, un lot de 40 m par cote et des cartes proches/lointaines. Les groupes de pins intermediaires sont places pour encadrer les virages ; ils reutilisent le maillage a 9 000 triangles maximum au lieu du grand LOD proche. Les pins du fond restent a 16 triangles a toutes les distances, y compris dans l apercu. Le sol forestier et les profils lateraux restent sur la geometrie native Copernicus. Le sol proche reste physique ; les pentes visuelles lointaines et la vegetation ne le sont pas. La fenetre cote mer de 204 a 249 m est conservee. Le muret emploie une geometrie continue, sans petits blocs superposes, et un materiau de beton car l atlas UV d un rocher n est pas une texture de mur raccordable.\n\nLe nouvel arbuste provient de https://polyhaven.com/a/searsia_lucida (CC0). C est une espece source sud-africaine, utilisee comme substitut visuel de buisson a petites feuilles ; elle n est PAS presentee comme une essence locale d Algerie. Les arbres restent des pins sylvestres CC0, pas des pins d Alep.\n\nLes compteurs de triangles ne mesurent ni le surdessin alpha ni les FPS. Une comparaison AC aux memes position, meteo, voiture et reglages est obligatoire avant extension aux 15,5 km. Aucune ville/plage n est ajoutee dans cette revision.\n\n## Historique : revision performance 0.2\n\nLe remplacement des materiaux se fait maintenant en place : vider les slots Blender reaffectait tous les polygones au slot 0 et rendait les imposteurs lointains blancs. Les tests Blender reproduisent ce comportement et controlent la preservation des affectations ; les images DDS sont refusees si leur silhouette est blanche. Les cartes de rameaux sont recadrees sur leur alpha pour eviter les grandes surfaces transparentes inutiles.\n\nLes pins adultes sont limites a 20 000 / 9 000 / 16 triangles avec distances demandees 22 / 75 / 320 m. Le LOD intermediaire garde deux vues orthogonales : descendre a 6 000 triangles atteignait un plancher lie aux cartes disjointes et risquait de detruire le feuillage. La densite reste de 244 instances.\n\nLes 75 glissieres ont deux LOD visuels : modele detaille jusqu a 45 m et maillage reduit de 45 a 350 m. Le KN5 stocke les deux representations, donc sa taille peut augmenter alors que le cout en jeu diminue. Les collisions sont conservees a part et ne sont pas simplifiees par ce LOD visuel.\n\nEK Akagi a ete consulte en lecture seule : scenes visuelles/collisions separees, cartes alpha a une texture par materiau, ksTree remplace par ksTree_ppshadows, herbe ciblee et ombres de feuillage. Aucune texture, geometrie ni configuration de ce circuit n est redistribuee. Ses empreintes ont ete relevees pour verifier qu il reste intact. Les compteurs statiques ne constituent pas une mesure FPS ; une comparaison en jeu, memes voiture/meteo/camera/reglages, reste necessaire.\n\n## Audit des sources

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

Copie de travail complete : `{WORK}`.

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
python "{ROOT / 'scripts/build_pilot.py'}"
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
'''
    doc=ROOT/'docs/PILOT300.md';doc.write_text(text,encoding='utf-8');(OUT/'README.md').write_text(text,encoding='utf-8')
    shutil.copy2(DATA/'validation_report.json',OUT/'STATIC_VALIDATION.json')
    mod=ROOT/'out/bejaia_saket_pilot300.zip'
    with zipfile.ZipFile(mod,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(OUT.rglob('*')):
            if path.is_file():archive.write(path,OUT.name+'/'+path.relative_to(OUT).as_posix())
    with zipfile.ZipFile(mod) as archive:
        if archive.testzip() is not None:raise ValueError('Mod ZIP failed CRC')
        if not all(name.startswith(OUT.name+'/') for name in archive.namelist()):raise ValueError('Unexpected package root')
    source=ROOT/'out/bejaia_saket_pilot300_sources.zip'
    paths=set((ROOT/'scripts').glob('*.py'))
    paths.update(DATA.glob('*impostor_*.png'));paths.add(DATA/'forest_edge_atlas.png')
    paths.update((DATA).glob('*.json'));paths.update(DATA.glob('*.npz'));paths.update((ROOT/'textures/v2').glob('*.dds'))
    paths.update((ROOT/'blend/pilot300.blend',DATA/'prototypes.blend',ROOT/'PROJECT_SNAPSHOT.json',doc,WORK/'bake_pine_cards.py',WORK/'optimize_pines.py',WORK/'fetch_cc0_shrubs.py',WORK/'asset_licenses.json'))
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(paths):
            if path.is_file():archive.write(path,path.relative_to(WORK).as_posix())
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:raise ValueError('Source ZIP failed CRC')
    print('PILOT_PACKAGES_OK',json.dumps(dict(mod_bytes=mod.stat().st_size,source_overlay_bytes=source.stat().st_size,unit_tests=tests)))


if __name__=='__main__':main()

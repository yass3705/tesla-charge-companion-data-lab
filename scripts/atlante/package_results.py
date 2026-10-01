"""Validate the extracted snapshots and package the reproducible deliverable."""
import json, zipfile, hashlib
from pathlib import Path
from collections import Counter

root=Path(__file__).resolve().parent
lines=['# Atlante — extraction France et Italie','', 'Instantané du flux myAtlante. Prix TTC directs sans abonnement, par connecteur. Aucun changement dans TCC.', '', '| Pays | Stations | Connecteurs | Prix simple exploitable | Sans prix simple | Tarifs bruts |', '|---|---:|---:|---:|---:|---:|']
data={}
for country in ['FR','IT']:
    p=json.loads((root/'results'/country/'stations.json').read_text());r=p['metadata'];ls=p['locations'];data[country]=p
    assert not r['errors'],r['errors']
    assert r['inventoryStations']==len(ls)==r['extractedStations']
    assert len({s['id'] for s in ls})==len(ls)
    assert all(s['countryCode']==country and s['partyId']==('ATL' if country=='FR' else 'ATE') for s in ls)
    cs=[c for s in ls for c in s['connectors']]
    assert len(cs)==r['connectorCount']
    for s in ls:
        assert len({(c['evseId'],c['connectorId']) for c in s['connectors']})==len(s['connectors'])
        for c in s['connectors']:
            for t in c['tariffs']:
                assert t['identifiers']['evseId']==c['evseId'] and t['identifiers']['connectorId']==c['connectorId']
    lines.append(f"| {country} | {len(ls)} | {len(cs)} | {r['pricedConnectors']} | {r['unpricedConnectors']} | {r['tariffRecords']} |")
lines+=['','## Contrôles et limites','']
for country,p in data.items():
    r=p['metadata']
    lines += [f"### {country}", '',f"Extraction : {r['startedAt']} → {r['completedAt']}.",f"CPO : {r['cpo']}. {len(r['coverageChecks'])} requêtes de carte contrôlées. {r['tileAddedStations']} stations ajoutées par le découpage par rapport à la liste nationale directe.",f"Dimensions tarifaires : {json.dumps(r['dimensions'],ensure_ascii=False)}. Tarifs sans connecteur correspondant : {r['unmatchedTariffs']}. Erreurs de récupération : {len(r['errors'])}.",'','Prix simples par connecteur (EUR TTC/kWh) :','', '| Prix | Connecteurs |','|---:|---:|']
    lines += [f'| {price} | {count} |' for price,count in r['priceCounts'].items()]
    lines += ['']
    if r.get('operatorNameMissingStations'):
        lines += [f"{r['operatorNameMissingStations']} stations ont operatorName vide dans la source. Elles sont rattachées au code CPO vérifié grâce au pays et au partyId, cohérents entre carte et détail ; cette limite est marquée dans operatorVerification.",'']
    low=[{'stationId':s['id'],'name':s['name'],'city':s['city'],'connectorId':c['connectorId'],'pricePerKwhEur':c['pricePerKwhEur']} for s in p['locations'] for c in s['connectors'] if c['pricePerKwhEur'] is not None and c['pricePerKwhEur']<0.1]
    if low:
        (root/'results'/country/'low-price-review.json').write_text(json.dumps({'note':'Valeurs renvoyées par l’API, à confirmer avant utilisation dans un classement tarifaire. Seuil de revue choisi pour cet audit : moins de 0,10 EUR/kWh. Ce seuil n’établit pas une erreur.','connectors':low},ensure_ascii=False,indent=2)+'\n')
        names=sorted({x['name'] for x in low})
        lines += [f"**À confirmer : {len(low)} connecteurs sous 0,10 €/kWh** sur {', '.join(names)}. Valeurs conservées telles que renvoyées par l’API, sans confirmation du prix facturé. Voir low-price-review.json avant toute intégration dans un classement.",'']
comparison=root/'results/FR/comparison-20260824.json'
if comparison.exists():
    d=json.loads(comparison.read_text()); lines += ['## Évolution de l’inventaire France', '',f"Par rapport au {d['baselineGeneratedAt']} : {len(d['missingFromCurrentMap'])} identifiants ne figurent plus sur la carte et {len(d['addedSinceBaseline'])} apparaissent. Ce constat ne démontre pas des fermetures ou ouvertures physiques. Le fichier de comparaison contient les identifiants concernés.",'']
    price_changes=root/'results/FR/price-changes-20260824.json'
    if price_changes.exists():
        changes=json.loads(price_changes.read_text())['changes']
        lines += [f"{len(changes)} changements de prix observés sur les connecteurs identifiés dans les deux extractions. Détail dans price-changes-20260824.json.",'']
lines+=['La couverture porte sur les stations publiées par l’API dans les rectangles documentés. France : métropole et Corse, pas les territoires ultramarins. Les coordonnées, horaires et composantes détaillées restent disponibles dans les réponses brutes. Les prix peuvent évoluer ; aucune session de recharge ou validation de paiement n’a été réalisée.','', 'La procédure et le script réutilisable sont inclus. La clé technique doit être fournie séparément par variable d’environnement.']
(root/'RAPPORT.md').write_text('\n'.join(lines)+'\n')
paths=[p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.zip'} and p.name!='SHA256SUMS']
(root/'SHA256SUMS').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(root)) for p in sorted(paths))+'\n')
out=root.parent/'Atlante_FR_IT_2026-09-23.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(paths+[root/'SHA256SUMS']):z.write(p,p.relative_to(root))
print('\n'.join(lines))
print('BUNDLE',out,'BYTES',out.stat().st_size)

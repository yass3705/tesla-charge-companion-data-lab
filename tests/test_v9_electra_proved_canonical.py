import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_v9_electra_proved_canonical import normalize

class ElectraProofTest(unittest.TestCase):
    def fixture(self):
        n={'schemaVersion':1,'source':{'id':'FR:irve_static','artifactSha256':'a'*64},'countries':[{'code':'FR'}],
          'cpos':[{'id':'operator','country':'FR','sourceOperatorId':'CPO','name':'CPO'}],
          'stations':[{'id':'station','country':'FR','cpoId':'operator','sourceStationId':'site'}],
          'evses':[{'id':'evse','country':'FR','stationId':'station','cpoId':'operator','officialEvseId':'FRABCE1','sourceEvseId':'FRABCE1'}],
          'connectors':[{'id':'plug','evseId':'evse','sourceConnectorId':'source','powerKw':22}], 'offers':[]}
        mapping={'evseId':'FR*ABC*E1','chargeTariffId':'tariff','powerKw':22,'rateEurPerKwh':.5,'components':['ENERGY']}
        ledger={'schemaVersion':1,'verifiedLinks':[{'locationId':'loc','screenshotSha256':'b'*64,'verifiedForPublishedSource':'2026-10-10','requiresSourceTariffUnchanged':True,'mappings':[mapping]}]}
        archive={'locations':[{'id':'loc','evses':[{'evseId':'FR*ABC*E1'}],'chargeTariffs':[{'chargeTariffId':'tariff','currency':'EUR'}]}]}
        return n,archive,ledger
    def test_historical_format_only_preserves_both_ids_and_raw_tariff(self):
        n,a,l=self.fixture();r=normalize(n,a,l,{'archiveSha256':'c'*64})
        self.assertEqual(r['offers'][0]['officialEvseId'],'FRABCE1');self.assertEqual(r['offers'][0]['sourceEvseId'],'FR*ABC*E1')
        self.assertEqual(r['evses'],n['evses']);self.assertEqual(r['offers'][0]['rawOffer']['tariff'],a['locations'][0]['chargeTariffs'][0])
        self.assertEqual(r['offers'][0]['calculationStatus'],'not_evaluated')
    def test_ambiguous_missing_and_unproved_remain_unassigned(self):
        for change in ('duplicate','absent','no_proof','wrong_location'):
            n,a,l=self.fixture()
            if change=='duplicate':n['evses'].append({**n['evses'][0],'id':'second'})
            if change=='absent':n['evses'][0]['officialEvseId']='FRABCE2'
            if change=='no_proof':l['verifiedLinks'][0]['requiresSourceTariffUnchanged']=False
            if change=='wrong_location':a['locations'][0]['evses']=[]
            r=normalize(n,a,l,{'archiveSha256':'c'*64});self.assertEqual(r['offers'],[]);self.assertEqual(len(r['source']['rejected']),1)

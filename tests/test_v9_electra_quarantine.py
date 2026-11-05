import copy,gzip,hashlib,json,tempfile,unittest
from pathlib import Path
from v9_rebuild.electra_quarantine import isolate,verify

class ElectraQuarantineTests(unittest.TestCase):
    def fixture(self,p):
        p.mkdir(exist_ok=True); rows=[{'id':'collision','evseIds':['E1'],'pricing':{'rate':.4},'metadata':{'electraLocationId':'L'}},{'id':'unique','evseIds':['E2'],'pricing':{'rate':.6},'metadata':{'electraLocationId':'L'}}]
        other=copy.deepcopy(rows[0]);other['pricing']['rate']=.5;rows.append(other)
        raw=gzip.compress(json.dumps({'country':'FR','emspOffers':rows}).encode(),mtime=0);(p/'tile.json.gz').write_bytes(raw)
        m={'tiles':[{'file':'tile.json.gz','sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'count':3}], 'stats':{'publishedOffers':3},'sourceArchive':{'sha256':'a'*64},'cpoSummary':{}}
        (p/'manifest.json').write_text(json.dumps(m));return rows
    def test_no_price_selected_and_lossless_originals(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);rows=self.fixture(p);before=(p/'tile.json.gz').read_bytes();isolate(p);m=json.loads((p/'manifest.json').read_bytes());verify(p,m)
            self.assertEqual(json.loads(gzip.decompress((p/'tile.json.gz').read_bytes()))['emspOffers'],[rows[1]])
            self.assertEqual((p/'unvalidated-original/tile.json.gz').read_bytes(),before)
            self.assertEqual(m['quarantine']['withheldRows'],2);self.assertEqual(m['stats']['publishedOffers'],1)
            isolate(p);verify(p,json.loads((p/'manifest.json').read_bytes()))
            # Even with a rewritten current SHA, changing a surviving price is
            # rejected against the preserved original input.
            payload=json.loads(gzip.decompress((p/'tile.json.gz').read_bytes()));payload['emspOffers'][0]['pricing']['rate']=99
            (p/'tile.json.gz').write_bytes(gzip.compress(json.dumps(payload).encode()))
            with self.assertRaisesRegex(ValueError,'altered non-conflicting'):verify(p,m)
    def test_corrupt_original_and_ledger_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.fixture(p);isolate(p);m=json.loads((p/'manifest.json').read_bytes());(p/'unvalidated-original/tile.json.gz').write_bytes(b'broken')
            with self.assertRaisesRegex(ValueError,'original tile integrity'):verify(p,m)

if __name__=='__main__':unittest.main()

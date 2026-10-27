"""Testes sinteticos de retomada; nao sao resultados do CirCor."""
import json
import tempfile
from pathlib import Path
import unittest
from pcg.board_test import Journal, exclusive_run, finalize, expected_windows
from pcg.board import transact
from pcg.metrics import aggregate, binary_metrics

def tempdir():
    base=Path(__file__).resolve().parents[1]/'work/tests'
    base.mkdir(parents=True,exist_ok=True)
    return tempfile.TemporaryDirectory(prefix='software-resume-only-',dir=base)

def windows():
    return [{'patient_id':p,'recording_id':r,'label':label,'start':start,'original_host_probability':value}
        for p,r,label,start,value in [('A','AV',0,0,.25),('A','AV',0,6000,.5),('A','MV',0,0,.75),('B','AV',1,0,.5),('B','AV',1,6000,.75)]]

def observation(i,w):
    return {'segment':'SYNTHETIC_TEST_ONLY','reference_probability':w['original_host_probability'],
        'original_host_probability':w['original_host_probability'],'input_crc_matches_host':True,
        'response':{'type':'result','seq':i+1,'prob_present':w['original_host_probability'],
            'preprocessing_us':10,'inference_us':5,'processing_us':15,'feature_crc32':42}}

class ResumeTests(unittest.TestCase):
    def test_interrupted_write_resumes_exact_prefix_and_same_metrics(self):
        ws=windows(); protocol={'protocol_id':'a'*64}
        with tempdir() as tmp:
            out=Path(tmp); j=Journal(out,protocol,ws)
            for i in range(3): j.append(observation(i,ws[i]))
            prefix=(out/'predictions.jsonl').read_bytes()
            with (out/'predictions.jsonl').open('ab') as f: f.write(b'{"index":3,"interrupted":')
            resumed=Journal(out,protocol,ws)
            self.assertEqual(len(resumed.rows),3)
            self.assertEqual((out/'predictions.jsonl').read_bytes(),prefix)
            self.assertEqual(len(list(out.glob('partial-tail-*.bin'))),1)
            for i in range(3,5): resumed.append(observation(i,ws[i]))
            reopened=Journal(out,protocol,ws)
            self.assertEqual(len(reopened.rows),5)
            ids,y,p=aggregate([r['response']['prob_present'] for r in reopened.rows],ws)
            m=binary_metrics(y,p,.5)
            self.assertEqual(ids,['A','B'])
            self.assertEqual((m['tp'],m['tn'],m['fp'],m['fn']),(1,0,1,0))
            self.assertAlmostEqual(m['f1'],2/3)
            self.assertEqual(m['accuracy'],.5)
    def test_altered_saved_probability_is_rejected(self):
        ws=windows()
        with tempdir() as tmp:
            out=Path(tmp); j=Journal(out,{'protocol_id':'a'*64},ws); j.append(observation(0,ws[0]))
            row=json.loads((out/'predictions.jsonl').read_text()); row['response']['prob_present']=.5
            (out/'predictions.jsonl').write_text(json.dumps(row)+'\n')
            with self.assertRaisesRegex(ValueError,'hash'): Journal(out,{'protocol_id':'a'*64},ws)
    def test_other_protocol_or_different_window_cannot_resume(self):
        ws=windows()
        with tempdir() as tmp:
            out=Path(tmp); j=Journal(out,{'protocol_id':'a'*64},ws); j.append(observation(0,ws[0]))
            with self.assertRaises(ValueError): Journal(out,{'protocol_id':'b'*64},ws)
            changed=[dict(w) for w in ws]; changed[0]['start']=6000
            with self.assertRaisesRegex(ValueError,'Janela'): Journal(out,{'protocol_id':'a'*64},changed)
    def test_no_final_metrics_for_incomplete_collection(self):
        ws=windows()
        with tempdir() as tmp:
            out=Path(tmp); j=Journal(out,{'protocol_id':'a'*64},ws); j.append(observation(0,ws[0]))
            with self.assertRaisesRegex(ValueError,'incompleta'): finalize(out,j.protocol,ws,j)
            self.assertFalse((out/'reports').exists())
    def test_two_collectors_cannot_share_output(self):
        with tempdir() as tmp:
            with exclusive_run(tmp):
                with self.assertRaises(RuntimeError):
                    with exclusive_run(tmp): pass
            with exclusive_run(tmp): pass
    def test_all_windows_include_padding_and_last_complete_window(self):
        c={'patient_id':'A','encounter_id':'A','label':0,'split':'test','path':'a.wav'}
        rows=[c|{'recording_id':'short','samples':4000},c|{'recording_id':'long','samples':25000}]
        expected=list(expected_windows(rows,{'window_samples':12000,'hop_samples':6000}))
        self.assertEqual([(r['recording_id'],r['start']) for r in expected],[('short',0),('long',0),('long',6000),('long',12000)])
    def test_response_ack_does_not_require_windows_flush(self):
        class Port:
            def write(self,data): return len(data)
            def flush(self): raise AssertionError('FlushFileBuffers nao deve ser chamado')
            def readline(self): return b'{"type":"result","seq":7}\n'
        self.assertEqual(transact(Port(),7,1,b'abc',flush_output=False)['seq'],7)
    def test_partial_usb_write_is_rejected(self):
        class Port:
            def write(self,data): return len(data)-1
        with self.assertRaisesRegex(TimeoutError,'parcialmente'): transact(Port(),1,1,b'abc',flush_output=False)

    def test_complete_reports_after_resume_use_all_patients_and_preserve_host(self):
        ws=windows()
        with tempdir() as tmp:
            base=Path(tmp); out=base/'SYNTHETIC_SOFTWARE_ONLY'; out.mkdir()
            host=base/'original-host'; (host/'reports').mkdir(parents=True)
            ids,y,p=aggregate([w['original_host_probability'] for w in ws],ws)
            frozen=binary_metrics(y,p,.5)
            original_file=host/'reports/int8_host_metrics.json'
            original_file.write_text(json.dumps(frozen))
            original_bytes=original_file.read_bytes()
            protocol={'protocol_id':'a'*64,'task':'software_test_only','patients':2,
                'threshold':.5,'config':{'bootstrap_replicates':30,'bootstrap_seed':2026},
                'model_dir':str(host),'latency_scope':'SYNTHETIC_SOFTWARE_ONLY',
                'model_sha256':'SYNTHETIC_NOT_A_REAL_MODEL'}
            journal=Journal(out,protocol,ws)
            for i in range(2): journal.append(observation(i,ws[i]))
            resumed=Journal(out,protocol,ws)
            for i in range(2,len(ws)): resumed.append(observation(i,ws[i]))
            result=finalize(out,protocol,ws,resumed)
            self.assertEqual(result['patients'],2)
            self.assertAlmostEqual(result['f1'],2/3)
            self.assertEqual(original_file.read_bytes(),original_bytes)
            receipt=json.loads((out/'session.json').read_text())
            self.assertEqual(receipt['kind'],'software_validation_only')
            self.assertEqual(receipt['completed_windows'],5)
            self.assertIn('reports/int8_rp2040_metrics.json',receipt['artifact_hashes'])

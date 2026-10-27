"""Teste completo no RP2040: protocolo congelado e diario duravel por janela.
Nao treina, nao seleciona limiar e nao interrompe o teste por discordancia de
classificacao. Diferencas numericas no teste sao resultados, nao criterio de ajuste.
"""
import binascii
import contextlib
import csv
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import shutil
import time
from datetime import datetime, timezone
import numpy as np
from .common import ROOT, read_json, write_json, write_csv, sha256, object_hash, provenance
from .data import audit_disjoint
from .features import load_audio, extract, quantize
from .learning import verify_export, lite_probabilities
from .metrics import aggregate, binary_metrics, write_report
from .board import packet, transact


def utc():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path=Path(path)
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('w',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
        f.flush(); os.fsync(f.fileno())
    os.replace(temporary,path)


@contextlib.contextmanager
def exclusive_run(out):
    """Trava liberada pelo sistema inclusive se o processo morrer."""
    path=Path(out)/'process.lock'
    with path.open('a+b') as f:
        if f.tell()==0: f.write(b'0'); f.flush()
        f.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('Outra avaliacao ja esta usando esta pasta. Nao abra duas janelas.') from error
        try: yield
        finally:
            f.seek(0)
            if os.name=='nt': msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(f,fcntl.LOCK_UN)


def source_files():
    files=list((ROOT/'pcg').glob('*.py'))+[ROOT/'scripts/evaluate-test-usb.py']
    return {p.relative_to(ROOT).as_posix():sha256(p) for p in sorted(files)}


def read_normalization(model):
    header=(model/'generated/frontend_config.h').read_text(encoding='utf-8')
    arrays=[]
    for key in ('kMean','kStd'):
        m=re.search(r'\b'+key+r'\[24\]\s*=\s*\{([^}]+)\}',header)
        if not m: raise ValueError('Normalizacao congelada ausente')
        v=np.array([float(x.strip().removesuffix('f')) for x in m[1].split(',')],np.float32)
        if v.shape!=(24,) or not np.isfinite(v).all(): raise ValueError('Normalizacao invalida')
        arrays.append(v)
    if (arrays[1]<=0).any(): raise ValueError('Desvio padrao invalido')
    return arrays


def expected_windows(recordings, c):
    for r in recordings:
        for start in range(0,max(c['window_samples'],r['samples'])-c['window_samples']+1,c['hop_samples']):
            yield {k:r[k] for k in ('patient_id','encounter_id','recording_id','label','split','path')}|{'start':start}


def prepare(model, data_root, benchmark, out):
    model,data_root,benchmark,out=map(lambda p:Path(p).resolve(),(model,data_root,benchmark,out))
    ex=verify_export(model)
    original=read_json(model/'evaluation_receipt.json')
    if original['status']!='complete' or original['export_sha256']!=sha256(model/'export.json'):
        raise ValueError('Teste host/exportacao congelados nao estao completos ou foram alterados')
    for name,digest in original['report_hashes'].items():
        if sha256(model/'reports'/name)!=digest: raise ValueError(f'Relatorio original alterado: {name}')
    training=read_json(model/'training.json'); c=training['config']
    manifest_path=model.parent/'split-manifest.json'; manifest=read_json(manifest_path)
    audit_disjoint(manifest['recordings'])
    if manifest['config']!=c or object_hash(c)!=original['config_hash']:
        raise ValueError('Configuracao diferente da avaliacao host congelada')
    records=[r for r in manifest['recordings'] if r['split']=='test']
    if not records: raise ValueError('Sem gravacoes de teste')
    # Checa os WAVs de teste e validacao antes de abrir a porta serial.
    checked={}
    for r in manifest['recordings']:
        if r['split'] not in ('validation','test'): continue
        rel=Path(r['path']); path=(data_root/rel).resolve()
        if rel.is_absolute() or not path.is_relative_to(data_root): raise ValueError('Caminho de audio fora da base')
        if r['path'] in checked: raise ValueError('Caminho duplicado no manifesto')
        if sha256(path)!=r['sha256']: raise ValueError(f'WAV alterado: {path}')
        import wave
        with wave.open(str(path),'rb') as f:
            if (f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getnframes())!=(1,2,c['sample_rate'],r['samples']):
                raise ValueError(f'Formato/duracao do WAV diferente do manifesto: {path}')
        checked[r['path']]=r['sha256']
    with (model/'reports/test_windows.csv').open(encoding='utf-8',newline='') as f:
        rows=list(csv.DictReader(f))
    windows=[]
    for row in rows:
        w={k:row[k] for k in ('patient_id','encounter_id','recording_id','split','path')}
        w.update(start=int(row['start']),label=int(row['label']),original_host_probability=float(row['int8_probability']))
        if not math.isfinite(w['original_host_probability']) or not 0<=w['original_host_probability']<=1:
            raise ValueError('Probabilidade original invalida')
        windows.append(w)
    observed=[{k:v for k,v in w.items() if k!='original_host_probability'} for w in windows]
    if observed!=list(expected_windows(records,c)):
        raise ValueError('Lista original nao cobre exatamente todas as janelas do teste congelado')
    labels={r['patient_id']:r['label'] for r in records}
    metrics=read_json(model/'reports/int8_host_metrics.json')
    if (len(labels),sum(labels.values()))!=(metrics['patients'],metrics['support_present']):
        raise ValueError('Coorte diferente do teste host')
    prior=read_json(benchmark/'session.json')
    if prior['status']!='complete' or prior['model_sha256']!=ex['model_sha256']:
        raise ValueError('Benchmark real de validacao ausente ou com modelo diferente')
    for name,digest in prior['artifact_hashes'].items():
        if sha256(benchmark/name)!=digest: raise ValueError('Benchmark anterior alterado')
    parity=read_json(benchmark/'parity.json')
    if not parity['passed'] or 'BUILTIN_REF' not in parity['acceptance']:
        raise ValueError('Benchmark anterior sem paridade de referencia aprovada')
    runtime={name:importlib.metadata.version(name) for name in ('numpy','ai-edge-litert','pyserial')}
    frozen={'version':1,'task':'full_frozen_test_on_rp2040','model_dir':str(model),'data_root':str(data_root),
        'benchmark_dir':str(benchmark),'model_sha256':ex['model_sha256'],'export_sha256':sha256(model/'export.json'),
        'evaluation_receipt_sha256':sha256(model/'evaluation_receipt.json'),
        'test_windows_sha256':sha256(model/'reports/test_windows.csv'),'manifest_sha256':sha256(manifest_path),
        'benchmark_session_sha256':sha256(benchmark/'session.json'),'threshold':ex['threshold'],
        'config':c,'windows':len(windows),'recordings':len(records),'patients':len(labels),
        'present_patients':sum(labels.values()),'absent_patients':len(labels)-sum(labels.values()),
        'plan_hash':object_hash(windows),'source_hashes':source_files(),'runtime':runtime,
        'reference_resolver':'BUILTIN_REF','original_host_comparison':'saved original AUTO/XNNPACK probabilities',
        'aggregation':'mean windows per recording; maximum recording score per patient',
        'validation_gate':'5 recordings per class; input <=1 step, output vs reference <=2 steps',
        'test_disagreements':'record all; do not filter samples, tune model or threshold, or loosen validation gate',
        'test_input_diagnostic':'CRC32 of all quantized features compared; mismatch is reported, not used to tune',
        'latency_scope':'MFE and Invoke only, excludes acquisition/USB/CRC/display'}
    protocol=frozen|{'protocol_id':object_hash(frozen)}
    if (out/'protocol.json').exists():
        if read_json(out/'protocol.json')!=protocol or read_json(out/'plan.json')!=windows:
            raise ValueError('Protocolo, fontes, runtime ou dados mudaram. Nao e permitido misturar resultados.')
    else:
        if out.exists() and any(out.iterdir()): raise FileExistsError('Pasta de saida ja contem outros arquivos')
        out.mkdir(parents=True,exist_ok=True)
        write_json(out/'plan.json',windows)
        write_json(out/'protocol.json',protocol)
        for name,digest in protocol['source_hashes'].items():
            dest=out/'source'/name; dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/name,dest)
            if sha256(dest)!=digest: raise ValueError('Copia dos fontes nao confere')
        write_json(out/'source/config.json',c)
        atomic_json(out/'session.json',{'status':'prepared_hardware_not_started','completed_windows':0,
            'total_windows':len(windows),'protocol_id':protocol['protocol_id'],'updated_utc':utc()})
    return protocol,windows,manifest,ex


class Journal:
    """Append + fsync; prefixo continuo e hash encadeado vinculados ao protocolo."""
    def __init__(self,out,protocol,windows):
        self.out=Path(out); self.path=self.out/'predictions.jsonl'
        self.protocol=protocol; self.windows=windows; self.rows=[]; self.chain=protocol['protocol_id']
        if self.path.exists():
            with self.path.open('rb+') as f:
                while True:
                    begin=f.tell(); line=f.readline()
                    if not line: break
                    if not line.endswith(b'\n'):
                        # Apenas a ultima escrita incompleta e descartada; preserva os bytes para auditoria.
                        tail=self.out/('partial-tail-'+str(time.time_ns())+'.bin')
                        tail.write_bytes(line)
                        f.seek(begin); f.truncate(); f.flush(); os.fsync(f.fileno())
                        break
                    row=json.loads(line)
                    digest=row.pop('record_hash')
                    self.validate(row)
                    if object_hash(row)!=digest: raise ValueError('Diario alterado: hash de previsao invalido')
                    row['record_hash']=digest; self.rows.append(row); self.chain=digest
    def validate(self,row):
        i=len(self.rows)
        if i>=len(self.windows) or row['index']!=i or row['previous_hash']!=self.chain:
            raise ValueError('Diario sem prefixo continuo ou vinculo de hash')
        if row['window_hash']!=object_hash(self.windows[i]): raise ValueError('Janela diferente do plano congelado')
        validate_result(row['response'])
        for key in ('reference_probability','original_host_probability'):
            if not math.isfinite(row[key]) or not 0<=row[key]<=1: raise ValueError('Probabilidade invalida no diario')
        if row['original_host_probability']!=self.windows[i]['original_host_probability']:
            raise ValueError('Comparacao original alterada no diario')
    def append(self,record):
        row=record|{'index':len(self.rows),'previous_hash':self.chain,
            'window_hash':object_hash(self.windows[len(self.rows)])}
        self.validate(row)
        row['record_hash']=object_hash(row)
        with self.path.open('ab') as f:
            f.write((json.dumps(row,separators=(',',':'),allow_nan=False)+'\n').encode('utf-8'))
            f.flush(); os.fsync(f.fileno())
        self.rows.append(row); self.chain=row['record_hash']
        return row


def synchronize(port):
    # Recupera a fronteira dos pacotes apos uma interrupcao no meio do PCM.
    # O firmware abandona leituras incompletas em 30 s. Apenas HELLO e repetido;
    # previsoes de teste nunca sao descartadas por seu valor.
    deadline=time.monotonic()+45; next_send=0; buffer=bytearray()
    port.timeout=0.2
    try:
        while time.monotonic()<deadline:
            if time.monotonic()>=next_send:
                port.write(packet(0,0)); next_send=time.monotonic()+2
            buffer.extend(port.read(max(1,min(port.in_waiting,4096))))
            while b'\n' in buffer:
                line,_,rest=buffer.partition(b'\n'); buffer=bytearray(rest)
                try: response=json.loads(line)
                except (ValueError,UnicodeDecodeError): continue
                if isinstance(response,dict) and response.get('type')=='hello' and response.get('seq')==0:
                    return response
            if len(buffer)>65536: buffer.clear()
        raise TimeoutError('Sem HELLO da placa. Reconecte o USB sem BOOTSEL e retome pelo mesmo iniciador.')
    finally: port.timeout=60


def validate_result(result):
    if result.get('type')!='result': raise ValueError('Resposta nao e inferencia')
    p=result.get('prob_present')
    if not isinstance(p,(float,int)) or not math.isfinite(p) or not 0<=p<=255/256:
        raise ValueError('Probabilidade da placa invalida')
    if abs(p*256-round(p*256))>1e-6: raise ValueError('Saida fora da grade INT8')
    for key in ('preprocessing_us','inference_us','processing_us','feature_crc32'):
        if type(result.get(key)) is not int or result[key]<0: raise ValueError('Campo invalido da placa: '+key)
    if result['feature_crc32']>0xffffffff: raise ValueError('CRC fora de 32 bits')
    if type(result.get('seq')) is not int or result['seq']<1: raise ValueError('Sequencia USB invalida')
    if result['processing_us']!=result['preprocessing_us']+result['inference_us']:
        raise ValueError('Soma dos tempos nao confere')


def finalize(out,protocol,windows,journal):
    if len(journal.rows)!=len(windows): raise ValueError('Coleta incompleta; metricas finais nao liberadas')
    if protocol.get('task')=='full_frozen_test_on_rp2040':
        model=Path(protocol['model_dir'])
        verify_export(model)
        if sha256(model/'export.json')!=protocol['export_sha256'] or sha256(model/'evaluation_receipt.json')!=protocol['evaluation_receipt_sha256']:
            raise ValueError('Artefato original alterado durante a coleta')
        original_receipt=read_json(model/'evaluation_receipt.json')
        for name,digest in original_receipt['report_hashes'].items():
            if sha256(model/'reports'/name)!=digest: raise ValueError('Relatorio original alterado durante coleta')
        if read_json(Path(out)/'protocol.json')!=protocol or object_hash(read_json(Path(out)/'plan.json'))!=protocol['plan_hash']:
            raise ValueError('Plano/protocolo alterado durante coleta')
    scores=np.array([r['response']['prob_present'] for r in journal.rows])
    reference=np.array([r['reference_probability'] for r in journal.rows])
    old=np.array([w['original_host_probability'] for w in windows])
    ids,y,p=aggregate(scores,windows)
    _,yr,pr=aggregate(reference,windows); _,yo,po=aggregate(old,windows)
    if len(ids)!=protocol['patients'] or not np.array_equal(y,yr) or not np.array_equal(y,yo):
        raise ValueError('Agregacao incompleta ou rotulos divergentes')
    reports=Path(out)/'reports'; reports.mkdir(exist_ok=True)
    board_metrics=write_report(reports,'int8_rp2040',ids,y,p,protocol['threshold'],protocol['config'])
    ref_metrics=write_report(reports,'int8_reference_host',ids,y,pr,protocol['threshold'],protocol['config'])
    original_metrics=binary_metrics(y,po,protocol['threshold'])
    frozen=read_json(Path(protocol['model_dir'])/'reports/int8_host_metrics.json')
    for key,value in original_metrics.items():
        if key not in ('undefined_metrics',) and value!=frozen[key]:
            raise ValueError('Recalculo das previsoes originais difere do relatorio congelado: '+key)
    comparison={'threshold_unchanged':protocol['threshold'],'patients':len(ids),'windows':len(windows),
        'rp2040':board_metrics,'reference_host':ref_metrics,'original_host_saved':original_metrics,
        'board_reference_patient_prediction_agreement':float(np.mean((p>=protocol['threshold'])==(pr>=protocol['threshold']))),
        'board_original_host_patient_prediction_agreement':float(np.mean((p>=protocol['threshold'])==(po>=protocol['threshold']))),
        'max_board_reference_window_probability_difference':float(np.max(np.abs(scores-reference))),
        'max_board_original_host_window_probability_difference':float(np.max(np.abs(scores-old))),
        'input_crc_mismatch_windows':sum(not r['input_crc_matches_host'] for r in journal.rows),
        'note':'Original host AUTO/XNNPACK metrics remain unchanged. All test windows included; no tuning on disagreements.'}
    write_json(reports/'runtime_comparison.json',comparison)
    write_csv(reports/'test_windows.csv',[w|{'board_probability':r['response']['prob_present'],
        'reference_probability':r['reference_probability'],'input_crc_matches_host':r['input_crc_matches_host'],
        'preprocessing_us':r['response']['preprocessing_us'],'inference_us':r['response']['inference_us'],
        'processing_us':r['response']['processing_us']} for w,r in zip(windows,journal.rows)])
    write_csv(reports/'runtime_patients.csv',[{'patient_id':pid,'label':int(t),'board_probability':float(b),
        'reference_probability':float(r),'original_host_probability':float(o)} for pid,t,b,r,o in zip(ids,y,p,pr,po)])
    write_json(reports/'test_timing_summary.json',{'windows':len(windows),'units':'microseconds',
        'scope':protocol['latency_scope'],'timings':{key:dict(zip(('median','p95','maximum'),np.percentile(
        [r['response'][key] for r in journal.rows],[50,95,100]).tolist())) for key in ('preprocessing_us','inference_us','processing_us')}})
    atomic_json(Path(out)/'session.json',{'status':'complete','kind':('real_board_full_frozen_test' if protocol.get('task')=='full_frozen_test_on_rp2040' else 'software_validation_only'),
        'completed_windows':len(windows),'total_windows':len(windows),'protocol_id':protocol['protocol_id'],
        'journal_last_hash':journal.chain,'model_sha256':protocol['model_sha256'],'updated_utc':utc(),
        'artifact_hashes':{f.relative_to(out).as_posix():sha256(f) for f in sorted(Path(out).rglob('*'))
            if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc' and f.name not in ('session.json','process.lock') and not f.name.endswith('.tmp')}})
    return board_metrics


def run(model,data_root,benchmark,out,port_name='auto',prepare_only=False):
    protocol,windows,manifest,ex=prepare(model,data_root,benchmark,out)
    out=Path(out).resolve()
    print(f"Teste congelado: {len(windows)} janelas, {protocol['recordings']} gravacoes, {protocol['patients']} pacientes. Limiar {ex['threshold']:.12f}.",flush=True)
    if prepare_only:
        print('Plano e fontes preservados. Hardware ainda nao executado neste teste completo.'); return
    if read_json(out/'session.json')['status']=='complete':
        for name,digest in read_json(out/'session.json')['artifact_hashes'].items():
            if sha256(out/name)!=digest: raise ValueError('Artefato final alterado: '+name)
        print(f'Teste ja concluido e hashes conferidos, nao sera reexecutado: {out}'); return
    import serial
    from serial.tools.list_ports import comports
    from ai_edge_litert.interpreter import Interpreter,OpResolverType
    with exclusive_run(out):
        journal=Journal(out,protocol,windows)
        start_count=len(journal.rows); started=time.monotonic(); segment=str(time.time_ns())
        def status(state,error=None):
            done=len(journal.rows); elapsed=time.monotonic()-started
            eta=((len(windows)-done)*elapsed/(done-start_count)) if done>start_count else None
            atomic_json(out/'session.json',{'status':state,'kind':'real_board_full_frozen_test',
                'completed_windows':done,'total_windows':len(windows),'protocol_id':protocol['protocol_id'],
                'model_sha256':ex['model_sha256'],'journal_last_hash':journal.chain,'updated_utc':utc(),
                'segment':segment,'remaining_seconds_estimate':eta,'error':error})
        if start_count==len(windows):
            finalize(out,protocol,windows,journal); print(f'Relatorios finais prontos: {out}'); return
        status('starting_or_resuming')
        # Inibicao de suspensao somente enquanto este processo executa; nao muda o plano de energia.
        power=None
        try:
            if os.name=='nt':
                import ctypes
                power=ctypes.windll.kernel32.SetThreadExecutionState
                power.argtypes=[ctypes.c_uint32]; power.restype=ctypes.c_uint32
                power(0x80000001)
            reference=Interpreter(model_path=str(Path(model)/'model_int8.tflite'),num_threads=1,
                experimental_op_resolver_type=OpResolverType.BUILTIN_REF)
            reference.allocate_tensors()
            mean,std=read_normalization(Path(model))
            cache={}; records={r['path']:r for r in manifest['recordings']}
            def payload(w):
                if w['path'] not in cache:
                    path=Path(data_root)/w['path']
                    if sha256(path)!=records[w['path']]['sha256']: raise ValueError('WAV alterado durante coleta')
                    x=load_audio(path,protocol['config']['sample_rate'])
                    cache.clear(); cache[w['path']]=np.pad(x,(0,max(0,12000-len(x))))
                x=cache[w['path']][w['start']:w['start']+12000]
                if x.shape!=(12000,): raise ValueError('Janela incompleta')
                pcm=np.clip(np.rint(x*32768),-32768,32767).astype('<i2')
                return pcm.tobytes(),pcm.astype(np.float32)/32768
            if port_name=='auto':
                ports=[p for p in comports() if p.vid==0x2e8a and p.pid==0x000a]
                if len(ports)!=1: raise RuntimeError('Esperada uma unica porta USB Pico. Reconecte sem BOOTSEL e tente novamente.')
                port_name=ports[0].device
            with serial.Serial(port_name,115200,timeout=60,write_timeout=60) as port:
                port.dtr=True; port.reset_input_buffer(); seq=0
                def call(mode,raw=b''):
                    nonlocal seq
                    seq+=1
                    result=transact(port,seq,mode,raw,flush_output=False)
                    if mode==1: validate_result(result)
                    return result
                hello=synchronize(port)
                if not hello.get('ready') or hello.get('model_sha256')!=ex['model_sha256'] or hello.get('clock_hz')!=133000000:
                    raise ValueError('Placa sem modelo correto pronto a 133 MHz')
                write_json(out/f'board-{segment}.json',hello|{'port':port_name,'resume_after_windows':start_count})
                vals=[r for r in manifest['recordings'] if r['split']=='validation']
                rng=np.random.default_rng(2026); vals=[vals[int(i)] for i in rng.permutation(len(vals))]
                gate=[r|{'start':0} for label in (0,1) for r in [v for v in vals if v['label']==label][:5]]
                if len(gate)!=10: raise ValueError('Validacao de paridade incompleta')
                entries=[]
                for w in gate:
                    raw,pcm=payload(w)
                    f=((extract(pcm,protocol['config'])-mean)/std)[...,None]
                    q=quantize(f,ex['input_scale'],ex['input_zero_point']).ravel()
                    _,observed=call(2,raw); result=call(1,raw)
                    expected=float(lite_probabilities(reference,f[None])[0])
                    entries.append({'recording_id':w['recording_id'],'split':'validation',
                        'max_feature_difference':int(np.max(np.abs(q.astype(int)-observed.astype(int)))),
                        'probability_difference':abs(expected-result['prob_present'])})
                passed=all(r['max_feature_difference']<=1 and r['probability_difference']<=2*ex['output_scale']+1e-7 for r in entries)
                write_json(out/f'validation-{segment}.json',{'passed':passed,'reference':'BUILTIN_REF','entries':entries})
                if not passed: raise ValueError('Paridade de VALIDACAO falhou; nenhuma janela nova de teste foi adicionada')
                for w in gate: call(1,payload(w)[0])  # Warmups de validacao; fora do teste.
                started=time.monotonic()
                status('running')
                print(f'Retomando na janela {start_count+1}/{len(windows)}. Cada resposta sera salva imediatamente.',flush=True)
                for i in range(start_count,len(windows)):
                    w=windows[i]; raw,pcm=payload(w)
                    feature=((extract(pcm,protocol['config'])-mean)/std)[...,None]
                    q=quantize(feature,ex['input_scale'],ex['input_zero_point'])
                    expected=float(lite_probabilities(reference,feature[None])[0])
                    crc=binascii.crc32(q.tobytes())&0xffffffff
                    result=call(1,raw)
                    journal.append({'segment':segment,'received_utc':utc(),'payload_sha256':__import__('hashlib').sha256(raw).hexdigest(),
                        'expected_feature_crc32':crc,'input_crc_matches_host':crc==result['feature_crc32'],
                        'reference_probability':expected,'original_host_probability':w['original_host_probability'],
                        'response':result})
                    status('running')
                    if (i+1)%25==0 or i+1==len(windows):
                        remaining=(len(windows)-i-1)*(time.monotonic()-started)/(i+1-start_count)
                        print(f'Teste na placa: {i+1}/{len(windows)}; faltam aproximadamente {remaining/60:.0f} min.',flush=True)
            metrics=finalize(out,protocol,windows,journal)
            print(f"TESTE COMPLETO NA BITDOGLAB: F1={metrics['f1']:.4f}, recall={metrics['recall']:.4f}, accuracy={metrics['accuracy']:.4f}.",flush=True)
            print(f'Relatorios e matriz de confusao: {out}/reports',flush=True)
        except BaseException as error:
            status('interrupted' if isinstance(error,KeyboardInterrupt) else 'failed_resumable',str(error))
            print(f'Progresso preservado: {len(journal.rows)}/{len(windows)}. Abra o mesmo iniciador para retomar.',flush=True)
            raise
        finally:
            if power is not None: power(0x80000000)

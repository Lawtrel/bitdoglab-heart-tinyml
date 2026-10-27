"""Benchmark USB independente do treino: somente validacao e modelo congelado.
Nao calcula F1 de teste; nao treina nem modifica o run. Requer NumPy, pyserial
 e ai-edge-litert. O microfone e OLED nao participam deste protocolo digital.
"""
import argparse
import importlib.metadata
import json
import re
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pcg.common import read_json, write_json, write_csv, sha256, fresh_directory, provenance
from pcg.learning import verify_export, lite_probabilities
from pcg.features import load_audio, extract, quantize
from pcg.board import transact


def normalization(header):
    values=[]
    for name in ('kMean','kStd'):
        match=re.search(r'\b'+name+r'\[24\]\s*=\s*\{([^}]+)\}',header)
        if not match: raise ValueError(f'Coeficientes ausentes: {name}')
        row=np.array([float(v.strip().removesuffix('f')) for v in match[1].split(',')],np.float32)
        if row.shape!=(24,) or not np.isfinite(row).all(): raise ValueError('Normalizacao invalida')
        values.append(row)
    if np.any(values[1]<=0): raise ValueError('Desvio padrao invalido')
    return values


def choose_rows(manifest, count):
    # Ordem definida antes de acessar resultados; usa exclusivamente validacao.
    rows=[r for r in manifest['recordings'] if r['split']=='validation']
    rng=np.random.default_rng(2026)
    selected=[rows[int(i)] for i in rng.permutation(len(rows))]
    if not selected: raise ValueError('Sem validacao')
    parity=[]
    for label in (0,1):
        parity.extend([r for r in selected if r['label']==label][:5])
    if len(parity)!=10: raise ValueError('Paridade requer 5 gravacoes por classe')
    return parity,[selected[i%len(selected)] for i in range(count)]


def main():
    import serial
    from serial.tools.list_ports import comports
    from ai_edge_litert.interpreter import Interpreter, OpResolverType
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True,help='Pasta model/ exportada')
    p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--port',default='auto')
    p.add_argument('--windows',type=int,default=100)
    p.add_argument('--prepare-only',action='store_true',help='Verifica os insumos sem USB; nao e validacao de hardware')
    a=p.parse_args()
    if a.windows<100: p.error('Use pelo menos 100 janelas')
    ex=verify_export(a.run)
    training=read_json(a.run/'training.json')
    manifest_path=a.run.parent/'split-manifest.json'
    manifest=read_json(manifest_path)
    c=training['config']
    mean,std=normalization((a.run/'generated/frontend_config.h').read_text())
    # CMSIS-NN segue os kernels inteiros de referencia. AUTO ativa XNNPACK,
    # cuja requantizacao pode diferir. Preserve ambos para auditoria.
    interpreter=Interpreter(model_path=str(a.run/'model_int8.tflite'),num_threads=1,
        experimental_op_resolver_type=OpResolverType.BUILTIN_REF)
    optimized=Interpreter(model_path=str(a.run/'model_int8.tflite'),num_threads=1)
    optimized.allocate_tensors()
    interpreter.allocate_tensors()
    inp=interpreter.get_input_details()[0]
    out_tensor=interpreter.get_output_details()[0]
    if tuple(inp['shape'])!=(1,186,24,1) or inp['dtype']!=np.int8 or out_tensor['dtype']!=np.int8:
        raise ValueError('Interface INT8 diferente do firmware')
    if tuple(inp['quantization'])!=(ex['input_scale'],ex['input_zero_point']):
        raise ValueError('Escala de entrada diferente da exportacao')
    if tuple(out_tensor['quantization'])!=(ex['output_scale'],ex['output_zero_point']):
        raise ValueError('Escala de saida diferente da exportacao')
    parity_rows,timing_rows=choose_rows(manifest,a.windows)
    cache={}
    def payload(row):
        # Tambem verifica o WAV escolhido contra o manifesto congelado.
        rel=Path(row['path'])
        if rel.is_absolute() or '..' in rel.parts: raise ValueError('Caminho invalido no manifesto')
        if row['path'] not in cache:
            path=a.data_root/rel
            if sha256(path)!=row['sha256']: raise ValueError(f'WAV alterado: {path}')
            pcm=load_audio(path,c['sample_rate'])
            pcm=np.pad(pcm,(0,max(0,c['window_samples']-len(pcm))))[:c['window_samples']]
            cache[row['path']]=np.clip(np.rint(pcm*32768),-32768,32767).astype('<i2')
        pcm=cache[row['path']]
        return pcm.tobytes(),pcm.astype(np.float32)/32768
    prepared=[]
    for row in parity_rows:
        raw,pcm=payload(row)
        feature=((extract(pcm,c)-mean)/std)[...,None]
        expected=quantize(feature,ex['input_scale'],ex['input_zero_point']).ravel()
        probability=float(lite_probabilities(interpreter,feature[None])[0])
        optimized_probability=float(lite_probabilities(optimized,feature[None])[0])
        prepared.append((row,raw,expected,probability,optimized_probability))
    for row in timing_rows: payload(row)
    metadata={'kind':'real_board_validation_only','model_sha256':ex['model_sha256'],
        'export_sha256':sha256(a.run/'export.json'),'manifest_sha256':sha256(manifest_path),
        'script_sha256':sha256(__file__),'windows':a.windows,'clock_required_hz':133000000,
        'selection':'validation recordings shuffled with NumPy default_rng(2026); first 3 seconds, padded if short',
        'host_runtime':{'name':'ai-edge-litert','version':importlib.metadata.version('ai-edge-litert'),
            'parity_resolver':'BUILTIN_REF','secondary_diagnostic_resolver':'AUTO (XNNPACK)'},
        'protocol_revision':{'reason':'Observed exact features and board agreement with reference kernels; AUTO differed up to 4 output steps on validation.',
            'previous_reference':'AUTO (XNNPACK)','weights_thresholds_and_tolerances_unchanged':True},
        'provenance':provenance(),'measured_scope':'MFE and inference only; excludes acquisition, USB, CRC and display'}
    if a.prepare_only:
        write_json(a.out,metadata|{'status':'host_inputs_checked_hardware_not_executed',
            'verified_wavs':len(cache),'parity_host_probabilities':[v[3] for v in prepared]})
        print('Insumos verificados; nenhuma metrica da placa coletada.')
        return
    port_name=a.port
    if port_name=='auto':
        ports=[q for q in comports() if q.vid==0x2e8a and q.pid==0x000a]
        if len(ports)!=1:
            raise ValueError('Selecao automatica exige uma unica porta Pico SDK (VID 2E8A PID 000A). Use --port COMx somente apos identificar a placa.')
        port_name=ports[0].device
    dest=fresh_directory(a.out)
    write_json(dest/'session.json',metadata|{'status':'started','port':port_name})
    try:
        with serial.Serial(port_name,115200,timeout=60,write_timeout=60) as port, (dest/'usb_log.jsonl').open('w',encoding='utf-8') as log:
            seq=0
            def call(mode,raw=b''):
                nonlocal seq
                seq+=1
                response=transact(port,seq,mode,raw)
                log.write(json.dumps(response[0] if isinstance(response,tuple) else response)+'\n'); log.flush()
                return response
            port.dtr=True
            port.reset_input_buffer()
            hello=call(0)
            write_json(dest/'board_info.json',hello)
            if not hello.get('ready') or hello.get('model_sha256')!=ex['model_sha256']:
                raise ValueError('Placa sem modelo pronto ou com modelo diferente')
            if hello.get('clock_hz')!=133000000: raise ValueError('Clock inesperado')
            entries=[]
            for row,raw,expected,host_probability,optimized_probability in prepared:
                _,observed=call(2,raw)
                result=call(1,raw)
                difference=np.abs(expected.astype(int)-observed.astype(int))
                entries.append({'recording_id':row['recording_id'],'patient_id':row['patient_id'],
                    'split':'validation','max_int8_feature_difference':int(difference.max()),
                    'different_feature_elements':int(np.count_nonzero(difference)),
                    'host_probability':host_probability,'reference_probability':host_probability,
                    'optimized_host_probability':optimized_probability,
                    'board_probability':result['prob_present'],
                    'absolute_optimized_host_difference':abs(optimized_probability-result['prob_present']),
                    'absolute_probability_difference':abs(host_probability-result['prob_present'])})
            passed=all(r['max_int8_feature_difference']<=1 and r['absolute_probability_difference']<=2*ex['output_scale']+1e-7 for r in entries)
            write_json(dest/'parity.json',{'passed':passed,'acceptance':'max input INT8 difference <=1; output vs BUILTIN_REF <=2 steps',
                'optimized_host_within_same_tolerance':all(r['absolute_optimized_host_difference']<=2*ex['output_scale']+1e-7 for r in entries),
                'note':'AUTO/XNNPACK differences remain reported; this does not establish cohort-level equivalence to original host test metrics.',
                'entries':entries})
            if not passed: raise ValueError('Paridade falhou. Tempos cientificos nao liberados.')
            for row in timing_rows[:10]: call(1,payload(row)[0])
            times=[]
            for number,row in enumerate(timing_rows,1):
                result=call(1,payload(row)[0])
                for key in ('preprocessing_us','inference_us','processing_us'):
                    if not isinstance(result.get(key),(int,float)) or not np.isfinite(result[key]) or result[key]<0:
                        raise ValueError('Tempo invalido recebido da placa')
                times.append({'index':number,'recording_id':row['recording_id'],'split':'validation',**result})
                if number%10==0: print(f'Placa: {number}/{len(timing_rows)} janelas medidas',flush=True)
            write_csv(dest/'timings.csv',times)
            summary={key:{'median_us':float(np.median([r[key] for r in times])),
                'p95_us':float(np.percentile([r[key] for r in times],95)),
                'max_us':float(max(r[key] for r in times))} for key in ('preprocessing_us','inference_us','processing_us')}
            write_json(dest/'latency.json',{'warmup_windows_excluded':10,'measured_windows':len(times),
                'units':'microseconds','timings':summary,'total_peak_ram_bytes':None,'stack_high_water_bytes':None})
        write_json(dest/'session.json',metadata|{'status':'complete','port':port_name,
            'artifact_hashes':{f.name:sha256(f) for f in dest.iterdir() if f.is_file() and f.name!='session.json'}})
        print(f'Paridade e benchmark da placa concluidos: {dest}')
    except Exception as error:
        write_json(dest/'session.json',metadata|{'status':'failed','port':port_name,'error':str(error)})
        raise

if __name__=='__main__':
    main()

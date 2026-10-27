"""Fresh validation benchmark. Never trains, selects thresholds or evaluates the test cohort."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
os.environ['TF_ENABLE_ONEDNN_OPTS']='0'
from pathlib import Path
import argparse,datetime,hashlib,json,time,platform,sys
import numpy as np
from heart_tinyml.adapters.repositories import FrozenModelRepository
from heart_tinyml.signal import coefficients,extract,quantize
from heart_tinyml.adapters.usb_protocol import ProtocolClient,Mode,validate_inference

def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(p,obj):p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf8')
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--bundle',type=Path,required=True);ap.add_argument('--mode',choices=['cpu_float','gpu_float','cpu_float_lite','cpu_int8','board_int8'],required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--port',default='auto');a=ap.parse_args()
    bundle=a.bundle.resolve();plan=json.loads((bundle/'plan.json').read_text(encoding='utf8'));model=FrozenModelRepository(bundle/'source/heart_tinyml/resources').load()
    for name,value in plan['files'].items():
        if digest(bundle/name)!=value:raise ValueError('Benchmark input changed: '+name)
    archive=np.load(bundle/'inputs.npz',allow_pickle=False);pcm=archive['pcm'];ids=archive['recording_id'];assert pcm.shape==(100,12000) and pcm.dtype==np.int16
    assert all(r['split']=='validation' for r in plan['windows'])
    fingerprint=hashlib.sha256(((bundle/'plan.json').read_text()+digest(__file__)+a.mode).encode()).hexdigest()
    a.out.mkdir(parents=True,exist_ok=True);meta_path=a.out/(a.mode+'.json');rows_path=a.out/(a.mode+'.jsonl')
    if meta_path.exists():
        old=json.loads(meta_path.read_text());assert old['fingerprint']==fingerprint,'Different protocol: use a new output directory'
        if old['status']=='complete':print('Already complete, preserved:',meta_path);return
    rows=[]
    if rows_path.exists():
        raw=rows_path.read_bytes();parts=raw.splitlines(keepends=True)
        # Descarta somente um fragmento sem newline, nunca uma resposta confirmada.
        confirmed=[line for line in parts if line.endswith(b'\n')];rows=[json.loads(line) for line in confirmed]
        rows_path.write_bytes(b''.join(confirmed))
    report={'status':'running','kind':'fresh_validation_compute_benchmark_not_test_accuracy','mode':a.mode,'fingerprint':fingerprint,'started_utc':stamp(),'plan_sha256':digest(bundle/'plan.json'),'script_sha256':digest(__file__),'model_sha256':plan['files']['source/heart_tinyml/resources/model/model_int8.tflite'],'float_model_sha256':plan['files']['float.keras'],'windows':100,'repetitions':3,'warmup_calls_per_session':10,'batch_size':1,'host':{'platform':platform.platform(),'python':platform.python_version(),'numpy':np.__version__},'completed_calls':len(rows),'threshold_int8':model.manifest['threshold'],'threshold_float':plan['threshold_float'],'limits':'Validation windows are correlated; do not interpret 300 calls as 300 patients. TF graph dispatch/readback differs from LiteRT Invoke and TFLM Invoke. No energy, peak RAM or isolated quantization speedup measured.'}
    write(meta_path,report)
    c=model.manifest['frontend'];coef=coefficients(c);connection=None
    def frontend(x):return ((extract(x.astype(np.float32)/32768,c,coef)-model.mean)/model.std)[...,None]
    if a.mode in ('cpu_float','gpu_float'):
        import tensorflow as tf
        tf.config.threading.set_intra_op_parallelism_threads(1);tf.config.threading.set_inter_op_parallelism_threads(1)
        tf.config.experimental.enable_tensor_float_32_execution(False);tf.config.set_soft_device_placement(False)
        gpus=tf.config.list_physical_devices('GPU')
        if a.mode=='gpu_float' and not gpus:raise RuntimeError('GPU required; no silent CPU fallback')
        if a.mode=='cpu_float':tf.config.set_visible_devices([],'GPU')
        else:
            for gpu in gpus:tf.config.experimental.set_memory_growth(gpu,True)
        device='/GPU:0' if a.mode=='gpu_float' else '/CPU:0'
        with tf.device(device):
            net=tf.keras.models.load_model(bundle/'float.keras',compile=False)
            @tf.function(input_signature=[tf.TensorSpec([1,186,24,1],tf.float32)],jit_compile=False)
            def forward(x):return net(x,training=False)
        report['runtime']={'tensorflow':tf.__version__,'device':device,'tf32':False,'intra_threads':1,'inter_threads':1,'gpus':[tf.config.experimental.get_device_details(g).get('device_name',g.name) for g in gpus]}
        def run_one(x):
            begin=time.perf_counter_ns();features=frontend(x);prepared=time.perf_counter_ns()
            with tf.device(device):
                inp=tf.constant(features[None]);uploaded=time.perf_counter_ns();out=forward(inp)
                if a.mode=='gpu_float' and 'GPU:' not in out.device.upper():raise RuntimeError('Tensor did not execute on GPU')
                score=float(out.numpy()[0,1]);end=time.perf_counter_ns()
            return {'score':score,'preprocessing_ms':(prepared-begin)/1e6,'inference_ms':(end-uploaded)/1e6,'processing_ms':((prepared-begin)+(end-uploaded))/1e6,'including_tensor_transfer_ms':(end-begin)/1e6}
        report['timing_scope']='CPU MFE and normalization; tf.function call plus synchronized output.numpy readback. Input tensor creation/upload excluded from inference_ms but included in including_tensor_transfer_ms. No WAV I/O, plotting or training.'
    elif a.mode in ('cpu_int8','cpu_float_lite'):
        float_lite = a.mode == 'cpu_float_lite'
        lite_path = model.path
        if float_lite:
            import tensorflow as tf
            tf.config.set_visible_devices([], 'GPU')
            tf.config.threading.set_intra_op_parallelism_threads(1)
            tf.config.threading.set_inter_op_parallelism_threads(1)
            tf.config.experimental.enable_tensor_float_32_execution(False)
            from tensorflow.python.framework.convert_to_constants import convert_variables_to_constants_v2
            with tf.device('/CPU:0'):
                net = tf.keras.models.load_model(bundle/'float.keras', compile=False)
                @tf.function(input_signature=[tf.TensorSpec([1,186,24,1],tf.float32)])
                def forward(x): return net(x, training=False)
                frozen = convert_variables_to_constants_v2(forward.get_concrete_function())
            converter = tf.lite.TFLiteConverter.from_concrete_functions([frozen])
            lite_path = a.out/'model_float32.tflite'
            lite_path.write_bytes(converter.convert())
            report['float_tflite_sha256'] = digest(lite_path)
            report['float_tflite_bytes'] = lite_path.stat().st_size
            report['int8_tflite_bytes'] = model.path.stat().st_size
        try:
            from ai_edge_litert.interpreter import Interpreter,OpResolverType
            import importlib.metadata
            version=importlib.metadata.version('ai-edge-litert');engine='LiteRT'
        except ImportError:
            import tensorflow as tf
            tf.config.set_visible_devices([],'GPU');tf.config.threading.set_intra_op_parallelism_threads(1);tf.config.threading.set_inter_op_parallelism_threads(1)
            Interpreter,OpResolverType=tf.lite.Interpreter,tf.lite.experimental.OpResolverType
            version=tf.__version__;engine='TensorFlow Lite'
        runtime=Interpreter(model_path=str(lite_path),num_threads=1,experimental_op_resolver_type=OpResolverType.BUILTIN_REF);runtime.allocate_tensors();inp=runtime.get_input_details()[0];out=runtime.get_output_details()[0]
        report['runtime']={'engine':engine,'version':version,'resolver':'BUILTIN_REF','threads':1,'device':'CPU','precision':'Float32' if float_lite else 'INT8'}
        if float_lite:
            errors=[]
            for x in pcm:
                z=frontend(x)[None]
                with tf.device('/CPU:0'): expected=net(tf.constant(z),training=False).numpy()
                runtime.set_tensor(inp['index'],z);runtime.invoke();actual=runtime.get_tensor(out['index'])
                np.testing.assert_allclose(actual,expected,atol=1e-5,rtol=1e-5)
                errors.append(float(np.max(np.abs(actual-expected))))
            report['conversion_check']={'partition':'validation','windows':100,'maximum_absolute_error':max(errors),'atol':1e-5,'rtol':1e-5,'threshold_tuned':False}
        def run_one(x):
            begin=time.perf_counter_ns();z=frontend(x);q=z.astype(np.float32) if float_lite else quantize(z,*inp['quantization']);prepared=time.perf_counter_ns();runtime.set_tensor(inp['index'],q[None]);start=time.perf_counter_ns();runtime.invoke();end=time.perf_counter_ns();s,zp=out['quantization'];value=runtime.get_tensor(out['index'])[0,1];score=float(value) if float_lite else float((int(value)-zp)*s)
            return {'score':score,'preprocessing_ms':(prepared-begin)/1e6,'inference_ms':(end-start)/1e6,'processing_ms':((prepared-begin)+(end-start))/1e6}
        report['timing_scope']='CPU MFE + normalization + INT8 input quantization when used; reference Invoke only. Input tensor copy, score readout, WAV I/O and plotting excluded.'
    else:
        import serial
        from serial.tools.list_ports import comports
        ports=[p.device for p in comports() if p.vid==0x2e8a]
        if a.port=='auto':
            if len(ports)!=1:raise RuntimeError('Expected one Pico USB port; found '+str(ports))
            port=ports[0]
        else:
            if a.port not in ports:raise RuntimeError('Port is not an enumerated Pico')
            port=a.port
        connection=serial.Serial(port,115200,timeout=1,write_timeout=5);connection.dtr=True;connection.reset_input_buffer();client=ProtocolClient(connection,timeout=30)
        hello=client.request(Mode.HELLO)
        if not hello.get('ready') or hello.get('model_sha256')!=report['model_sha256']:raise RuntimeError('Board model/ready mismatch; no firmware was flashed')
        report['runtime']={'engine':'TFLM','hello':hello,'port':port}
        def run_one(x):
            start=time.perf_counter_ns();r=validate_inference(client.request(Mode.INFER,x.astype('<i2').tobytes()));elapsed=(time.perf_counter_ns()-start)/1e6
            return {'score':float(r['prob_present']),'preprocessing_ms':r['preprocessing_us']/1000,'inference_ms':r['inference_us']/1000,'processing_ms':r['processing_us']/1000,'including_usb_ms':elapsed,'feature_crc32':r.get('feature_crc32')}
        report['timing_scope']='Firmware timestamp MFE and Invoke; excludes USB/acquisition/display. including_usb_ms is separate host wall time, not added to compute time. Hello records the actual firmware; this is not an old build resource audit.'
    report['runtime_initialized_utc']=stamp();write(meta_path,report)
    order=[]
    for repeat in range(3):
        for ix in np.random.default_rng(20261027+repeat).permutation(100):order.append((repeat+1,int(ix)))
    try:
        print(a.mode+': warm-up de 10 chamadas (excluidas).',flush=True)
        for x in pcm[:10]:run_one(x)
        with rows_path.open('a',encoding='utf8') as f:
            for k,(repeat,ix) in enumerate(order):
                if k<len(rows):continue
                result=run_one(pcm[ix]);row={'call':k+1,'repeat':repeat,'index':ix,'recording_id':str(ids[ix]),'pcm_sha256':plan['windows'][ix]['pcm_sha256'],**result}
                if not 0<=row['score']<=1 or not all(np.isfinite(row[key]) and row[key]>=0 for key in ('preprocessing_ms','inference_ms','processing_ms')):raise ValueError('Invalid result')
                f.write(json.dumps(row,allow_nan=False)+'\n');f.flush();rows.append(row)
                if (k+1)%25==0:print(a.mode+': '+str(k+1)+'/300',flush=True)
        report['status']='complete';report['completed_calls']=len(rows);report['ended_utc']=stamp();report['rows_sha256']=digest(rows_path)
        report['summary']={key:{'median_ms':float(np.median([r[key] for r in rows])),'p95_ms':float(np.percentile([r[key] for r in rows],95)),'min_ms':float(min(r[key] for r in rows)),'max_ms':float(max(r[key] for r in rows))} for key in ('preprocessing_ms','inference_ms','processing_ms')}
        write(meta_path,report);print('BENCHMARK_CONCLUIDO:',meta_path,flush=True)
    except BaseException:
        report['status']='interrupted';report['completed_calls']=len(rows);write(meta_path,report);raise
    finally:
        if connection:connection.close()
if __name__=='__main__':main()

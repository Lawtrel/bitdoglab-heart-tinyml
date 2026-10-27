from pathlib import Path
import argparse,json,struct,hashlib
parser=argparse.ArgumentParser(description='Verifica UF2 RP2040, modelo congelado e secoes ELF sem executar hardware.')
parser.add_argument('--build',type=Path,required=True)
parser.add_argument('--model',type=Path,required=True)
parser.add_argument('--out',type=Path)
a=parser.parse_args()
build=a.build
modeldir=a.model
report=json.loads((build/'resource-report.json').read_text())
h=lambda b:hashlib.sha256(b).hexdigest()
for name,digest in report['artifacts'].items(): assert h((build/name).read_bytes())==digest,name
model=(modeldir/'model_int8.tflite').read_bytes(); image=(build/'pcg_bitdoglab.bin').read_bytes()
assert h(model)==report['model_sha256']
assert image.count(model)==1
raw=(build/'pcg_bitdoglab.uf2').read_bytes()
assert len(raw)%512==0
blocks={}
for offset in range(0,len(raw),512):
    block=raw[offset:offset+512]
    m0,m1,flags,addr,n,num,total,family=struct.unpack_from('<8I',block)
    assert (m0,m1,struct.unpack_from('<I',block,508)[0])==(0x0A324655,0x9E5D5157,0x0AB16F30)
    assert flags==0x2000 and family==0xE48BFF56 and n==256
    assert total==len(raw)//512 and num not in blocks
    assert addr==0x10000000+num*256
    blocks[num]=block[32:32+n]
reassembled=b''.join(blocks[i] for i in range(len(blocks)))
assert reassembled[:len(image)]==image
elf=(build/'pcg_bitdoglab.elf').read_bytes()
assert elf[:6]==b'\x7fELF\x01\x01'
hdr=struct.unpack_from('<16sHHIIIIIHHHHHH',elf)
sections=[struct.unpack_from('<10I',elf,hdr[6]+i*hdr[11]) for i in range(hdr[12])]
strings=sections[hdr[13]]
strtab=elf[strings[4]:strings[4]+strings[5]]
sec=[]
for s in sections:
    name=strtab[s[0]:].split(b'\0',1)[0].decode()
    if 0x20000000<=s[3]<0x20042000:
        sec.append({'name':name,'address':hex(s[3]),'bytes':s[5],'type':s[1],'allocated':bool(s[2]&2)})
audit={'status':'build_artifacts_verified_not_runtime_tested','model_sha256':h(model),
       'uf2_sha256':h(raw),'uf2_blocks':len(blocks),'uf2_family':'RP2040',
       'uf2_matches_binary':True,'model_present_once_in_firmware_binary':True,
       'firmware_flash_image_bytes':len(image),'elf_ram_addressed_sections':sec,
       'original_resource_report_sha256':h((build/'resource-report.json').read_bytes()),
       'note':'Berkeley size text/data/bss are categories, not memory regions. RAM contains copied code/data, vectors, bss, heap and stacks. Do not interpret data+bss as total or peak RAM. Runtime arena/latency remain pending.'}
(a.out or build/'build-audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
print(json.dumps(audit,indent=2))

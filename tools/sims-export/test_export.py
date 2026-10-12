"""Execute the real exporter against original synthetic packages; no game assets."""
import json, pathlib, struct, subprocess, sys, tempfile, hashlib

def words(*values): return struct.pack('<'+'I'*len(values),*values)
def package(path,payload,kind=0x01D10F34,instance=1):
    header=bytearray(96);header[:12]=b'DBPF'+words(2,1)
    struct.pack_into('<III',header,36,1,0,32);struct.pack_into('<Q',header,64,96+len(payload))
    path.write_bytes(header+payload+words(0,kind,0,0,instance,96,len(payload),len(payload)))
def triangle():
    mlod=b'MLOD'+words(0x202,1,72,0x123,0,0x10000001,0x10000002,0x10000003,3,0,0,0,0,3,1)+bytes(24)
    fmt=b'VRTF'+words(2,12,1,0)+bytes([0,0,2,0])
    verts=b'VBUF'+words(1,0,0)+struct.pack('<9f',0,0,0,1,0,0,0,1,0)
    indices=b'IBUF'+words(1,0,0)+struct.pack('<3H',0,1,2)
    chunks=[mlod,fmt,verts,indices];keys=b''.join(struct.pack('<QII',i,0,0) for i in range(4));offset=116;directory=b''
    for chunk in chunks:directory+=words(offset,len(chunk));offset+=len(chunk)
    return words(3,1,0,0,4)+keys+directory+b''.join(chunks)

def single_chunk(chunk):
    return words(3,1,0,0,1)+struct.pack('<QII',0,0,0)+words(44,len(chunk))+chunk

def external_triangle(source):
    fmt=b'VRTF'+words(2,12,1,0)+bytes([0,0,2,0])
    verts=b'VBUF'+words(1,0,0)+struct.pack('<9f',0,0,0,1,0,0,0,1,0)
    indices=b'IBUF'+words(1,0,0)+struct.pack('<3H',0,1,2)
    for i,chunk in enumerate([fmt,verts,indices]):package(source/('buffer'+str(i)+'.package'),single_chunk(chunk),0x111+i,10+i)
    mlod=b'MLOD'+words(0x202,1,72,0x123,0,0x30000001,0x30000002,0x30000003,3,0,0,0,0,3,1)+bytes(24)
    keys=struct.pack('<QII',0,0,0)+b''.join(struct.pack('<QII',10+i,0x111+i,0) for i in range(3))
    package(source/'cross.package',words(3,1,0,3,1)+keys+words(92,len(mlod))+mlod,instance=2)

def catalog_fixture(source,instance=100,common=11,tags=(270,276,217,222)):
    # COBJ common prefix: both 16-bit legacy and 32-bit modern tags.
    cobj=words(25,common,12345,0,100)+struct.pack('<Q',0)+words(0)+bytes([0])
    cobj+=bytes(12) if common>=10 else bytes([0])
    cobj+=words(len(tags))+struct.pack('<'+('I' if common>=11 else 'H')*len(tags),*tags)
    package(source/('catalog'+str(instance)+'.package'),cobj,0x319E4F1D,instance)
    name=b'Fixture chair'
    props=words(len(name))+name+words(4)+struct.pack('<QII',5<<32,0x01661233,0)
    table=6+len(props)
    objd=struct.pack('<HI',1,table)+props+struct.pack('<H',2)+words(0xE7F07786,6,0x8D20ACC6,10+len(name))
    package(source/('definition'+str(instance)+'.package'),objd,0xC0DB5AE7,instance)
    modl=b'MODL'+words(256,1)+bytes(24)+words(0x30000001,0,0,0,0)
    keys=struct.pack('<QII',5,0x01661233,0)+struct.pack('<QII',1,0x01D10F34,0)
    package(source/'model.package',words(3,1,0,1,1)+keys+words(60,len(modl))+modl,0x01661233,5)

def main():
    command=sys.argv[1:]
    if not command:raise SystemExit('Usage: python test_export.py <dotnet> <SimsExport.dll>')
    with tempfile.TemporaryDirectory() as temporary:
        root=pathlib.Path(temporary);source=root/'game';source.mkdir();out=root/'exports'
        valid=source/'original.package';package(valid,triangle());package(source/'unsupported.package',words(99),instance=3)
        external_triangle(source)
        catalog_fixture(source)
        display='Mr. Comfortable Chair • Deluxe'
        encoded=display.encode('utf-8')
        stbl=b'STBL'+struct.pack('<HBQHI',5,0,1,0,len(encoded)+7)+struct.pack('<IBH',12345,0,len(encoded))+encoded
        package(source/'strings.package',stbl,0x220557DA,200)
        catalog_fixture(source,101,9,(272,225,65500))
        catalog_fixture(source,102,12)
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}
        run=subprocess.run(command+[str(source),str(out)],capture_output=True,text=True)
        assert run.returncode==1,(run.stdout,run.stderr)
        objects=list(out.rglob('*.obj'));assert len(objects)==2
        text=objects[0].read_text();assert 'v 1 0 0' in text and 'f 1 2 3' in text
        rows=[json.loads(line) for p in out.glob('*.jsonl') for line in p.read_text().splitlines()]
        assert any(r['status']=='unsupported-or-invalid' for r in rows)
        assert any(r['status']=='geometry-only' and not r['textures'] and r['catalogLinked'] for r in rows)
        assert any(r['status']=='catalog-unlinked' and 'version 12' in r['error'] for r in rows)
        sidecars=list(out.rglob('*.catalog.json'));assert len(sidecars)==1
        metadata=json.loads(sidecars[0].read_text())
        assert metadata['name']==display
        assert set(metadata['rooms'])=={'Living room','Office','Bedroom'}
        assert set(metadata['categories'])=={'Seating','Beds'}
        assert 65500 in metadata['catalogTags'] and len(metadata['catalogKeys'])==2
        sidecars[0].unlink() # Resume must regenerate metadata without exporting geometry again.
        again=subprocess.run(command+[str(source),str(out)],capture_output=True,text=True);assert again.returncode==1
        assert len(list(out.rglob('*.obj')))==2
        assert len(list(out.rglob('*.catalog.json')))==1
        assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}
        protected=subprocess.run(command+[str(source),str(source/'exports')],capture_output=True,text=True)
        assert protected.returncode==2 and not (source/'exports').exists()
        assert not list(out.rglob('*.tmp'))
        executable=source/'Game'/'Bin'/'TS4_x64.exe';executable.parent.mkdir(parents=True);executable.write_bytes(b'synthetic-exe-path-fixture')
        (source/'Data'/'Client').mkdir(parents=True)
        from_exe=subprocess.run(command+[str(executable),str(out)],capture_output=True,text=True)
        assert from_exe.returncode==1,(from_exe.stdout,from_exe.stderr)
        assert len(list(out.rglob('*.obj')))==2
        wrong=executable.with_name('OtherGame.exe');wrong.write_bytes(b'synthetic-exe-path-fixture')
        invalid=subprocess.run(command+[str(wrong),str(out)],capture_output=True,text=True);assert invalid.returncode==2
    print('PASS real exporter: STBL UTF-8 display names, COBJ v9/v11, unknown-version report, multi-room/type tags, OBJD/MODL/MLOD links, metadata resume, valid triangle, cross-package dependencies, EXE discovery, unsupported report, resume, unchanged sources, output protection, atomic cleanup')
if __name__=='__main__':main()

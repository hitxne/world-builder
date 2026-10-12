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
    package(source/'cross.package',words(3,1,0,3,1)+keys+words(92,len(mlod))+mlod)

def main():
    command=sys.argv[1:]
    if not command:raise SystemExit('Usage: python test_export.py <dotnet> <SimsExport.dll>')
    with tempfile.TemporaryDirectory() as temporary:
        root=pathlib.Path(temporary);source=root/'game';source.mkdir();out=root/'exports'
        valid=source/'original.package';package(valid,triangle());package(source/'unsupported.package',words(99))
        external_triangle(source)
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}
        run=subprocess.run(command+[str(source),str(out)],capture_output=True,text=True)
        assert run.returncode==1,(run.stdout,run.stderr)
        objects=list(out.rglob('*.obj'));assert len(objects)==2
        text=objects[0].read_text();assert 'v 1 0 0' in text and 'f 1 2 3' in text
        rows=[json.loads(line) for p in out.glob('*.jsonl') for line in p.read_text().splitlines()]
        assert any(r['status']=='unsupported-or-invalid' for r in rows)
        assert any(r['status']=='geometry-only' and not r['textures'] and not r['catalogLinked'] for r in rows)
        again=subprocess.run(command+[str(source),str(out)],capture_output=True,text=True);assert again.returncode==1
        assert len(list(out.rglob('*.obj')))==2
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
    print('PASS real exporter: valid triangle, cross-package dependencies, EXE discovery, unsupported report, resume, unchanged sources, output protection, atomic cleanup')
if __name__=='__main__':main()

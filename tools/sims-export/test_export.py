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

def textured_fixture(source,format="DST1",number=0):
    mlod=b'MLOD'+words(0x202,1,72,0x123,0x10000005,0x10000001,0x10000002,0x10000003,3,0,0,0,0,3,1)+bytes(24)
    fmt=b'VRTF'+words(2,32,3,0)+bytes([0,0,2,0,2,0,1,12,1,0,2,20])
    data=[(0,0,0,0,0,0,0,1),(1,0,0,1,0,0,0,1),(0,1,0,0,1,0,0,1)]
    verts=b'VBUF'+words(1,0,0)+b''.join(struct.pack('<8f',*v) for v in data)
    indices=b'IBUF'+words(1,0,0)+struct.pack('<3H',0,1,2)
    params=words(0x637DAA05,1,3,64)+words(0x420520E9,1,3,76)+words(0x6CC0FD85,4,4,88)
    payload=struct.pack('<6f',1,1,1,1/32767,1/32767,1/32767)+struct.pack('<QII',300+number,0x00B2D882,0)
    mtnf=b'MTNF'+words(0,40,3)+params+payload
    matd=b'MATD'+words(0x103,0,0x123456,len(mtnf),0,0)+mtnf
    mtst=b'MTST'+words(0x300,0,0x10000004,0)
    chunks=[mlod,fmt,verts,indices,matd,mtst];keys=b''.join(struct.pack('<QII',i,0,0) for i in range(6));offset=20+6*24;directory=b''
    for chunk in chunks:directory+=words(offset,len(chunk));offset+=len(chunk)
    package(source/('textured'+str(number)+'.package'),words(3,1,0,0,6)+keys+directory+b''.join(chunks),instance=4+number)
    header=bytearray(128);struct.pack_into('<I',header,0,0x20534444);struct.pack_into('<I',header,4,124)
    struct.pack_into('<II',header,12,4,8);struct.pack_into('<I',header,76,32);header[84:88]=format.encode()
    colors=struct.pack('<HH',0xf800,0x001f)+struct.pack('<HH',0x001f,0xf800)
    color0=colors[:4]+bytes(4);color1=colors[4:]+bytes(4)
    if format=='DST1':payload=colors+bytes(8)
    elif format=='DXT1':payload=color0+color1
    elif format=='DXT3':payload=bytes([255])*8+color0+bytes([255])*8+color1
    elif format=='DXT5':payload=bytes([255,0])+bytes(6)+color0+bytes([255,0])+bytes(6)+color1
    elif format=='DST5':payload=bytes([255,0,255,0])+colors+bytes(12)+bytes(8)
    texture=header+payload
    package(source/('texture'+str(number)+'.package'),texture,0x00B2D882,300+number)
    return bytes(texture),matd

def main():
    command=sys.argv[1:]
    if not command:raise SystemExit('Usage: python test_export.py <dotnet> <SimsExport.dll>')
    with tempfile.TemporaryDirectory() as temporary:
        root=pathlib.Path(temporary);source=root/'game';source.mkdir();out=root/'exports'
        valid=source/'original.package';package(valid,triangle());package(source/'unsupported.package',words(99),instance=3)
        external_triangle(source)
        original_texture,original_material=textured_fixture(source)
        for i,format in enumerate(['DST5','DXT1','DXT3','DXT5'],1):textured_fixture(source,format,i)
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
        objects=list(out.rglob('*.obj'));assert len(objects)==7
        text=objects[0].read_text();assert 'v 1 0 0' in text and 'f 1 2 3' in text
        rows=[json.loads(line) for p in out.glob('*.jsonl') for line in p.read_text().splitlines()]
        assert any(r['status']=='unsupported-or-invalid' for r in rows)
        assert any(r['status']=='geometry-only' and not r['textures'] and r['catalogLinked'] for r in rows)
        assert any(r['status']=='catalog-unlinked' and 'version 12' in r['error'] for r in rows)
        textured=[r for r in rows if r['status']=='appearance-supported'];assert len(textured)==5
        from PIL import Image
        for record in textured:
            candidate=pathlib.Path(record['output']);manifest=json.loads(pathlib.Path(str(candidate)+'.appearance.json').read_text());entry=manifest['materials'][0]['maps'][0]
            image=Image.open(pathlib.Path(str(candidate)+'.appearance')/entry['converted']);assert image.getpixel((0,0))==(255,0,0,255) and image.getpixel((7,3))==(0,0,255,255)
        obj=pathlib.Path(next(r['output'] for r in textured if r['source']=='textured0.package'));assert 'vt 0 1' in obj.read_text() and 'vn 0 0 1' in obj.read_text()
        assert 'f 1/1/1 2/2/2 3/3/3' in obj.read_text()
        manifest=json.loads(pathlib.Path(str(obj)+'.appearance.json').read_text());material=manifest['materials'][0]
        folder=pathlib.Path(str(obj)+'.appearance')
        assert (folder/material['rawMaterial']).read_bytes()==original_material
        texture=material['maps'][0];assert (folder/texture['rawTexture']).read_bytes()==original_texture
        from PIL import Image
        image=Image.open(folder/texture['converted']);assert image.size==(8,4)
        assert image.getpixel((0,0))==(255,0,0,255) and image.getpixel((7,3))==(0,0,255,255)
        assert 'map_Kd' in obj.with_suffix('.mtl').read_text()
        sidecars=list(out.rglob('*.catalog.json'));assert len(sidecars)==1
        metadata=json.loads(sidecars[0].read_text())
        assert metadata['name']==display
        assert set(metadata['rooms'])=={'Living room','Office','Bedroom'}
        assert set(metadata['categories'])=={'Seating','Beds'}
        assert 65500 in metadata['catalogTags'] and len(metadata['catalogKeys'])==2
        obj.write_text('# Sims object MLOD geometry only: old version\nv 0 0 0\n') # Migration must upgrade existing OBJ.
        sidecars[0].unlink() # Resume must regenerate metadata without exporting geometry again.
        again=subprocess.run(command+[str(source),str(out)],capture_output=True,text=True);assert again.returncode==1
        assert len(list(out.rglob('*.obj')))==7
        assert len(list(out.rglob('*.catalog.json')))==1
        assert "f 1/1/1 2/2/2 3/3/3" in obj.read_text()
        assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}
        protected=subprocess.run(command+[str(source),str(source/'exports')],capture_output=True,text=True)
        assert protected.returncode==2 and not (source/'exports').exists()
        assert not list(out.rglob('*.tmp'))
        executable=source/'Game'/'Bin'/'TS4_x64.exe';executable.parent.mkdir(parents=True);executable.write_bytes(b'synthetic-exe-path-fixture')
        (source/'Data'/'Client').mkdir(parents=True)
        from_exe=subprocess.run(command+[str(executable),str(out)],capture_output=True,text=True)
        assert from_exe.returncode==1,(from_exe.stdout,from_exe.stderr)
        assert len(list(out.rglob('*.obj')))==7
        wrong=executable.with_name('OtherGame.exe');wrong.write_bytes(b'synthetic-exe-path-fixture')
        invalid=subprocess.run(command+[str(wrong),str(out)],capture_output=True,text=True);assert invalid.returncode==2
    print('PASS real exporter: MTST/MATD, raw texture/material preservation, UV/normals, BC1/BC2/BC3 and DST1/DST5 pixels, existing appearance upgrade, STBL UTF-8 display names, COBJ v9/v11, unknown-version report, multi-room/type tags, OBJD/MODL/MLOD links, metadata resume, valid triangle, cross-package dependencies, EXE discovery, unsupported report, resume, unchanged sources, output protection, atomic cleanup')
if __name__=='__main__':main()

from pathlib import Path
import zipfile
root=Path(__file__).parent;source=root/'WB_TrackTools';output=root/'Dist/WB_TrackTools_Addon_v08.zip';output.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(source.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':archive.write(path,'WB_TrackTools/'+str(path.relative_to(source)))
print(output)

"""Build a deployment ZIP containing source/models, never raw data or runtime state."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parent
SOURCES=['app.py','server.py','optimizer.py','demo_auth.py','manage_users.py','intelligence.py','risk_model.py',
         'train_model.py','improve_model.py','dataset_context.py','fetch_data.py',
         'shipment_model.py','live_policy.py','live_engine.py','benchmark_live.py','build_package.py']
DOCS=['README.md','MODEL_CARD.md','REALTIME_MODEL_CARD.md','DEMO_SCRIPT.md','requirements.txt','.gitignore']


def build():
    files=[ROOT/name for name in SOURCES+DOCS]
    for directory,pattern in [('static','*'),('models','*.json'),('reports','*.json'),('tests','*.py'),('notebooks','*.ipynb')]:
        files.extend((ROOT/directory).glob(pattern))
    files.extend((ROOT/'static'/'ui').rglob('*'))
    files.extend(ROOT/'frontend'/name for name in ['package.json','package-lock.json','vite.config.js','index.html'])
    files.extend((ROOT/'frontend'/'src').rglob('*'))
    destination=ROOT/'TradeOff-Realtime.zip'
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            if path.is_file(): archive.write(path,'TradeOff/'+str(path.relative_to(ROOT)))
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None: raise ValueError('ZIP verification failed.')
        names=archive.namelist()
        if any('/data/raw/' in name or '/runtime/' in name or '/node_modules/' in name for name in names):
            raise ValueError('Private or runtime files must not be packaged.')
    print(f'{destination.name}: {len(names)} files, {destination.stat().st_size:,} bytes')
    return destination


if __name__=='__main__':
    build()

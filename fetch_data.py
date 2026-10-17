"""Download the three public source datasets. No third-party packages needed."""
import argparse
from pathlib import Path
import urllib.request
import zipfile

BASE = Path(__file__).resolve().parent / 'data/raw'


def download(url, path):
    if path.exists():
        print('Keeping existing', path)
        return
    print('Downloading', url, flush=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'TradeOff-datathon/1.0'})
    with urllib.request.urlopen(request, timeout=180) as response:
        content = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.part')
    temporary.write_bytes(content)
    temporary.replace(path)


def fetch(selection):
    BASE.mkdir(parents=True, exist_ok=True)
    if selection in ('all', 'dataco'):
        archive = BASE / 'dataco.zip'
        download('https://www.kaggle.com/api/v1/datasets/download/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis', archive)
        with zipfile.ZipFile(archive) as zipped:
            # Extract only the named CSV, never arbitrary archive paths or access logs.
            content = zipped.read('DataCoSupplyChainDataset.csv')
            (BASE / 'DataCoSupplyChainDataset.csv').write_bytes(content)
    if selection in ('all', 'cset'):
        for name in ['providers.csv', 'provision.csv', 'inputs.csv', 'stages.csv',
                     'sequence.csv', 'README.md', 'technical_notes.md']:
            download('https://raw.githubusercontent.com/georgetown-cset/eto-chip-explorer/main/data/' + name,
                     BASE / 'cset' / name)
    if selection in ('all', 'smat'):
        download('https://raw.githubusercontent.com/kwoo-lee/SMAT2022/main/General%20Data/dataset%204/SMAT_2022_Model_Data_-_LVHM_E.xlsx',
                 BASE / 'smat/LVHM_E.xlsx')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', choices=['all', 'dataco', 'cset', 'smat'], default='all')
    args = parser.parse_args()
    try:
        fetch(args.dataset)
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        parser.exit(1, f'Dataset download failed: {exc}\nFor DataCo, download the CSV manually from Kaggle into data/raw/.\n')

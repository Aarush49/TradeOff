"""Source-aware semiconductor context, kept separate from the retail classifier."""
import csv
import hashlib
import json
import posixpath
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def workbook_tables(path):
    """Read cell values from this data-only XLSX; do not execute formulas/macros."""
    with zipfile.ZipFile(path) as archive:
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared = [''.join(t.text or '' for t in node.iter('{' + NS['s'] + '}t'))
                      for node in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        rels = {r.get('Id'): r.get('Target') for r in
                ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        for sheet in workbook.find('s:sheets', NS):
            target = rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            name = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            root = ET.fromstring(archive.read(name))
            rows = []
            for row in root.findall('s:sheetData/s:row', NS):
                values = {}
                for cell in row:
                    column = ''.join(c for c in cell.get('r', '') if c.isalpha())
                    value = cell.findtext('s:v', default='', namespaces=NS)
                    if cell.get('t') == 's':
                        value = shared[int(value)]
                    elif cell.get('t') == 'inlineStr':
                        value = ''.join(cell.find('s:is', NS).itertext())
                    if cell.find('s:f', NS) is not None:
                        raise ValueError('Formula cells are not supported by the data adapter.')
                    values[column] = value
                if any(values.values()):
                    rows.append(values)
            headers = rows[0] if rows else {}
            yield sheet.get('name'), [{title: row.get(col, '') for col, title in headers.items()}
                                     for row in rows[1:]], list(headers.values())


def cset_context(directory):
    def read(name):
        with (directory / name).open(encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))
    providers = {r['provider_id']: r for r in read('providers.csv')}
    inputs = {r['input_id']: r for r in read('inputs.csv')}
    stages = {r['stage_id']: r for r in read('stages.csv')}
    provision = read('provision.csv')
    grouped = {}
    for row in provision:
        provider = providers.get(row['provider_id'], {})
        if provider.get('provider_type') != 'country' or not row['share_provided'].strip():
            continue
        try:
            year, share = int(row['year']), float(row['share_provided'])
        except ValueError:
            continue
        if not 0 <= share <= 100:
            continue
        grouped.setdefault((row['provided_id'], year), []).append(
            dict(country=provider['provider_name'], reported_share_percent=share, source=row['source'],
                 aggregate_geography=provider['provider_name'] in ('Various countries', 'EUR')))
    output = []
    for key in sorted({k for k, _ in grouped}):
        year = max(y for k, y in grouped if k == key)
        countries = sorted(grouped[(key, year)], key=lambda r: -r['reported_share_percent'])
        label = inputs.get(key, {}).get('input_name', stages.get(key, {}).get('stage_name', key))
        individual_shares = [c['reported_share_percent'] for c in countries if not c['aggregate_geography']]
        output.append(dict(input_id=key, input=label,
                           year=year, countries=countries,
                           reported_share_sum_percent=sum(c['reported_share_percent'] for c in countries),
                           largest_individual_country_share_percent=max(individual_shares) if individual_shares else None))
    return dict(source='https://github.com/georgetown-cset/eto-chip-explorer/tree/main/data',
                provider_records=len(providers), provision_records=len(provision),
                inputs=len(inputs), upstream_relationships=len(read('sequence.csv')),
                country_exposure=sorted(output, key=lambda r: r['input']),
                interpretation='Latest available year per input or stage. Reported geography shares, not outage probabilities or capacities.',
                caveat='Repository main/data snapshot; its README distinguishes it from the official release. Various countries and EUR are aggregate geographies, not single countries. Shares can be missing, rounded, or sum above 100. No normalization or cross-year summing.')


def smat_context(path):
    sheets, groups = {}, []
    for name, rows, headers in workbook_tables(path):
        sheets[name] = dict(records=len(rows), columns=headers)
        if name == 'Equipment':
            counts = Counter(r['TOOL_GROUP'] for r in rows)
            groups = [dict(tool_group=k, equipment_records=v) for k, v in counts.most_common(12)]
    return dict(source='https://github.com/kwoo-lee/SMAT2022', workbook=path.name,
                model='LVHM_E', sheets=sheets, largest_equipment_groups=groups,
                interpretation='Static AMHS/factory topology inventory, not observed production or delay labels.',
                caveat='No throughput, yield, utilization, capacity, or delay forecast is inferred from equipment counts. The repository simulator is Windows-only and is not executed.')


def build(raw=Path('data/raw'), destination=Path('models/dataset_context.json')):
    context = dict(cset=cset_context(raw / 'cset'), smat=smat_context(raw / 'smat/LVHM_E.xlsx'),
                   relationship='Three separate datasets; no validated record-level join exists between them.')
    manifest = []
    for path in sorted(raw.rglob('*')):
        if path.is_file():
            manifest.append(dict(path=str(path.relative_to(raw)), bytes=path.stat().st_size,
                                 sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    context['files'] = manifest
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(context, indent=2) + '\n')
    return context


if __name__ == '__main__':
    result = build()
    print(json.dumps(dict(cset_inputs=result['cset']['inputs'],
                          cset_exposures=len(result['cset']['country_exposure']),
                          smat_sheets=result['smat']['sheets']), indent=2))

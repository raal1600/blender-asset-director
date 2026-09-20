"""User display labels are version-bound and separate from asset/rights identity."""
from pathlib import Path
import re
from .core import fields, load_json, require

EDITABLE = {'character','environment','prop','rigged-model','model','pack'}


def read(filename=None):
    if not filename: return {}
    value=load_json(Path(filename),2*1024*1024)
    fields(value,{'schema','labels'},{'schema','labels'})
    require(value['schema']==1 and isinstance(value['labels'],dict) and len(value['labels'])<=10000,
            'INVALID_LABELS','Invalid display label store')
    for aid,label in value['labels'].items():
        require(re.fullmatch(r'a_[0-9a-f]{24}',aid),'INVALID_LABELS','Invalid label asset ID')
        fields(label,{'version','subcategory'},{'version','subcategory'})
        require(isinstance(label['version'],str) and re.fullmatch(r'[0-9a-f]{64}',label['version'])
                and label['subcategory'] in EDITABLE,'INVALID_LABELS','Invalid version-bound display label')
    return value['labels']

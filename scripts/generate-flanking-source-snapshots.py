#!/usr/bin/env python3
"""Generate non-redistributive source/claim snapshots for Flanking protocol authorities.

The public source bundle does not copy third-party manuals.  Instead this ledger
pins the vendor locator metadata and the exact canonical claim scope in which each
source is used.  A remote-document SHA-256 may be added by Linux qualification
when the reviewed bytes are legally/reliably retrievable; it is never fabricated.
"""
from __future__ import annotations
import argparse, hashlib, json, tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'contracts/chemistry/flanking-protocols.toml'
OUTPUT=ROOT/'knowledge/sources/flanking-source-snapshots.json'
REGISTRY_REL='knowledge/sources/flanking-source-snapshots.json'
STATUS='canonical-claim-snapshot-pinned'

def canon(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(value): return hashlib.sha256(canon(value)).hexdigest()

def build(raw):
    provenance=raw['provenance']; groups=raw['groups']; comp=raw['compatibility']; route_evidence=raw.get('routing_evidence', {}).get('digital_platforms', {})
    out={}
    for source_id,row in sorted(provenance.items()):
        memberships=[]
        for group,ids in groups.items():
            if source_id in ids: memberships.append(f'groups.{group}')
        for platform,source_ids in route_evidence.items():
            if source_id in source_ids: memberships.append(f'routing_evidence.digital_platforms.{platform}')
        compatibility_claims={}
        for map_name,mapping in comp.items():
            if source_id in mapping:
                memberships.append(f'compatibility.{map_name}.key')
                compatibility_claims[map_name]=mapping[source_id]
        base={
            'source_id':source_id,
            'url':row['url'],
            'kind':row['kind'],
            'reviewed_date':row['reviewed_date'],
            'availability_scope':row['availability_scope'],
            'document_identity':row.get('document_identity'),
            'document_revision':row.get('document_revision'),
            'claim_scope_note':row.get('claim_scope'),
            'canonical_claim_scope':memberships,
            'canonical_compatibility_claims':compatibility_claims,
            'remote_document_bytes_status':'not-redistributed-in-public-source',
            'remote_document_sha256':row.get('remote_document_sha256'),
        }
        digest=sha(base)
        out[source_id]={**base,'claim_snapshot_sha256':digest}
    return {
      'schema_version':'1.0.0','authority':'flanking-source-claim-snapshots',
      'effective_date':'2026-09-05','snapshot_kind':'canonical-source-locator-and-claim-scope',
      'remote_document_bytes_redistributed':False,
      'policy':'A claim snapshot proves which reviewed locator and canonical PCRStudio authority scope were used. It is not a hash of third-party bytes unless remote_document_sha256 is explicitly populated by qualification.',
      'sources':out,
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
    raw=tomllib.loads(SOURCE.read_text(encoding='utf-8')); payload=build(raw)
    # The canonical TOML must carry the exact generated claim digest for every source.
    for sid,snap in payload['sources'].items():
        row=raw['provenance'][sid]
        if row.get('snapshot_status') != STATUS: raise SystemExit(f'{sid}: snapshot_status is not {STATUS}')
        if row.get('snapshot_registry') != REGISTRY_REL: raise SystemExit(f'{sid}: snapshot_registry drift')
        if row.get('claim_snapshot_sha256') != snap['claim_snapshot_sha256']: raise SystemExit(f'{sid}: claim_snapshot_sha256 drift')
    text=json.dumps(payload,indent=2,ensure_ascii=False,sort_keys=True)+'\n'
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding='utf-8')!=text:
            print('FLANKING_SOURCE_SNAPSHOTS=CHECK-DRIFT'); return 1
        print(f'FLANKING_SOURCE_SNAPSHOTS=CHECK-PASS sources={len(payload["sources"])}'); return 0
    OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_text(text,encoding='utf-8',newline='\n')
    print(f'FLANKING_SOURCE_SNAPSHOTS=GENERATED sources={len(payload["sources"])}')
    return 0
if __name__=='__main__': raise SystemExit(main())

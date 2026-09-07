#!/usr/bin/env python3
"""Build an atomic, fingerprinted MFEprimer/BLAST specificity database on Linux."""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from toolchain_config import read_toolchain_config  # noqa: E402
TOOLDIR=Path(os.environ.get('PCRSTUDIO_TOOL_PREFIX', ROOT/'.local'/'tools')).expanduser().resolve()
IUPAC=re.compile(r'^[ACGTRYSWKMBDHVN]+$')

def sha256(path: Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def measure_fasta(path: Path)->dict[str,int]:
    # Stream even multi-gigabyte references; never materialise a chromosome or
    # whole genome in Python memory. UTF-8 errors are hard failures because a
    # FASTA identifier used in a manifest must be reproducible text.
    ids=set(); records=bases=ambiguous=current=0; current_id=''
    with path.open('r',encoding='utf-8',newline=None) as handle:
        for raw in handle:
            line=raw.strip()
            if not line: continue
            if line.startswith('>'):
                if records and current==0: raise SystemExit(f"Specificity FASTA record {current_id!r} contains no sequence")
                header=line[1:].strip()
                if not header: raise SystemExit('Specificity FASTA contains an empty header')
                current_id=header.split()[0]
                if current_id in ids: raise SystemExit(f"Specificity FASTA contains duplicate record identifier {current_id!r}")
                ids.add(current_id); records+=1; current=0; continue
            if not records: raise SystemExit('Specificity input must have a FASTA header before sequence data')
            seq=''.join(line.split()).upper()
            if not IUPAC.fullmatch(seq): raise SystemExit('FASTA must contain ungapped DNA/IUPAC symbols ACGTRYSWKMBDHVN only')
            bases+=len(seq); current+=len(seq); ambiguous+=sum(c not in 'ACGT' for c in seq)
    if not records or not bases or not current: raise SystemExit('Specificity FASTA contains an empty/no usable sequence record')
    return {'sequence_count':records,'total_bases':bases,'ambiguous_bases':ambiguous}

def normalize_fasta(source: Path,target: Path)->None:
    # Canonical 60-column normalization with O(1) sequence memory. Only the
    # sub-60-base line remainder is retained between input lines.
    with source.open('r',encoding='utf-8',newline=None) as src, target.open('w',encoding='utf-8',newline='\n') as out:
        seen_header=False; remainder=''
        def flush_remainder():
            nonlocal remainder
            if remainder:
                out.write(remainder.upper()+'\n'); remainder=''
        for raw in src:
            line=raw.strip()
            if not line: continue
            if line.startswith('>'):
                if seen_header: flush_remainder()
                out.write(line+'\n'); seen_header=True; remainder=''
                continue
            if not seen_header:
                raise SystemExit('Specificity input must have a FASTA header before sequence data')
            remainder += ''.join(line.split()).upper()
            while len(remainder) >= 60:
                out.write(remainder[:60]+'\n'); remainder=remainder[60:]
        if seen_header: flush_remainder()

def run(*args:str,cwd:Path|None=None)->None:
    subprocess.run([str(x) for x in args],cwd=cwd or ROOT,check=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('fasta',type=Path); ap.add_argument('database_id')
    ap.add_argument('--scope',choices=['production','approved-reference'],default='production')
    ap.add_argument('--sequence-release',default='user-supplied'); ap.add_argument('--taxonomy-release',default='unresolved')
    ap.add_argument('--filtering',default='user-reviewed'); ap.add_argument('--deduplication',default='user-reviewed')
    ap.add_argument('--mfeprimer-k',type=int,choices=range(1,16),default=9); ap.add_argument('--force',action='store_true')
    ap.add_argument('--output-root',type=Path,default=None,help='directory that receives the versioned database directory')
    ap.add_argument('--env-output',type=Path,default=None,help='where to write specificity.env (default: <tool-prefix>/specificity.env)')
    a=ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9._-]+',a.database_id): raise SystemExit('database_id must match [A-Za-z0-9._-]+')
    source=a.fasta.expanduser().resolve()
    if not source.is_file() or source.stat().st_size<=0: raise SystemExit('Specificity FASTA is missing or empty')
    config_path=TOOLDIR/'toolchain.json'
    if not config_path.is_file(): raise SystemExit('Run scripts/provision-tools.py before configuring specificity')
    try: env=read_toolchain_config(config_path)
    except ValueError as exc: raise SystemExit(f'Invalid toolchain configuration: {exc}') from exc
    mfe=Path(env.get('PCRSTUDIO_MFEPRIMER','')); blastn=Path(env.get('PCRSTUDIO_BLASTN',''))
    if not mfe.is_file() or not blastn.is_file(): raise SystemExit('Pinned MFEprimer/BLAST executables are unavailable')
    makeblastdb=blastn.parent/'makeblastdb'
    if not makeblastdb.is_file(): raise SystemExit('makeblastdb is unavailable beside blastn')
    measure=measure_fasta(source); root=(a.output_root.expanduser().resolve() if a.output_root else TOOLDIR/'databases'); root.mkdir(parents=True,exist_ok=True)
    dest=root/a.database_id
    if dest.exists() and any(dest.iterdir()) and not a.force: raise SystemExit(f"Database {a.database_id!r} exists; use --force for atomic replacement")
    staging=root/f'.{a.database_id}.staging-{os.getpid()}'; backup=root/f'.{a.database_id}.backup-{os.getpid()}'
    for x in (staging,backup):
        if x.exists(): shutil.rmtree(x)
    staging.mkdir()
    try:
        fasta=staging/f'{a.database_id}.fasta'; normalize_fasta(source,fasta); fasta_hash=sha256(fasta)
        run(str(mfe),'index','-i',fasta.name,'-k',str(a.mfeprimer_k),'-f',cwd=staging)
        blast_prefix=staging/a.database_id
        run(str(makeblastdb),'-in',str(fasta),'-dbtype','nucl','-out',str(blast_prefix))
        artifacts=[]
        for p in sorted(staging.iterdir(),key=lambda x:x.name):
            if p.is_file() and p!=fasta:
                artifacts.append({'name':p.name,'bytes':p.stat().st_size,'sha256':sha256(p)})
        if not artifacts: raise RuntimeError('Database indexing produced no index_artifacts')
        manifest={
          'schema_version':'1.1.0','database_id':a.database_id,'scope':a.scope,
          'sequence_release':a.sequence_release,'taxonomy_release':a.taxonomy_release,
          'source_fasta':source.name,'source_fasta_sha256':sha256(source),'indexed_fasta':fasta.name,'source_size_bytes':source.stat().st_size,
          **measure,'fasta_sha256':fasta_hash,'filtering':a.filtering,'deduplication':a.deduplication,
          'mfeprimer_index_k':a.mfeprimer_k,
          'mfeprimer_query_k_policy':'omit query -k; MFEprimer 4.5.1 reads k from the index header and rejects an explicit mismatch',
          'index_artifacts':artifacts,'created_at_utc':datetime.now(timezone.utc).isoformat(),
          'coordinate_policy':'ungapped source sequences retained verbatim; query coordinates adapter-normalized',
          'intended_use':'PCRStudio independent specificity evidence'}
        (staging/f'{a.database_id}.manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        if dest.exists(): dest.rename(backup)
        try: staging.rename(dest)
        except Exception:
            if backup.exists(): backup.rename(dest)
            raise
        if backup.exists(): shutil.rmtree(backup)
        final_fasta=dest/fasta.name; final_manifest=dest/f'{a.database_id}.manifest.json'; final_blast=dest/a.database_id
        rows=[
          f'PCRSTUDIO_MFEPRIMER_DATABASES={final_fasta}',f'PCRSTUDIO_MFEPRIMER_DATABASES_SHA256={fasta_hash}',
          f'PCRSTUDIO_MFEPRIMER_DATABASES_SCOPE={a.scope}',f'PCRSTUDIO_MFEPRIMER_DATABASES_MANIFEST={final_manifest}',
          f'PCRSTUDIO_BLAST_DATABASE={final_blast}',f'PCRSTUDIO_BLAST_DATABASE_SHA256={fasta_hash}',
          f'PCRSTUDIO_BLAST_DATABASE_SCOPE={a.scope}',f'PCRSTUDIO_BLAST_DATABASE_MANIFEST={final_manifest}']
        env_output=(a.env_output.expanduser().resolve() if a.env_output else TOOLDIR/'specificity.env'); env_output.parent.mkdir(parents=True,exist_ok=True); env_output.write_text('\n'.join(rows)+'\n',encoding='utf-8')
        print(f"Approved specificity database prepared: {a.database_id} ({a.scope})")
        print(f"FASTA: {measure['sequence_count']} record(s), {measure['total_bases']} bases, {measure['ambiguous_bases']} ambiguous base(s); {len(artifacts)} index artifact(s) fingerprinted.")
    finally:
        if staging.exists(): shutil.rmtree(staging)
        if backup.exists() and not dest.exists(): backup.rename(dest)

if __name__=='__main__': main()

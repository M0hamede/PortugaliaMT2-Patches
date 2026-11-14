#!/usr/bin/env python3
"""Prepara uma GitHub Release do cliente Metin2.

Suporta packs .data/.index, eix/epk e guarda os assets alterados para carregamento manual
no GitHub. O manifesto novo pode reutilizar URLs das releases anteriores.
"""
import argparse, fnmatch, hashlib, json, re, shutil
from pathlib import Path

INCLUDES = ['pack/*.data','pack/*.index','pack/**/*.data','pack/**/*.index',
            'pack/*.eix','pack/*.epk','pack/**/*.eix','pack/**/*.epk',
            'locale/**/*','locale/*','metin2client.exe','mt2moonrise.exe','config.exe']
EXCLUDES = ['screenshots/**','syserr.txt','syslog.txt','config.cfg','*.log',
            'pack/**/*.tmp','locale/**/*.log']

def allowed(rel):
    rel = rel.lower()
    return any(fnmatch.fnmatch(rel, rule) for rule in INCLUDES) and not any(fnmatch.fnmatch(rel, rule) for rule in EXCLUDES)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cliente', required=True, type=Path, help='Pasta de instalacao do cliente Metin2')
    ap.add_argument('--repo', required=True, help='UTILIZADOR/REPOSITORIO')
    ap.add_argument('--tag', required=True, help='ex: v0.1.0')
    ap.add_argument('--anterior', type=Path, help='manifest.json da release anterior, se existir')
    ap.add_argument('--saida', type=Path, default=Path('publicacao'))
    args = ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo): ap.error('Repositorio invalido')
    if not re.fullmatch(r'v?[A-Za-z0-9_.-]+', args.tag): ap.error('Tag invalida')
    if not args.cliente.is_dir(): ap.error('Pasta do cliente nao existe')
    previous = {}
    if args.anterior and args.anterior.is_file():
        doc=json.loads(args.anterior.read_text(encoding='utf-8'))
        previous={x['path']:x for x in doc.get('files',[])}
    assets = args.saida/'assets'
    assets.mkdir(parents=True,exist_ok=True)
    for stale in assets.iterdir():
        if stale.is_file(): stale.unlink()
    output=[]
    changed=[]
    for f in sorted(args.cliente.rglob('*')):
        if not f.is_file() or f.is_symlink(): continue
        rel=f.relative_to(args.cliente).as_posix()
        if not allowed(rel):continue
        # O validador do patcher no Windows so aceita caminhos ASCII sem espacos.
        if not re.fullmatch(r'[A-Za-z0-9_./-]+', rel) or '..' in rel:
            raise RuntimeError(f'Caminho nao suportado pelo atualizador: {rel}')
        size=f.stat().st_size
        if size >= 2*1024**3: raise RuntimeError(f'Ficheiro ultrapassa 2GiB: {rel}')
        digest=hashlib.sha256()
        with f.open('rb') as fh:
            for part in iter(lambda:fh.read(8*1024*1024),b''):digest.update(part)
        sha=digest.hexdigest()
        old=previous.get(rel)
        if old and old.get('sha256')==sha and old.get('size')==size and old.get('url', '').startswith(f'https://github.com/{args.repo}/releases/download/'):
            url=old['url']
        else:
            safe=re.sub(r'[^A-Za-z0-9._-]','_',f.name)[:75]
            asset_name='mt2_'+hashlib.sha256(rel.encode('utf-8')).hexdigest()[:12]+'_'+sha[:12]+'_'+safe
            url=f'https://github.com/{args.repo}/releases/download/{args.tag}/{asset_name}'
            shutil.copy2(f,assets/asset_name)
            changed.append((rel,size,asset_name))
        output.append({'path':rel,'size':size,'sha256':sha,'url':url})
    if not output:raise RuntimeError('Nao foram encontrados ficheiros autorizados; confirma --cliente')
    if len(output)>999:raise RuntimeError('Mais de 999 ficheiros. Agrupa os packs ou utiliza outro alojamento.')
    manifest={'schema':1,'version':args.tag,'files':output}
    (assets/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (args.saida/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (args.saida/'ALTERADOS.txt').open('w',encoding='utf-8') as out:
        for rel,size,name in changed:out.write(f'{rel}\t{size} bytes\t{name}\n')
    print(f'Repo: {args.repo} | Tag: {args.tag}')
    print(f'Ficheiros totais: {len(output)} | Para carregar no GitHub: {len(changed)} + manifest.json')
    print(f'Pasta dos assets: {assets.resolve()}')
    print('IMPORTANTE: publica a release (nao pre-release) so depois de carregar todos os assets.')

if __name__=='__main__': main()

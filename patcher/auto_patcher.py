#!/usr/bin/env python3
# Publicador local de patches do Metin2 Portugalia - Python 3.9+ / Windows.
# Nao inclui tokens; utiliza a autenticacao do GitHub CLI (gh auth login).
"""Comandos: scan | baseline | run | publish

scan: examina os ficheiros autorizados e atualiza o indice versionado.
baseline: memoriza o commit publicado e ativa a referencia inicial (sem publicar).
run: scan, seguido de verificacao do Push; publica caso exista commit novo.
publish: publica apos Push (sem atualizar o indice).
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from preparar_release import allowed

ROOT = Path(__file__).resolve().parent.parent
REPO = 'M0hamede/PortugaliaMT2-Patches'
BRANCH = 'main'
INDEX = ROOT / 'patcher' / 'estado_cliente.json'
APP = Path(os.environ.get('LOCALAPPDATA', str(ROOT))) / 'PortugaliaMT2Patcher'
STATE = APP / 'estado_publicador.json'
CACHE = APP / 'cache_hashes.json'
PREP = Path(__file__).with_name('preparar_release.py')


def cmd(*args, capture=True, timeout=180):
    command = [str(a) for a in args]
    r = subprocess.run(command, cwd=str(ROOT), capture_output=capture,
                       text=True, encoding='utf-8', errors='replace', timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"Falhou: {' '.join(command[:3])}\n{r.stderr or r.stdout or 'Sem detalhes'}")
    return (r.stdout or '').strip() if capture else ''


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.writing')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def load_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {} if default is None else default


def hash_file(path):
    d = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            d.update(chunk)
    return d.hexdigest()


def scan():
    old = load_json(CACHE)
    new = {}
    entries = []
    for f in sorted(ROOT.rglob('*')):
        if not f.is_file() or f.is_symlink():
            continue
        rel = f.relative_to(ROOT).as_posix()
        if not allowed(rel):
            continue
        if not re.fullmatch(r'[A-Za-z0-9_./-]+', rel) or '..' in rel:
            raise RuntimeError('Caminho nao suportado pelo patcher: ' + rel)
        stat = f.stat()
        cache = old.get(rel, {})
        if cache.get('size') == stat.st_size and cache.get('mtime_ns') == stat.st_mtime_ns and cache.get('sha256'):
            sha = cache['sha256']
        else:
            sha = hash_file(f)
        new[rel] = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns, 'sha256': sha}
        entries.append({'path': rel, 'size': stat.st_size, 'sha256': sha})
    if not entries:
        raise RuntimeError('Nao foram encontrados ficheiros de cliente autorizados.')
    # A listagem e ordenada; so conteudo e hashes entram no commit (nunca timestamps).
    data = {'schema': 1, 'files': entries}
    prior = load_json(INDEX)
    if prior != data:
        save_json(INDEX, data)
        print(f'Indice atualizado: {len(entries)} ficheiros. Faz Commit + Push no GitHub Desktop.')
    else:
        print(f'Indice sem alteracoes: {len(entries)} ficheiros.')
    save_json(CACHE, new)
    return data


def get_sha_local():
    branch = cmd('git', 'branch', '--show-current')
    if branch != BRANCH:
        raise RuntimeError(f'Branch local {branch!r}. Usa {BRANCH!r} para publicar.')
    return cmd('git', 'rev-parse', 'HEAD')


def get_sha_remote():
    result = cmd('git', 'ls-remote', 'origin', f'refs/heads/{BRANCH}')
    if not result:
        raise RuntimeError('Branch remota nao encontrada.')
    return result.split()[0]


def committed_index():
    raw = cmd('git', 'show', 'HEAD:patcher/estado_cliente.json')
    obj = json.loads(raw)
    if obj.get('schema') != 1 or not obj.get('files'):
        raise RuntimeError('Indice de cliente do commit invalido.')
    return obj


def verify_git_and_index(current):
    local = get_sha_local()
    remote = get_sha_remote()
    if local != remote:
        print('Commit local ainda nao enviado ao GitHub. Aguarda Push origin.')
        return None
    commit = committed_index()
    if commit != current:
        print('Ficheiros do cliente diferentes dos incluidos no ultimo commit. Faz Commit + Push do indice atualizado.')
        return None
    return local


def get_latest_manifest(tmp):
    tag = cmd('gh', 'release', 'view', '--repo', REPO, '--json', 'tagName', '--jq', '.tagName')
    if not tag:
        raise RuntimeError('Nao existe Release publicada no GitHub.')
    cmd('gh', 'release', 'download', tag, '--repo', REPO, '--pattern', 'manifest.json', '--dir', tmp, timeout=240)
    path = Path(tmp) / 'manifest.json'
    doc = load_json(path)
    if doc.get('schema') != 1 or not doc.get('files'):
        raise RuntimeError('manifest.json remoto invalido.')
    return tag, path, doc


def next_tag(tag):
    match = re.fullmatch(r'v(\d+)\.(\d+)\.(\d+)', tag)
    if not match:
        raise RuntimeError('Tag nao tem formato vX.Y.Z: ' + tag)
    a, b, c = map(int, match.groups())
    return f'v{a}.{b}.{c+1}'


# Unica excecao de migracao permitida: executaveis antigos que deixaram
# de existir na pasta distribuida. Nunca sao apagados nos clientes instalados.
LEGACY_EXECUTABLES = frozenset(('config.exe', 'metin2client.exe'))


def changed_count(previous, current):
    old = {x['path']: x for x in previous['files']}
    present = {x['path']: x for x in current['files']}
    deleted = sorted(set(old) - set(present))
    unexpected = [path for path in deleted if path not in LEGACY_EXECUTABLES]
    if unexpected:
        raise RuntimeError('Ha ficheiros removidos. O patcher atual nao remove ficheiros nos clientes: ' + ', '.join(unexpected[:8]))
    if deleted:
        if 'MT2Moonrise.exe' not in present:
            raise RuntimeError('Migracao de executaveis bloqueada: MT2Moonrise.exe nao esta no indice atual.')
        print('MIGRACAO_EXE: nomes antigos omitidos do novo manifesto (sem apagar nos clientes): ' + ', '.join(deleted))
    return sum(old.get(path, {}).get('sha256') != obj['sha256'] for path, obj in present.items())


def release_details(tag):
    try:
        return json.loads(cmd('gh', 'release', 'view', tag, '--repo', REPO, '--json', 'isDraft,assets'))
    except RuntimeError as exc:
        # Evitar esconder erros de rede/autorizacao como se nao existisse a Release.
        msg = str(exc).lower()
        if 'not found' in msg or 'release not found' in msg or '404' in msg:
            return None
        raise


def release(current, sha):
    APP.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='portugalia_patch_') as tmp:
        latest, previous_path, previous = get_latest_manifest(tmp)
        n = changed_count(previous, current)
        if n == 0:
            print('Nao existem novos ficheiros para publicar nesta versao.')
            return False
        tag = next_tag(latest)
        folder = APP / 'publicacoes' / tag
        cmd(sys.executable, PREP, '--cliente', ROOT, '--repo', REPO,
            '--tag', tag, '--anterior', previous_path, '--saida', folder,
            timeout=7200)
        generated = load_json(folder / 'manifest.json')
        if ({x['path']: (x['size'], x['sha256']) for x in generated['files']} !=
                {x['path']: (x['size'], x['sha256']) for x in current['files']}):
            raise RuntimeError('O cliente mudou durante a preparacao. Faz novo Commit + Push antes de publicar.')
        assets = sorted((folder / 'assets').iterdir())
        if len(assets) != n + 1:
            raise RuntimeError('Numero de assets inesperado: ' + str(len(assets)))
        draft = release_details(tag)
        if draft is None:
            cmd('gh', 'release', 'create', tag, '--repo', REPO, '--draft',
                '--target', sha, '--title', f'PortugaliaMT2 - Patch {tag}',
                '--notes', f'Atualizacao automatica: {n} ficheiro(s) alterado(s).',
                timeout=240)
        elif not draft['isDraft']:
            raise RuntimeError('A release ' + tag + ' ja foi publicada. Rever manualmente.')
        for path in assets:
            # Manifesto sempre em ultimo: publicacao ocorre depois de validar todos.
            if path.name == 'manifest.json':
                continue
            existing = release_details(tag)
            found = {a['name'] for a in existing['assets']}
            if path.name not in found:
                print(f'A enviar {path.name} ({path.stat().st_size} bytes)...', flush=True)
                cmd('gh', 'release', 'upload', tag, path, '--repo', REPO, timeout=7200)
        manifest = folder / 'assets' / 'manifest.json'
        existing = release_details(tag)
        found = {a['name'] for a in existing['assets']}
        if manifest.name not in found:
            cmd('gh', 'release', 'upload', tag, manifest, '--repo', REPO, timeout=300)
        existing = release_details(tag)
        found = {a['name'] for a in existing['assets']}
        expected = {x.name for x in assets}
        if not expected.issubset(found):
            raise RuntimeError('Upload incompleto. A release fica em rascunho.')
        cmd('gh', 'release', 'edit', tag, '--repo', REPO, '--draft=false', '--latest', timeout=240)
        print(f'PATCH PUBLICADO: {tag} | {n} ficheiros alterados')
        return True


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('scan', 'baseline', 'run', 'publish'):
        raise SystemExit('Uso: python auto_patcher.py [scan|baseline|run|publish]')
    mode = sys.argv[1]
    if mode == 'scan':
        scan()
        return
    if mode == 'baseline':
        current = scan()
        sha = verify_git_and_index(current)
        if not sha:
            raise RuntimeError('Faz Commit + Push do estado_cliente.json antes de instalar a automacao.')
        tag = cmd('gh', 'release', 'view', '--repo', REPO, '--json', 'tagName', '--jq', '.tagName')
        save_json(STATE, {'last_sha': sha, 'last_tag': tag})
        print(f'Baseline criada em {sha[:10]} / Release {tag}.')
        return
    if mode == 'run':
        current = scan()
    else:
        current = load_json(INDEX)
    sha = verify_git_and_index(current)
    if not sha:
        return
    state = load_json(STATE)
    if not state.get('last_sha'):
        print('Falta baseline: instala a tarefa com instalar_tarefa.ps1.')
        return
    if sha == state['last_sha']:
        print('Nenhum Push novo desde a ultima verificacao.')
        return
    release(current, sha)
    save_json(STATE, {'last_sha': sha, 'last_tag': cmd('gh', 'release', 'view', '--repo', REPO, '--json', 'tagName', '--jq', '.tagName')})
    print('Commit verificado e registado.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERRO:', exc, file=sys.stderr)
        sys.exit(1)

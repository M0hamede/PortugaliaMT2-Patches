#!/usr/bin/env python3
# Actualiza exclusivamente a whitelist do exe Moonrise no preparar_release.py.
# Nao altera auto_patcher.py, packs, EXEs ou qualquer fonte do cliente.
import argparse
import datetime
import hashlib
import os
import sys
from pathlib import Path

OLD = b"'metin2client.exe','config.exe'"
NEW = b"'metin2client.exe','mt2moonrise.exe','config.exe'"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description='Autorizar MT2Moonrise.exe no publicador de patches')
    parser.add_argument('--cliente', required=True, type=Path, help='Pasta principal Metin2FullClient')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--aplicar', action='store_true')
    group.add_argument('--repor', metavar='BACKUP', type=Path)
    args = parser.parse_args()
    root = args.cliente.resolve()
    path = root / 'patcher' / 'preparar_release.py'
    if not path.is_file():
        parser.error('Nao existe ' + str(path))
    original = path.read_bytes()
    if args.repor:
        src = args.repor.resolve()
        if not src.is_file() or src.name != 'preparar_release.py.bak':
            parser.error('BACKUP deve ser o ficheiro preparar_release.py.bak criado por este instalador')
        restore = src.read_bytes()
        compile(restore, str(src), 'exec')
        if original == restore:
            print('JA_REPOSTO: sem alteracoes.')
            return
        temp = path.with_suffix(path.suffix + '.moonrise_tmp')
        try:
            temp.write_bytes(restore)
            os.replace(temp, path)
        finally:
            if temp.exists(): temp.unlink()
        print('REPOSTO:', path)
        return

    if original.count(NEW) == 1:
        print('INSTALADO:', path)
        changed = False
    elif original.count(OLD) == 1 and original.count(NEW) == 0:
        print('ATUALIZAR:', path)
        changed = True
    else:
        raise RuntimeError('O filtro atual difere do esperado. Nao foi alterado: ' + str(path))

    exe = root / 'MT2Moonrise.exe'
    if not exe.is_file():
        exe = next((p for p in root.iterdir() if p.is_file() and p.name.lower() == 'mt2moonrise.exe'), None)
    print('EXE_CLIENTE:', str(exe) if exe else 'NAO ENCONTRADO na raiz do cliente')
    if not exe:
        print('AVISO: o patcher so incluiria MT2Moonrise.exe na raiz do cliente.')

    if args.check:
        print('CHECK_OK: nenhuma alteracao efetuada.')
        return
    if not changed:
        print('APLICAR_OK: filtro ja atualizado; nenhuma alteracao necessaria.')
        return
    patched = original.replace(OLD, NEW, 1)
    compile(patched, str(path), 'exec')
    backups = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'PortugaliaMT2Patcher' / 'backups' / 'filtro_exe'
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    folder = backups / stamp
    folder.mkdir(parents=True, exist_ok=False)
    backup = folder / 'preparar_release.py.bak'
    backup.write_bytes(original)
    if backup.read_bytes() != original:
        raise RuntimeError('Backup falhou. Nao foram alteradas as fontes.')
    temp = path.with_suffix(path.suffix + '.moonrise_tmp')
    try:
        temp.write_bytes(patched)
        if sha256(temp.read_bytes()) != sha256(patched):
            raise RuntimeError('Validacao da escrita temporaria falhou.')
        os.replace(temp, path)
    finally:
        if temp.exists(): temp.unlink()
    print('APLICADO:', path)
    print('BACKUP:', backup)
    print('NOVO_SHA256:', sha256(patched))
    print('APLICAR_OK: apenas a whitelist de mt2moonrise.exe foi alterada.')

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, SyntaxError) as exc:
        print('ERRO:', exc, file=sys.stderr)
        sys.exit(1)

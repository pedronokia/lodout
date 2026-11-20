"""Empacota, cifra (AES-256-CBC + PBKDF2 via openssl) e envia o backup mais
recente do Lodout para um destino off-site (ex.: Oracle Object Storage PAR
com permissão só de escrita — 20 GB Always Free — ou qualquer endpoint
HTTPS que aceite PUT). Também decifra pra restauração em 1 comando.

Uso:
    # Empacotar + cifrar localmente (sem subir):
    BACKUP_PASSPHRASE='...' python scripts/backup_offsite.py empacotar /data/backups -o /tmp/backup.tar.gz.enc

    # Empacotar + cifrar + enviar via HTTP PUT (usado pelo backup-offsite.yml):
    BACKUP_PASSPHRASE='...' BACKUP_UPLOAD_URL='https://.../o/' \
      python scripts/backup_offsite.py enviar /data/backups

    # Decifrar pra restaurar:
    BACKUP_PASSPHRASE='...' python scripts/backup_offsite.py decifrar lodout-backup-20261120-043000.tar.gz.enc -o restaurar.tar.gz
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

_PADROES = (
    "public_site-*.db",
    "notas_historico-*.sqlite3",
    "json-*.zip",
)
_PBKDF2_ITER = "200000"
_TIMEOUT_UPLOAD_S = 120.0


def selecionar_mais_recentes(backup_dir: "Path | str") -> list[Path]:
    """Seleciona o arquivo mais recente de cada família de backup em `backup_dir`."""
    pasta = Path(backup_dir)
    if not pasta.exists():
        return []
    escolhidos: list[Path] = []
    for padrao in _PADROES:
        candidatos = sorted(p for p in pasta.glob(padrao) if p.is_file())
        if candidatos:
            escolhidos.append(candidatos[-1])
    return escolhidos


def criar_pacote_tar_gz(arquivos: list[Path], destino: Path) -> Path:
    """Empacota `arquivos` em `destino` (.tar.gz) usando só nomes base."""
    if not arquivos:
        raise ValueError("nenhum arquivo de backup encontrado para empacotar")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destino, "w:gz") as tf:
        for arq in arquivos:
            tf.add(arq, arcname=arq.name)
    return destino


def cifrar_arquivo(origem: Path, destino: Path, senha: str) -> Path:
    """Cifra `origem` -> `destino` com AES-256-CBC + PBKDF2 + salt via openssl."""
    if not senha or len(senha) < 12:
        raise ValueError("BACKUP_PASSPHRASE precisa ter ao menos 12 caracteres")
    env = dict(os.environ, _LODOUT_ENC_PASS=senha)
    subprocess.run(
        [
            "openssl", "enc", "-aes-256-cbc", "-pbkdf2",
            "-iter", _PBKDF2_ITER, "-salt",
            "-in", str(origem), "-out", str(destino),
            "-pass", "env:_LODOUT_ENC_PASS",
        ],
        check=True,
        env=env,
        capture_output=True,
    )
    return destino


def decifrar_arquivo(origem: Path, destino: Path, senha: str) -> Path:
    """Decifra `origem` (.enc) -> `destino` usando a mesma senha."""
    if not senha:
        raise ValueError("BACKUP_PASSPHRASE ausente")
    env = dict(os.environ, _LODOUT_ENC_PASS=senha)
    subprocess.run(
        [
            "openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2",
            "-iter", _PBKDF2_ITER,
            "-in", str(origem), "-out", str(destino),
            "-pass", "env:_LODOUT_ENC_PASS",
        ],
        check=True,
        env=env,
        capture_output=True,
    )
    return destino


def enviar_http_put(arquivo: Path, upload_url_prefix: str, timeout: float = _TIMEOUT_UPLOAD_S) -> int:
    """Envia `arquivo` via HTTP PUT para `<upload_url_prefix>/<arquivo.name>`.

    Nunca imprime a URL (pode conter token de PAR/presigned URL).
    """
    prefixo = (upload_url_prefix or "").strip()
    if not prefixo.startswith("https://"):
        raise ValueError("BACKUP_UPLOAD_URL precisa começar com https://")
    destino = f"{prefixo.rstrip('/')}/{arquivo.name}"
    dados = arquivo.read_bytes()
    req = urllib.request.Request(
        destino,
        data=dados,
        method="PUT",
        headers={
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(dados)),
            "User-Agent": "Lodout-BackupOffsite/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = int(resp.status)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"upload rejeitado com HTTP {e.code}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"falha de rede no upload: {e.reason}") from None
    if status not in (200, 201, 204):
        raise RuntimeError(f"upload retornou HTTP inesperado: {status}")
    return status


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Backup off-site cifrado do Lodout.")
    sub = parser.add_subparsers(dest="acao", required=True)

    p_emp = sub.add_parser("empacotar", help="Empacota e cifra os backups mais recentes.")
    p_emp.add_argument("backup_dir", help="Pasta com os backups (ex.: /data/backups)")
    p_emp.add_argument("-o", "--saida", required=True, help="Arquivo .tar.gz.enc de saída")

    p_env = sub.add_parser("enviar", help="Empacota, cifra e envia via HTTPS PUT.")
    p_env.add_argument("backup_dir", help="Pasta com os backups (ex.: /data/backups)")

    p_dec = sub.add_parser("decifrar", help="Decifra um arquivo .tar.gz.enc.")
    p_dec.add_argument("entrada", help="Arquivo .tar.gz.enc cifrado")
    p_dec.add_argument("-o", "--saida", required=True, help="Arquivo .tar.gz decifrado")

    args = parser.parse_args(argv)
    senha = os.environ.get("BACKUP_PASSPHRASE", "").strip()

    if args.acao == "decifrar":
        decifrar_arquivo(Path(args.entrada), Path(args.saida), senha)
        print(f"OK: decifrado em {args.saida}")
        return 0

    arquivos = selecionar_mais_recentes(args.backup_dir)
    if not arquivos:
        print(f"Nenhum backup encontrado em {args.backup_dir}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="lodout-offsite-") as tmp:
        tmp_dir = Path(tmp)
        tar_path = criar_pacote_tar_gz(arquivos, tmp_dir / "pacote.tar.gz")
        if args.acao == "empacotar":
            saida = Path(args.saida)
            cifrar_arquivo(tar_path, saida, senha)
            print(f"OK: {len(arquivos)} arquivo(s) empacotado(s) e cifrado(s) em {saida}")
            return 0

        nome = time.strftime("lodout-backup-%Y%m%d-%H%M%S.tar.gz.enc", time.gmtime())
        enc_path = cifrar_arquivo(tar_path, tmp_dir / nome, senha)
        upload_url = os.environ.get("BACKUP_UPLOAD_URL", "").strip()
        status = enviar_http_put(enc_path, upload_url)
        print(
            f"OK: {enc_path.name} ({enc_path.stat().st_size} B, "
            f"{len(arquivos)} arquivos) enviado (HTTP {status})"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())

#!/bin/sh
# Entrypoint do site público -- roda como root só o tempo necessário
# pra corrigir a posse de /data, depois cede o processo principal
# (gunicorn do "web" ou "python -m ...worker" do "worker") pro usuário
# sem privilégio `lodout` (achado de auditoria, skill docker-
# security-guide, 2026-11-05: a imagem rodava como root inteira,
# nenhum USER no Dockerfile).
#
# O ajuste de posse e' necessario (nao cosmetico): um volume novo ou
# legado (`skinvault_data` de antes de 2026-11-05) pode chegar como
# root:root. Porem rodar `chown -R` incondicional em todo start fazia o
# container levar ~45 s percorrendo milhares de arquivos em icon_cache/
# e og_cache/. Conferindo a raiz de /data primeiro e depois apenas o
# nivel 1 (bancos, JSONs, chave e pastas imediatas), a subida cai pra
# menos de 1 s sem perder a garantia de posse.
set -e
uid_gid="$(id -u lodout):$(id -g lodout)"
if [ "$(stat -c '%u:%g' /data)" != "$uid_gid" ]; then
    chown -R lodout:lodout /data
else
    find /data -maxdepth 1 \( ! -user lodout -o ! -group lodout \) -exec chown -R lodout:lodout {} +
fi
exec su -s /bin/sh lodout -c 'exec "$0" "$@"' -- "$@"

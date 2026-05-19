# Lições Aprendidas — LTO SG1 Rotate do Homelab — 2026-05-19

## L1. Diretório existente nao prova que a fita esta montada

`/mnt/tape_sg1/logs` existia no host, mas isso escondia o problema principal: o CIFS `LTO6_SG1` estava desmontado. Em pipelines de arquivamento, validar apenas `ls` ou `mkdir -p` no destino nao basta; e necessario testar `mountpoint`.

## L2. Drain para storage remoto precisa de guarda de mount, nao so de path

O `tape-log-spool-drain` escrevia corretamente para o destino configurado, mas o destino ja nao era mais a fita e sim um diretório local subjacente. Scripts de drain para CIFS/NFS/LTFS precisam falhar cedo quando o mount exigido nao esta ativo.

## L3. Automount reduz janelas de falha para mounts de fita exportados

O `fstab` sozinho deixava o `sg1` dependente de uma tentativa pontual de mount. O `mnt-tape_sg1.automount` tornou a recuperacao sob demanda e melhorou o comportamento apos falhas transientes entre homelab e NAS.

## L4. Logrotate falha silenciosamente em cenarios de permissao insegura

Sem `su root root`, o `logrotate` simplesmente pulava `create_snapshot.log` e impedia a formacao da fila. Quando houver `parent directory has insecure permissions`, a acao correta e ajustar o snippet, nao forcar retries do timer.

## L5. Mount perdido pode gerar backlog invisivel sob o mesmo path

Quando o CIFS caiu, o drain passou a gravar sob o mesmo caminho montável. Depois que o mount voltou, esses arquivos ficaram ocultos. Em incidentes com mount remoto, sempre considerar a existencia de backlog no diretório subjacente antes de declarar o fluxo recuperado.

## L6. Recuperacao completa exige reconciliar dados, nao apenas religar servicos

Levantar `mnt-tape_sg1` e ver o timer `active` nao bastava. O saneamento so ficou completo apos:

- reenviar o backlog local oculto
- confirmar a presenca final na LTFS do NAS
- zerar a fila `routes/tape_sg1`
- testar novo rotate de ponta a ponta

## L7. A fita logica sg1 pode continuar existindo mesmo com o device fisico mudando

No NAS, a fita logica `sg1` continua valida, mas o drive real hoje e `/dev/sg2` com `/dev/nst2`. O erro operacional mais perigoso aqui e confundir nome logico de fluxo com node fisico do kernel.

## L8. Documentacao operacional deve separar nome logico, mount exportado e device real

Para esse stack, os tres niveis precisam aparecer juntos:

- nome logico: `sg1`
- exportacao consumida pelo homelab: `//192.168.15.4/LTO6_SG1`
- device LTFS real no NAS: `/dev/sg2` e `/mnt/tape/lto6-sg1`

Sem essa separacao, drift de documentacao vira drift operacional.

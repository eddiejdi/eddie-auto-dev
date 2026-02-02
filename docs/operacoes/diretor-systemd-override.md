## Correção: `diretor.service` - escape de caracteres em `DATABASE_URL`

Problema
-------
Ao definir a variável de ambiente `DATABASE_URL` no drop-in do systemd para o serviço `diretor.service`, o caractere `%` presente na senha foi interpretado pelo systemd como um *specifier* inválido, fazendo com que a linha fosse ignorada e o serviço não estabelecesse polling no DB.

Diagnóstico
----------
- Erro nos logs: "Failed to resolve specifiers in DATABASE_URL=... ignoring: Invalid slot".
- O motivo é que systemd usa `%` para specifiers; para usar um `%` literal é necessário escapá-lo como `%%`.

Correção aplicada
-----------------
1. Atualizei o drop-in de override em `/etc/systemd/system/diretor.service.d/override.conf` para escapar o caractere `%` na URL, por exemplo:

```
[Service]
Environment="DATABASE_URL=postgresql://eddie:Eddie%%402026@localhost:5432/eddie_bus"
```

2. Recarreguei o systemd e reiniciei o serviço:

```
sudo systemctl daemon-reload
sudo systemctl restart diretor.service
sudo systemctl status diretor.service --no-pager
```

Verificação
-----------
- Logs confirmaram: `[Diretor] DB polling enabled` e requests do DB sendo processados.
- Use `journalctl -u diretor.service -f` para acompanhar em tempo real.

Recomendações
------------
- Prefira injetar segredos via um arquivo `.env` gerenciado ou via systemd `EnvironmentFile=` em vez de colocar senhas diretamente no unit drop-in.
- Ao usar `Environment=` em systemd, lembre-se de escapar `%` como `%%` em valores literais.
- Considere migrar segredos para o Bitwarden (ou similar) e inserir via CI/CD seguro.

Notas de auditoria
-----------------
- Commit que documenta esta correção: "docs: document systemd DATABASE_URL percent-escape fix".

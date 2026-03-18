# Homelab btop Fix (GPU1 + Discos) - 2026-03-18

## Contexto

- Host: `homelab` (`192.168.15.2`)
- Usuário: `homelab`
- Sintoma inicial: `btop` mostrava apenas `GPU0`
- Após habilitar `gpu1`, novo sintoma: `btop` abortava com assertion em `std::vector`:
  - `/usr/include/c++/13/bits/stl_vector.h:1125 ... Assertion '__n < this->size()' failed.`

## Diagnóstico

1. Driver NVIDIA estava correto:
   - `nvidia-smi -L` retornou `GPU 0` (RTX 2060 SUPER) e `GPU 1` (GTX 1050).
2. Causa 1 (GPU1 ausente):
   - `shown_boxes` não incluía GPUs.
3. Causa 2 (crash):
   - Na versão `btop 1.3.0`, combinação `shown_boxes` com `gpu0 gpu1` + `show_gpu_info = "On"` reproduz abort.
4. Validação de workaround:
   - `show_gpu_info = "Auto"` estabiliza.

## Ajustes aplicados

Arquivo alterado no host:
- `~/.config/btop/btop.conf`

Estado final aplicado:

```ini
shown_boxes = "cpu mem net proc gpu0 gpu1"
show_gpu_info = "Auto"
show_disks = True
io_mode = False
show_io_stat = True
proc_filter_kernel = True
```

### Resultado esperado no layout

- `GPU0` e `GPU1` visíveis
- Discos visíveis com barra de uso em `%` (progressbar)
- Menos ruído na lista de processos (filtro de kernel)
- `btop` sem abort na resolução usada na sessão

## Evidências rápidas

- `btop --version`: `1.3.0`
- `nvidia-smi -L`: 2 GPUs detectadas
- Teste de estabilidade pós-fix em sessão pseudo-interativa (`tmux`): sem crash

## Rollback

Foram gerados backups automáticos de `btop.conf` em:

- `~/.config/btop/btop.conf.bak-20260318-174424`
- `~/.config/btop/btop.conf.bak-20260318-<timestamp>-gpufix`
- `~/.config/btop/btop.conf.bak-20260318-<timestamp>-disks`
- `~/.config/btop/btop.conf.bak-20260318-<timestamp>-diskbar`

Para reverter:

```bash
cp ~/.config/btop/btop.conf.bak-<timestamp> ~/.config/btop/btop.conf
```

## Operação

Na sessão SSH já aberta, após alterações:

```bash
reset
btop
```

## Nota técnica

Se for necessário usar `show_gpu_info = "On"` com duas GPUs, considerar upgrade do `btop` para versão superior a `1.3.0` e revalidar a mesma matriz de testes.

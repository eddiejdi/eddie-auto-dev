"""Bridge PandaPlus ↔ Telegram.

Detecta eventos da fechadura PandaPlus na nuvem Tuya (DP `unlock_request` e
`alarm_lock`) e envia notificações para o Telegram. Quando o modo de resposta
está habilitado, recebe aprovação/negação via HTTP local e envia comando
`reply_unlock_request` para a fechadura.
"""

__version__ = "0.1.0"

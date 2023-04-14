#!/usr/bin/env python

import apprise

bot_token = "5198410262:AAFfyI5u-HLBXqbzsm2bx7dEy1vuTqZoKD0"
chat_id = "-1001261613616"

# Crea un objeto de la clase "Apprise" con la URL de la API de Telegram, el token de acceso de tu bot y el chat_id del chat al que deseas enviar la notificación
apobj = apprise.Apprise()
apobj.add(f'tgram://{bot_token}/{chat_id}/', tag='telegram')

# Envía una notificación a Telegram
apobj.notify(title='Prueba de notificación', body='Esta es una notificación de prueba enviada desde Python usando Apprise y Telegram.', tag='telegram')

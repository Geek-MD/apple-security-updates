# Apple Security Updates Notifier

Python script that checks for Apple software updates, and notifies via Telegram Bot.

## Basic installation and configuration

This script relies on a previously created Telegram bot. If you don't have one follow [this steps](https://www.alphr.com/telegram-create-bot/) to create one.

Clone this repo with...
  
```
git clone https://github.com/Geek-MD/apple-security-updates-notifier.git
```

Now open ***config.json*** with the editor of your preference, and change *"timezone"*, *"bot_token"* and *"chat_id_n"* with their corresponding values.

Now, you have to create a cron job which will execute the script at a defined time and day. In the example, the script will run every 4 hours from monday to sunday.

```
crontab -e
0 */4 * * * python3 /home/emontes/python/apple-security-updates-notifier/asun.py
Ctrl O
Ctrl X
```

Obviously you can change change the time interval at wich the script is executed, modifying the cron command. I recomend [https://crontab.guru](https://crontab.guru) to do that.

Finally you have to reboot so changes take effect.

```
sudo reboot
```

## Note

This is a first workaround attempt for a persistent bot in the near future.

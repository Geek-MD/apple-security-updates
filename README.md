# Apple Security Updates Notifier

Python script that checks for Apple software updates, and notifies via Telegram Bot.

## Previous steps

This script relies on a previously created Telegram bot. If you don't have one follow [this steps](https://www.alphr.com/telegram-create-bot/) to create one. You need your bot token at hand in order to run this script.

## Basic installation and configuration

Clone this repo with...
  
```
git clone https://github.com/Geek-MD/apple-security-updates-notifier.git
```

To run the script you must add *-b* or *--bot-token* option followed by the bot token itself. Bot token is mandatory, if you don't provide it, the script will exit with an error. Timezone or country arguments are optional. The default timezone is UTC.
The basic syntax to run the script is as the following examples.

```
python3 config.py -b <bot_token>
python3 config.py --bot-token <bot_token>
```

You can check the script help by using *-h* or *--help* option.

```
python3 config.py -h
python3 config.py --help
```

You can check the script version by using *-v* or *--version* option.

```
python3 config.py -v
python3 config.py --version
```

## Advanced configuration

There are two options, independent one from the other, to define the time zone of the bot. You can use timezone or country options. Remember that this is optional.
Additionally, you can define the chat ids where Telegram notifications will be sent.  

### Timezone or country configuration

If you don't provide timezone or country at startup, the script will display a dialog indicating that the default timezone is *"UTC"* and asking if you're OK with that.
If you answer *"no"*, the script will try to identify your country based on the IP address and will ask if that guess is OK or not.
If you answer *"yes"*, the script will display a list with all the timezones associated to that country, and will ask for a selection. Type in the option of your choice. If you want to switchback to the default timezone *(UTC)*, type *"0"* in answer to that dialog.

For timezone configuration you can use *-t* or *--timezone* followed by the timezone according to IANA Zone ID list (http://nodatime.org/TimeZones). Alternatively you may use *'x'* or *'X'* as argument, so the script will try to identify your country based on the IP address.

```
python3 config.py -b <bot_token> -t <timezone>
python3 config.py --bot-token <bot_token> --timezone x
```

For timezone configuration through country code, you can use *-c* or *--country* followed by the country code according to ISO Alpha-2 codes (http://iban.com/country-codes). Country code is a 2-letter code in upper case, but this script accepts it in lower case. Alternatively you may use *'x'* or *'X'* as argument, so the script will try to identify your country based on the IP address.

```
python3 config.py -b <bot_token> -c <country_code>
python3 config.py --bot-token <bot_token> --country x
```

### Chat ids configuration

For chat ids configuration you can use *-i* or *--chat-ids* followed by chat ids separated by a space between them. Don't forget to add the minus sign before the numeric code of the chat id.
If you don't provide chat ids at startup, the script will ask for them one by one, and you will have to type "0" to finish the input.

```
python3 config.py -b <bot_token> -i <chat_id_1>
python3 config.py --bot-token <bot_token> --chat-ids <chat_id_1> <chat_id_2>
```

## Functionality

This piece of software comprehends 2 *.py* files, 1 *.json* file and 1 *.sh* file. Python files are *config.py* which runs just once at start, and *apple_security_updates.py* which is the persistent script. The JSON file is *asu-notifier.json* which contains some basic information for *config.py*. Finally, the bash file is *asu-notifier.sh* which contains shell commands in order to run the persistent Python script as a systemd service. 
Once the script is run, it will automatically recreate 2 files using the information you gave it, a *asu-notifier.service* file used to start a *systemd* service, and a *config.json* file with the configuration needed by the persistent script.
Finally, the script will execute the bash file in order to enable and start the systemd service. This will take some time to start because of *ExecStartPre* section which will wait for 60 seconds. This is due to a recommendation found on several forums which intention is to ensure that the script executes only when the system is fully loaded.
When you see the system prompt, if you haven't received an error message, the script will be running in background, and you'll receive a Telegram Notification with the latest Apple Security Updates.

## Troubleshooting

Eventually, the systemd service may need to be restarted due to a system restart or by any other reason. You can do it manually using the following shell commands.

```
sudo systemctl daemon-reload
sudo systemctl enable asu-notifier.service
sudo systemctl start asu-notifier.service
```

## Note

This is a first workaround attempt for a permanent bot in the near future, instead of a self-hosted bot.
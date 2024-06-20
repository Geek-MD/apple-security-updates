# Apple Security Updates Notifier

Python script that checks for Apple software updates, and notifies via Telegram Bot.

This script relies on a previously created Telegram bot. If you don't have one follow [this steps](https://www.alphr.com/telegram-create-bot/) to create one. You need your bot token at hand in order to run this script.

## Previous steps

Clone this repo with...
  
```
git clone https://github.com/Geek-MD/apple-security-updates-notifier.git
```

Now execute the *setup.sh* file with the following command.

```
bash setup.sh
```

Once the script is finished, you will get help information on how to run the python script.

## Basic configuration

To run the script you must add *-b* or *--bot-token* option followed by the bot token itself. Bot token is mandatory, if you don't provide it, the script will exit with an error. Timezone or country arguments are optional. The default timezone is UTC.
The basic syntax to run the script is as the following examples.

```
./asu-notifier.py -b <bot_token>
./asu-notifier.py --bot-token <bot_token>
```

You can check the script help by using *-h* or *--help* option.

```
./asu-notifier.py -h
./asu-notifier.py --help
```

You can check the script version by using *-v* or *--version* option.

```
./asu-notifier.py -v
./asu-notifier.py --version
```

## Advanced configuration

There are two options, independent one from the other, to define the bot timezone. You can use timezone or country options. Remember that this is optional.
Additionally, you can define the chat ids where Telegram notifications will be sent.  

### Timezone or country configuration

If you don't provide timezone or country at startup, the script will display a dialog indicating that the default timezone is *"UTC"* and asking if you're OK with that.
If you answer *"no"*, the script will try to identify your country based on the IP address and will ask if that guess is OK or not.
If you answer *"yes"*, the script will display a list with all the timezones associated to that country, and will ask for a selection. Type in the option of your choice. If you want to switchback to the default timezone *(UTC)*, type *"0"* in answer to that dialog.

For timezone configuration you can use *-t* or *--timezone* followed by the timezone according to IANA Zone ID list (http://nodatime.org/TimeZones). Alternatively you may use *'x'* or *'X'* as argument, so the script will try to identify your country based on the IP address.

```
./asu-notifier.py -b <bot_token> -t <timezone>
./asu-notifier.py --bot-token <bot_token> --timezone x
```

For timezone configuration through country code, you can use *-c* or *--country* followed by the country code according to ISO Alpha-2 codes (http://iban.com/country-codes). Country code is a 2-letter code in upper case, but this script accepts it in lower case. Alternatively you may use *'x'* or *'X'* as argument, so the script will try to identify your country based on the IP address.

```
./asu-notifier.py -b <bot_token> -c <country_code>
./asu-notifier.py --bot-token <bot_token> --country x
```

### Chat ids configuration

For chat ids configuration you can use *-i* or *--chat-ids* followed by chat ids separated by a space between them and enclosed in single hyphens. Don't forget to add the minus sign before the numeric code of the chat id.
If you don't provide chat ids at startup, the script will ask for them one by one, and you will have to type "0" to finish the input.

```
./asu-notifier.py -b <bot_token> -i <chat_id_1>
./asu-notifier.py --bot-token <bot_token> --chat-ids '<chat_id_1> <chat_id_2>'
```

# Apple Security Updates Notifier

Python script that checks for Apple software updates, and notifies via Telegram Bot.

This script relies on a previously created Telegram bot. If you don't have one follow [this steps](https://www.alphr.com/telegram-create-bot/) to create one. You need your bot token at hand in order to run this script.

## Previous steps

Clone this repo with...
  
```
git clone https://github.com/Geek-MD/apple-security-updates-notifier.git
```

Now execute the *setup.sh* file with the following command. This will install all dependencies needed by the script
listed on *requirements.txt*.

```
./setup.sh
```

Once the script is finished, you will get help information on how to run the python script.

## Basic configuration

To run the script you must add *-b* or *--bot-token* option followed by the bot token itself. Bot token is mandatory, if you don't provide it, the script will exit with an error. The script will check the bot token using a regular expression, so you can use any valid bot token. Using an invalid bot token will cause the script to exit with an error.
Timezone or country arguments are optional. The default timezone is UTC.
The basic syntax to run the script is as the following examples.

```
./asu-notifier.sh -b <bot_token>
./asu-notifier.sh --bot-token <bot_token>
```

You can check the script help by using *-h* or *--help* option.

```
./asu-notifier.sh -h
./asu-notifier.sh --help
```

You can check the script version by using *-v* or *--version* option.

```
./asu-notifier.sh -v
./asu-notifier.sh --version
```

## Advanced configuration

There are two options, independent one from the other, to define the bot timezone. You can use timezone or country
options. Remember that this is optional.
Additionally, you can define the chat ids where Telegram notifications will be sent.  

### Timezone or country configuration

If you don't provide timezone or country at startup, the script will display a dialog indicating that the default timezone is *"UTC"* and asking if you're OK with that.
If you answer *"no"*, the script will try to identify your country based on the IP address and will ask if that guess is OK or not.
If you answer *"yes"*, the script will display a list with all the timezones associated to that country, and will ask for a selection. Type in the option of your choice. If you want to switchback to the default timezone *(UTC)*, type *"0"* in answer to that dialog.

For timezone configuration you can use *-t* or *--timezone* followed by the timezone according to IANA Zone ID list (http://nodatime.org/TimeZones). Alternatively you may use *'x'* or *'X'* as argument, so the script will try to identify your country based on the IP address.

```
./asu-notifier.sh -b <bot_token> -t <timezone>
./asu-notifier.sh --bot-token <bot_token> --timezone x
```

For timezone configuration through country code, you can use *-c* or *--country* followed by the country code according to ISO Alpha-2 codes (http://iban.com/country-codes). Country code is a 2-letter code in upper case, but this script accepts it in lower case. Alternatively you may use *'x'* or *'X'* as argument, so the script will try to identify your country based on the IP address.

```
./asu-notifier.sh -b <bot_token> -c <country_code>
./asu-notifier.sh --bot-token <bot_token> --country x
```

### Channels configuration

For Telegram channels configuration you can use *-ch* or *--channels* followed by channels ids separated by a space between them. Don't forget to add the minus sign before the numeric code of the channel id. The script will check every channel id using a regular expression, so you can use any valid channel id. Using an invalid channel id will cause the script to exit with an error.
If you don't provide a channel id at startup, the script will ask for them one by one, and you will have to type "0" to finish the input.

```
./asu-notifier.sh -b <bot_token> -ch <channel_1>
./asu-notifier.sh --bot-token <bot_token> --channels <channel_1> <channel_2>
```

### Crontab configuration

This configuration is optional. The default value for the crontab is "0 */6 * * *". This means that the script will run every 6 hours. You can change it by using *-c* or *--cron* followed by the crontab expression. The script will check the crontab expression using a regular expression, so you can use any valid crontab expression. Using an invalid crontab expression will cause the script to exit with an error.
For example crontab expressions you can check at https://crontab.guru/.

```
./asu-notifier.sh -b <bot_token> -c <crontab>
./asu-notifier.sh --bot-token <bot_token> --cron <crontab>
```

## Note

This is a first workaround attempt for a permanent bot in the near future, instead of a self-hosted bot.
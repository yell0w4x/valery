# Valery: Llama based telegram bot
<p align="center">
    <img src="https://github.com/yell0w4x/assets/blob/215e53b298756a4c1d53e8ade38b34b46d05636a/valery.png" alt="Valery"/>
</p>

[@Valery](https://t.me/ValeryAIBot). 
To run own instance one needs to [create telegram bot](https://core.telegram.org/bots#how-do-i-create-a-bot). 
Obtain [https://www.anyscale.com/platform](Anyscale) and 
[https://deepgram.com](Deepgram) API token if speech recognition is necessary. 
And put them into `./config/prod.env`. See `./config/test.env.example`. 

```
VALERY_TELEGRAM_TOKEN=...
VALERY_MONGODB_URI=mongodb://mongo-db-url
VALERY_ANYSCALE_TOKEN=...
VALERY_DEEPGRAM_TOKEN=...
```

# Deploy to fly.io
One can deploy to fly.io easily. First deploy mongo instance by using this repo https://github.com/yell0w4x/fly-mongo.
Then use the deployed mongo instance name in mongo url variable as follows.

    VALERY_MONGODB_URI=mongodb://your-fly-mongo-instance.internal:27017/valery?uuidRepresentation=standard

Then deploy your bot instance via `deploy` script.

```
$ ./deploy --help
Valery bot

Fly.io based Valery bot deploy script

Usage:
    ./deploy [OPTIONS]

Options:
    --new               Launch new application using fly.toml template
    --app APP           Application name to use for deploy. Overrides one in toml file
    --envs              .env file to expose inside app container (default: prod.env)
    --image             Docker image to use as base for the app (default: python:3.11-bookworm)
    --allocate-ips      Allocate ip addresses on launch
    --debug             Set bash 'x' option
    --help              Show help message

Examples:
    Deploy new app.
    
        ./deploy --new --app mybot

    Redeploy. 
        
        ./deploy

Note:
    This script allocates shared ipv4 and ipv6 addresses that cost nothing
    Dedicated ipv4 address costs $2/month
```

# Run on prem in docker

Use `run` script. Remember to provide correct `config/prod.env`.

```
$ ./run --help
Valery bot

Run on this machine within specified environment

Usage:
    ./run [OPTIONS]

Options:
    --envs        .env file to expose inside app container (default: test.env)
    --image       Docker image to use as base for the app (default: python:3.11-bookworm)
    --detach      Detach from containers
    --stop        Stop containers
    --remove      Remove containers on stop. If no --stop given and attached to containers.
                  After containers stopped they are removed. 
    --debug       Set bash 'x' option
    --help        Show help message
```

# Run tests

To run tests one needs a telegram bot and a pyrogram session. 
To obtain pyrogram session use `e2e-tests/obtain_pyrogram_session.py`.

```
$ python e2e-tests/obtain_pyrogram_session.py --help
usage: obtain_pyrogram_session.py [-h] --session-name SESSION_NAME [--api-id API_ID] [--api-hash API_HASH]

options:
  -h, --help            show this help message and exit
  --session-name SESSION_NAME
                        Arbitrary session name
  --api-id API_ID       Telegram API id
  --api-hash API_HASH   Telegram API hash
```

It will create a file `.session`. Put it inside `e2e-tests/src` folder and run tests as follows.

    VALERY_BOT_CHAT_ID=@YourTelegramBot VALERY_BOT_SESSION_NAME=YourPyrogramSessionName ./run-tests

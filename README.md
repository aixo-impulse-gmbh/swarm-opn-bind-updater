# Swarm OPNSense bind service updater

## Current situation

I'm running my workloads as services in a docker swarm cluster. To expose those services to my internal network or the outside world, I use a Traefik reverse proxy and an OPNSense Router as a perimeter firewall and DNS server.

Exposing the services with Traefik you can usually do in two ways.

1. Running on a prefix path of the ingress
1. Running on on an own hostname pointing to the ingress

For the first approach to work the application to be exposed on a path must met some preconditions. The application must either be path agnostic or support the configuration of a base path, sometimes called base URL.

Path agnostic applications are those, where a response from the application does not return any embedded links in the response headers or the body. That also applies to redirects, e.g. to a login page.

If your application meets the preconditions, the first approach is perfectly well supported through Traefik with prefix rules and middlewares that can strip or modify the path prefix from request or response headers.

For the second approach you need some kind of dynamic DNS that creates one or more host names when a new docker swarm stack starts its services and remove them when the stack gets removed. For an OPNSense box running the bind service this is exactly what the Swarm OPNSense bind service updater does.

## Build

### Dependencies on build tools

Before your can build the project, you have to make sure the following build tools are installed on your system:

1. Python language in version 3.12 or later.

   Most often your Linux distribution comes with an already installed python. If not refer to the python guide of your distribution.

   You can check if python is installed on your system with the following command

   ```sh
   python3 -V
   ```

   If installed you should see the answer

   ```sh
   Python 3.12.3
   ```

    If you get an error that python is not installed, you can check for the [official Python download guide](https://www.python.org/downloads/). It contains the necessary installation instructions to install the python language on your system.
1. The pipx package manager.

   See the official [pipx installation guide](https://pipx.pypa.io/stable/installation/) for instructions.

   Please make sure that you get at least the pipx version `1.5.0`, better the current version `1.7.0`. If pipx comes with your distribution you can check the pipx installation guide listed above to check which version might come with your distribution and how to upgrade.
1. The poetry dependency management and packaging in Python.

    Refer to the [poetry installation guide](https://python-poetry.org/docs/#installation) for instructions.

### Build instructions

After you have checked or installed the necessary third party tools, you can build the project with the following build instructions.

#### Check out the project sources

```sh
git clone https://github.com/aixo-impulse-gmbh/swarm-opn-bind-updater.git
```

#### Change the working directory into the project directory

```sh
cd swarm-opn-bind-updater
```

#### Create and activate an Python virtual environment

The instructions create a Python virtual environment named `.venv`.

If you like another name, feel free to do so. But be advised that the building instructions assume the venv environment to be named `.venv`. If you want to learn more about Python virtual environments please refer to [Python virtual environment documentation](https://docs.python.org/3/library/venv.html)

```sh
python -m venv .venv
```

Activate the environment.

```sh
source .venv/bin/activate
```

#### Install the projects dependencies

To install the projects dependencies we use poetry.

```sh
poetry install
```

#### Build the distribution artifacts

To build the distribution artifacts use the following command.

```sh
poetry build
```

This command creates a directory called `dist`. Inside the dist directory you will find the distribution artifacts named `swarm_opn_bind_updater-0.2.0-py3-none-any.whl` and `swarm_opn_bind_updater-0.2.0.tar.gz`

## Installation

Once you have build the distribution you can use the build artifacts to install the software to your system. You can do that in two variants. The local and the global variant. The difference is the path to which the software will be installed.

I will show both version and it is up to you to decide which method to choose. If you want to use the software as a system service, I recommend the global version. See the [installation as a system service section](#system-daemon-service) and the [daemon usage section](#daemon-usage) for details.

### Global installation variant

To use the global installation variant use the following command.

```sh
sudo pipx install --global dist/swarm_opn_bind_updater-0.2.0-py3-none-any.whl
```

### Local installation variant

If you prefer to install the software to your local directory use the following command.

```sh
pipx install dist/swarm_opn_bind_updater-0.2.0-py3-none-any.whl
```

The command might give you a warning that you have to add the local installation directory to your `PATH` variable. If so, refer to your distribution on how do to that.

### Check your installation

Regardless of the variant you used, you can check the installation with the command.

```sh
which swarm_opn_bind_updater
```

It will show you the location where the executable was installed.

## Configuration

### Basic Configuration

The executable expects some values configured as environment variables.

| Variable | Required | Description | Example |
| - | - | - | - |
| REQUESTS_CA_BUNDLE | No | Points to file containing the systems CA certificates used by the `requests` module. Must be set, if the OPNSense gateway uses a self signed certificate | /etc/ssl/certs/ca-certificates.crt |
| GW_API_URL | Yes | Points to the URL of your OPNSense box | <https://gatway.exmaple.org> |
| GW_API_KEY | Yes | The key of the OPNSense API token | w86XNZob/8Oq8aC5r0kbNarNtdpoQU781fyoeaOBQsBwkXUt |
| GW_API_SECRET | Yes | The secret of the OPNSense API token | XeD26XVrJ5ilAc/EmglCRC+0j2e57tRsjHwFepOseySWLM53pJASeTA3 |
| DOCKER_HOST | Yes | The URL to the docker daemon API | unix://var/run/docker.sock |

Please refer to the [OPNSens documentation](https://docs.opnsense.org/development/how-tos/api.html) on how to create tokens.

You can store the variable in the file `.env` that is located in the same directory than the installed executable.

### System daemon service

If you want to use the executable as a system service, you have to install it with the [global method](#global-installation-variant)

For a system using `systemd` follow the instructions given below to install the executable as a system service. For other service, please adapt the configuration accordingly.

#### Create a configuration

Create a configuration directory for the service.

```sh
sudo mkdir /etc/swarm-opn-bind-updater
```

Create the environment file used by the service.

```sh
sudo vi /etc/swarm-opn-bind-updater/.env
```

The following content is an example for the content of the configuration file. Use your own tokens and docker connections suiting your need.

```txt
REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

GW_API_URL = "https://gateway.example.org"

GW_API_KEY = "w86XNZob/8Oq8aC5r0kbNarNtdpoQU781fyoeaOBQsBwkXUt"
GW_API_SECRET = "XeD26XVrJ5ilAc/EmglCRC+0j2e57tRsjHwFepOseySWLM53pJASeTA3"

DOCKER_HOST = "unix://var/run/docker.sock"
```

#### Add the service

Create a new systemd service unit.

```sh
vi /etc/systemd/system/swarm_opn_bind_updater.service
```

And add the following content.

```txt
[Unit]
Description=Updates the OPNSense bind dns record upon starting docker swarm services
After=docker.service
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=1
EnvironmentFile=/etc/swarm-opn-bind-updater/.env
ExecStart=/usr/local/bin/swarm_opn_bind_updater events

[Install]
WantedBy=multi-user.target
```

Then start the service with.

```sh
systemctl start swarm_opn_bind_updater.service
```

And check the status.

```sh
systemctl status swarm_opn_bind_updater.service
```

It should give you an output similar to that.

```sh
● swarm_opn_bind_updater.service - Updates the OPNSense bind dns record upon starting docker swarm services
     Loaded: loaded (/etc/systemd/system/swarm_opn_bind_updater.service; disabled; preset: enabled)
     Active: active (running) since Fri 2025-03-07 22:19:38 CET; 1 day 15h ago
   Main PID: 929744 (swarm_opn_bind_)
      Tasks: 1 (limit: 9257)
     Memory: 19.2M (peak: 19.7M)
        CPU: 5.384s
     CGroup: /system.slice/swarm_opn_bind_updater.service
             └─929744 /opt/pipx/venvs/swarm-opn-bind-updater/bin/python /usr/local/bin/swarm_opn_bind_updater events
Mar 07 21:24:36 server systemd[1]: Started swarm_opn_bind_updater.service - Updates the OPNSense bind dns record upon starting docker swarm services.
Mar 07 21:24:37 server swarm_opn_bind_updater[924371]: INFO:swarm_opn_bind_updater.main:Loaded environment
Mar 07 21:24:37 server swarm_opn_bind_updater[924371]: INFO:swarm_opn_bind_updater.main:Created docker client
Mar 07 21:24:37 server swarm_opn_bind_updater[924371]: INFO:swarm_opn_bind_updater.main:Created event stream
Mar 07 21:24:37 server swarm_opn_bind_updater[924371]: INFO:swarm_opn_bind_updater.main:Listening for events...
```

If everything is to your needs you can enable the system service to start automatically.

```sh
systemctl enable swarm_opn_bind_updater.service
```

If services were started for which OPNSense bind records are created check the logs. They should look similar to that.

<!-- cSpell:disable -->
```log
Mar 07 21:24:36 camina systemd[1]: Started swarm_opn_bind_updater.service - Updates the OPNSense bind dns record upon starting docker swarm services.
Mar 07 21:24:37 server swarm_opn_bind_updater[924371]: INFO:swarm_opn_bind_updater.main:Loaded environment
Mar 07 21:24:37 server swarm_opn_bind_updater[924371]: INFO:swarm_opn_bind_updater.main:Created docker client
Mar 07 21:24:37 server swarm_opn_bind_updater[924371]: INFO:swarm_opn_bind_updater.main:Created event stream
Mar 07 21:24:37 server swarm_opn_bind_updater[924371]: INFO:swarm_opn_bind_updater.main:Listening for events...
Mar 07 21:31:07 server swarm_opn_bind_updater[924371]: INFO:swarm_opn_bind_updater.main:Added bind record {'domain': 'example.org', 'host': 'myhost', 'type': 'CNAME', 'value': 'server ', 'domain_id': 'e7079f24-aeb7-4741-bd05-e005350bb5bf', 'id': 'baffc598-1fb9-46>
Mar 07 21:31:07 server swarm_opn_bind_updater[924371]: INFO:swarm_opn_bind_updater.main:Added service {'id': 'dgs5smiam1457ncvnrmf0qgk6', 'record': {'domain': 'example.org', 'host': 'myhost', 'type': 'CNAME', 'value': 'server ', 'domain_id': 'e7079f24-aeb7-4741-b>
Mar 07 21:34:06 server swarm_opn_bind_updater[924371]: INFO:swarm_opn_bind_updater.main:Removed bind record {'domain': 'example.org', 'host': 'myhost', 'type': 'CNAME', 'value': 'server ', 'domain_id': 'e7079f24-aeb7-4741-bd05-e005350bb5bf', 'id': 'baffc598-1fb9->
Mar 07 21:34:06 server swarm_opn_bind_updater[924371]: INFO:swarm_opn_bind_updater.main:Removed service {'id': 'dgs5smiam1457ncvnrmf0qgk6', 'record': {'domain': 'example.org', 'host': 'myhost', 'type': 'CNAME', 'value': 'server ', 'domain_id': 'e7079f24-aeb7-4741>
```
<!-- cSpell:enable -->

## Usage

### Cli usage

The updater has two intended usages. First you can use it as a handy cli to manually manage the OPNSense bind service. You can use the following command to get the cli usage.

```sh
swarm_opn_bind_updater --help
```

### Daemon usage

The second type of usage is intended to run as a daemon with the following command.

```sh
swarm_opn_bind_updater events
```

It will start a docker event listener and process service created and service remove events. For each service event the listener will inspect the service and search for the specific labels that give information about the OPNSense bind service records to create or remove.

For that add the following labels to services in your docker stack descriptor (compose.yml).

```yml
services:
    your-service:
    ...

    deploy:
      labels:
        - 'com.aixo.cloud.ingress.mappings.0.domain=example.org'
        - 'com.aixo.cloud.ingress.mappings.0.host=hostname'
        - 'com.aixo.cloud.ingress.mappings.0.type=CNAME'
        - 'com.aixo.cloud.ingress.mappings.0.value=ingress'
```

Substitute the values for `domain`, `host`, `type` and `value` to your needs. They are the same than the values you type in the OPNSense bind service gui for new records.

The label part `.0.` is the selector of the mapping. You can change it to whatever value your like. It is the internal identifier of the mapping.

You can add as many mappings as you like. Here is a more complicated example.

```yml
services:
    your-service:
    ...

    deploy:
      labels:
        - 'com.aixo.cloud.ingress.mappings.m1.domain=example.org'
        - 'com.aixo.cloud.ingress.mappings.m1.host=first-host'
        - 'com.aixo.cloud.ingress.mappings.m1.type=CNAME'
        - 'com.aixo.cloud.ingress.mappings.m1.value=ingress'

        - 'com.aixo.cloud.ingress.mappings.m2.domain=example.org'
        - 'com.aixo.cloud.ingress.mappings.m2.host=second-host'
        - 'com.aixo.cloud.ingress.mappings.m2.type=CNAME'
        - 'com.aixo.cloud.ingress.mappings.m2.value=ingress'
```

In daemon mode the executable will give you log messages about events processed and host records added to the OPNSense bind service database. After each change to the OPNSense bind database the service will be instructed to reconfigure.

If you expect for the host records to become valid and a short amount of time, please change the `TTL`, `Refresh`, `Retry`, `Expire` and `Negative TTL` of the domain the records belong to.

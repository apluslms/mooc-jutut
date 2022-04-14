Production installation
=======================

Environment
-----------

### Install following software in to your system:

* git
* nginx
* PostgreSQL
* memcached
* RabbitMQ
* GNU gettext
* python 3
* python 3 virtualenv
* python 3 psycopg2
* python 3 certifi (used to get up-to-date CA list from system)


#### Debian:

```sh
sudo apt-get -y install \
  git nginx postgresql memcached rabbitmq-server gettext \
  python3 python-virtualenv python3-psycopg2 python3-certifi
```

### Setup environment

#### Use installation script

**Debian note**: You should probably remove nginx default server `rm /etc/nginx/sites-enabled/*`.

Create user, clone repo and init config files.

```sh
wget 'https://raw.githubusercontent.com/Aalto-LeTech/mooc-jutut/stable/scripts/install.py' -O-|sudo python3 - \
 --user=jutut --home=/opt/jutut --fqdn=jutut.example.com
```

Edit files `/opt/jutut/mooc-jutut/install_config.ini` and `/opt/jutut/mooc-jutut/jutut/local_settings.py` for your needs.

Upgrade code

```sh
sudo /opt/jutut/mooc-jutut/scripts/install.py upgrade
```

Install code

```sh
sudo /opt/jutut/mooc-jutut/scripts/install.py install
```

Online service

```sh
sudo /opt/jutut/mooc-jutut/scripts/install.py online
```

*Or `sudo /opt/jutut/mooc-jutut/scripts/install.py --chain upgrade` to do it all.*

You can read server logs using `journalctl -t mooc-jutut` or follow with `journalctl -t mooc-jutut -f`.
Celery logs with `journalctl -t mooc-jutut-celery`.


#### Or do manually at least following steps

* Create user

  ```sh
  adduser --system --disabled-password \
  --gecos 'MOOC Jutut webapp server,,,' \
  --home /opt/jutut --group nogroup jutut
  ```

* Configure DB
* Configure rabbitmq
* Configure nginx
* Configure systemd services (checkout `scripts/templates/` for templates)
* Clone repo / checkout new branch
* Install virtual env
* Link python packages from the system

  ```sh
  sudo -H -u jutut sh -c "
    for p in certifi psycopg2; do
      for d in /opt/jutut/venv/lib/python3*; do
        psrc=\$(python3 -c \"import \$p; print(\$p.__file__)\")
        rm \$d/site-packages/\$p-*.egg-info
        ln -s -t \$d/site-packages/ \${psrc%/*}*
      done
    done"
  ```

* Install requirements.txt
* Install gunicorn
* Configure local_settings.py
* Django migrate
* Django compilemessages
* Django collectstatic


#### Force Rabbitmq and Erlang name server on localhost

`/etc/rabbitmq/rabbitmq-env.conf`

```
# Defaults to rabbit. This can be useful if you want to run more than one node
# per machine - RABBITMQ_NODENAME should be unique per erlang-node-and-machine
# combination. See the clustering on a single machine guide for details:
# http://www.rabbitmq.com/clustering.html#single-machine
#NODENAME=rabbit

# By default RabbitMQ will bind to all interfaces, on IPv4 and IPv6 if
# available. Set this if you only want to bind to one network interface or#
# address family.
NODE_IP_ADDRESS=127.0.0.1

# Defaults to 5672.
#NODE_PORT=5672

# Load erlang configuration
CONFIG_FILE="/etc/rabbitmq/rabbit"

# Configure EPMD for lo
export ERL_EPMD_ADDRESS=127.0.0.1
```

`/etc/rabbitmq/rabbit.config`

```
[
    {rabbitmq_management, [
        {listener, [{port, 15672}, {ip, "127.0.0.1"}]}
    ]},
    {kernel, [
        {inet_dist_use_interface,{127,0,0,1}}
    ]}
].
```

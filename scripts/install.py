#!/usr/bin/env python3

import argparse
import pwd
import grp
import string
import sys
import time
from collections import OrderedDict
from configparser import ConfigParser
from os import execl, geteuid, lchown, makedirs
from os.path import expandvars
from pathlib import Path
from random import choice as random_choice
from shlex import split as _split
from shutil import copyfile, rmtree, which
from subprocess import run, Popen, PIPE, STDOUT


DEBUG = True
OPTS = None
ORIGINAL_OPTS = None
PARSER = None
ROOT_TOOLS = (
    'adduser',
    'psql', 'createuser', 'createdb',
    'rabbitmqctl',
    'systemctl', 'systemd-tmpfiles',
    'openssl',
)
USER_TOOLS = (
    'git',
    'virtualenv',
    'pg_dump', 'gzip',
)


# ------------------- UTILS----------------------
# -----------------------------------------------

def exit_with_error(code, msg):
    if code != 0:
        print("ERROR:", msg, file=sys.stderr)
    else:
        print(msg)
    sys.exit(code)

def debug(*msg):
    print("DEBUG:", *msg)

def warning(*msg):
    print("WARNING:", *msg)

def disable_debug():
    global DEBUG, debug
    DEBUG = False

    def nop(*args):
        pass
    debug = nop

def arg_split(args):
    return tuple(_split(args))

def is_root():
    return geteuid() == 0

def get_uid_for(user):
    try:
        return pwd.getpwnam(user)[2]
    except KeyError:
        return None

def is_user(user):
    return geteuid() == get_uid_for(user)

def is_in_virtualenv():
    return hasattr(sys, 'real_prefix')

def get_git_hash():
    code, out = exec_git('rev-parse', 'HEAD', get_output=True)
    if code:
        return None
    return out.strip().split(None, 1)[0][:7]

def get_random_string(n=32):
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return ''.join((random_choice(chars) for k in range(n)))

def require_tools(tools):
    for tool in tools:
        if which(tool) is None:
            exit_with_error(1, "your installation is missing executable '%s'" % (tool,))

def link_system_python_packages():
    packages = OPTS.system_packages.split()
    python_paths = [x / 'site-packages' for x in OPTS.venv.joinpath("lib").glob('python3*')]

    files_to_clean = []
    files_to_link = []
    uid = pwd.getpwnam(OPTS.user)[2]
    gid = grp.getgrnam(OPTS.group)[2]

    for package in packages:
        try:
            pkg = __import__(package, globals())
        except ImportError:
            exit_with_error(1, "Couldn't find python package %r from the system" % (package,))
        pkg_src, _, _ = pkg.__file__.rpartition('/')
        pkg_path, _, pkg_name = pkg_src.rpartition('/')
        sources = Path(pkg_path).glob(pkg_name + '*')
        for dst in python_paths:
            files_to_clean.extend(dst.glob(pkg_name + '*'))
            files_to_link.extend((dst / file_.name, file_) for file_ in sources)

    for file_ in files_to_clean:
        debug("removing file or dir '%s'" % (file_,))
        try:
            file_.unlink()
        except OSError:
            rmtree(str(file_))
    for dst, src in files_to_link:
        debug("creating symlink '%s' -> '%s'" % (dst, src))
        dst.symlink_to(src)
        lchown(str(dst), uid, gid)

def restart_program_with_replaced_arg(olds, new):
    argv = sys.argv
    n_argv = [(new if x in olds else x) for x in argv]
    assert argv != n_argv, "Couldn't replace action in argv: %s" % (argv,)

    sys.stdout.flush()
    sys.stderr.flush()
    python = sys.executable
    debug(" .. executing installer again: %s" % (n_argv,))
    execl(python, python, *n_argv) # WARNING: Will exec new instance and replace current one!!

def _exec(cmd, quiet_test=False, get_output=False, **kwargs):
    cmd = [str(x) for x in cmd]
    debug("executing:", cmd)
    returncode = -1
    output = None
    if get_output: quiet_test = True
    if DEBUG and not quiet_test:
        def handle_line(line):
            if line:
                print(">", line.decode('utf-8'), end='')
        with Popen(cmd, stdout=PIPE, stderr=STDOUT, **kwargs) as proc:
            while proc.poll() is None:
                handle_line(proc.stdout.readline())
            for line in proc.stdout:
                handle_line(line)
            returncode = proc.returncode
    else:
        proc = run(cmd, stdout=PIPE, stderr=STDOUT, check=False, **kwargs)
        returncode = proc.returncode
        output = proc.stdout.decode('utf-8')
        if not quiet_test and returncode != 0:
            sys.stderr.write(output)
    if not quiet_test and returncode != 0:
        exit_with_error(returncode, "Execution of %r failed with %d" % (" ".join(cmd), returncode))

    if get_output:
        return returncode, output
    return returncode

def exec(*cmd, **kwargs): # pylint: disable=redefined-builtin
    return _exec(cmd, **kwargs)

def define_execs():
    """define shorthand executables in global namespace"""
    if OPTS.sudo_user:
        sudo_user = arg_split(OPTS.sudo_user)

        def exec_user(*cmd, **kwargs):
            kwargs.setdefault('cwd', str(OPTS.home))
            return _exec(sudo_user + cmd, **kwargs)
    else:
        exec_user = exec

    sudo_pg = arg_split(OPTS.sudo_pg)

    def exec_pg(*cmd, **kwargs): # pylint: disable=possibly-unused-variable
        kwargs.setdefault('cwd', '/tmp')
        return _exec(sudo_pg + cmd, **kwargs)

    def exec_git(*cmd, **kwargs): # pylint: disable=possibly-unused-variable
        kwargs.setdefault('cwd', str(OPTS.dest))
        return exec_user('git', *cmd, **kwargs)

    venv_bin = OPTS.venv / 'bin'

    def exec_venv(proc, *args, **kwargs):
        cmd = venv_bin / proc
        kwargs.setdefault('cwd', str(OPTS.dest))
        return exec_user(cmd, *args, **kwargs)

    def exec_manage(*args, **kwargs): # pylint: disable=possibly-unused-variable
        return exec_venv('python', 'manage.py', *args, **kwargs)

    globals().update({k: v for k, v in locals().items() if k.startswith('exec')})


def write_from_template(output, template, **kwargs):
    template_path = OPTS.templates / template

    if not kwargs:
        kwargs = vars(OPTS)

    if not str(output).startswith(str(OPTS.home)) and not is_root():
        output = OPTS.fakeroot / (str(output)[1:])
        dirs = output.parent
        if not dirs.exists():
            makedirs(str(dirs))

    with template_path.open('r') as template_file:
        template = string.Template(template_file.read())
    content = template.substitute(kwargs)
    del template

    if output.exists():
        new_out = output.with_name(output.name + '.new')

        # Check if there is changes
        with output.open('r') as output_file:
            current_content = output_file.read()
        if current_content.strip() == content.strip():
            debug("File '%s' exists and there is no changes for it." % (output,))
            if new_out.exists():
                # cleanup if there is .new file
                new_out.unlink()
            return

        warning("File '%s' exists. Creating '%s' instead from '%s'." % (
            output, new_out, template_path))
        output = new_out
    else:
        debug("Creating file '%s' from '%s'" % (output, template_path))

    with output.open('w') as output_file:
        output_file.write(content)


# -------------- INSTALL ACTIONS ----------------
# -----------------------------------------------

def ensure_user():
    # create user
    if get_uid_for(OPTS.user) is None:
        exec('adduser',
             '--system', '--disabled-password',
             '--gecos', 'MOOC Jutut webapp server,,,',
             '--home', OPTS.home,
             '--ingroup', OPTS.group, OPTS.user)

def ensure_dest():
    if not OPTS.dest.exists():
        origin, _, branch = OPTS.branch.partition('/')
        if not branch:
            origin, branch = 'origin', origin
        exec_user('git', 'clone', '--origin', origin, '--branch', branch, OPTS.source, OPTS.dest)
    elif not (OPTS.dest / '.git').exists():
        exit_with_error(1, "Destination '%s' is not a git directory, but it does exists." % (OPTS.dest,))

def checkout_branch():
    exec_git('fetch')
    exec_git('checkout', OPTS.branch)

def ensure_local_conf():
    local_conf = OPTS.dest / 'jutut' / 'local_settings.py'
    example_conf = OPTS.dest / 'jutut' / 'local_settings.example.py'
    if not local_conf.exists():
        copyfile(str(example_conf), str(local_conf))

def test_database_exists():
    return 0 == exec_user('psql', '-U', OPTS.user, OPTS.sql_db_name,
                          '--command=SELECT version();', quiet_test=True)

def configure_databases():
    # configure postgres
    if not test_database_exists():
        exec_pg('createuser', OPTS.user)
        exec_pg('createdb', '-O', OPTS.user, OPTS.sql_db_name)

    # configure message broker
    c_conf = OPTS.dest / 'jutut' / 'local_settings_celery.py'
    if not c_conf.exists():
        pw = get_random_string()
        c_path = OPTS.sql_db_name + '/'
        exec('rabbitmqctl', 'add_user', OPTS.user, pw)
        exec('rabbitmqctl', 'add_vhost', c_path)
        exec('rabbitmqctl', 'set_permissions', '-p', c_path, OPTS.user, '.*', '.*', '.*')
        write_from_template(c_conf, 'local_settings_celery.py',
            user=OPTS.user,
            password=pw,
            path=c_path
        )

def configure_systemd():
    # Configure systemd to create us folder in /run
    write_from_template(OPTS.tmpfiles_path, 'tmpfiles.conf')

    if is_root():
        # create tmpfiles configured above
        exec('systemd-tmpfiles', '--create')

    # Gunicorn
    write_from_template(
        OPTS.systemd_path.joinpath(OPTS.gunicorn_service + '.service'),
        'systemd-gunicorn.service')

    # Celery
    write_from_template(
        OPTS.systemd_path.joinpath(OPTS.celery_service + '.service'),
        'systemd-celery.service')

    # Celery beat
    write_from_template(
        OPTS.systemd_path.joinpath(OPTS.celerybeat_service + '.service'),
        'systemd-celerybeat.service')


def configure_nginx():
    # configure nginx
    conf = OPTS.nginx_conf_path
    link = OPTS.nginx_link_path

    write_from_template(conf, 'nginx-site.conf')

    if is_root():
        if link and not link.exists():
            link.symlink_to(conf)
        # create dhparams if it doesn't exists
        if not OPTS.nginx_dhparams_path.exists():
            exec('openssl', 'dhparam', '-out', OPTS.nginx_dhparams_path, '2048')
            OPTS.nginx_dhparams_path.chmod(0o400)
        # create key if one doesn't exists
        if not OPTS.nginx_key_path.exists():
            exec('openssl', 'ecparam', '-genkey',
                 '-name', 'prime256v1', # '-param_enc', 'explicit',
                 '-out', OPTS.nginx_key_path)
            OPTS.nginx_key_path.chmod(0o400)
        # create self signed certificate if one doesn't exists
        if not OPTS.nginx_cert_path.exists():
            exec('openssl', 'req', '-new', '-x509', '-days', '365',
                 '-subj', OPTS.nginx_cert_subj,
                 '-key', OPTS.nginx_key_path,
                 '-out', OPTS.nginx_cert_path)
            OPTS.nginx_cert_path.chmod(0o444)

def install_virtualenv():
    # 1) install virtualenv
    exec_user('virtualenv', '--python=' + OPTS.python, OPTS.venv)

    # 2) link system packages
    link_system_python_packages()

    # 3) install requirements.txt
    exec_venv('pip', 'install', '-r', OPTS.dest / 'requirements.txt')

    # 4) install gunicorn
    exec_venv('pip', 'install', 'gunicorn')

def setup_django():
    # create tables
    exec_manage('migrate')

    # compile localization
    exec_manage('compilemessages')

    # collect static
    exec_manage('collectstatic', '--noinput')

def create_sql_backup(db_ok=False):
    if db_ok or test_database_exists():
        hash_ = get_git_hash()
        name = "{prefix}_{time}_git-{hash}.sql".format(
            prefix=OPTS.sql_backup_prefix,
            time=time.strftime("%Y-%m-%dT%H:%M:%S"),
            hash=hash_,
        )
        file_ = OPTS.sql_backup_path / name
        exec_user('pg_dump', '-U', OPTS.user, '-f', file_, '-c', OPTS.sql_db_name)
        exec_user('gzip', file_)
        file_.with_name(file_.name + '.gz').chmod(0o400)

def stop_services():
    services = (OPTS.gunicorn_service,  OPTS.celery_service, OPTS.celerybeat_service)
    services = [s + '.service' for s in services]
    exec('systemctl', 'stop', *services, quiet_test=True)

def setup_services():
    exec('systemctl', 'daemon-reload')

    services = (OPTS.gunicorn_service,  OPTS.celery_service, OPTS.celerybeat_service)
    services = [s + '.service' for s in services]
    exec('systemctl', 'enable', *services)
    exec('systemctl', 'stop', *services) # make sure they are stopped (e.g. if online is run again)
    exec('systemctl', 'start', *services)
    exec('systemctl', 'restart', 'nginx.service')

    all_services = ['nginx.service', 'rabbitmq-server.service'] + services
    failures = False
    for s in all_services:
        if exec('systemctl', 'is-active', s, quiet_test=True) != 0:
            warning("Service %s is not active" % (s,))
            failures = True
    if failures:
        exit_with_error(3, "Some services are not active!")

    exec('journalctl', '-xn', '-t', OPTS.name)
    exec('journalctl', '-xn', '-t', OPTS.name + '-celery')

def get_maintenance_file():
    return Path(OPTS.dest) / 'maintenance_enabled'

def fail_if_not_disabled():
    if not get_maintenance_file().exists():
        exit_with_error(1, "This step requires that app is offline, su run offline/ugprade before this.")

def disable_site():
    debug("Disabling the site..")
    get_maintenance_file().touch()

def enable_site():
    flag_file = get_maintenance_file()
    if flag_file.exists():
        debug("Enabling the site...")
        flag_file.unlink()


# -------------------- CLI ----------------------
# -----------------------------------------------

SECTIONS = {
    'positional arguments': None,
    'optional arguments': 'jutut',
    'runtime': None
}

CONFIG_LOADED = None
CONFIG_OPTIONS = set()
def load_configuration(parser, namespace, config):
    """Loads configuration and applies it to namespace"""
    global CONFIG_LOADED, CONFIG_OPTIONS # pylint: disable=global-variable-not-assigned
    assert config, "Config file is required"
    config_parser = ConfigParser(interpolation=None)
    config_parser.read(str(config))
    actions = {}
    get_bool = lambda c, n: c.getboolean(n) # pylint: disable=unnecessary-lambda-assignment
    for group in parser._action_groups:
        section = SECTIONS.get(group.title, group.title)
        if section:
            for action in group._group_actions:
                if action.type is None and isinstance(action.const, bool):
                    getter = get_bool
                else:
                    convert = parser._registry_get('type', action.type, action.type)
                    # pylint: disable-next=unnecessary-lambda-assignment cell-var-from-loop
                    getter = lambda c, n: convert(c[n])
                actions[action.dest] = getter
    for section in config_parser.sections():
        section_conf = config_parser[section]
        for key in section_conf.keys():
            if key in actions:
                value = actions[key](section_conf, key)
                setattr(namespace, key, value)
                CONFIG_OPTIONS.add(key)
    CONFIG_LOADED = config

def store_configuration(config):
    config_parser = ConfigParser()
    dont_store = frozenset(['config', 'action'])
    opts = ORIGINAL_OPTS
    if not isinstance(config, Path):
        config = Path(config)
    for group in PARSER._action_groups:
        section = SECTIONS.get(group.title, group.title)
        if section:
            vals = OrderedDict()
            for action in group._group_actions:
                name = action.dest
                if name in opts and name not in dont_store:
                    default, value = PARSER.get_default(name), opts[name]
                    if name not in CONFIG_OPTIONS and default == value:
                        name = '; ' + name
                    vals[name] = value
            if vals:
                config_parser[section] = vals
    with config.open('w', encoding='utf-8') as f:
        f.write("""; Configuration file for MOOC Jutut installer\n\n""")
        config_parser.write(f)

# pylint: disable-next=too-many-branches too-many-statements too-many-locals
def parse_options(): # noqa: MC0001
    global OPTS, ORIGINAL_OPTS, PARSER

    proc_path = Path(sys.argv[0])
    if proc_path.exists():
        base = proc_path.resolve().parent.parent
        conf_path = base / 'install_config.ini'
        conf_path = str(conf_path) if conf_path.exists() else None
    else:
        conf_path = None

    # Define parser for configuration file
    p_conf = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )

    p_conf.add_argument('-c', '--config', metavar="PATH",
                        default=conf_path,
                        help="Installer configuration file")

    args, remaining_argv = p_conf.parse_known_args()

    # Define parser for rest of the options
    PARSER = parser = argparse.ArgumentParser(parents=[p_conf])

    # argumetns that are not stored
    pa_run = parser.add_argument_group('runtime')
    pa_run.add_argument('-q', '--quiet', action="store_true",
                        help="Don't print debug messages")
    pa_run.add_argument('-A', '--chain', action="store_true",
                        help="Automatically run next command in chain")

    # generic
    parser.add_argument('-e', '--env', default="prod",
                        help="Installation environment")
    parser.add_argument('-n', '--name', default="mooc-jutut",
                        help="Name for this installation")
    parser.add_argument('-D', '--dest', default="$home/mooc-jutut", metavar="PATH",
                        help="Install destination")
    parser.add_argument('-S', '--source', metavar="URL",
                        default="https://github.com/Aalto-LeTech/mooc-jutut.git",
                        help="Source for the code")
    parser.add_argument('-B', '--branch', metavar='REF',
                        default="origin/stable",
                        help="Version of the source we are installing or upgrading to")
    parser.add_argument('-U', '--user', default="jutut",
                        help="User for the web service")
    parser.add_argument('-G', '--group', default="nogroup",
                        help="Group for the user")
    parser.add_argument('-H', '--home', default="/opt/$user", metavar="PATH",
                        help="Home for the user")
    parser.add_argument('-V', '--venv', default="$home/venv", metavar="PATH",
                        help="path where virtual environment is installed")
    parser.add_argument('--python', default="python3", metavar='EXE',
                        help="python executable to be used when installing virtualenv")
    parser.add_argument('--system_packages', default="certifi psycopg2", metavar="PKGS",
                        help="list of python packages linked from the system")

    pa_ins = parser.add_argument_group('installer')
    pa_ins.add_argument('--templates', default="$dest/scripts/templates", metavar="PATH",
                        help="Source for installation template files")
    pa_ins.add_argument('--fakeroot', default="$home/system_files/", metavar="PATH",
                        help="Location to write system files when not running as root.")

    par_db = parser.add_argument_group('database')
    par_db.add_argument('--sql_db_name', default="mooc_jutut_${env}", metavar="DB",
                        help="Name of the sql database (remember to write in local_settings.py)")
    par_db.add_argument('--sql_backup_path', default="$home", metavar="PATH",
                        help="Location to write SQL dumps on upgrade.")
    par_db.add_argument('--sql_backup_prefix', default="db_dump", metavar="PREFIX",
                        help="Prefix for the sql dumps.")

    par_ng = parser.add_argument_group('nginx')
    par_ng.add_argument('--fqdn', metavar="DOMAIN",
                        default="localhost",
                        help="Full domain name of the service")
    par_ng.add_argument('--nginx_conf_path', metavar="PATH",
                        default="/etc/nginx/sites-available/$fqdn.conf",
                        help="Location where to put nginx configuration")
    par_ng.add_argument('--nginx_link_path', metavar="PATH",
                        default="/etc/nginx/sites-enabled/$fqdn.conf",
                        help="Location where to put link to the conf. Set empty to disable")
    par_ng.add_argument('--nginx_cert_path', metavar="PATH",
                        default="/etc/nginx/$fqdn.crt",
                        help="Location where the certificate is found (or selfsigned is created)")
    par_ng.add_argument('--nginx_key_path', metavar="PATH",
                        default="/etc/nginx/$fqdn.key",
                        help="Location where the cert key is found (or one is created)")
    par_ng.add_argument('--nginx_dhparams_path', metavar="PATH",
                        default="/etc/nginx/dhparams.pem",
                        help="Location where the dh params are found (or are created to)")
    par_ng.add_argument('--nginx_cert_subj', metavar="SUBJ",
                        default="/C=FI/ST=aState/L=aCity/CN=$fqdn/emailAddress=webmaster@$fqdn/",
                        help="Subject field for created certificate")

    pa_sys = parser.add_argument_group('system')
    pa_sys.add_argument('--tmpfiles_path', default="/etc/tmpfiles.d/$name.conf", metavar="PATH",
                        help="tempfiles path")
    pa_sys.add_argument('--run_path', default="/run/$name", metavar="PATH",
                        help="run folder path")
    pa_sys.add_argument('--systemd_path', default="/etc/systemd/system/", metavar="PATH",
                        help="systemd path")
    pa_sys.add_argument('--gunicorn_service', default="$name-gunicorn", metavar="NAME",
                        help="name for the gunicorn systemd service")
    pa_sys.add_argument('--celery_service', default="$name-celery", metavar="NAME",
                        help="name for the celery systemd service")
    pa_sys.add_argument('--celerybeat_service', default="$name-celerybeat", metavar="NAME",
                        help="name for the celery beat systemd service")
    pa_sys.add_argument('--sudo_user', metavar="CMD", default="sudo -H -u $user")
    pa_sys.add_argument('--sudo_pg', metavar="CMD", default="sudo -H -u postgres")


    parser.set_defaults(action=do_init)
    subs = parser.add_subparsers(
        title='actions',
        description="Actions you should take when installing or upgrading MOOC Jutut.\n"
                    "Typically: init -> upgrade -> install -> online")

    subs.add_parser('init', aliases=['start'],
                    help="Initialise system, destination and code")
    subs.add_parser('upgrade', aliases=['offline'],
                    help="Upgrade installed version to newest in branch"
                    ).set_defaults(action=do_upgrade)
    subs.add_parser('install',
                    help="Install system files and upgrades the state"
                    ).set_defaults(action=do_install)
    subs.add_parser('online', aliases=['done', 'finalize'],
                    help="When installation/upgrade is done, this will turn site back online"
                    ).set_defaults(action=do_done)

    subs.add_parser('backup_db',
                    help="Extra action. Creates backup of SQL DB."
                    ).set_defaults(action=do_backup)

    # Parse configuration file
    namespace = argparse.Namespace(**vars(args))
    if args.config and Path(args.config).exists():
        load_configuration(parser, namespace, args.config)

    # Parse commandline options
    OPTS = parser.parse_args(args=remaining_argv, namespace=namespace)
    data = vars(OPTS)
    ORIGINAL_OPTS = data.copy()

    # Expand variables in options
    # pylint: disable-next=consider-using-set-comprehension
    todo = set([k for k, v in data.items() if isinstance(v, str) and '$' in v])
    for k in todo:
        data[k] = v = expandvars(data[k])
        if '$' not in v: todo.remove(k)
    while todo:
        left = list(todo)
        for k in left:
            data[k] = v = string.Template(data[k]).substitute(data)
            if '$' not in v: todo.remove(k)
        if len(left) == len(todo):
            for k in todo:
                print("  %s = %s" % (k, data[k]))
            exit_with_error(2, "Couldn't expand all options")
    for k, v in data.items():
        if isinstance(v, str):
            assert '$' not in v, "not all variables were expaned: %s = %s" % (k, v)
    # Convert all variables ending in '_path' to pathlib.Path
    for k, v in list(data.items()):
        if k.endswith('_path'):
            data[k] = Path(v)
    for k in ('dest', 'venv', 'templates', 'fakeroot', 'config'):
        val = data[k]
        if val: data[k] = Path(val)


# ------------------ ACTIONS --------------------
# -----------------------------------------------


def do_init():
    # check tools
    if is_root():
        require_tools(ROOT_TOOLS)
    require_tools(USER_TOOLS)

    # Make sure we have the user for the web service
    if is_root():
        ensure_user()

    # Make sure we have the clone
    ensure_dest()
    ensure_local_conf()

    # Store installer config
    conf = OPTS.config or OPTS.dest / 'install_config.ini'
    store_configuration(conf)

    # Tell user to edit configs
    debug(
        "We have:\n"
        " * ensured existence of an user '{user}'\n"
        " * ensured that the repo exists in '{dest}'\n"
        " * ensured that there is configuration files for you to edit:\n"
        "   * installer config: '{conf}'\n"
        "   * django config   : '{dconf}'\n"
        "Edit those configurations for your needs and then run:\n"
        "  '{dest}/scripts/install.py{conf_arg} upgrade'"
        .format(
            user=OPTS.user,
            dest=OPTS.dest,
            conf=conf,
            conf_arg=('-c {}'.format(conf) if OPTS.config else ''),
            dconf=OPTS.dest / 'jutut' / 'local_settings.py',
        )
    )


def do_upgrade():
    debug(" ----- UPGRADE")

    # Disable site (flag for nxing) and stop services
    disable_site()
    if is_root():
        stop_services()

    # Create db backup before doing django mirations etc.
    create_sql_backup()

    # Fetch and checkout branch
    checkout_branch()

    debug(" ----- UPGRADE: Done")
    if OPTS.chain:
        restart_program_with_replaced_arg(['upgrade', 'offline'], 'install')
    else:
        debug("Upgrade step is ready. Proceed to 'install'")


def do_install():
    # Run only if upgrade is done first
    fail_if_not_disabled()

    debug(" ----- INSTALL")

    # Configure system
    if is_root():
        configure_databases()
    configure_systemd()
    configure_nginx()

    # (re)install virtualenv
    install_virtualenv()

    # Do all django stuff
    setup_django()

    debug(" ----- INSTALL: Done")
    if OPTS.chain:
        restart_program_with_replaced_arg(['install'], 'online')
    else:
        debug("Install step is ready. If everything works, then do 'online'")


def do_done():
    debug(" ----- ONLINE")

    if is_root():
        setup_services()

    # Enable site as everything should be fine now :)
    enable_site()

    debug(" ----- ONLINE: Done")
    debug("Service should be now online and serving requests.")


def do_backup():
    if test_database_exists():
        create_sql_backup(db_ok=True)
    else:
        exit_with_error(
            1,
            "User %s can't connect to db %s. Have you configured it yet?" % (OPTS.user, OPTS.sql_db_name)
        )


if __name__ == '__main__':
    # options
    parse_options()

    # debug output?
    if OPTS.quiet:
        disable_debug()

    if CONFIG_LOADED:
        debug("Configuration read from '%s'" % (CONFIG_LOADED,))

    # check if we are in virtualenv
    if is_in_virtualenv():
        exit_with_error(1, "Installer requires that it's run outside of a virtualenv.")

    # make sure there was config argument
    if not OPTS.config and OPTS.action != do_init: # pylint: disable=comparison-with-callable
        exit_with_error(
            1,
            "Run action 'init' first to create config files. After that always call with --config argument"
        )
    elif OPTS.config and not OPTS.config.exists():
        exit_with_error(1, "Specified config file doesn't exists: %s" % (OPTS.config,))

    # check user
    if not is_root():
        warning("Not running installation script as root,")
        warning(" .. so skipping system commands and writing configs to '%s'" % (OPTS.fakeroot))
        if is_user(OPTS.user):
            OPTS.sudo_user = ''
        else:
            exit_with_error(
                1,
                "Installation expects you to be root for full installation or user for upgrade. "
                "Make sure --user and --group are set correctly."
            )

    # define all exec_* commands to global namespace
    define_execs()

    # Do an installation step
    OPTS.action()

import os
import yaml
import shutil


def copy_default_config(config_file_path):
    try:
        shutil.copy('./default_config.yml', config_file_path)
    except Exception as e:
        raise Exception("Error copying default config file to {}:\n{}".format(
            config_file_path, str(e)))


def get_config_file_path():
    config_path = os.environ.get(
        'YDL_CONFIG_PATH', os.getcwd())
    if '.' in os.path.basename(config_path):
        return config_path
    return os.path.join(config_path, 'config.yml')


def load_config():
    config = None
    config_file_path = get_config_file_path()
    print("Using configuration file {}".format(config_file_path))

    if not os.path.isfile(config_file_path):
        print("{} does not exist, creating it from default values".format(
            config_file_path))
        copy_default_config(config_file_path)
    with open(config_file_path) as configfile:
        config = yaml.load(configfile, Loader=yaml.SafeLoader)

    return config


app_config = load_config()

if app_config is None or app_config.get('ydl_server') is None or \
        app_config.get('ydl_options') is None or \
        app_config['ydl_options'].get('output') is None:
    raise Exception('Invalid configuration file')

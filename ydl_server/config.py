import os
import yaml

def load_config(config_path):
    config = None
    if not os.path.isfile(config_path):
        print("Config file `{}` not found.".format(config_path))
        return None
    with open(config_path) as configfile:
        config = yaml.load(configfile, Loader=yaml.SafeLoader)
    return config

config_path = os.environ.get('YDL_CONFIG_PATH', 'config.yml')
app_config = load_config(config_path)

if app_config is None or app_config.get('ydl_server') is None or \
        app_config.get('ydl_options') is None or \
        app_config['ydl_options'].get('output') is None:
    raise Exception('Invalid configuration file `{}`'.format(config_path))

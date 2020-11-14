import os
import yaml

def load_config(config_path):
    config = None
    if not os.path.isfile(config_path):
        print("Config file '%s' not found." % config_path)
        return None
    with open(config_path) as configfile:
        config = yaml.load(configfile, Loader=yaml.SafeLoader)
    return config

app_config = load_config(os.environ.get('YDL_CONFIG_PATH', 'config.yml'))
if app_config is None or app_config.get('ydl_server') is None:
    raise Exception('No configuration file found')

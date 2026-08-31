import os
import shutil
from functools import cache

import yaml


class ConfigError(Exception):
    pass


YDL_PATH_TYPES = (
    "home",
    "temp",
    "chapter",
    "description",
    "annotation",
    "infojson",
    "link",
    "pl_thumbnail",
    "pl_description",
    "pl_infojson",
    "subtitle",
    "thumbnail",
)

YDL_FORMATS = {
    "Video": {
        "video/best": "Best",
        "video/bestvideo": "Best Video",
        "video/mp4": "MP4",
        "video/flv": "Flash Video (FLV)",
        "video/webm": "WebM",
        "video/ogg": "Ogg",
        "video/mkv": "Matroska (MKV)",
        "video/avi": "AVI",
    },
    "Audio": {
        "bestaudio/best": "Best Audio",
        "audio/aac": "AAC",
        "audio/flac": "FLAC",
        "audio/mp3": "MP3",
        "audio/m4a": "M4A",
        "audio/opus": "Opus",
        "audio/vorbis": "Vorbis",
        "audio/wav": "WAV",
    },
}


def get_ydl_formats(app_config):
    if len(app_config.get("profiles", {}).keys()) > 0:
        YDL_FORMATS["Profiles"] = {
            f"profile/{k}": v.get("name") for k, v in app_config.get("profiles").items()
        }
    return YDL_FORMATS


def get_ui_aliases(app_config):
    return {
        key: alias.get("name", key)
        for key, alias in app_config.get("aliases", {}).items()
        if alias.get("ui", True)
    }


def normalize_use(use):
    if use is None:
        return []
    if isinstance(use, str):
        return [use]
    return list(use)


def expand_alias(name, aliases, stack):
    if name in stack:
        raise ConfigError(f"Recursive alias definition: {' -> '.join(stack + [name])}")
    if name not in aliases:
        raise ConfigError(f"Unknown alias '{name}'")
    alias = aliases[name]
    options = expand_uses(alias.get("use"), aliases, stack + [name])
    options.update(alias.get("ydl_options", {}))
    return options


def expand_uses(use, aliases, stack):
    options = {}
    for name in normalize_use(use):
        options.update(expand_alias(name, aliases, stack))
    return options


def resolve_aliases(config):
    aliases = config.get("aliases") or {}
    for name, alias in aliases.items():
        alias["ydl_options"] = expand_alias(name, aliases, [])
        alias.pop("use", None)
    for name, profile in (config.get("profiles") or {}).items():
        options = expand_uses(profile.get("use"), aliases, [])
        options.update(profile.get("ydl_options", {}))
        profile["ydl_options"] = options
        profile.pop("use", None)


def copy_default_config(config_file_path):
    try:
        shutil.copy("./default_config.yml", config_file_path)
    except OSError as e:
        raise ConfigError(
            f"Error copying default config file to {config_file_path}:\n{e!s}"
        ) from e


def get_config_file_path():
    config_path = os.environ.get("YDL_CONFIG_PATH", os.getcwd())
    if "." in os.path.basename(config_path):
        return config_path
    return os.path.join(config_path, "config.yml")


def load_config():
    config = None
    config_file_path = get_config_file_path()
    print(f"Using configuration file {config_file_path}")

    if not os.path.isfile(config_file_path):
        print(
            f"{config_file_path} does not exist, creating it from default values"
        )
        try:
            copy_default_config(config_file_path)
        except ConfigError:
            print("Error copying default config file, loading it directly")
            config_file_path = "./default_config.yml"
    with open(config_file_path) as configfile:
        config = yaml.load(configfile, Loader=yaml.SafeLoader)

    if config is not None:
        resolve_aliases(config)

    return config


def get_static_prefix(output_template):
    prefix = []
    for s in output_template.split("/"):
        if "%" in s.replace("%%", ""):
            break
        prefix.append(s)
    if prefix == [""]:
        return "/"
    return "/".join(prefix)


def get_paths_home():
    paths = app_config["ydl_options"].get("paths")
    if not paths:
        return None
    path_type, sep, path = str(paths).partition(":")
    if not sep:
        return paths
    if path_type == "home":
        return path
    if path_type in YDL_PATH_TYPES:
        return None
    return paths


@cache
def get_finished_path():
    prefix = get_static_prefix(app_config["ydl_options"].get("output"))
    if not os.path.isabs(prefix):
        prefix = os.path.join(get_paths_home() or os.getcwd(), prefix)
    finished_path = os.path.normpath(prefix)
    if finished_path == os.path.sep:
        output = app_config["ydl_options"].get("output")
        raise ConfigError(
            f"Could not determine the download directory from ydl_options.output "
            f"('{output}'): it resolves to the filesystem root. Set ydl_options.paths, or "
            f"give ydl_options.output a static directory prefix."
        )
    os.makedirs(finished_path, mode=0o755, exist_ok=True)
    return finished_path + "/"


def resolve_finished_file(fname):
    """Resolve fname within the finished directory, or None if it escapes it."""
    root = os.path.realpath(get_finished_path())
    path = os.path.realpath(os.path.join(root, fname))
    if path != root and os.path.commonpath((path, root)) != root:
        return None
    return path


app_config = load_config()

if (
    app_config is None
    or app_config.get("ydl_server") is None
    or app_config.get("ydl_options") is None
    or app_config["ydl_options"].get("output") is None
):
    raise ConfigError("Invalid configuration file")

get_finished_path()

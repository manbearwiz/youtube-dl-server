import os
import yaml
import shutil

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
    "Metadata only": {"metadata": "Metadata"},
}


def get_ydl_formats(app_config):
    if len(app_config.get("profiles", {}).keys()) > 0:
        YDL_FORMATS["Profiles"] = {
            f"profile/{k}": v.get("name") for k, v in app_config.get("profiles").items()
        }
    return YDL_FORMATS


def copy_default_config(config_file_path):
    try:
        shutil.copy("./default_config.yml", config_file_path)
    except Exception as e:
        raise Exception(
            "Error copying default config file to {}:\n{}".format(
                config_file_path, str(e)
            )
        )


def get_config_file_path():
    config_path = os.environ.get("YDL_CONFIG_PATH", os.getcwd())
    if "." in os.path.basename(config_path):
        return config_path
    return os.path.join(config_path, "config.yml")


def load_config():
    config = None
    config_file_path = get_config_file_path()
    print("Using configuration file {}".format(config_file_path))

    if not os.path.isfile(config_file_path):
        print(
            "{} does not exist, creating it from default values".format(
                config_file_path
            )
        )
        copy_default_config(config_file_path)
    with open(config_file_path) as configfile:
        config = yaml.load(configfile, Loader=yaml.SafeLoader)

    return config


def get_finished_path():
    finished_path = []
    for s in app_config["ydl_options"].get("output").split("/"):
        if "%" in s and "%%" not in s:
            break
        finished_path.append(s)
    finished_path = "/".join(finished_path) + "/"
    if not os.path.isdir(finished_path):
        os.mkdir(finished_path, 0o755)
    return finished_path


app_config = load_config()

if (
    app_config is None
    or app_config.get("ydl_server") is None
    or app_config.get("ydl_options") is None
    or app_config["ydl_options"].get("output") is None
):
    raise Exception("Invalid configuration file")

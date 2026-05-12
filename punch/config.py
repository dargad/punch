import os
import glob
import yaml

try:
    from ruamel.yaml import YAML
except ImportError:
    YAML = None

def get_config_path():
    # Allow override with PUNCH_CONFIG_DIR, otherwise use ~/.config/punch
    config_dir = os.environ.get("PUNCH_CONFIG_DIR") or \
                 os.path.join(os.path.expanduser("~/.config"), "punch")
    return os.path.join(config_dir, "punch.yaml")

def get_config_d_path():
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(xdg_config_home, "punch", "punch.d")

def get_tasks_file():
    # Allow override with PUNCH_DATA_DIR, otherwise use ~/.local/share/punch
    data_dir = os.environ.get("PUNCH_DATA_DIR") or \
               os.path.join(os.path.expanduser("~/.local/share"), "punch")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "tasks.txt")

def _deep_merge(base, override):
    """
    Deep merge override into base. Override values take precedence.
    For dicts, merge recursively. For other types, override replaces base.
    """
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result

def load_config(config_path):
    """
    Load configuration. If ~/.config/punch/punch.d exists, read all *.yaml files
    from that directory in alphabetical order, merging them sequentially.
    Otherwise, load the single config file at config_path.
    """
    config_d_path = get_config_d_path()
    
    if os.path.isdir(config_d_path):
        config = {}
        yaml_files = sorted(glob.glob(os.path.join(config_d_path, "*.yaml")))
        for yaml_file in yaml_files:
            with open(yaml_file, "r") as f:
                file_config = yaml.safe_load(f) or {}
                config = _deep_merge(config, file_config)
        return config
    
    with open(config_path, "r") as f:
        return yaml.safe_load(f) or {}
    
def set_config_value(config, config_path, key, value):
    """
    Set a config value, preserving whitespace and comments in the YAML file.
    Requires ruamel.yaml.
    """
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    if YAML is None:
        raise ImportError("ruamel.yaml is required to preserve comments and formatting.")
    yaml_ruamel = YAML()
    yaml_ruamel.preserve_quotes = True
    # Load the original YAML preserving formatting
    with open(config_path, "r") as f:
        data = yaml_ruamel.load(f)
    data[key] = value
    with open(config_path, "w") as f:
        yaml_ruamel.dump(data, f)
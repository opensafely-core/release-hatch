from hatch import config, signing


signing.set_default_key(config.BACKEND_TOKEN, salt="hatch")

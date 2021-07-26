import argparse
import getpass
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from hatch import config, signing


def token(argv=sys.argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", help="workspace for token url")
    parser.add_argument("--user", "-u", default=getpass.getuser(), help="token user")
    parser.add_argument(
        "--scope", "-s", default="view", help="token scope [view, release, upload]"
    )
    parser.add_argument(
        "--duration", "-d", default=60, help="how many minutes is the token valid for"
    )

    args = parser.parse_args(argv[1:])

    url = urljoin(config.SERVER_HOST, f"/workspace/{args.workspace}")
    expiry = datetime.now(timezone.utc) + timedelta(minutes=args.duration)
    token = signing.AuthToken(url=url, user=args.user, expiry=expiry, scope=args.scope)
    print(token.sign())


if __name__ == "__main__":
    token()

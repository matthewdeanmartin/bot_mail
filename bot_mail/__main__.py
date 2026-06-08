"""Enable ``python -m bot_mail``."""

from __future__ import annotations

import sys

from bot_mail.cli import main

if __name__ == "__main__":
    sys.exit(main())

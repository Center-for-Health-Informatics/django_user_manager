#!/usr/bin/env python
"""Run the user_manager test suite standalone, without a host project.

python runtests.py [tests.test_views ...]
"""

import os
import sys

import django
from django.conf import settings
from django.test.utils import get_runner


def main(argv):
    os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings"
    django.setup()
    runner = get_runner(settings)(verbosity=2)
    return runner.run_tests(argv or ["tests"])


if __name__ == "__main__":
    sys.exit(bool(main(sys.argv[1:])))

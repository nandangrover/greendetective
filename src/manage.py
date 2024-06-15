#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'green_detective.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
        
    is_testing = "test" in sys.argv
    with_coverage = "--without-coverage" not in sys.argv

    if is_testing is True and with_coverage is True:
        import coverage

        work_dir = os.environ["WORKDIR"]
        config_file = f"{work_dir}/../coverage/.coveragerc"
        data_file = f"{work_dir}/../coverage/.coverage"
        coverage_instance = coverage.coverage(config_file=config_file, data_file=data_file)

        coverage_instance.start()

    execute_from_command_line(sys.argv)

    if is_testing is True and with_coverage is True:
        coverage_instance.stop()
        coverage_instance.combine()
        coverage_instance.html_report()
        coverage_instance.report()

if __name__ == '__main__':
    main()

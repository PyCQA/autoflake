#!/usr/bin/env python
"""Fuzz test against the latest packages on PyPI."""
import os
import subprocess
import sys
import tarfile
import zipfile

import test_fuzz


TMP_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                       'pypi_tmp')


def latest_packages(last_hours):
    """Return names of latest released packages on PyPI."""
    process = subprocess.Popen(
        ['yolk', f'--latest-releases={last_hours}'],
        stdout=subprocess.PIPE)

    for line in process.communicate()[0].decode('utf-8').split('\n'):
        if line:
            yield line.split()[0]


def download_package(name, output_directory):
    """Download package to output_directory.

    Raise CalledProcessError on failure.
    """
    subprocess.check_call(['yolk', f'--fetch-package={name}'],
                          cwd=output_directory)


def extract_package(path, output_directory):
    """Extract package at path."""
    if path.lower().endswith('.tar.gz'):
        try:
            tar = tarfile.open(path)
            tar.extractall(path=output_directory)
            tar.close()
            return True
        except (tarfile.ReadError, OSError):
            return False
    elif path.lower().endswith('.zip'):
        try:
            archive = zipfile.ZipFile(path)
            archive.extractall(path=output_directory)
            archive.close()
        except (zipfile.BadZipfile, OSError):
            return False
        return True

    return False


def main():
    """Run main."""
    try:
        os.mkdir(TMP_DIR)
    except OSError:
        pass

    args = test_fuzz.process_args()
    if args.files:
        # Copy
        names = list(args.files)
    else:
        names = None

    checked_packages = []
    skipped_packages = []
    last_hours = 1
    while True:
        if args.files:
            if not names:
                break
        else:
            while not names:
                # Continually populate if user did not specify a package
                # explicitly.
                names = [p for p in latest_packages(last_hours)
                         if p not in checked_packages and
                         p not in skipped_packages]

                if not names:
                    last_hours *= 2

        package_name = names.pop(0)
        print(package_name, file=sys.stderr)

        package_tmp_dir = os.path.join(TMP_DIR, package_name)
        try:
            os.mkdir(package_tmp_dir)
        except OSError:
            print('Skipping already checked package', file=sys.stderr)
            skipped_packages.append(package_name)
            continue

        try:
            download_package(
                package_name,
                output_directory=package_tmp_dir)
        except subprocess.CalledProcessError:
            print('yolk fetch failed', file=sys.stderr)
            continue

        for download_name in os.listdir(package_tmp_dir):
            try:
                if not extract_package(
                        os.path.join(package_tmp_dir, download_name),
                        output_directory=package_tmp_dir):
                    print('Could not extract package', file=sys.stderr)
                    continue
            except UnicodeDecodeError:
                print('Could not extract package', file=sys.stderr)
                continue

            args.files = [package_tmp_dir]
            if test_fuzz.check(args):
                checked_packages.append(package_name)
            else:
                return 1

    if checked_packages:
        print('\nTested packages:\n    ' + '\n    '.join(checked_packages),
              file=sys.stderr)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)

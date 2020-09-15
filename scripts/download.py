#!/usr/bin/env python
# coding: utf-8

import sys
import os
import argparse
import csv
import requests


def load_file(filename):
    with open(filename, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter='|')

        line_count = 0
        for row in csv_reader:
            if not line_count == 0:
                params = {
                    "url": row['youtube_url'],
                    "format": "bestvideo",
                    "filename": row['video_id']
                }
                requests.post(
                    'http://localhost:8080/youtube-dl/q', data=params)

            line_count += 1


def arg_parser():
    parser = argparse.ArgumentParser(description="Download youtube videso from csv.")
    parser.add_argument("--file", type=str, help="Path to the CSV file.")

    args = parser.parse_args()

    return args


def main():
    args = arg_parser()

    if not args:
        print("usage:  --file <path to the csv file>")
        sys.exit(1)
    elif not os.path.exists(args.file):
        print("File does not exist: " + args.file)
        sys.exit(1)

    load_file(args.file)


if __name__ == "__main__":
    main()

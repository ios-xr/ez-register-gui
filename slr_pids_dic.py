#!/usr/bin/env python

from netmiko import ConnectHandler
import requests
from argparse import ArgumentParser
import logging

# convert dictionary string to dictionary
# using json.loads()
import json

# copy auth_code file to the router
from paramiko import SSHClient
from scp import SCPClient
import os

# read input from excel sheet
import xlrd

# write output to the excel sheet
#import xlwt

# call sleep before retrieving smart license status
import time

if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument("-v", "--verbose", help="print debugging messages",
                        action="store_true")
    parser.add_argument("input_file",
                        help="input file location")
    args = parser.parse_args()

    entitlement_Tags = {}
    # log debug messages if verbose argument specified
    if args.verbose:
        logger = logging.getLogger("SLR")
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(("%(asctime)s - %(name)s - "
                                      "%(levelname)s - %(message)s"))
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Read the excel sheet
    print("================================")
    print("Reading the excel sheet")
    print("================================")
    input_file = args.input_file
    wb = xlrd.open_workbook(input_file)
    sheet = wb.sheet_by_index(0)
    dict = {}
    pid_val = []
    pid = ""
    for i in range(1, sheet.nrows):
        if sheet.cell_value(i, 0) == "" and sheet.cell_value(i, 1) == "":
           break
        elif sheet.cell_value(i, 0) != "":
           if pid != "":
              dict[pid] = pid_val
           pid_val = []
       	   pid = sheet.cell_value(i, 0)
           pid_val.append(sheet.cell_value(i, 1))
        else:
           pid_val.append(sheet.cell_value(i, 1))
    print(json.dumps(dict, sort_keys=True, indent=4))

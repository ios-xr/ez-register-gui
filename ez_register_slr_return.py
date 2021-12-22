#!/usr/bin/env python

from netmiko import ConnectHandler
import requests
from argparse import ArgumentParser
import logging

# convert dictionary string to dictionary
# using json.loads()
import json

# read input from excel sheet
import xlrd

# write output to the excel sheet
import xlwt

# call sleep before retrieving smart license status
import time


if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument("-v", "--verbose", help="print debugging messages",
                        action="store_true")
    parser.add_argument("input_file",
                        help="input file location")
    args = parser.parse_args()

    # Add  logs to the file
    log_Format = "%(levelname)s %(asctime)s - %(message)s"
    input_file = args.input_file
    filepath_list = input_file.split("/")
    filename = filepath_list[len(filepath_list)-1].split(".")[0]
    timestr = time.strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(filename = filename + "_" + timestr + ".log",
                        filemode = "w",
                        format = log_Format,
                        level = logging.INFO)
    logger = logging.getLogger()

    # Initialize output file
    wb_output = xlwt.Workbook()
    sheet_output = wb_output.add_sheet('output')
    sheet_output.write(0, 0, "Hostname")
    sheet_output.write(0, 1, "Username")
    sheet_output.write(0, 2, "SLR Return Status")

    # # Initializing license return reservation payload
    # logger.info("=====================================================")
    # logger.info("Initializing license return reservation payload")
    # logger.info("=====================================================")

    # Read the excel sheet
    logger.info("================================")
    logger.info("Reading the excel sheet")
    logger.info("================================")
    wb = xlrd.open_workbook(input_file)
    sheet = wb.sheet_by_index(0)
    for i in range(1, sheet.nrows):
        if sheet.cell_value(i, 0) == "":
           break
        elif sheet.cell_value(i, 0) != "":
       	   hostname = sheet.cell_value(i, 0)
           username = sheet.cell_value(i, 1)
           password = sheet.cell_value(i, 2)
           smart_account = sheet.cell_value(i, 3)
           virtual_account = sheet.cell_value(i, 4)
           client_id = sheet.cell_value(i, 5)
           client_secret = sheet.cell_value(i, 6)

           sheet_output.write(i, 0, hostname)
           sheet_output.write(i, 1, username)

           # connect to the devices
           logger.info("================================")
           logger.info("connecting to the node")
           logger.info("================================")
           device = ConnectHandler(device_type='cisco_xr', ip=hostname, username=username, password=password)
           device.find_prompt()

           # check initial registration status
           initial_license_status = device.send_command("show license status")
           if "Status: REGISTERED" in initial_license_status:
              # create reservation return code
              logger.info("============================================================")
              logger.info("Retrieveing reservation return code from the node")
              logger.info("============================================================")
              output = device.send_command("license smart reservation return local ")
              return_code = output.split("portal:")[1].replace("\n", "")

              # Retrieve payload info
              udi = device.send_command("show license techsupport | include UDI:")
              udi_sn = udi.split("\n")[2].split(":")[3]
              udi_pid = udi.split("\n")[2].split(":")[2].split(",")[0]
              software_id = device.send_command("show license techsupport | include Software ID:")
              prod_tag_name = software_id.split("\n")[2].split(": ")[1]

              # create bearer access token
              logger.info("=================================================")
              logger.info("Creating access token to securely connect CSSM")
              logger.info("=================================================")
              url = "https://cloudsso.cisco.com/as/token.oauth2"
              params = {
                   'grant_type': "client_credentials",
                   'client_id': client_id,
                   'client_secret': client_secret
              }
              response = requests.request("POST", url,  params=params)
              logger.info(response.text)
              # using json.loads()
              # convert dictionary string to dictionary
              bearer = json.loads(response.text)
              access_token = bearer["access_token"]

              # SLR on CSSM
              logger.info("=============================================")
              logger.info("Constructing SLR return REST API")
              logger.info("=============================================")
              url = "https://swapi.cisco.com/services/api/smart-accounts-and-licensing/v2/accounts/" + smart_account + "/virtual-accounts/" + virtual_account + "/devices/remove"
              headers = {
    	            'Authorization': ' '.join(('Bearer',access_token)),
                    'Content-Type':'application/json',
                    'Accept':'application/json'
    	      }
              payload = {"productInstacesRemoveRequests":[{
                             "sudi": {
                               "udiPid": udi_pid,
                               "udiSerialNumber": udi_sn
                             },
                             "productTagName": prod_tag_name,
                             "returnCode": return_code
                           }]
                         }
              data = json.dumps(payload)

              logger.info("====================================================================================")
              logger.info("Executing SLR REST API to return reservation")
              logger.info("====================================================================================")
              response = requests.request("POST", url,  data=data, headers=headers)
              logger.info(response.text)
              result = json.loads(response.text)

              registered = False
              # verify SLR return status
              logger.info("==============================================")
              logger.info("verify SLR return status")
              logger.info("===============================================")
              if result['status'] == "SUCCESS":
                 registered = True

              if registered:
                 sheet_output.write(i, 2, "succcess")
                 logger.info("===================================================")
                 logger.info("===================================================")
                 logger.info("SLR return completed!!")
                 logger.info("====================================================")
                 logger.info("====================================================")
              else:
                 sheet_output.write(i, 2, "failed")
                 logger.info("===================================================")
                 logger.info("===================================================")
                 logger.info("SLR reservation failed!!")
                 logger.info("====================================================")
                 logger.info("====================================================")

           # disconnect device
           device.disconnect()
    wb_output.save(filename + "_output_" + timestr + ".xls")

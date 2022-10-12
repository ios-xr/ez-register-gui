#!/usr/bin/env python3

from netmiko import ConnectHandler
import requests
from argparse import ArgumentParser
import logging
import threading
# convert dictionary string to dictionary
# using json.loads()
import json

# read input from excel sheet
import xlrd

# write output to the excel sheet
import xlwt

# call sleep before retrieving smart license status
import time

# dictionary to store registration status of a node
registration_status = {}

# initialize tokens dictionary
sa_va_tokens = {}

# Initialize output file
wb_output = xlwt.Workbook()
sheet_output = wb_output.add_sheet('output')
sheet_output.write(0, 0, "Hostname")
sheet_output.write(0, 1, "Username")
sheet_output.write(0, 2, "SL Registration Status")
sheet_output.write(0, 3, "License Authorization Status")
sheet_output.write(0, 4, "Device Name")


def register(hostname, username, password, smart_account,
             virtual_account, fcm, description, expires_after_days,
             export_controlled, client_id, client_secret,
             vrf, reregister, device_name, i):
    print("register vrf :" + vrf)
    try:
        # connect to the devices
        logger.info("================================")
        logger.info("connecting to the node")
        logger.info("================================")
        device = ConnectHandler(device_type='cisco_xr', ip=hostname, username=username, password=password)
        device.find_prompt()

        # check initial registration status
        initial_license_status = device.send_command("show license status")
        logger.info(initial_license_status)
        if "Status: REGISTERED" in initial_license_status and not (reregister.upper() == "YES" or reregister.upper() == "Y"):
            actual_smart_account = device.send_command("show license status | include Smart Account:").split("Smart Account: ")[1]
            actual_virtual_account = device.send_command("show license status | include Virtual Account:").split("Virtual Account: ")[1]
            reg_status = " Already registered with the Smart Account: " + actual_smart_account + " and the Virtual Account: " + actual_virtual_account
            print("Host: " + hostname + " - " + reg_status)
            sheet_output.write(i, 2, reg_status)
            registration_status[hostname] = True
            lic_auth = device.send_command("show license status | begin License Authorization")
            # TODO: split number varies between 2 or 3 based on the env
            logger.info(lic_auth.split('\n'))
            auth = lic_auth.split('\n')
            comp_stat = ""
            if 'Status' in auth[3]:
                comp_stat = auth[3].split("Status: ")[1]
            elif 'Status' in auth[2]:
                comp_stat = auth[2].split("Status: ")[1]
            sheet_output.write(i, 3, comp_stat)
        elif "Status: REGISTERED" in initial_license_status and (reregister.upper() == "YES" or reregister.upper() == "Y"):
            deregister = device.send_command("license smart deregister ")
            logger.info(deregister)
        license_status = device.send_command("show license status")
        if "Status: REGISTERED" not in initial_license_status:
            # configure call-home
            logger.info("====================================================================")
            logger.info("Configuring Call Home")
            logger.info("====================================================================")
            if vrf:
                config_commands = ['call-home',
                                   'vrf ' + vrf, 'profile CiscoTAC-1',
                                   'destination address http https://tools.cisco.com/its/service/oddce/services/DDCEService',
                                   'commit', 'end']
                output = device.send_config_set(config_commands)
            else:
                config_commands = ['call-home', 'profile CiscoTAC-1',
                                   'destination address http https://tools.cisco.com/its/service/oddce/services/DDCEService',
                                   'commit', 'end']
                output = device.send_config_set(config_commands)
            logger.info(output)

            if (smart_account, virtual_account) in sa_va_tokens:
                idtoken = sa_va_tokens[(smart_account, virtual_account)]
            else:
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

                # Constructing Retrieve Existing Tokens Rest API
                logger.info("=============================================")
                logger.info("Constructing Retrieve Existing Tokens Rest API")
                logger.info("=============================================")
                tokens_url = "https://swapi.cisco.com/services/api/smart-accounts-and-licensing/v1/accounts/" + smart_account + "/virtual-accounts/" + virtual_account + "/tokens"
                headers = {
                     'Authorization': ' '.join(('Bearer',access_token)),
                     'Content-Type': 'application/json',
                     #'Content-Type':'application/x-www-form-urlencoded',
                     'Accept': 'application/json'
                }

                logger.info("====================================================================================")
                logger.info("Executing SL REST API to Retrieve Existing Tokens in CSSM")
                logger.info("====================================================================================")
                existing_tokens = requests.request("GET", tokens_url, headers=headers)
                logger.info(response.text)
                # using json.loads()
                # convert dictionary string to dictionary
                tokens = json.loads(existing_tokens.text)
                logger.info(tokens)
                if len(tokens['tokens']) != 0:
                    idtoken = tokens['tokens'][0]['token']
                else:
                    logger.info("There are no existing token available")
                    # Contructing Create New Token Rest API
                    logger.info("=============================================")
                    logger.info("Constructing Create New token REST API")
                    logger.info("=============================================")
                    url = "https://swapi.cisco.com/services/api/smart-accounts-and-licensing/v1/accounts/" + smart_account + "/virtual-accounts/" + virtual_account + "/tokens"
                    headers = {
                     'Authorization': ' '.join(('Bearer', access_token)),
                     'Content-Type': 'application/json',
                     # 'Content-Type': 'application/x-www-form-urlencoded',
                     'Accept': 'application/json'
                    }

                    data = {}
                    data["description"] = description
                    data["expiresAfterDays"] = expires_after_days
                    data["exportControlled"] = export_controlled

                    data = json.dumps(data)
                    logger.info("====================================================================================")
                    logger.info("Executing SL REST API to generate registration token in CSSM")
                    logger.info("====================================================================================")
                    response = requests.request("POST", url, data=data, headers=headers)
                    logger.info(response.text)
                    # using json.loads()
                    # convert dictionary string to dictionary
                    token = json.loads(response.text)
                    idtoken = token["tokenInfo"]["token"]
                sa_va_tokens[(smart_account, virtual_account)] = idtoken

            # register smart license idtoken on the node
            logger.info("==============================================")
            logger.info("registering smart license idtoken")
            logger.info("===============================================")
            reg_output = device.send_command("license smart register idtoken " + idtoken)
            logger.info(reg_output)

            if fcm.upper() == "YES" or fcm.upper() == "Y":
                # enable license smart reservation configuration
                logger.info("====================================================================")
                logger.info("enabling license smart flexible-consumption on the node")
                logger.info("====================================================================")
                config_commands = ['license smart flexible-consumption enable', 'commit', 'end']
                output = device.send_config_set(config_commands)
                logger.info(output)
                logger.info("===================================================")
                logger.info("FCM is enabled successfully!!")
                logger.info("====================================================")

            print("Host: " + hostname + " - Registration attempt completed")

            print("\nBeginning Verification")

            registered = False
            lic_auth = device.send_command("show license status | begin License Authorization")
            comp_stat = lic_auth.split('\n')[2].split("Status: ")[1]
            sheet_output.write(i, 3, comp_stat)

            # register smart license status
            logger.info("==============================================")
            logger.info("registering smart license status (waiting for 30 sec to allow device to complete the registration....")
            logger.info("===============================================")
            time.sleep(30)
            license_status = device.send_command("show license status")
            if "Status: REGISTERED" in license_status:
                registered = True
            logger.info(license_status)

            if registered:
                sheet_output.write(i, 2, "succcess")
                registration_status[hostname] = True
                print("Host: " + hostname + " - Registration Successful")
                logger.info("===================================================")
                logger.info("===================================================")
                logger.info("SL registration completed successfully!!")
                logger.info("====================================================")
                logger.info("====================================================")
            else:
                sheet_output.write(i, 2, "failed")
                registration_status[hostname] = False
                print("Host: " + hostname + " - Registration Failed")
                logger.info("===================================================")
                logger.info("===================================================")
                logger.info("SL registration failed!!")
                logger.info("====================================================")
                logger.info("====================================================")

            # disconnect device
            device.disconnect()
    except Exception as e:
        logger.info("="*60)
        logger.info("Exception!!")
        logger.info("="*60)
        err = str(e)
        logger.info(err)
        print("Host: " + device_name + " - Registration attempt failed" + ". Exception: " + err)


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
    logging.basicConfig(filename=filename + "_" + timestr + ".log",
                        filemode="w",
                        format=log_Format,
                        level=logging.INFO)
    logger = logging.getLogger()

    thread_list = []

    # Read the excel sheet
    logger.info("================================")
    logger.info("Reading the excel sheet")
    logger.info("================================")
    wb = xlrd.open_workbook(input_file)
    sheet = wb.sheet_by_index(0)
    print("Beginning Registration Attempts")
    for i in range(1, sheet.nrows):
        if sheet.cell_value(i, 0) == "":
            break
        else:
            logger.info("Retrieving data of " + str(i) + " st/nd/th node")
            hostname = sheet.cell_value(i, 0)
            username = sheet.cell_value(i, 1)
            password = sheet.cell_value(i, 2)
            smart_account = sheet.cell_value(i, 3)
            virtual_account = sheet.cell_value(i, 4)
            fcm = sheet.cell_value(i, 5)
            description = sheet.cell_value(i, 6)
            expires_after_days = sheet.cell_value(i, 7)
            export_controlled = sheet.cell_value(i, 8)
            client_id = sheet.cell_value(i, 9)
            client_secret = sheet.cell_value(i, 10)
            vrf = sheet.cell_value(i, 11)
            reregister = sheet.cell_value(i, 12)
            device_name = sheet.cell_value(i, 13)
            logger.info("hostname : " + hostname)

            # Replace space with %20 in SA name
            smart_account = smart_account.replace(" ", "%20")


            #t = threading.Thread(target=register,
            #                     args=(hostname, username, password, reregister,
            #                           smart_account, virtual_account, fcm,
            #                           description, expires_after_days,
            #                           export_controlled, client_id, client_secret,
            #                           vrf, device_name, i))
            t = threading.Thread(target=register,
                     args=(hostname, username, password,
                           smart_account, virtual_account, fcm,
                           description, expires_after_days,
                           export_controlled, client_id, client_secret,
                           vrf, reregister, device_name, i))
            thread_list.append(t)
            t.start()

    for t in thread_list:
        t.join()

    count = 0
    for key in registration_status:
        if registration_status[key]:
            count += 1

    print("\nOut of " + str(sheet.nrows-1) + " node(s), " + str(count) + " node(s) is/are successfully registered")
    folder = "output_files/"
    wb_output.save(folder + filename + "_output_" + timestr + ".xls")

#!/usr/bin/env python3

from netmiko import ConnectHandler
from argparse import ArgumentParser
import logging
import threading


# read input from excel sheet
import xlrd

# call sleep before retrieving smart license status
import time


def check_reachabilty(hostname, username, password, device_name, i):
    try:
        timestr = time.strftime("%Y%m%d_%H%M%S")
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(folder + hostname + "_" + filename + "_" + timestr + ".log")
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(log_Format)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # connect to the devices
        logger.info("="*60)
        logger.info("connecting to the node " + device_name)
        logger.info("="*60)
        device = ConnectHandler(device_type='cisco_ios', ip=hostname, username=username, password=password)
        device.find_prompt()

        logger.info("="*60)
        logger.info("config t")
        logger.info("="*60)
        config_commands = ['end']
        config_commands_output = device.send_config_set(config_commands)
        # term_length += device.send_command('\n', expect_string=r'#', delay_factor=3)
        logger.info(config_commands_output)

        print(device_name + " node" + str(i) + " : command executed succesfully")

        logger.info("="*80)
        logger.info("="*80)

        device.disconnect()
        logger.removeHandler(handler)

    except Exception as e:
        logger.info("="*60)
        logger.info("Exception!!")
        logger.info("="*60)
        err = str(e)
        logger.info(err)
        print("Host: " + device_name + " - command execution failed" + ". Exception: " + err)
        logger.info("Host: " + device_name + " - command execution failed" + ". Exception: " + err)
        logger.info("="*80)
        logger.info("="*80)


if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument("-v", "--verbose", help="print debugging messages",
                        action="store_true")
    parser.add_argument("input_file",
                        help="input file location")
    parser.add_argument("num",
                        help="number of parallel threads")
    args = parser.parse_args()

    thread_list = []

    # Add  logs to the file
    log_Format = "%(levelname)s %(asctime)s - %(message)s"
    input_file = args.input_file
    number = int(args.num)
    filepath_list = input_file.split("/")
    filename = filepath_list[len(filepath_list)-1].split(".")[0]
    folder = "logs/"
    timestr = time.strftime("%Y%m%d_%H%M%S")

    main_logger = logging.getLogger()
    main_logger.setLevel(logging.INFO)
    main_handler = logging.FileHandler(folder + filename + "_" + timestr + ".log")
    main_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(log_Format)
    main_handler.setFormatter(formatter)
    main_logger.addHandler(main_handler)


    # Read the excel sheet
    main_logger.info("="*60)
    main_logger.info("Reading the excel sheet")
    main_logger.info("="*60)
    wb = xlrd.open_workbook(input_file)
    sheet = wb.sheet_by_index(0)
    print("Beginning Command Execution")
    main_logger.info("="*60)
    main_logger.info("Beginning Command Execution")
    main_logger.info("="*60)
    num = 0

    for i in range(1, sheet.nrows):
        if sheet.cell_value(i, 0) == "":
            break
        else:
            main_logger.info("="*80)
            main_logger.info("Retrieving data of " + str(i) + " st/nd/th node")
            main_logger.info("="*80)

            hostname = sheet.cell_value(i, 0)
            username = sheet.cell_value(i, 1)
            password = sheet.cell_value(i, 2)
            device_name = sheet.cell_value(i,16)

            t = threading.Thread(target=check_reachabilty, args=(hostname, username, password, device_name, i))
            thread_list.append(t)
            t.start()

            if num == number:
                time.sleep(60)
                num = 0

    for t in thread_list:
        t.join()

    main_logger.info("Login attempts Completed")
    main_logger.removeHandler(main_handler)

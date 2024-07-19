# -*- coding: utf-8 -*-

import os
import json
from colorama import Fore, Back, Style

class Pretty:
    """
    A utility class for pretty printing dictionaries and lists.

    Example usage:
    ```
    data = {'a': 1, 'b': 2}
    PrettyPrint(data)
    ```
    """

    OK_COLOR = Fore.GREEN
    FAILED_COLOR = Fore.RED

    def log(data, file_path='./log.txt', overwrite=False, mode='w'):
        """
        Log data to a file with format.

        Args:
            data (dict or list): The data to log.
            file_path (str): The path to the file where the log should be written.
            mode (str): The file mode (e.g., 'w' for write, 'a' for append). Defaults to 'w'.
            overwrite (bool): Whether to overwrite the file or not. Defaults to False.
        """
        if not overwrite and os.path.exists(file_path):
            print(f'File {file_path} already exists. Set overwrite=True to overwrite it.')
            return
        
        with open(file_path, mode) as file:
            if type(data) == dict:
                json.dump(data, file, indent=4)
            elif type(data) == list:
                for item in data:
                    json.dump(item, file, indent=4)
                    file.write('\n')
            else:
                file.write(data)
            
            file.write('\n')


    def print(data, state=OK_COLOR):
        """
        Print the data.

        Args:
            data (dict or list): The data to print.
            state (str): The state color to use for printing. Defaults to OK_COLOR.
        """
        if type(data) == dict:
            Pretty._print_dict(data, state)
        elif type(data) == list:
            Pretty._print_list(data, state)
        else:
            print(state + data)
            print(Style.RESET_ALL)

    def _print_dict(self, data, state):
        """
        Pretty print a dictionary.

        Args:
            data (dict): The dictionary to print.
            state (str): The state color to use for printing.
        """
        for key, value in data.items():
            print(state + str(key) + ': ' + Style.RESET_ALL + str(value))

    def _print_list(self, data, state):
        """
        Pretty print a list of dictionaries.

        Args:
            data (list): The list to print.
            state (str): The state color to use for printing.
        """
        for item in data:
            self._print_dict(item, state)
            print(Style.RESET_ALL + '\n')

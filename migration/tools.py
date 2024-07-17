# -*- coding: utf-8 -*-

from colorama import Fore, Back, Style

class PrettyPrint:
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

    def __init__(self, data, state=OK_COLOR):
        """
        Initialize the PrettyPrint object.

        Args:
            data (dict or list): The data to print.
            state (str): The state color to use for printing. Defaults to OK_COLOR.
        """
        if type(data) == dict:
            self._print_dict(data, state)
        elif type(data) == list:
            self._print_list(data, state)
        else:
            print(state + data)
            print(Style.RESET_ALL + '\n')

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

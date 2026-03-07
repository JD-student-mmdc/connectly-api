import logging
import sys

class LoggerSingleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LoggerSingleton, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.logger = logging.getLogger("connectly_logger")
        self.logger.handlers.clear()
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        file_handler = logging.FileHandler('connectly.log')
        file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        self.logger.setLevel(logging.INFO)

    def get_logger(self):
        return self.logger
import logging
import datetime as dt


def log_examples(extra_words):
    logger = logging.getLogger(__name__)
    logger.debug("hey im debugging!")
    logger.info("infoing %s", extra_words)
    logger.warning("Hell is here!")
    logger.error("something's not right")
    logger.critical("OMG critical error!")
    # TODO: read https://docs.python.org/3/library/logging.html for effective logging


def log_keeper(file_path):
    if file_path is None:
        file_path = "info.log"
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)

    file_handler = logging.FileHandler(f"C:\\Users\\User\\Desktop\\Learn_Coding\\Portfolio_Projects\\"
                                       f"trade-bot-first\\logfiles\\{file_path}")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
# logger.info("im actually a logkeeper file.")


if __name__ == '__main__':
    log_keeper()
    log_examples("helloo")

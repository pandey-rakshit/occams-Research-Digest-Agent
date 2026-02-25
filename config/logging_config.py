import logging
import os
import warnings

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "pipeline.log")


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    root_logger.handlers.clear()

    file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    noisy_loggers = [
        "httpx",
        "httpcore",
        "urllib3",
        "sentence_transformers",
        "huggingface_hub",
        "transformers",
        "safetensors",
        "filelock",
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.ERROR)

    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["TRANSFORMERS_VERBOSITY"] = "error"

    warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")
    warnings.filterwarnings("ignore", category=FutureWarning)

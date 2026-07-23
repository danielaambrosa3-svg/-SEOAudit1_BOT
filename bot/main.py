import logging

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from bot import config
from bot import handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_cmd))
    app.add_handler(CommandHandler("backlinks", handlers.backlinks))
    app.add_handler(MessageHandler(filters.COMMAND, handlers.unknown))

    logger.info("Bot starting (long polling)...")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()

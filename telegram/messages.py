from aiogram.types import Message


async def answer_long_message(message: Message, text: str) -> None:
    limit = 4096
    while text:
        end = min(len(text), limit)
        if len(text) > limit:
            newline = text.rfind('\n', 0, limit)
            if newline >= 0:
                end = newline + 1

        await message.answer(text[:end])
        text = text[end:]

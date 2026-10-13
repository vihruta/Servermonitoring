from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from telegram.messages import answer_long_message


@pytest.mark.asyncio
@pytest.mark.parametrize('text', [
    'Короткий ответ',
    'А' * 4096,
    'Диск: /dev/nvme0n1\n' * 500,
    'Я' * 9000,
])
async def test_long_answers_keep_all_text_within_message_limit(text):
    message = SimpleNamespace(answer=AsyncMock())

    await answer_long_message(message, text)

    parts = [call.args[0] for call in message.answer.await_args_list]
    assert ''.join(parts) == text
    assert all(0 < len(part) <= 4096 for part in parts)
    if len(text) <= 4096:
        message.answer.assert_awaited_once_with(text)


@pytest.mark.asyncio
async def test_long_answer_splits_between_lines():
    message = SimpleNamespace(answer=AsyncMock())
    first_line = 'А' * 3000 + '\n'
    second_line = 'Б' * 2000

    await answer_long_message(message, first_line + second_line)

    parts = [call.args[0] for call in message.answer.await_args_list]
    assert parts == [first_line, second_line]

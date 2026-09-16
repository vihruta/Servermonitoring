from types import SimpleNamespace

import pytest

from telegram.filters import AllowedUserFilter

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_id, expected",
    [(123, True),
    (456, False),
    (None, False)]
)

async def test_allowed_user_filter(user_id, expected):
    user_filter = AllowedUserFilter(
        allowed_users={123}
    )

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=user_id)
    )

    result = await user_filter(message)

    assert result == expected

    
@pytest.mark.asyncio
async def test_allowed_user_filter_user_none():
    user_filter = AllowedUserFilter(
        allowed_users={123}
    )
    
    message = SimpleNamespace(
        from_user=None
    )

    result = await user_filter(message)

    assert result == False
import aiohttp


async def refresh_access_token(refresh_token: str, refresh_url: str) -> str:
    """Оновлює access token за допомогою refresh token."""
    data = {
        "refresh_token": refresh_token
    }

    headers = {
        'Content-Type': 'application/json'
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(refresh_url, json=data, headers=headers) as response:
            if response.status == 200:
                response_data = await response.json()
                return response_data["access_token"]
            else:
                raise PermissionError("Помилка оновлення токену. Можливо, refresh токен недійсний.")

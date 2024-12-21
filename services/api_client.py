from lib2to3.fixes.fix_input import context

import aiohttp
import requests
from decouple import config

CLIENT_NAME = config('CLIENT_NAME')
CLIENT_PASSWORD = config('CLIENT_PASSWORD')


async def register_user(user_id, user_data):
    """Реєстрація користувача через API"""
    url = "https://bot.bckwdd.fun/auth/register/"
    data = {
        "phone_num": user_data["phone_num"],
        "tg_id": str(user_id),
        "firstname": user_data["firstname"],
        "lastname": user_data["lastname"],
        "patronymic": user_data["patronymic"],
        "role_id": user_data["role_id"],
        "client": CLIENT_NAME,
        "password": CLIENT_PASSWORD,
    }

    if user_data["role_id"] == 2:
        location = user_data.get("location", {})
        if location:
            data["location"] = location

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data) as response:
            if response.status != 201:
                raise Exception(f"Помилка API: {response.status}, {await response.text()}")


import aiohttp

API_URL = "https://bot.bckwdd.fun"


async def login_user(login_request):
    """Відправка запиту на авторизацію користувача."""
    url = f"{API_URL}/auth/login/"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=login_request) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 400:
                data = await response.json()
                raise ValueError(data.get("detail", "Invalid request"))
            elif response.status == 403:
                data = await response.json()
                raise PermissionError(data.get("detail", "Forbidden"))
            else:
                raise Exception(f"Unexpected error: {response.status}")


import logging

logging.basicConfig(level=logging.INFO)


async def edit_volunteer_location_and_categories(access_token, location, categories):
    url = "https://bot.bckwdd.fun/volunteer/profile/"

    payload = {
        "location": location if location else None,
        "categories": categories if categories else []
    }

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    logging.info(f"URL: {url}")
    logging.info(f"Headers: {headers}")
    logging.info(f"Payload: {payload}")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.put(url, headers=headers, json=payload) as response:
                response_text = await response.text()

                logging.info(f"Response Status: {response.status}")
                logging.info(f"Response Text: {response_text}")

                if response.status == 200:
                    return await response.json()
                else:
                    logging.error(f"Error: {response.status} - {response_text}")
                    return None
        except aiohttp.ClientError as e:
            logging.error(f"HTTP request error: {str(e)}")
            return None


import logging
import aiohttp

logger = logging.getLogger(__name__)


async def deactivate_volunteer_account(access_token: str) -> bool:
    url = "https://bot.bckwdd.fun/volunteer/profile/"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.delete(url, headers=headers) as response:
                if response.status == 204:
                    return True
                else:
                    error_message = await response.json()
                    detail = error_message.get("detail", "Unknown error occurred.")
                    logging.error(f"Unexpected error in deactivate_volunteer_account: {detail}")

                    # Handle specific backend errors
                    if "Multiple rows were found" in detail:
                        raise RuntimeError(
                            "Database inconsistency detected: Multiple profiles found for your account. "
                            "Please contact support."
                        )
                    else:
                        raise RuntimeError(detail)
        except aiohttp.ClientError as e:
            logging.error(f"HTTP request error: {str(e)}")
            raise RuntimeError("A network error occurred. Please try again later.")
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            raise


import aiohttp
import logging

# Логування
logging.basicConfig(level=logging.INFO)


async def get_applications_by_status(access_token: str, status: str):
    url = f"{API_URL}/volunteer/applications/?type={status}"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    logging.info(f"Sending request to: {url} with headers: {headers}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    applications = await response.json()
                    return applications
                else:
                    logging.error(f"Error fetching applications: {response.status}")
                    return {"detail": f"Error: {response.status}"}
    except Exception as e:
        logging.error(f"Request failed: {str(e)}")
        return {"detail": "Error: Unable to fetch applications."}


async def accept_application(access_token, application_id):
    """
    Прийняти заявку поточним волонтером.

    :param access_token: Токен доступу для авторизації
    :param application_id: ID заявки, яку волонтер приймає
    :return: Інформація про оновлену заявку
    """
    url = f"{API_URL}/volunteer/applications/accept/"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"application_id": application_id}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 403:
                raise PermissionError("Access denied. User not verified by moderator")
            elif response.status == 404:
                error_detail = await response.json()
                raise ValueError(error_detail.get("detail", "Resource not found"))
            elif response.status == 500:
                error_detail = await response.json()
                raise Exception(f"Server error: {error_detail.get('detail', 'Unknown error')}")
            else:
                response.raise_for_status()


from aiohttp import FormData, ClientSession


async def close_application(access_token, application_id, files):
    """Закриття заявки із завантаженням файлів."""
    url = f"https://bot.bckwdd.fun/volunteer/applications/close/"
    headers = {"Authorization": f"Bearer {access_token}"}

    form_data = aiohttp.FormData()
    form_data.add_field("application_id", str(application_id))

    for file_name, file_content in files:
        form_data.add_field(
            "files",
            file_content,
            filename=file_name,
            content_type="application/octet-stream"
        )

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=form_data) as response:
            if response.status == 413:
                logging.error("Помилка: Завеликий розмір даних (Payload Too Large)")
            return await response.json()


async def login_moderator(login_request):
    """Відправка запиту на авторизацію модератора."""
    url = f"{API_URL}/moderator/login/"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=login_request) as response:
            if response.status == 200:
                return await response.json()  # Успішна авторизація
            elif response.status == 400:
                data = await response.json()
                raise ValueError(data.get("detail", "Invalid request"))
            elif response.status == 403:
                data = await response.json()
                raise PermissionError(data.get("detail", "Forbidden"))
            else:
                raise Exception(f"Unexpected error: {response.status}")


async def create_or_activate_category(name: str, parent_id: int = None, access_token: str = "") -> dict:
    """
    Створює нову категорію або активує існуючу через API.

    Args:
        name (str): Назва категорії.
        parent_id (int, optional): Ідентифікатор батьківської категорії.
        access_token (str): Токен доступу модератора.

    Returns:
        dict: Дані категорії у разі успіху.
    """
    url = f"{API_URL}/moderator/categories/"  # Замініть на реальний URL
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "name": name,
    }
    if parent_id is not None:
        payload["parent_id"] = parent_id

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 201:
                    return await response.json()
                elif response.status == 400:
                    error_message = await response.json()
                    raise ValueError(error_message.get("detail", "Unknown error"))
                else:
                    error_message = await response.json()
                    raise RuntimeError(f"Unexpected error: {error_message.get('detail', 'Unknown error')}")
    except Exception as e:
        raise RuntimeError(f"Помилка при створенні категорії: {str(e)}")


async def deactivate_category(category_id: int, access_token: str) -> dict:
    url = f"{API_URL}/moderator/categories/"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"id": category_id}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, json=payload, headers=headers) as response:
                if response.status == 204:
                    return {"detail": "Категорія успішно деактивована"}
                elif response.status == 404:
                    error_message = await response.json()
                    raise ValueError(error_message.get("detail", "Категорія не знайдена"))
                else:
                    error_message = await response.json()
                    raise RuntimeError(error_message.get("detail", "Невідома помилка"))
    except Exception as e:
        raise RuntimeError(f"Помилка при деактивації категорії: {str(e)}")


async def deactivate_application(application_id: int, access_token: str):
    """Деактивація заявки за її ID."""
    url = f"{API_URL}/moderator/applications/"

    if not access_token:
        raise PermissionError("Не знайдено токен доступу. Будь ласка, авторизуйтесь.")

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    data = {
        "application_id": application_id
    }

    async with aiohttp.ClientSession() as session:
        async with session.delete(url, json=data, headers=headers) as response:
            if response.status == 204:
                return {"detail": "Application deleted successfully"}
            elif response.status == 404:
                data = await response.json()
                raise ValueError(data.get("detail", "Application not found"))
            elif response.status == 401:
                raise PermissionError("Помилка авторизації: Токен не є дійсним.")
            else:
                raise Exception(f"Unexpected error: {response.status}")


async def verify_user(user_id: int, is_verified: bool, access_token: str, refresh_token: str, refresh_url: str):
    """Оновлення статусу верифікації користувача з перевіркою токену."""
    url = f"{API_URL}/moderator/verify_user/"

    data = {
        "user_id": user_id,
        "is_verified": is_verified
    }

    try:
        response_data = await make_authenticated_request_with_refresh(
            url,
            "POST",
            access_token,
            refresh_token,
            refresh_url,
            json=data
        )
        return response_data
    except Exception as e:
        print(f"Error in verify_user: {str(e)}")
        raise


async def refresh_access_token(refresh_token: str, refresh_url: str) -> str:
    """
    Оновлює токен доступу за допомогою `refresh_token`.

    Args:
        refresh_token (str): Токен для оновлення.
        refresh_url (str): URL для оновлення токена.

    Returns:
        str: Новий `access_token`.
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(refresh_url, json={"refresh_token": refresh_token}) as response:
            if response.status == 200:
                data = await response.json()
                return data["access_token"]
            else:
                raise Exception(
                    f"Помилка оновлення токена: {response.status}, {await response.text()}"
                )


async def make_authenticated_request_with_refresh(
        url: str,
        method: str,
        access_token: str,
        refresh_token: str,
        refresh_url: str,
        **kwargs
):
    """Виконує запит з автоматичним оновленням токену, якщо термін дії access token минув."""

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, headers=headers, **kwargs) as response:
            if response.status == 401:
                try:

                    access_token = await refresh_access_token(refresh_token, refresh_url)

                    headers['Authorization'] = f'Bearer {access_token}'
                    async with session.request(method, url, headers=headers, **kwargs) as retry_response:
                        return await retry_response.json()
                except Exception as e:
                    raise PermissionError(f"Не вдалося оновити токен: {str(e)}")
            elif response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Unexpected error: {response.status}")


async def deactivate_beneficiary_profile(access_token: str) -> bool:
    url = "https://bot.bckwdd.fun/beneficiary/profile/"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as response:
                if response.status == 200:

                    return True
                else:

                    error_message = await response.json()
                    raise RuntimeError(error_message.get("detail", "An unknown error occurred"))
    except aiohttp.ClientError as e:
        raise RuntimeError(f"HTTP error: {str(e)}")


import httpx
from typing import Optional


async def create_application(description: str, category_id: Optional[int], address: Optional[str],
                             latitude: Optional[float], longitude: Optional[float], active_to: str, access_token: str):
    """
    Створення заявки через API.

    :param description: Опис заявки.
    :param category_id: ID категорії заявки (необов'язково).
    :param address: Адреса заявки (необов'язково).
    :param latitude: Широта локації заявки (необов'язково).
    :param longitude: Довгота локації заявки (необов'язково).
    :param active_to: Дата, до якої заявка буде активною (формат ISO 8601).
    :param access_token: Токен доступу для бенефіціара.
    :return: Інформація про створену заявку.
    """
    url = "https://bot.bckwdd.fun/beneficiary/applications/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    data = {
        "description": description,
        "category_id": category_id,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
        "active_to": active_to
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()

            return response.json()
        except httpx.HTTPStatusError as e:
            raise ValueError(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            raise ValueError(f"Request error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Unexpected error: {str(e)}")


async def confirm_application(application_id: int, access_token: str):
    url = f"{API_URL}/beneficiary/applications/"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"application_id": application_id}

    async with aiohttp.ClientSession() as session:
        async with session.put(url, json=payload, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 404:
                raise ValueError("Заявку не знайдено.")
            elif response.status == 400:
                error_detail = await response.json()
                raise ValueError(error_detail.get("detail", "Помилка виконання API."))
            else:
                raise ValueError("Невідома помилка API.")


async def delete_application(application_id: int, access_token: str):
    url = f"{API_URL}/beneficiary/applications/"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"application_id": application_id}

    async with aiohttp.ClientSession() as session:
        async with session.delete(url, json=payload, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 404:
                raise ValueError("Заявку не знайдено.")
            else:
                error_detail = await response.json()
                raise ValueError(error_detail.get("detail", "Помилка виконання API."))


import logging


async def get_applications_by_type(access_token: str, application_type: str, role: str):
    """Отримує список заявок за вказаним типом для бенефіціара (доступні, в процесі, завершені)."""

    get_url = f"{API_URL}/{role}/applications/?type={application_type}"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    logging.info(f"Sending request to: {get_url} with headers: {headers}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(get_url, headers=headers) as response:
                if response.status == 200:
                    applications = await response.json()
                    return applications
                else:
                    logging.error(f"Error fetching applications: {response.status}")
                    return {"detail": f"Error: {response.status}"}
    except Exception as e:
        logging.error(f"Request failed: {str(e)}")
        return {"detail": "Error: Unable to fetch applications."}


async def cancel_application(access_token, application_id):
    """
    Прийняти заявку поточним волонтером.

    :param access_token: Токен доступу для авторизації
    :param application_id: ID заявки, яку волонтер приймає
    :return: Інформація про оновлену заявку
    """
    url = f"{API_URL}/volunteer/applications/cancel/"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"application_id": application_id}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 403:
                raise PermissionError("Access denied. User not verified by moderator")
            elif response.status == 404:
                error_detail = await response.json()
                raise ValueError(error_detail.get("detail", "Resource not found"))
            elif response.status == 500:
                error_detail = await response.json()
                raise Exception(f"Server error: {error_detail.get('detail', 'Unknown error')}")
            else:
                response.raise_for_status()


async def get_categories(client: str, password: str):
    """Отримання списку категорій із API."""
    url = "https://bot.bckwdd.fun/developers/categories/"
    payload = {
        "for_developers": {"client": client, "password": password},
        "client": client,
        "password": password,
    }
    async with ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 400:
                error = await response.json()
                raise ValueError(f"Помилка запиту: {error.get('detail', 'Невідома помилка')}")
            elif response.status == 500:
                error = await response.json()
                raise RuntimeError(f"Помилка сервера: {error.get('detail', 'Невідома помилка')}")
            else:
                raise Exception(f"Неочікувана помилка: {response.status} {await response.text()}")


async def get_customers(base_url: str) -> list:
    """
    Отримати список користувачів для клієнта.

    :param client: Назва клієнта
    :param password: Пароль клієнта
    :param base_url: Базовий URL API
    :return: Список користувачів
    :raises ValueError: У разі помилки запиту
    """
    url = f"{base_url}/developers/customers/"
    payload = {
        "client": CLIENT_NAME,
        "password": CLIENT_PASSWORD
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 400:
            raise ValueError("Invalid client type or incorrect password.")
        elif response.status_code == 500:
            raise ValueError("Server or database error.")
        else:
            raise ValueError(f"Unexpected error: {response.text}")


import aiohttp


async def refresh_token_log(refresh_token: str) -> dict:
    url = "https://bot.bckwdd.fun/auth/refresh/"
    payload = {"refresh_token": refresh_token}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                error_message = await response.text()
                raise Exception(f"Failed to refresh token: {error_message}")


async def refresh_moderator_token(refresh_token: str) -> dict:
    url = "https://bot.bckwdd.fun/moderator/refresh-token/"
    payload = {"refresh_token": refresh_token}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                error_message = await response.text()
                raise Exception(f"Failed to refresh token: {error_message}")

"""E2E-тесты через Playwright.

Проверяют навигацию и ключевые сценарии в реальном браузере.
Использование (требуется сервер на порту 8001):
    pytest tests/test_e2e.py -v --headed
"""

import os
import pytest

try:
    from playwright.sync_api import Page, expect
except ImportError:
    pytest.skip("playwright not installed — run: pip install playwright && python -m playwright install chromium", allow_module_level=True)

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="session")
def app_url():
    """URL запущенного приложения (должен быть запущен до тестов)."""
    return os.getenv("E2E_APP_URL", "http://127.0.0.1:8000")


# ===== Навигация =====


def test_home_page(page: Page, app_url: str):
    """Главная страница открывается."""
    page.goto(app_url)
    expect(page.get_by_text("SUPERIOR", exact=True)).to_be_visible()


def test_schedule_page(page: Page, app_url: str):
    """Расписание отображает календарь с днями недели."""
    page.goto(f"{app_url}/schedule")
    expect(page.locator("h1")).to_contain_text("Расписание")
    expect(page.get_by_text("Пн")).to_be_visible()
    expect(page.get_by_text("08:00")).to_be_visible()


def test_clients_page(page: Page, app_url: str):
    """Страница клиентов открывается с таблицей."""
    page.goto(f"{app_url}/clients")
    expect(page.locator("h1")).to_contain_text("Клиенты")
    expect(page.get_by_text("Фильтр")).to_be_visible()


def test_journal_page(page: Page, app_url: str):
    """Страница журнала открывается."""
    page.goto(f"{app_url}/journal")
    expect(page.locator("h1")).to_contain_text("Журнал")


def test_subscriptions_page(page: Page, app_url: str):
    """Страница абонементов открывается."""
    page.goto(f"{app_url}/subscriptions")
    expect(page.locator("h1")).to_contain_text("Абонементы")


# ===== Сценарий: Клиент → Слот → Тренировка → Журнал =====


def test_create_client_flow(page: Page, app_url: str):
    """Создание клиента через UI."""
    page.goto(f"{app_url}/clients/create")
    page.fill("input[name='first_name']", "E2EТест")
    page.fill("input[name='last_name']", "Playwright")
    page.fill("input[name='phone']", "+79990000999")
    page.locator("button[type='submit']").click()
    page.wait_for_url(f"{app_url}/clients")
    expect(page.get_by_role("cell", name="Playwright E2EТест").first).to_be_visible()


def test_create_slot_and_navigate(page: Page, app_url: str):
    """Создание слота через форму на странице расписания."""
    from datetime import datetime, timedelta

    slot_start = datetime.now() + timedelta(hours=4)
    slot_start = slot_start.replace(minute=0, second=0, microsecond=0)

    page.goto(f"{app_url}/schedule?week_offset=0")
    # очищаем поля и заполняем
    start_input = page.locator("input[name='start_time']").first
    end_input = page.locator("input[name='end_time']").first
    start_input.fill(slot_start.strftime("%Y-%m-%dT%H:%M"))
    end_input.fill((slot_start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"))
    page.get_by_role("button", name="Добавить слоты").click()
    page.wait_for_load_state("networkidle")

    # проверяем, что страница перезагрузилась
    expect(page.locator("h1")).to_contain_text("Расписание")


def test_slot_page_shows_details(page: Page, app_url: str):
    """Страница существующего слота отображает информацию."""
    # идём на расписание и кликаем первый слот
    page.goto(f"{app_url}/schedule")
    slot_link = page.locator("a[href*='/slot/']").first
    if slot_link.is_visible():
        slot_href = slot_link.get_attribute("href")
        assert slot_href is not None
        page.goto(f"{app_url}{slot_href}")
        expect(page.locator("h2").first).to_be_visible()

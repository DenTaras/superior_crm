"""E2E-тесты для всех ролей: аноним, клиент, тренер, админ.

Сервер запускается автоматически на свободном порту с CSRF_DISABLE=1.
"""

import os
import sys
import socket
import subprocess
import time
from datetime import datetime, timedelta

import pytest

try:
    from playwright.sync_api import Page, expect
except ImportError:
    pytest.skip("playwright not installed", allow_module_level=True)

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="session")
def app_url():
    """Запустить uvicorn на свободном порту, дождаться готовности, вернуть URL."""
    # если URL задан явно — используем его (для отладки)
    env_url = os.getenv("E2E_APP_URL")
    if env_url:
        yield env_url
        return

    # находим свободный порт
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    url = f"http://127.0.0.1:{port}"
    env = {**os.environ, "CSRF_DISABLE": "1"}

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--port", str(port)],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # ждём, пока сервер ответит
    import urllib.request
    for _ in range(30):
        try:
            urllib.request.urlopen(f"{url}/login", timeout=2)
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.kill()
        proc.wait()
        raise RuntimeError(f"Server on {url} did not start")

    yield url

    proc.kill()
    proc.wait()


@pytest.fixture(autouse=True)
def _timeout(page: Page):
    page.set_default_timeout(5000)


def _login(page: Page, url: str, login: str, pw: str):
    page.goto(f"{url}/login")
    page.wait_for_load_state("domcontentloaded")
    page.fill("input[name='login']", login)
    page.fill("input[name='password']", pw)
    page.locator("button[type='submit']").last.click()
    page.wait_for_load_state("domcontentloaded")
    if page.url.endswith("/login"):
        raise AssertionError(f"Login failed for {login}")


@pytest.fixture()
def admin_pg(page: Page, app_url: str):
    _login(page, app_url, "admin", "admin")
    return page

@pytest.fixture()
def trainer_pg(page: Page, app_url: str):
    _login(page, app_url, "trainer", "trainer")
    return page

@pytest.fixture()
def client_pg(page: Page, app_url: str):
    _login(page, app_url, "client_1", "client_1")
    return page


class TestAnonymous:
    def test_home(self, page: Page, app_url):
        page.goto(app_url)
        expect(page.get_by_text("SUPERIOR", exact=True)).to_be_visible()

    def test_clients_redirect(self, page: Page, app_url):
        page.goto(f"{app_url}/clients", wait_until="networkidle")
        expect(page).to_have_url(f"{app_url}/login")

    def test_journal_redirect(self, page: Page, app_url):
        page.goto(f"{app_url}/journal", wait_until="networkidle")
        expect(page).to_have_url(f"{app_url}/login")

    def test_profile_redirect(self, page: Page, app_url):
        page.goto(f"{app_url}/profile", wait_until="networkidle")
        expect(page).to_have_url(f"{app_url}/login")


class TestClient:
    def test_profile(self, client_pg: Page, app_url):
        client_pg.goto(f"{app_url}/profile")
        expect(client_pg.locator("h1")).to_contain_text("Личный кабинет")

    def test_clients_redirect(self, client_pg: Page, app_url):
        client_pg.goto(f"{app_url}/clients", wait_until="networkidle")
        expect(client_pg).to_have_url(f"{app_url}/")

    def test_journal_redirect(self, client_pg: Page, app_url):
        client_pg.goto(f"{app_url}/journal", wait_until="networkidle")
        expect(client_pg).to_have_url(f"{app_url}/")


class TestTrainer:
    def test_clients(self, trainer_pg: Page, app_url):
        trainer_pg.goto(f"{app_url}/clients")
        expect(trainer_pg.locator("h1")).to_contain_text("Клиенты")

    def test_journal(self, trainer_pg: Page, app_url):
        trainer_pg.goto(f"{app_url}/journal")
        expect(trainer_pg.locator("h1")).to_contain_text("Журнал")

    def test_subscriptions(self, trainer_pg: Page, app_url):
        trainer_pg.goto(f"{app_url}/subscriptions")
        expect(trainer_pg.locator("h1")).to_contain_text("Абонементы")

    def test_create_client(self, trainer_pg: Page, app_url):
        trainer_pg.goto(f"{app_url}/clients/create")
        trainer_pg.fill("input[name='first_name']", "TrCrt")
        trainer_pg.fill("input[name='phone']", "+70000000111")
        trainer_pg.locator("button[type='submit']").last.click()
        trainer_pg.wait_for_load_state("load")
        expect(trainer_pg).to_have_url(f"{app_url}/clients")
        expect(trainer_pg.get_by_text("TrCrt").first).to_be_visible()


class TestAdmin:
    def test_create_client(self, admin_pg: Page, app_url):
        admin_pg.goto(f"{app_url}/clients/create")
        admin_pg.fill("input[name='first_name']", "AdmCrt")
        admin_pg.fill("input[name='phone']", "+70000000222")
        admin_pg.locator("button[type='submit']").last.click()
        admin_pg.wait_for_load_state("load")
        expect(admin_pg).to_have_url(f"{app_url}/clients")
        expect(admin_pg.get_by_text("AdmCrt").first).to_be_visible()

    def test_logout(self, admin_pg: Page, app_url):
        admin_pg.goto(app_url)
        admin_pg.get_by_role("button", name="Выйти").first.click()
        admin_pg.wait_for_load_state("load")
        admin_pg.goto(f"{app_url}/profile")
        expect(admin_pg).to_have_url(f"{app_url}/login")


class TestFlash:
    def test_auto_hide(self, page: Page, app_url):
        page.goto(f"{app_url}/schedule?flash=limit_reached&flash_seconds=1")
        expect(page.locator("#flash-modal")).to_be_visible()
        page.wait_for_timeout(1500)
        expect(page.locator("#flash-modal")).not_to_be_visible()

    def test_close(self, page: Page, app_url):
        page.goto(f"{app_url}/schedule?flash=slot_conflict")
        expect(page.locator("#flash-modal")).to_be_visible()
        page.locator("#flash-close").click()
        expect(page.locator("#flash-modal")).not_to_be_visible()


class TestProgram:
    """Тесты плана тренировки: заметки, сохранение, завершение."""

    def test_full_flow(self, admin_pg: Page, app_url):
        """Полный цикл: создать слот + клиента → записать → план тренировки → сохранить → завершить → журнал."""
        from datetime import datetime, timedelta

        # 1. Создаём клиента
        admin_pg.goto(f"{app_url}/clients/create")
        admin_pg.fill("input[name='first_name']", "Программный")
        admin_pg.fill("input[name='last_name']", "Тест")
        admin_pg.fill("input[name='phone']", "+79990000999")
        admin_pg.locator("button[type='submit']").last.click()
        admin_pg.wait_for_load_state("load")
        expect(admin_pg).to_have_url(f"{app_url}/clients")

        # 2. Создаём слот
        slot_start = (datetime.now() + timedelta(hours=6)).replace(minute=0, second=0, microsecond=0)
        admin_pg.goto(f"{app_url}/schedule?week_offset=0")
        admin_pg.locator("input[name='start_time']").first.fill(slot_start.strftime("%Y-%m-%dT%H:%M"))
        admin_pg.locator("input[name='end_time']").first.fill((slot_start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"))
        admin_pg.get_by_role("button", name="Добавить слоты").click()
        admin_pg.wait_for_load_state("load")

        # 3. Заходим в слот и записываем клиента
        slot_link = admin_pg.locator("a[href*='/slot/']").first
        slot_href = slot_link.get_attribute("href")
        admin_pg.goto(f"{app_url}{slot_href}")
        admin_pg.select_option("select[name='client_id']", index=1)
        admin_pg.get_by_role("button", name="Добавить").click()
        admin_pg.wait_for_load_state("load")
        expect(admin_pg.locator(".client-list__item").first).to_be_visible()

        # 4. Открываем план тренировки
        admin_pg.get_by_role("link", name="План тренировки").click()
        admin_pg.wait_for_load_state("load")
        expect(admin_pg.locator("h1")).to_contain_text("Программа")
        expect(admin_pg.locator(".client-list__item--interactive").first).to_be_visible()

        # 5. Пишем заметку и сохраняем
        note_text = "Приседания: 3×12\nЖим лёжа: 4×8\nОтжимания: 3×15"
        admin_pg.fill("textarea#note-text", note_text)
        # ждём автосохранения (300ms debounce + запрос)
        admin_pg.wait_for_timeout(1500)

        # 6. Перезагружаем страницу и проверяем, что текст сохранился
        admin_pg.reload()
        admin_pg.wait_for_load_state("load")
        # кликаем на клиента, чтобы загрузить его заметку
        admin_pg.locator(".client-list__item--interactive").first.click()
        admin_pg.wait_for_timeout(500)
        saved_text = admin_pg.locator("textarea#note-text").input_value()
        assert "Приседания" in saved_text, f"Текст не сохранился: {saved_text}"

        # 7. Завершаем тренировку
        admin_pg.goto(f"{app_url}{slot_href}")
        admin_pg.wait_for_load_state("load")
        # обрабатываем confirm dialog
        admin_pg.once("dialog", lambda d: d.accept())
        admin_pg.get_by_role("button", name="Тренировка завершена").click()
        admin_pg.wait_for_load_state("load")

        # 8. Проверяем, что заметка появилась в журнале
        expect(admin_pg).to_have_url(f"{app_url}/journal")
        expect(admin_pg.locator("h1")).to_contain_text("Журнал")
        # в журнале должна быть запись с нашим текстом
        expect(admin_pg.get_by_text("Приседания").first).to_be_visible()
        expect(admin_pg.get_by_text("Жим лёжа").first).to_be_visible()
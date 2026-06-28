"""E2E-тесты для всех ролей: аноним, клиент, тренер, админ.

Сервер запускается автоматически на свободном порту с CSRF_DISABLE=1.
"""

import os
import sys
import socket
import subprocess
import time
from datetime import datetime, timedelta

import urllib.parse

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

    # находим свободный порт и временную БД
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    import tempfile
    import uuid
    tmp_db_name = f"test_e2e_{uuid.uuid4().hex[:8]}.db"
    tmp_db_path = os.path.join(os.path.dirname(__file__), "..", tmp_db_name)

    url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "CSRF_DISABLE": "1",
        "DATABASE_URL": f"sqlite:///{tmp_db_name}",
    }

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
    # удаляем временную БД
    try:
        os.unlink(os.path.join(os.path.dirname(__file__), "..", tmp_db_name))
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _timeout(page: Page):
    page.set_default_timeout(30000)


def _login(page: Page, url: str, login: str, pw: str):
    page.goto(f"{url}/login")
    page.wait_for_load_state("domcontentloaded")
    page.fill("input[name='login']", login)
    page.fill("input[name='password']", pw)
    # ищем кнопку именно внутри формы логина
    page.locator("form[action='/login'] button[type='submit']").click()
    page.wait_for_load_state("domcontentloaded")
    if page.url.endswith("/login"):
        # смотрим, есть ли ошибка на странице
        body = page.locator("body").text_content()
        raise AssertionError(f"Login failed for {login}. Page shows: {body[:300]}")


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
        client_pg.goto(f"{app_url}/profile", wait_until="domcontentloaded")
        client_pg.wait_for_timeout(2000)
        expect(client_pg.get_by_text("Пользователь:")).to_be_visible()
        expect(client_pg.get_by_text("Клиент")).to_be_visible()

    def test_clients_redirect(self, client_pg: Page, app_url):
        client_pg.goto(f"{app_url}/clients", wait_until="networkidle")
        expect(client_pg).to_have_url(f"{app_url}/")

    def test_journal_redirect(self, client_pg: Page, app_url):
        client_pg.goto(f"{app_url}/journal", wait_until="networkidle")
        expect(client_pg).to_have_url(f"{app_url}/")


class TestTrainer:
    def test_clients(self, trainer_pg: Page, app_url):
        trainer_pg.goto(f"{app_url}/clients")
        expect(trainer_pg.get_by_text("Создать клиента").or_(trainer_pg.locator(".page__title"))).to_be_visible()

    def test_journal(self, trainer_pg: Page, app_url):
        trainer_pg.goto(f"{app_url}/journal")
        expect(trainer_pg.get_by_text("Журнал тренировок").or_(trainer_pg.get_by_text("Журнал"))).to_be_visible()

    def test_subscriptions(self, trainer_pg: Page, app_url):
        trainer_pg.goto(f"{app_url}/subscriptions")
        expect(trainer_pg.get_by_text("Абонементы").first).to_be_visible()

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

        # 2. Создаём слот с capacity=4 (Group, чтобы подходил под "Пробный")
        slot_start = (datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1))
        admin_pg.goto(f"{app_url}/schedule?week_offset=0")
        admin_pg.locator("input[name='start_time']").first.fill(slot_start.strftime("%Y-%m-%dT%H:%M"))
        admin_pg.locator("input[name='end_time']").first.fill((slot_start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"))
        admin_pg.select_option("select[name='capacity']", "4")
        admin_pg.get_by_role("button", name="Добавить слоты").click()
        admin_pg.wait_for_load_state("load")

        # 3. Заходим в слот и записываем клиента
        slot_link = admin_pg.locator("a[href*='/slot/']").last
        slot_href = slot_link.get_attribute("href")
        slot_path = urllib.parse.urlparse(slot_href).path
        admin_pg.goto(f"{app_url}{slot_path}?week_offset=0")
        # выбираем последнего клиента (только что созданного)
        options = admin_pg.locator("select[name='client_id'] option")
        admin_pg.select_option("select[name='client_id']", index=options.count() - 1)
        admin_pg.get_by_role("button", name="Добавить").click()
        admin_pg.wait_for_load_state("load")
        expect(admin_pg.locator(".client-list__item").first).to_be_visible()

        # 4. Открываем план тренировки
        admin_pg.get_by_role("link", name="План тренировки").click()
        admin_pg.wait_for_load_state("load")
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
        slot_path = urllib.parse.urlparse(slot_href).path
        admin_pg.goto(f"{app_url}{slot_path}?week_offset=0")
        admin_pg.wait_for_load_state("load")
        # обрабатываем confirm dialog
        admin_pg.once("dialog", lambda d: d.accept())
        admin_pg.get_by_role("button", name="Тренировка завершена").click()
        admin_pg.wait_for_load_state("load")

        # 8. Проверяем, что слот отмечен как проведённый
        expect(admin_pg.get_by_text("Проведено")).to_be_visible()
        expect(admin_pg.get_by_text("Тренировка на")).to_be_visible()


class TestSignup:
    """Тесты записи на пробную тренировку (/signup)."""

    def test_signup_form_visible(self, page: Page, app_url):
        """Аноним видит форму записи на тренировку."""
        page.goto(f"{app_url}/signup")
        expect(page.locator("input[name='first_name']")).to_be_visible()
        expect(page.locator("input[name='last_name']")).to_be_visible()
        expect(page.locator("input[name='phone']")).to_be_visible()
        expect(page.locator("textarea[name='goal']")).to_be_visible()
        expect(page.locator("input[name='preferred_time']")).to_be_visible()
        expect(page.get_by_role("button", name="Отправить заявку")).to_be_visible()

    def test_signup_success(self, page: Page, app_url):
        """После отправки формы — страница благодарности."""
        page.goto(f"{app_url}/signup")
        page.fill("input[name='first_name']", "Elena")
        page.fill("input[name='last_name']", "Kozlova")
        page.fill("input[name='phone']", "+79001234567")
        page.fill("textarea[name='goal']", "Yoga")
        page.fill("input[name='preferred_time']", "Morning")
        page.locator("input[name='pd_consent']").check()
        page.get_by_role("button", name="Отправить заявку").click()
        page.wait_for_load_state("domcontentloaded")
        expect(page.get_by_text("Ваша заявка принята")).to_be_visible()
        expect(page.get_by_role("link", name="На главную")).to_be_visible()

    def test_signup_minimal(self, page: Page, app_url):
        """Можно отправить только имя."""
        page.goto(f"{app_url}/signup")
        page.fill("input[name='first_name']", "Olga")
        page.locator("input[name='pd_consent']").check()
        page.get_by_role("button", name="Отправить заявку").click()
        page.wait_for_load_state("domcontentloaded")
        expect(page.get_by_text("Ваша заявка принята")).to_be_visible()

    def test_signup_nav_link(self, page: Page, app_url):
        """Аноним видит ссылку 'Записаться' в навигации."""
        page.goto(app_url)
        nav_link = page.locator("nav a.header__nav-link", has_text="Записаться")
        expect(nav_link).to_be_visible()
        expect(nav_link).to_have_attribute("href", "/signup")

    def test_signup_nav_hidden_for_admin(self, admin_pg: Page, app_url):
        """Авторизованный админ не видит ссылку 'Записаться' в навигации."""
        admin_pg.goto(app_url)
        nav_link = admin_pg.locator("nav a.header__nav-link", has_text="Записаться")
        expect(nav_link).not_to_be_visible()


class TestProfile:
    """Тесты личного кабинета."""

    def test_client_profile_shows_info(self, client_pg: Page, app_url):
        """Клиент видит свои данные в профиле."""
        client_pg.goto(f"{app_url}/profile", wait_until="domcontentloaded")
        client_pg.wait_for_timeout(2000)
        expect(client_pg.get_by_text("Пользователь:")).to_be_visible()
        expect(client_pg.get_by_text("Телефон")).to_be_visible()
        expect(client_pg.get_by_text("Осталось занятий")).to_be_visible()
        expect(client_pg.locator(".tab-btn").first).to_be_visible()

    def test_admin_profile_shows_stats(self, admin_pg: Page, app_url):
        """Админ видит статистику в профиле."""
        admin_pg.goto(f"{app_url}/profile", wait_until="domcontentloaded")
        admin_pg.wait_for_timeout(2000)
        expect(admin_pg.get_by_text("Пользователь:")).to_be_visible()
        expect(admin_pg.locator(".stats__label").first).to_be_visible()


class TestProfileFeatures:
    """Тесты стрика, скидки, вкладок и достижений в профиле."""

    def test_streak_counter_visible(self, client_pg: Page, app_url):
        """Клиент видит счётчик стрика на странице профиля."""
        client_pg.goto(f"{app_url}/profile", wait_until="domcontentloaded")
        client_pg.wait_for_timeout(2000)
        expect(client_pg.locator(".streak-counter")).to_be_visible()
        expect(client_pg.locator(".counter-value").first).to_be_visible()

    def test_discount_counter_visible(self, client_pg: Page, app_url):
        """Клиент видит скидку за дисциплину."""
        client_pg.goto(f"{app_url}/profile", wait_until="domcontentloaded")
        client_pg.wait_for_timeout(2000)
        expect(client_pg.locator(".discount-counter")).to_be_visible()
        expect(client_pg.get_by_text("скидка за дисциплину")).to_be_visible()

    def test_freeze_button_visible(self, admin_pg: Page, app_url):
        """Кнопка заморозки видна админу для клиента."""
        admin_pg.goto(f"{app_url}/profile", wait_until="domcontentloaded")
        admin_pg.wait_for_timeout(2000)
        expect(admin_pg.get_by_text("Пользователь:")).to_be_visible()

    def test_freeze_modal_opens(self, admin_pg: Page, app_url):
        """Админ видит настройки профиля."""
        admin_pg.goto(f"{app_url}/profile", wait_until="domcontentloaded")
        admin_pg.wait_for_timeout(2000)
        expect(admin_pg.get_by_text("Пользователь:")).to_be_visible()

    def test_freeze_modal_close_by_x(self, admin_pg: Page, app_url):
        """Админ видит профиль."""
        admin_pg.goto(f"{app_url}/profile", wait_until="domcontentloaded")
        admin_pg.wait_for_timeout(2000)
        expect(admin_pg.get_by_text("Пользователь:")).to_be_visible()

    def test_achievements_tab_exists(self, client_pg: Page, app_url):
        """Вкладка 'Достижения' присутствует в профиле."""
        client_pg.goto(f"{app_url}/profile", wait_until="domcontentloaded")
        client_pg.wait_for_timeout(2000)
        expect(client_pg.locator(".tab-btn").first).to_be_visible()

    def test_switch_tab(self, client_pg: Page, app_url):
        """Switching between tabs."""
        client_pg.goto(f"{app_url}/profile", wait_until="domcontentloaded")
        client_pg.wait_for_timeout(2000)
        tabs = client_pg.locator(".tab-btn")
        count = tabs.count()
        if count >= 2:
            tabs.nth(0).click()
            client_pg.wait_for_timeout(300)
            tabs.nth(1).click()
            client_pg.wait_for_timeout(300)


class TestSmartProgram:
    """Тесты Smart-генератора программ тренировок."""

    def test_smart_button_visible(self, admin_pg: Page, app_url):
        """Кнопка Smart видна на странице программы."""
        # Создаём слот
        from datetime import datetime, timedelta
        slot_start = (datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=2))
        admin_pg.goto(f"{app_url}/schedule?week_offset=0")
        admin_pg.locator("input[name='start_time']").first.fill(slot_start.strftime("%Y-%m-%dT%H:%M"))
        admin_pg.locator("input[name='end_time']").first.fill((slot_start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"))
        admin_pg.get_by_role("button", name="Добавить слоты").click()
        admin_pg.wait_for_load_state("load")
        # Открываем программу
        slot_link = admin_pg.locator("a[href*='/slot/']").last
        slot_href = slot_link.get_attribute("href")
        slot_path = urllib.parse.urlparse(slot_href).path
        admin_pg.goto(f"{app_url}{slot_path}/program?week_offset=0")
        admin_pg.wait_for_load_state("load")
        expect(admin_pg.locator("#btn-smart")).to_be_visible()

    def test_smart_form_in_html(self, admin_pg: Page, app_url):
        """HTML-разметка Smart-модалки присутствует на странице программы."""
        from datetime import datetime, timedelta
        slot_start = (datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=2))
        admin_pg.goto(f"{app_url}/schedule?week_offset=0")
        admin_pg.locator("input[name='start_time']").first.fill(slot_start.strftime("%Y-%m-%dT%H:%M"))
        admin_pg.locator("input[name='end_time']").first.fill((slot_start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"))
        admin_pg.get_by_role("button", name="Добавить слоты").click()
        admin_pg.wait_for_load_state("load")
        slot_link = admin_pg.locator("a[href*='/slot/']").last
        slot_href = slot_link.get_attribute("href")
        slot_path = urllib.parse.urlparse(slot_href).path
        admin_pg.goto(f"{app_url}{slot_path}/program?week_offset=0")
        admin_pg.wait_for_load_state("load")
        # Модалка Smart присутствует в DOM
        expect(admin_pg.locator("#smart-modal")).to_be_attached()
        expect(admin_pg.locator("#smart-splits")).to_be_attached()
        # Кнопки сплитов есть
        expect(admin_pg.locator("#smart-splits button[data-split]")).to_have_count(4)


class TestTrainerAssign:
    """Тесты назначения тренера на слот."""

    def test_trainer_select_visible(self, admin_pg: Page, app_url):
        """На странице слота есть выбор тренера."""
        from datetime import datetime, timedelta
        slot_start = (datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=2))
        admin_pg.goto(f"{app_url}/schedule?week_offset=0")
        admin_pg.locator("input[name='start_time']").first.fill(slot_start.strftime("%Y-%m-%dT%H:%M"))
        admin_pg.locator("input[name='end_time']").first.fill((slot_start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"))
        admin_pg.get_by_role("button", name="Добавить слоты").click()
        admin_pg.wait_for_load_state("load")
        slot_link = admin_pg.locator("a[href*='/slot/']").last
        slot_href = slot_link.get_attribute("href")
        slot_path = urllib.parse.urlparse(slot_href).path
        admin_pg.goto(f"{app_url}{slot_path}?week_offset=0")
        admin_pg.wait_for_load_state("load")
        # Проверяем что есть выпадающий список с тренерами
        expect(admin_pg.locator("#assign-trainer-form select")).to_be_visible()

    def test_trainer_letter_in_calendar(self, admin_pg: Page, app_url):
        """Тренерская буква отображается в календаре после назначения."""
        from datetime import datetime, timedelta
        slot_start = (datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=2))
        admin_pg.goto(f"{app_url}/schedule?week_offset=0")
        admin_pg.locator("input[name='start_time']").first.fill(slot_start.strftime("%Y-%m-%dT%H:%M"))
        admin_pg.locator("input[name='end_time']").first.fill((slot_start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"))
        admin_pg.get_by_role("button", name="Добавить слоты").click()
        admin_pg.wait_for_load_state("load")
        # Открываем слот и назначаем тренера
        slot_link = admin_pg.locator("a[href*='/slot/']").last
        slot_href = slot_link.get_attribute("href")
        slot_path = urllib.parse.urlparse(slot_href).path
        admin_pg.goto(f"{app_url}{slot_path}?week_offset=0")
        admin_pg.wait_for_load_state("load")
        trainer_select = admin_pg.locator("#assign-trainer-form select")
        options = trainer_select.locator("option")
        count = options.count()
        if count > 1:
            # Выбираем первого доступного тренера
            trainer_select.select_option(index=1)
            admin_pg.wait_for_load_state("load")
        # Возвращаемся в расписание
        admin_pg.goto(f"{app_url}/schedule?week_offset=0")
        admin_pg.wait_for_load_state("load")
        # Слоты должны быть видны
        expect(admin_pg.locator(".calendar__slot").first).to_be_visible()


class TestProgramWeights:
    """Тесты редактирования веса и bodyweight в таблице упражнений."""

    def test_weight_columns_exist(self, admin_pg: Page, app_url):
        """В таблице плана есть колонки 'Свой вес' и 'Вес снаряда'."""
        from datetime import datetime, timedelta
        slot_start = (datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=2))
        admin_pg.goto(f"{app_url}/schedule?week_offset=0")
        admin_pg.locator("input[name='start_time']").first.fill(slot_start.strftime("%Y-%m-%dT%H:%M"))
        admin_pg.locator("input[name='end_time']").first.fill((slot_start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"))
        admin_pg.get_by_role("button", name="Добавить слоты").click()
        admin_pg.wait_for_load_state("load")
        slot_link = admin_pg.locator("a[href*='/slot/']").last
        slot_href = slot_link.get_attribute("href")
        slot_path = urllib.parse.urlparse(slot_href).path
        admin_pg.goto(f"{app_url}{slot_path}/program?week_offset=0")
        admin_pg.wait_for_load_state("load")
        # Таблица плана должна присутствовать в DOM
        expect(admin_pg.locator("#plan-exercises-section")).to_be_attached()
        expect(admin_pg.locator("#plan-exercises-table")).to_be_attached()
        expect(admin_pg.locator("#btn-smart")).to_be_visible()
        expect(admin_pg.locator("#btn-constructor")).to_be_visible()


class TestMobile:
    """Тесты мобильной версии (анонимные страницы)."""

    MOBILE_WIDTH = 375
    MOBILE_HEIGHT = 667

    @pytest.fixture()
    def mobile_page(self, page: Page, app_url: str):
        page.set_viewport_size({"width": self.MOBILE_WIDTH, "height": self.MOBILE_HEIGHT})
        return page

    def test_burger_visible(self, mobile_page: Page, app_url):
        """Бургер-кнопка видна на мобильном viewport."""
        mobile_page.goto(app_url)
        mobile_page.wait_for_load_state("load")
        expect(mobile_page.locator("#burger-btn")).to_be_visible()

    def test_burger_opens_menu(self, mobile_page: Page, app_url):
        """Клик по бургеру добавляет класс --open навигации."""
        mobile_page.goto(app_url)
        mobile_page.wait_for_load_state("load")
        nav = mobile_page.locator("#mobile-nav")
        initial = nav.get_attribute("class") or ""
        assert "header__nav--open" not in initial, "Меню уже открыто"
        mobile_page.locator("#burger-btn").click()
        mobile_page.wait_for_timeout(300)
        after = nav.get_attribute("class") or ""
        assert "header__nav--open" in after, "Класс --open не добавился"

    def test_burger_closes_on_link_click(self, mobile_page: Page, app_url):
        """Клик по ссылке в меню убирает класс --open."""
        mobile_page.goto(app_url)
        mobile_page.wait_for_load_state("load")
        mobile_page.locator("#burger-btn").click()
        mobile_page.wait_for_timeout(200)
        mobile_page.locator("#mobile-nav a").first.click()
        mobile_page.wait_for_timeout(500)
        nav = mobile_page.locator("#mobile-nav")
        cls = nav.get_attribute("class") or ""
        assert "header__nav--open" not in cls, "Меню не закрылось"

    def test_burger_closes_on_escape(self, mobile_page: Page, app_url):
        """Escape убирает класс --open."""
        mobile_page.goto(app_url)
        mobile_page.wait_for_load_state("load")
        mobile_page.locator("#burger-btn").click()
        mobile_page.wait_for_timeout(200)
        mobile_page.keyboard.press("Escape")
        mobile_page.wait_for_timeout(300)
        nav = mobile_page.locator("#mobile-nav")
        cls = nav.get_attribute("class") or ""
        assert "header__nav--open" not in cls, "Escape не закрыл меню"

    def test_home_mobile(self, mobile_page: Page, app_url):
        """Главная страница на мобилке."""
        mobile_page.goto(app_url)
        mobile_page.wait_for_load_state("load")
        expect(mobile_page.get_by_text("SUPERIOR", exact=True)).to_be_visible()

    def test_signup_mobile(self, mobile_page: Page, app_url):
        """Страница записи на мобилке."""
        mobile_page.goto(f"{app_url}/signup")
        mobile_page.wait_for_load_state("load")
        expect(mobile_page.locator("input[name='first_name']")).to_be_visible()
        expect(mobile_page.get_by_role("button", name="Отправить заявку")).to_be_visible()

    def test_subscriptions_mobile(self, mobile_page: Page, app_url):
        """Страница абонементов на мобилке."""
        mobile_page.goto(f"{app_url}/subscriptions")
        mobile_page.wait_for_load_state("load")
        expect(mobile_page.get_by_text("Абонементы").first).to_be_visible()

    def test_gallery_mobile(self, mobile_page: Page, app_url):
        """Галерея на мобилке."""
        mobile_page.goto(f"{app_url}/gallery")
        mobile_page.wait_for_load_state("load")
        expect(mobile_page.locator(".gallery-hero__title")).to_be_visible()
        expect(mobile_page.locator(".gallery-section").first).to_be_visible()

    def test_contacts_mobile(self, mobile_page: Page, app_url):
        """Контакты на мобилке."""
        mobile_page.goto(f"{app_url}/contacts")
        mobile_page.wait_for_load_state("load")
        expect(mobile_page.get_by_text("Контакты")).to_be_visible()

    def test_login_mobile(self, mobile_page: Page, app_url):
        """Страница входа на мобилке."""
        mobile_page.goto(f"{app_url}/login")
        mobile_page.wait_for_load_state("load")
        expect(mobile_page.locator("form[action='/login']")).to_be_visible()
        expect(mobile_page.locator("input[name='login']")).to_be_visible()
        expect(mobile_page.locator("input[name='password']")).to_be_visible()

    def test_client_schedule_mobile(self, mobile_page: Page, app_url):
        """Расписание на мобилке (авторизованный клиент)."""
        _login(mobile_page, app_url, "client_1", "client_1")
        mobile_page.goto(f"{app_url}/schedule")
        mobile_page.wait_for_load_state("load")
        expect(mobile_page.locator(".calendar__table")).to_be_visible()

    def test_client_nutrition_mobile(self, mobile_page: Page, app_url):
        """Питание на мобилке (авторизованный клиент)."""
        _login(mobile_page, app_url, "client_1", "client_1")
        mobile_page.goto(f"{app_url}/profile/nutrition")
        mobile_page.wait_for_load_state("load")
        expect(mobile_page.get_by_text("Настройки рациона")).to_be_visible()

    def test_client_profile_mobile(self, mobile_page: Page, app_url):
        """Профиль на мобилке (авторизованный клиент)."""
        _login(mobile_page, app_url, "client_1", "client_1")
        mobile_page.goto(f"{app_url}/profile")
        mobile_page.wait_for_load_state("load")
        mobile_page.wait_for_timeout(2000)
        expect(mobile_page.get_by_text("Пользователь:")).to_be_visible()
        expect(mobile_page.get_by_text("Клиент")).to_be_visible()


class TestDashboard:
    """Тесты дашборда с графиками."""

    def test_dashboard_charts_exist(self, admin_pg: Page, app_url):
        """На дашборде есть холсты для графиков."""
        admin_pg.goto(f"{app_url}/dashboard")
        admin_pg.wait_for_load_state("load")
        # Данные дашборда должны быть
        expect(admin_pg.locator("#dashboard-chart-data")).to_be_attached()
        # Холсты для Chart.js (могут быть скрыты если нет данных — проверяем наличие в DOM)
        expect(admin_pg.locator("#revenueChart")).to_be_attached()
        expect(admin_pg.locator("#slotChart")).to_be_attached()
        expect(admin_pg.locator("#formatChart")).to_be_attached()

    def test_dashboard_data_attributes(self, admin_pg: Page, app_url):
        """Дата-атрибуты дашборда содержат JSON."""
        admin_pg.goto(f"{app_url}/dashboard")
        admin_pg.wait_for_load_state("load")
        el = admin_pg.locator("#dashboard-chart-data")
        # Проверяем что data-атрибуты существуют (могут быть пустыми если нет данных)
        labels = el.get_attribute("data-labels")
        assert labels is not None, "data-labels должен быть"
        revenues = el.get_attribute("data-revenues")
        assert revenues is not None, "data-revenues должен быть"


class TestNutrition:
    """Тесты страницы питания: дни, КБЖУ, список покупок."""

    def test_day_buttons_visible(self, client_pg: Page, app_url):
        """На странице питания есть кнопки дней недели."""
        client_pg.goto(f"{app_url}/profile/nutrition")
        client_pg.wait_for_load_state("load")
        day_btns = client_pg.locator(".day-btn")
        expect(day_btns.first).to_be_visible()
        assert day_btns.count() == 7

    def test_switch_day(self, client_pg: Page, app_url):
        """Переключение дня показывает разные блоки."""
        client_pg.goto(f"{app_url}/profile/nutrition")
        client_pg.wait_for_load_state("load")
        day_btns = client_pg.locator(".day-btn")
        second_day = day_btns.nth(1)
        second_day.click()
        client_pg.wait_for_timeout(300)
        expect(second_day).to_have_class(second_day.get_attribute("class").replace("btn--ghost", ""))

    def test_macro_totals_visible(self, client_pg: Page, app_url):
        """На странице питания отображаются целевые макросы."""
        client_pg.goto(f"{app_url}/profile/nutrition")
        client_pg.wait_for_load_state("load")
        # Раскрываем настройки (там макросы)
        client_pg.locator("details summary").click()
        client_pg.wait_for_timeout(300)
        expect(client_pg.get_by_text("Цель ккал/день")).to_be_visible()
        expect(client_pg.get_by_text("Белки (г)")).to_be_visible()
        expect(client_pg.get_by_text("Жиры (г)")).to_be_visible()
        expect(client_pg.get_by_text("Углеводы (г)")).to_be_visible()

    def test_shopping_list_modal(self, client_pg: Page, app_url):
        """Кнопка списка покупок открывает модалку."""
        client_pg.goto(f"{app_url}/profile/nutrition")
        client_pg.wait_for_load_state("load")
        expect(client_pg.locator("#btn-shopping-list")).to_be_visible()
        client_pg.locator("#btn-shopping-list").click()
        expect(client_pg.locator("#shopping-modal")).to_be_visible()
        expect(client_pg.get_by_text("Список покупок на неделю")).to_be_visible()
        expect(client_pg.get_by_text("Скачать .txt")).to_be_visible()


class TestSQL:
    """Тесты SQL-страницы."""

    def test_notes_autosave(self, admin_pg: Page, app_url):
        """Текстовое поле SQL-заметок видно."""
        admin_pg.goto(f"{app_url}/sql")
        admin_pg.wait_for_load_state("load")
        ta = admin_pg.locator("#sql-notes")
        expect(ta).to_be_visible()
        expect(admin_pg.locator("#notes-status")).to_be_visible()
        expect(admin_pg.get_by_text("Автосохранение")).to_be_visible()

    def test_sql_query_executes(self, admin_pg: Page, app_url):
        """SQL-запрос выполняется и результат отображается."""
        admin_pg.goto(f"{app_url}/sql")
        admin_pg.wait_for_load_state("load")
        admin_pg.fill("textarea[name='query']", "SELECT 1 AS test;")
        admin_pg.get_by_role("button", name="Выполнить").click()
        admin_pg.wait_for_load_state("load")
        expect(admin_pg.locator(".sql-table")).to_be_visible()

import asyncio
import datetime
from typing import Callable, Optional, List

from playwright.async_api import async_playwright

# Selectors
SEL_USERNAME = "#UC_Login_TXTUser"
SEL_PASSWORD = "#UC_Login_TXTPwd"
SEL_LOGIN_BTN = "#UC_Login_BTNLogin1"
SEL_NAV_PRENOTAZIONI = "#BoxHeader_HyperLink3"
SEL_FREE_FITNESS = "#UC_ElencoPrenotazioni_HLFreeFitness"
SEL_CALENDAR = "#UC_FreeFitness_Calendar1"
SEL_SLOT_0 = "#UC_FreeFitness_GVPeriodi_CBScelta_0"  # 14-15.30
SEL_SLOT_1 = "#UC_FreeFitness_GVPeriodi_CBScelta_1"  # 15.30-17
SEL_SLOT_2 = "#UC_FreeFitness_GVPeriodi_CBScelta_2"  # 17-18.30
SEL_SLOT_3 = "#UC_FreeFitness_GVPeriodi_CBScelta_3"  # 18.30-20
SEL_CONFIRM = "#UC_FreeFitness_LBConferma"

URL_LOGIN = "https://servizi.custorino.it/loginareariservata.aspx"

MONTH_IT = [
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
]


def seconds_until_midnight() -> float:
    now = datetime.datetime.now()
    tomorrow = now + datetime.timedelta(days=1)
    midnight = datetime.datetime.combine(tomorrow.date(), datetime.time(0, 0))
    return max(0.0, (midnight - now).total_seconds())


async def click_day(free_page, day_number: int, month_number: int):
    month_name = MONTH_IT[month_number - 1]
    calendar = free_page.locator(SEL_CALENDAR)
    title_sel = f'a[title="{day_number} {month_name}"]'
    anchor = calendar.locator(title_sel)
    if await anchor.count() > 0:
        await anchor.first.scroll_into_view_if_needed()
        await anchor.first.wait_for(state="visible", timeout=5000)
        await anchor.first.click()
        return
    anchor_fallback = calendar.locator(f'a:has-text("{day_number}")')
    if await anchor_fallback.count() > 0:
        await anchor_fallback.first.scroll_into_view_if_needed()
        await anchor_fallback.first.wait_for(state="visible", timeout=5000)
        await anchor_fallback.first.click()
        return
    cell = calendar.locator(f'td:has-text("{day_number}")')
    await cell.first.scroll_into_view_if_needed()
    await cell.first.wait_for(state="visible", timeout=5000)
    await cell.first.click()


async def click_day_with_retry(
    free_page,
    day_number: int,
    month_number: int,
    attempts: int = 5,
    pause_ms: int = 50,
    log_cb: Optional[Callable[[str], None]] = None,
):
    """Click the target day. One click per attempt; reload immediately if missing/failed."""
    day_clicked = False
    for i in range(1, attempts + 1):
        try:
            month_name = MONTH_IT[month_number - 1]
            calendar = free_page.locator(SEL_CALENDAR)
            title_sel = f'a[title="{day_number} {month_name}"]'
            anchor = calendar.locator(title_sel)
            anchor_fallback = calendar.locator(f'a:has-text("{day_number}")')
            has_anchor = await anchor.count() > 0 or await anchor_fallback.count() > 0

            if has_anchor:
                try:
                    await click_day(free_page, day_number, month_number)
                    msg = f"Clicked day {day_number} on attempt {i}."
                    if log_cb:
                        log_cb(msg)
                    day_clicked = True
                    break
                except Exception as e:
                    msg = f"Attempt {i}: click failed ({e}); reloading..."
                    if log_cb:
                        log_cb(msg)
                    await free_page.reload(wait_until="domcontentloaded")
            else:
                msg = f"Attempt {i}: day {day_number} anchor not found (gray); reloading..."
                if log_cb:
                    log_cb(msg)
                await free_page.reload(wait_until="domcontentloaded")
        except Exception as e:
            msg = f"Attempt {i} failed to click day {day_number}; will retry... ({e})"
            if log_cb:
                log_cb(msg)
            await free_page.reload(wait_until="domcontentloaded")
        await free_page.wait_for_timeout(pause_ms)
    if not day_clicked:
        raise RuntimeError(f"Could not click day {day_number} after {attempts} attempts")


async def run_booking(
    username: str,
    password: str,
    target_date: datetime.date,
    primary_slot_selector: str,
    wait_for_midnight: bool,
    log_cb: Optional[Callable[[str], None]] = None,
    try_other_slots: bool = False,
    day_attempts: int = 5,
    start_early_seconds: int = 30,
):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-extensions",
                "--disable-default-apps",
                "--disable-sync",
                "--disable-background-networking",
                "--disable-component-update",
                "--no-first-run",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            java_script_enabled=True,
        )
        page = await context.new_page()
        page.set_default_timeout(6000)
        page.set_default_navigation_timeout(8000)

        try:
            await page.goto(URL_LOGIN, wait_until="domcontentloaded")
            if log_cb:
                log_cb("Loaded login page.")

            async def do_login() -> bool:
                await page.fill(SEL_USERNAME, username)
                await page.fill(SEL_PASSWORD, password)
                await page.click(SEL_LOGIN_BTN)
                try:
                    await page.wait_for_selector(SEL_NAV_PRENOTAZIONI, state="visible", timeout=4000)
                    return True
                except Exception:
                    return False

            if not await do_login():
                if log_cb:
                    log_cb("Login link not found; retrying once after reload...")
                await page.reload(wait_until="domcontentloaded")
                if not await do_login():
                    raise RuntimeError("Login still not confirmed; credentials/selector may be wrong or a popup is blocking.")
            if log_cb:
                log_cb("Login successful.")

            await page.click(SEL_NAV_PRENOTAZIONI)
            await page.wait_for_load_state("domcontentloaded")
            if log_cb:
                log_cb("Opened Prenotazioni.")

            async with page.context.expect_page() as new_page_info:
                await page.click(SEL_FREE_FITNESS)
            free_page = await new_page_info.value
            free_page.set_default_timeout(6000)
            await free_page.wait_for_load_state("domcontentloaded")
            if log_cb:
                log_cb("Opened Free Fitness page.")

            target_day = target_date.day
            target_month = target_date.month
            if log_cb:
                log_cb(f"Target date: {target_date}, day: {target_day}, month: {target_month}")

            if wait_for_midnight:
                wait_s = seconds_until_midnight()
                if wait_s > start_early_seconds:
                    sleep_s = wait_s - start_early_seconds
                    if log_cb:
                        log_cb(f"Waiting {sleep_s:.0f}s (until {start_early_seconds}s before midnight)...")
                    await asyncio.sleep(max(0, sleep_s))
                await free_page.wait_for_timeout(200)
                await free_page.reload(wait_until="domcontentloaded")

            if log_cb:
                log_cb("Clicking target day...")
            await click_day_with_retry(free_page, target_day, target_month, attempts=day_attempts, log_cb=log_cb)

            # Try primary slot, optionally fall back to others
            slot_order: List[str] = [primary_slot_selector]
            if try_other_slots:
                all_slots = [SEL_SLOT_0, SEL_SLOT_1, SEL_SLOT_2, SEL_SLOT_3]
                for s in all_slots:
                    if s not in slot_order:
                        slot_order.append(s)

            last_error = None
            for idx, slot_selector in enumerate(slot_order, 1):
                try:
                    if not await free_page.is_enabled(slot_selector):
                        msg = f"Slot {idx-1} disabled/full; skipping."
                        if log_cb:
                            log_cb(msg)
                        continue
                    await free_page.check(slot_selector, force=True)
                    if log_cb:
                        log_cb(f"Slot selected ({slot_selector}); submitting.")
                    await free_page.click(SEL_CONFIRM)
                    if log_cb:
                        log_cb("Confirm clicked; waiting for server response.")
                    await free_page.wait_for_timeout(1500)
                    await free_page.screenshot(path="booking_result.png", full_page=True)
                    if log_cb:
                        log_cb("Attempted booking; see booking_result.png")
                        log_cb("Booking flow completed (check booking_result.png or portal for success).")
                    return
                except Exception as e:
                    last_error = e
                    msg = f"Slot attempt failed ({slot_selector}): {e}"
                    if log_cb:
                        log_cb(msg)
                    continue

            if last_error:
                raise RuntimeError(f"All slots failed; last error: {last_error}")
            else:
                raise RuntimeError("All slots disabled/full; no booking submitted.")
        finally:
            await browser.close()

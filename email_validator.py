#!/usr/bin/env python3
import argparse
import csv
import random
import sys
import time
from typing import Dict, Iterable, Optional, Set, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, ElementNotInteractableException
from webdriver_manager.chrome import ChromeDriverManager
from unidecode import unidecode


GOOGLE_SIGNIN_URL = (
    "https://accounts.google.com/signin/v2/identifier"
    "?hl=en&flowName=GlifWebSignIn&flowEntry=ServiceLogin"
)


def make_driver(headless: bool = True) -> webdriver.Chrome:
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280,900")
    chrome_options.add_argument("--lang=en-US,en")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-features=UserAgentClientHint")
    chrome_options.add_argument("--remote-allow-origins=*")

    try:
        driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
    except TypeError:
        from selenium.webdriver.chrome.service import Service
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                const newProto = navigator.__proto__;
                delete newProto.webdriver;
                navigator.__proto__ = newProto;
                """,
            },
        )
    except Exception:
        pass

    return driver


def read_input_rows(path: str) -> Iterable[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def consent_click_if_present(driver: webdriver.Chrome):
    selectors = [
        "button#L2AGLb",
        "form[action*='consent'] button",
        "div[role='dialog'] button",
    ]
    for sel in selectors:
        try:
            elem = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
            label = (elem.text or "").strip().lower()
            if any(x in label for x in ["i agree", "accept", "agree"]):
                elem.click()
                time.sleep(0.3)
                return
        except TimeoutException:
            continue
        except Exception:
            continue


def account_chooser_bypass(driver: webdriver.Chrome):
    try:
        chooser = driver.find_elements(By.XPATH, "//div[text()='Use another account' or contains(., 'Use another account')]")
        if chooser:
            chooser[0].click()
            time.sleep(0.4)
    except Exception:
        pass


def detect_invalid_by_message(driver: webdriver.Chrome) -> bool:
    page = driver.page_source or ""
    if "Couldn't find your Google Account" in page:
        return True
    if "Enter a valid email" in page or "Enter an email or phone number" in page:
        return True
    try:
        err = driver.find_elements(By.CSS_SELECTOR, "div.o6cuMc")
        for e in err:
            if "Couldn't find" in (e.text or ""):
                return True
    except Exception:
        pass
    try:
        error_div = driver.find_element(By.CSS_SELECTOR, "div[aria-live='assertive']")
        if error_div and error_div.text and ("Couldn't find" in error_div.text or "Enter a valid" in error_div.text):
            return True
    except NoSuchElementException:
        pass
    return False


def is_saml_flow(driver: webdriver.Chrome) -> bool:
    url = driver.current_url
    return ("/saml2/" in url) or ("/o/saml2/" in url) or ("/samlredirect" in url) or ("/sso/" in url)


def at_password_step(driver: webdriver.Chrome) -> bool:
    url = driver.current_url
    if any(k in url for k in [
        "/v2/challenge/password",
        "/signin/v2/challenge/pwd",
        "/v3/signin/challenge/pwd",
        "/signin/challenge/pwd",
        "/challenge/password",
    ]):
        return True
    try:
        pwd = driver.find_elements(By.CSS_SELECTOR, "input[type='password'], input[name='Passwd']")
        if pwd:
            return True
    except Exception:
        pass
    return False


def submit_wrong_password_and_check(driver: webdriver.Chrome, timeout: float = 10.0) -> Optional[bool]:
    try:
        wait = WebDriverWait(driver, timeout)
        pwd_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password'], input[name='Passwd']")))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", pwd_input)
        try:
            pwd_input.click()
        except Exception:
            pass
        pwd_input.clear()
        pwd_input.send_keys("NotTheRightPassword123!!")
        pwd_input.send_keys(Keys.RETURN)
    except TimeoutException:
        return None

    try:
        WebDriverWait(driver, 8.0).until(lambda d: ("Wrong password" in (d.page_source or "")) or detect_invalid_by_message(d))
    except TimeoutException:
        pass

    page = driver.page_source or ""
    if "Wrong password" in page or "Enter your password" in page or "Try again" in page:
        return True
    if detect_invalid_by_message(driver):
        return False
    return None


def find_identifier_input(wait: WebDriverWait) -> Optional[object]:
    selectors = [
        (By.ID, "identifierId"),
        (By.CSS_SELECTOR, "input[type='email']"),
        (By.NAME, "identifier"),
    ]
    for by, sel in selectors:
        try:
            elem = wait.until(EC.element_to_be_clickable((by, sel)))
            return elem
        except TimeoutException:
            continue
    return None


def click_next_if_present(driver: webdriver.Chrome):
    try:
        btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.ID, "identifierNext")))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        btn.click()
    except TimeoutException:
        pass
    except Exception:
        pass


def validate_email_google(driver: webdriver.Chrome, email: str, per_item_timeout: float = 15.0) -> Optional[bool]:
    try:
        driver.get(GOOGLE_SIGNIN_URL)
    except WebDriverException:
        return None

    consent_click_if_present(driver)
    account_chooser_bypass(driver)

    try:
        wait = WebDriverWait(driver, per_item_timeout)
        email_input = find_identifier_input(wait)
        if not email_input:
            return None
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", email_input)
        try:
            email_input.click()
        except Exception:
            pass
        try:
            email_input.clear()
        except ElementNotInteractableException:
            # try re-fetching as clickable
            email_input = find_identifier_input(wait)
        try:
            email_input.send_keys(email)
        except ElementNotInteractableException:
            email_input = find_identifier_input(wait)
            if not email_input:
                return None
            email_input.send_keys(email)
        # Submit via Enter and also click Next as fallback
        email_input.send_keys(Keys.RETURN)
        time.sleep(0.3)
        click_next_if_present(driver)
    except TimeoutException:
        return None

    time.sleep(1.2)

    if is_saml_flow(driver):
        return None

    if detect_invalid_by_message(driver):
        return False

    if at_password_step(driver):
        return submit_wrong_password_and_check(driver)

    try:
        WebDriverWait(driver, 8.0).until(lambda d: at_password_step(d) or detect_invalid_by_message(d) or is_saml_flow(d))
    except TimeoutException:
        pass

    if is_saml_flow(driver):
        return None
    if detect_invalid_by_message(driver):
        return False
    if at_password_step(driver):
        return submit_wrong_password_and_check(driver)

    return None


def normalize_person_key(full_name: str, username: str) -> Tuple[str, str]:
    name_key = unidecode(full_name or "").strip().lower()
    user_key = (username or "").strip().lower()
    return name_key, user_key


def main():
    parser = argparse.ArgumentParser(description="Validate emails via Google sign-in flow (existence ping)")
    parser.add_argument("input_csv", nargs="?", default="permuted_emails.csv", help="CSV with at least an 'email' column")
    parser.add_argument("--output", "-o", default="verified_emails.csv", help="Output CSV for valid emails")
    parser.add_argument("--no-headless", action="store_true", help="Run Chrome with a visible window")
    parser.add_argument("--sleep-min", type=float, default=1.8, help="Minimum sleep between checks (seconds)")
    parser.add_argument("--sleep-max", type=float, default=4.0, help="Maximum sleep between checks (seconds)")
    parser.add_argument("--restart-n", type=int, default=200, help="Restart the browser after N checks to reduce rate limits")
    args = parser.parse_args()

    headless = not args.no_headless

    driver = make_driver(headless=headless)

    seen_emails: Set[str] = set()
    valid_emails: Set[str] = set()
    assigned_people: Set[Tuple[str, str]] = set()

    try:
        with open(args.output, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                valid_emails.add((row.get("email", "") or "").strip())
                assigned_people.add(normalize_person_key(row.get("full_name", ""), row.get("username", "")))
    except FileNotFoundError:
        pass

    total_checked = 0
    total_valid = len(valid_emails)

    def write_valid(row: Dict[str, str]):
        nonlocal total_valid
        with open(args.output, "a", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=["full_name", "username", "email"])
            if out.tell() == 0:
                writer.writeheader()
            writer.writerow({
                "full_name": row.get("full_name", ""),
                "username": row.get("username", ""),
                "email": row.get("email", ""),
            })
        total_valid += 1

    try:
        for idx, row in enumerate(read_input_rows(args.input_csv), start=1):
            email = (row.get("email", "") or "").strip()
            full_name = row.get("full_name", "") or ""
            username = row.get("username", "") or ""
            person_key = normalize_person_key(full_name, username)

            if not email or email in seen_emails or email in valid_emails:
                continue
            if person_key in assigned_people:
                continue

            seen_emails.add(email)

            verdict = validate_email_google(driver, email)
            total_checked += 1

            if verdict is True:
                write_valid(row)
                assigned_people.add(person_key)
            elif verdict is None:
                time.sleep(random.uniform(args.sleep_min + 1.0, args.sleep_max + 3.0))

            if total_checked % 25 == 0:
                print(f"Checked {total_checked} emails, {total_valid} valid found...")

            time.sleep(random.uniform(args.sleep_min, args.sleep_max))

            if args.restart_n and (total_checked % args.restart_n == 0):
                try:
                    driver.quit()
                except Exception:
                    pass
                time.sleep(2.0)
                driver = make_driver(headless=headless)

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    print(f"Done. Checked {total_checked} unique emails. Valid: {total_valid}. Output: {args.output}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    main()

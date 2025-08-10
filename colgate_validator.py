#!/usr/bin/env python3
import argparse
import csv
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

MS_LOGIN_URL = "https://login.microsoftonline.com/5b75a9d0-188c-4a00-af54-5800ada1149f/saml2?SAMLRequest=lZJRb5swFIXf8ysQ72DjwGasJFLadFukLImabA97qYy5pJaMzXzNtv77Au3W9WGVxuPhnk%2FnHHmBsjWdWPfh3t7C9x4wzKLoV2ssiunXMu69FU6iRmFlCyiCEqf1551gKRWdd8EpZ%2BJXprc9EhF80M6Opu1mGR%2F2N7vDx%2B3%2BjkNRAS%2FmCvI8q%2FKyVHUpGS9YrWTFQDUwZ%2B8Yp6PxK3gcGMt4QE4gxB62FoO0YRApKxLKk4yeGRNzLubs23i1GfppK8PkvA%2BhQ0GIcRdt01Yr79A1wVmjLaTKtaSo3heyrGmSca6SXFKayKbIk4JTKmuZZXnZkLExG%2BHH5zGutK21vby9QvV0hOLT%2BXxMjofTeUSsf29z7Sz2LfgT%2BB9awZfb3UvezvkgzRDQXGSAFOqeyE4T5TxMYe4QHYlXAy6KFqMgpnH86r8AC%2FK39QXWif1QZrs5OqPVw6SP3wfnWxn%2B3TlLs0nRddJMp6K32IHSjYY6%2FoNZG%2BN%2BXnsYci3j4HuII7KazZ7CvH6nq0c%3D&RelayState=https%3A%2F%2Fportal.colgate.edu%2Fapi%2Fcore%2Fsaml_sso"


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


def read_input_rows(path: str) -> Iterable[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def load_login_page(driver: webdriver.Chrome, timeout: float = 20.0) -> bool:
    try:
        driver.get(MS_LOGIN_URL)
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        return True
    except Exception:
        return False


def at_username_step(driver: webdriver.Chrome) -> bool:
    try:
        return (
            any(el.is_displayed() for el in driver.find_elements(By.ID, "i0116"))
            or any(el.is_displayed() for el in driver.find_elements(By.NAME, "loginfmt"))
            or any(el.is_displayed() for el in driver.find_elements(By.CSS_SELECTOR, "input[type='email']"))
        )
    except Exception:
        return False


def at_password_step(driver: webdriver.Chrome) -> bool:
    try:
        pw = [el for el in driver.find_elements(By.ID, "i0118") if el.is_displayed()]
        if pw:
            # Also confirm header suggests password entry
            headers = driver.find_elements(By.ID, "loginHeader")
            if any("password" in (h.text or "").lower() for h in headers):
                return True
            # Or presence of aria-label containing password
            return True
    except Exception:
        pass
    return False


def go_back_to_username(driver: webdriver.Chrome):
    for by, sel in [
        (By.ID, "idBtn_Back"),
        (By.XPATH, "//a[contains(., 'Use another account') or contains(., 'use another account')]"),
        (By.XPATH, "//div[@role='button' and contains(., 'Use another account')]")
    ]:
        try:
            btns = driver.find_elements(by, sel)
            if btns:
                btns[0].click()
                time.sleep(0.6)
                return
        except Exception:
            continue
    load_login_page(driver)


def type_like_human(element, text: str):
    for ch in text:
        element.send_keys(ch)
        time.sleep(0.05 + random.uniform(0.02, 0.08))


def find_username_error_text(driver: webdriver.Chrome) -> str:
    for by, sel in [
        (By.ID, "usernameError"),
        (By.CSS_SELECTOR, "div[role='alert']"),
        (By.CSS_SELECTOR, ".text-danger, .error, .alert")
    ]:
        try:
            els = driver.find_elements(by, sel)
            for e in els:
                txt = (e.text or "").strip()
                if txt and e.is_displayed():
                    return txt
        except Exception:
            continue
    return ""


def enter_email_and_submit(driver: webdriver.Chrome, email: str, timeout: float = 12.0) -> Optional[bool]:
    if not at_username_step(driver):
        go_back_to_username(driver)
        try:
            WebDriverWait(driver, 8.0).until(lambda d: at_username_step(d))
        except TimeoutException:
            return None

    try:
        wait = WebDriverWait(driver, timeout)
        email_input = None
        for by, sel in [
            (By.ID, "i0116"),
            (By.NAME, "loginfmt"),
            (By.CSS_SELECTOR, "input[type='email']"),
        ]:
            try:
                email_input = wait.until(EC.element_to_be_clickable((by, sel)))
                if email_input and email_input.is_displayed():
                    break
            except TimeoutException:
                continue
        if not email_input:
            return None
        email_input.clear()
        type_like_human(email_input, email)
        email_input.send_keys(Keys.RETURN)
    except TimeoutException:
        return None

    # Wait for an explicit state: visible password OR visible error
    try:
        WebDriverWait(driver, 10.0).until(lambda d: at_password_step(d) or (find_username_error_text(d) != ""))
    except TimeoutException:
        pass

    err_text = find_username_error_text(driver).lower()
    invalid_hints = [
        "this username may be incorrect",
        "we couldn't find an account",
        "enter a valid email address",
        "that microsoft account doesn't exist",
        "couldn't find your account",
        "no account found",
    ]
    if any(h in err_text for h in invalid_hints):
        return False

    if at_password_step(driver):
        return True

    # Ambiguous stays None (not valid)
    return None


def main():
    parser = argparse.ArgumentParser(description="Validate emails via Microsoft login first-step (username check)")
    parser.add_argument("input_csv", help="CSV with an 'email' column")
    parser.add_argument("--output", "-o", default="verified_colgate.csv", help="Output CSV for valid emails")
    parser.add_argument("--no-headless", action="store_true", help="Run Chrome visible")
    parser.add_argument("--sleep-min", type=float, default=4.0, help="Minimum sleep between checks")
    parser.add_argument("--sleep-max", type=float, default=7.5, help="Maximum sleep between checks")
    parser.add_argument("--cooldown-n", type=int, default=15, help="After N checks, pause longer to avoid flags")
    parser.add_argument("--cooldown-s", type=float, default=30.0, help="Cooldown seconds after cooldown-n")
    args = parser.parse_args()

    headless = not args.no_headless
    driver = make_driver(headless=headless)

    if not load_login_page(driver):
        print("Failed to load Microsoft login page")
        driver.quit()
        sys.exit(1)

    seen_emails: Set[str] = set()
    valid_emails: Set[str] = set()

    try:
        with open(args.output, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                e = (row.get("email", "") or "").strip().lower()
                if e:
                    valid_emails.add(e)
    except FileNotFoundError:
        pass

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
            email = (row.get("email", "") or "").strip()
            if not email:
                continue
            if email.lower() in seen_emails or email.lower() in valid_emails:
                continue
            seen_emails.add(email.lower())

            print(f"Checking {idx}: {email}")
            verdict = enter_email_and_submit(driver, email)

            if verdict is True:
                write_valid(row)
                valid_emails.add(email.lower())

            processed += 1

            # Human-like pacing and cooldowns
            time.sleep(random.uniform(args.sleep_min, args.sleep_max))
            if args.cooldown_n and processed % args.cooldown_n == 0:
                time.sleep(args.cooldown_s)

            # Reset to username step for next iteration
            go_back_to_username(driver)

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

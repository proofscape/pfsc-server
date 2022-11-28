# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2022 Proofscape contributors                           #
#                                                                             #
#   Licensed under the Apache License, Version 2.0 (the "License");           #
#   you may not use this file except in compliance with the License.          #
#   You may obtain a copy of the License at                                   #
#                                                                             #
#       http://www.apache.org/licenses/LICENSE-2.0                            #
#                                                                             #
#   Unless required by applicable law or agreed to in writing, software       #
#   distributed under the License is distributed on an "AS IS" BASIS,         #
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  #
#   See the License for the specific language governing permissions and       #
#   limitations under the License.                                            #
# --------------------------------------------------------------------------- #

import time
import logging
import pathlib

import requests
from requests.exceptions import ConnectionError
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains

import conf as pfsc_conf
from manage import PFSC_ROOT

BASIC_WAIT = pfsc_conf.SEL_BASIC_WAIT


def make_driver():
    """
    Construct a driver, with options such as:
      * which browser
      * whether to operate headlessly
    determined by our conf.py.
    """
    browser = pfsc_conf.SEL_BROWSER.upper()
    headless = pfsc_conf.SEL_HEADLESS

    driver = None
    if browser == "CHROME":
        options = ChromeOptions()
        options.headless = headless
        if pfsc_conf.SEL_STAY_OPEN:
            options.add_experimental_option("detach", True)
        return webdriver.Chrome(options=options)
    elif browser == "FIREFOX":
        options = FirefoxOptions()
        options.headless = headless
        return webdriver.Firefox(options=options)

    return driver


def get_pise_url():
    url = pfsc_conf.SEL_PISE_URL
    url = url.replace("<MCA_PORT>", str(pfsc_conf.PFSC_ISE_MCA_PORT))
    return url


def check_pise_server(logger_name='root'):
    """
        Try to connect to the PISE server for up to SEL_SERVER_READY_TIMEOUT seconds.
        Return a pair (code, message) indicating the result.
        code ranges from 0 to 4 incl., 4 means the server appears to be ready,
        anything less means it is not ready.
        """
    logger = logging.getLogger(logger_name)
    expected_text = '<title>Proofscape ISE</title>'
    result = 0, 'unknown issue'
    pise_url = get_pise_url()
    for i in range(int(pfsc_conf.SEL_SERVER_READY_TIMEOUT)):
        try:
            r = requests.get(pise_url)
        except ConnectionError:
            result = 1, 'could not connect'
        else:
            if r.status_code == 200:
                if r.text.find(expected_text) >= 0:
                    result = 4, 'status 200, and found expected text'
                    break
                else:
                    result = 3, f'status 200, but did not find expected text, "{expected_text}"'
            else:
                result = 2, f'status {r.status_code}'
        logger.debug(f'PISE server connection attempt {i + 1}: {result[1]}')
        time.sleep(1)
    return result


def load_page(driver, url, logger_name='root'):
    logger = logging.getLogger(logger_name)
    driver.get(url)
    logger.info(f"Loaded page {url}")
    w, h = pfsc_conf.SEL_WINDOW_WIDTH, pfsc_conf.SEL_WINDOW_HEIGHT
    driver.set_window_size(w, h)
    logger.info(f"Set page size {w}x{h}")


def dismiss_cookie_notice(driver, logger_name='root'):
    """
    Dismiss the cookie notice, if any.
    """
    logger = logging.getLogger(logger_name)
    buttons = driver.find_elements(By.CSS_SELECTOR, "body > div.noticeBox > div.buttonRow > button")
    if buttons:
        buttons[0].click()
        logger.info("Dismissed cookie notice")
    else:
        logger.info("Found no cookie notice")


def login_as_test_user(driver, user, wait=BASIC_WAIT, logger_name='root'):
    """
    Log in as a test.user
    """
    logger = logging.getLogger(logger_name)
    v = {}
    
    def wait_for_window(wait=BASIC_WAIT):
        time.sleep(wait)
        wh_now = driver.window_handles
        wh_then = v["window_handles"]
        if len(wh_now) > len(wh_then):
            return set(wh_now).difference(set(wh_then)).pop()
    logger.info("Logging in...")
    # Click the user menu
    driver.find_element(By.ID, "dijit_PopupMenuBarItem_8_text").click()
    v["window_handles"] = driver.window_handles
    # Click the "Log in" option
    driver.find_element(By.ID, "dijit_MenuItem_25_text").click()
    v["popup"] = wait_for_window(wait)
    v["root"] = driver.current_window_handle
    # In pop-up window, log in as the desired test user
    driver.switch_to.window(v["popup"])
    driver.find_element(By.NAME, "username").click()
    driver.find_element(By.NAME, "username").send_keys(user)
    driver.find_element(By.NAME, "password").send_keys(user)
    driver.find_element(By.CSS_SELECTOR, "p > input").click()
    driver.close()
    driver.switch_to.window(v["root"])
    # User menu text should now say our username
    WebDriverWait(driver, wait).until(expected_conditions.text_to_be_present_in_element((By.ID, "dijit_PopupMenuBarItem_8_text"), f"test.{user}"))
    assert driver.find_element(By.ID, "dijit_PopupMenuBarItem_8_text").text == f"test.{user}"
    logger.info(f"Logged in as test.{user}")


def log_out(driver, wait=BASIC_WAIT, logger_name='root'):
    logger = logging.getLogger(logger_name)
    driver.find_element(By.ID, "dijit_PopupMenuBarItem_8_text").click()
    driver.find_element(By.ID, "dijit_MenuItem_28_text").click()
    # User menu text should now once again say "User"
    WebDriverWait(driver, wait).until(expected_conditions.text_to_be_present_in_element((By.ID, "dijit_PopupMenuBarItem_8_text"), "User"))
    assert driver.find_element(By.ID, "dijit_PopupMenuBarItem_8_text").text == "User"
    logger.info(f"Logged out")


def check_user_menu(driver, wait=BASIC_WAIT, logger_name='root'):
    logger = logging.getLogger(logger_name)
    menu_text_elt = driver.find_element(By.ID, "dijit_PopupMenuBarItem_8_text")
    menu_text = menu_text_elt.text
    if menu_text == "User":
        logger.info("Appear to be logged out")
    else:
        logger.info(f"Appear to be logged in as {menu_text}")


def wait_for_element(driver, selector, wait=BASIC_WAIT):
    WebDriverWait(driver, wait).until(expected_conditions.presence_of_element_located((By.CSS_SELECTOR, selector)))
    return driver.find_element(By.CSS_SELECTOR, selector)


def wait_for_element_with_text(driver, selector, text, wait=BASIC_WAIT):
    WebDriverWait(driver, wait).until(expected_conditions.text_to_be_present_in_element((By.CSS_SELECTOR, selector), text))
    return driver.find_element(By.CSS_SELECTOR, selector)


def wait_for_element_visible(driver, selector, wait=BASIC_WAIT):
    WebDriverWait(driver, wait).until(expected_conditions.visibility_of_element_located((By.CSS_SELECTOR, selector)))
    return driver.find_element(By.CSS_SELECTOR, selector)


def wait_for_element_invisible(driver, selector, wait=BASIC_WAIT):
    WebDriverWait(driver, wait).until(expected_conditions.invisibility_of_element_located((By.CSS_SELECTOR, selector)))


def inner_html(element):
    return element.get_attribute('innerHTML')


def open_repo(driver, repopath, selector, wait=BASIC_WAIT, select_tab=None, logger_name='root'):
    """
    Open a content repo.

    selector: for the tree node element whose text will be the repopath, after
        the repo loads
    wait: max seconds to wait for repo to load
    """
    logger = logging.getLogger(logger_name)
    logger.info(f"Opening repo {repopath}...")
    driver.find_element(By.ID, "repoInputText").click()
    driver.find_element(By.ID, "repoInputText").send_keys(repopath)
    driver.find_element(By.ID, "repoInputButton").click()
    if select_tab:
        tab_sel = {
            'fs': '#dijit_layout_TabContainer_0_tablist_fsTab',
            'build': '#dijit_layout_TabContainer_0_tablist_buildTab',
            'struct': '#dijit_layout_TabContainer_0_tablist_buildTab',
        }[select_tab]
        tab = wait_for_element(driver, tab_sel, wait=wait)
        tab.click()
    root_node = wait_for_element(driver, selector, wait=wait)
    # Strangely, for this element it's not the inner text, but inner HTML that
    # is equal to the repopath.
    #logger.debug(f'repo root node text: {root_node.text}')
    #logger.debug(f'repo root node html: {root_node.get_attribute("innerHTML")}')
    assert inner_html(root_node) == repopath
    logger.info(f"Opened repo {repopath}.")


def click(driver, selector, button='l'):
    """
    Click element by selector.

    button: 'l' or 'r', default 'l'
    """
    elt = driver.find_element(By.CSS_SELECTOR, selector)
    actions = ActionChains(driver)
    actions.move_to_element(elt)
    if button == 'r':
        actions.context_click()
    else:
        actions.click()
    actions.perform()


def right_click(driver, selector):
    """
    Right-click element by selector.
    """
    return click(driver, selector, button='r')


def click_nth_context_menu_option(driver, elt_sel, menu_table_id, n, label, logger_name='root'):
    """
    Find an element of a given selector, right-click it, then (left-)click
    the nth option on the context menu.

    elt_sel: CSS selector for the element to be right-clicked
    menu_table_id: id of the <table> element of the context menu
    n: you want the nth item on the menu. Remember to count separators!
    label: the text that should appear as the label of the desired menu option
    """
    logger = logging.getLogger(logger_name)
    logger.info(f'Right-clicking {elt_sel}...')
    right_click(driver, elt_sel)
    menu_option = wait_for_element_with_text(
        driver,
        f"#{menu_table_id} > tbody > tr:nth-child({n}) > td:nth-child(2)",
        label
    )
    logger.info(f'Got context menu with item {n} saying "{label}"')
    logger.info(f'Clicking item {n}...')
    menu_option.click()


class Tester:

    def setup_method(self, method):
        self.driver = make_driver()
        self.driver.delete_all_cookies()
        self.logger_name = 'root'

    def teardown_method(self, method):
        if pfsc_conf.SEL_TAKE_FINAL_SCREENSHOT:
            p = pathlib.Path(PFSC_ROOT) / 'selenium_screenshots'
            p.mkdir(exist_ok=True)
            p /= f'{self.__class__.__name__}.png'
            self.driver.save_screenshot(p)
        if pfsc_conf.SEL_HEADLESS or not pfsc_conf.SEL_STAY_OPEN:
            self.driver.quit()

    def check_pise_server(self):
        return check_pise_server(logger_name=self.logger_name)

    def load_page(self, url):
        return load_page(self.driver, url, logger_name=self.logger_name)

    def find_element(self, selector):
        """Returns single element or raises exception"""
        return self.driver.find_element(By.CSS_SELECTOR, selector)

    def find_elements(self, selector):
        """Returns list of elements (possibly empty)"""
        return self.driver.find_elements(By.CSS_SELECTOR, selector)

    def dismiss_cookie_notice(self):
        return dismiss_cookie_notice(self.driver, logger_name=self.logger_name)

    def login_as_test_user(self, user, wait=BASIC_WAIT):
        return login_as_test_user(self.driver, user, wait=wait, logger_name=self.logger_name)

    def log_out(self, wait=BASIC_WAIT):
        return log_out(self.driver, wait=wait, logger_name=self.logger_name)

    def check_user_menu(self, wait=BASIC_WAIT):
        return check_user_menu(self.driver, wait=wait, logger_name=self.logger_name)

    def open_repo(self, repopath, selector, wait=BASIC_WAIT, select_tab=None):
        return open_repo(self.driver, repopath, selector, wait=wait, select_tab=select_tab, logger_name=self.logger_name)

    def click(self, selector, button='l'):
        return click(self.driver, selector, button=button)

    def right_click(self, selector):
        return right_click(self.driver, selector)

    def wait_for_element(self, selector, wait=BASIC_WAIT):
        return wait_for_element(self.driver, selector, wait=wait)

    def wait_for_element_visible(self, selector, wait=BASIC_WAIT):
        return wait_for_element_visible(self.driver, selector, wait=wait)

    def wait_for_element_invisible(self, selector, wait=BASIC_WAIT):
        return wait_for_element_invisible(self.driver, selector, wait=wait)

    def wait_for_element_with_text(self, selector, text, wait=BASIC_WAIT):
        return wait_for_element_with_text(self.driver, selector, text, wait=wait)

    def click_nth_context_menu_option(self, elt_sel, menu_table_id, n, label):
        return click_nth_context_menu_option(self.driver, elt_sel, menu_table_id, n, label, logger_name=self.logger_name)

import os
import re
import time
from datetime import datetime
from pathlib import Path

import fitz  # PyMuPDF

from playwright.sync_api import (
    sync_playwright,
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
)


# ============================================================
# CONFIGURATION
# ============================================================

URL = "https://www.indupaper.com/hindustan-times.html"

BENCH_PATH = Path.home() / "frappe-bench"

SITE_NAME = "site1.local"

AD_TIMEOUT_SECONDS = 300

DOWNLOAD_TIMEOUT_SECONDS = 900


# ============================================================
# CLICK VISIBLE TEXT
# ============================================================

def click_visible_text(page, text):

    for frame in page.frames:

        try:

            matches = frame.get_by_text(
                text,
                exact=True
            )

            for index in range(matches.count()):

                control = matches.nth(index)

                if control.is_visible():

                    control.click(
                        timeout=1500
                    )

                    return True

        except PlaywrightError:

            if page.is_closed():
                raise

            continue

    return False


# ============================================================
# FIND ADVERTISEMENT PROGRESS BAR
# ============================================================

def find_visible_progress_bar(page):

    for frame in page.frames:

        try:

            bars = frame.locator(
                "#progress-bar-inner"
            )

            for index in range(bars.count()):

                bar = bars.nth(index)

                if bar.is_visible():

                    return bar

        except PlaywrightError:

            if page.is_closed():
                raise

            continue

    return None


# ============================================================
# HANDLE ADVERTISEMENT
# ============================================================

def handle_ad(page, detection_seconds=3):

    detection_deadline = (
        time.monotonic()
        + detection_seconds
    )

    ad_started = False


    while time.monotonic() < detection_deadline:

        if click_visible_text(
            page,
            "Click here to continue"
        ):

            print(
                "\nAd: Continue clicked.",
                flush=True
            )

            ad_started = True

            break


        if find_visible_progress_bar(page) is not None:

            print(
                "\nAd: Running advertisement detected.",
                flush=True
            )

            ad_started = True

            break


        page.wait_for_timeout(500)


    if not ad_started:

        return False


    if click_visible_text(
        page,
        "RESUME"
    ):

        print(
            "Ad: Resumed.",
            flush=True
        )


    print(
        "Ad: Waiting for progress to reach 100%...",
        flush=True
    )


    deadline = (
        time.monotonic()
        + AD_TIMEOUT_SECONDS
    )

    last_width = None

    progress_completed = False


    while time.monotonic() < deadline:

        if page.is_closed():

            raise RuntimeError(
                "The newspaper tab was closed."
            )


        bar = find_visible_progress_bar(
            page
        )


        if bar is None:

            page.wait_for_timeout(500)

            continue


        try:

            width = bar.evaluate(
                "(element) => element.style.width"
            )

        except PlaywrightError:

            if page.is_closed():
                raise

            page.wait_for_timeout(500)

            continue


        if width != last_width:

            print(
                f"Ad progress: {width or 'waiting'}",
                flush=True
            )

            last_width = width


        percentage = None


        if width.endswith("%"):

            try:

                percentage = float(
                    width[:-1]
                )

            except ValueError:
                pass


        if (
            percentage is not None
            and percentage >= 100
        ):

            print(
                "Ad: 100% reached.",
                flush=True
            )

            progress_completed = True

            page.wait_for_timeout(
                1500
            )

            break


        page.wait_for_timeout(
            500
        )


    if not progress_completed:

        raise RuntimeError(
            "Advertisement did not reach "
            "100% within 5 minutes."
        )


    print(
        "Ad: Looking for Close...",
        flush=True
    )


    close_deadline = (
        time.monotonic()
        + 30
    )


    while time.monotonic() < close_deadline:

        if click_visible_text(
            page,
            "Close"
        ):

            print(
                "Ad: Close clicked.",
                flush=True
            )

            page.wait_for_timeout(
                1500
            )

            return True


        page.wait_for_timeout(
            500
        )


    raise RuntimeError(
        "Advertisement finished, "
        "but Close could not be clicked."
    )


# ============================================================
# CLICK PDF BUTTON
# ============================================================

def click_pdf_when_ready(
    page,
    pdf_button
):

    deadline = (
        time.monotonic()
        + 360
    )

    last_message = 0


    while time.monotonic() < deadline:

        if page.is_closed():

            raise RuntimeError(
                "The newspaper tab was closed."
            )


        handle_ad(
            page,
            detection_seconds=1
        )


        try:

            pdf_button.click(
                trial=True,
                timeout=1500
            )


        except PlaywrightTimeoutError:

            now = time.monotonic()


            if (
                now - last_message
                >= 15
            ):

                print(
                    "Waiting for PDF button...",
                    flush=True
                )

                last_message = now


            page.wait_for_timeout(
                500
            )

            continue


        print(
            "PDF button ready.",
            flush=True
        )


        pdf_button.click(
            timeout=10000
        )


        return


    raise RuntimeError(
        "PDF button remained unavailable."
    )


# ============================================================
# GET PDF PAGE COUNT
# ============================================================

def get_pdf_page_count(pdf_path):

    document = fitz.open(
        str(pdf_path)
    )

    try:

        return document.page_count

    finally:

        document.close()


# ============================================================
# MAIN
# ============================================================

def run():

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )


    site_path = (
        BENCH_PATH
        / "sites"
        / SITE_NAME
    )


    if not site_path.is_dir():

        raise RuntimeError(
            f"Frappe site folder not found:\n"
            f"{site_path}\n"
            f"Check BENCH_PATH and SITE_NAME."
        )


    save_folder = (
        site_path
        / "private"
        / "files"
        / "newspapers"
        / "hindustan_times"
        / today
    )


    save_folder.mkdir(
        parents=True,
        exist_ok=True
    )


    save_path = (
        save_folder
        / "hindustan_times_delhi.pdf"
    )


    temporary_path = (
        save_folder
        / "hindustan_times_delhi.pdf.part"
    )


    print(
        "\n======================================"
    )

    print(
        "ESTATE NOTICE - NEWSPAPER FETCHER"
    )

    print(
        "======================================"
    )


    print(
        f"\nToday's date: {today}"
    )


    print(
        "\nPDF will be saved here:"
    )


    print(
        save_path
    )


    # ========================================================
    # START PLAYWRIGHT
    # ========================================================

    with sync_playwright() as playwright:

        print(
            "\n1. Opening browser..."
        )


        browser = playwright.chromium.launch(
            headless=False
        )


        context = browser.new_context(
            accept_downloads=True
        )


        page = context.new_page()


        try:

            # =================================================
            # OPEN WEBSITE
            # =================================================

            print(
                "2. Opening InduPaper...",
                flush=True
            )


            page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=60000
            )


            print(
                "3. InduPaper opened.",
                flush=True
            )


            # =================================================
            # ADVERTISEMENT
            # =================================================

            print(
                "4. Checking for advertisement...",
                flush=True
            )


            if not handle_ad(
                page,
                detection_seconds=30
            ):

                print(
                    "No initial advertisement detected."
                )


            # =================================================
            # CITY
            # =================================================

            city = page.get_by_label(
                "City",
                exact=True
            )


            if city.count() > 0:

                city.select_option(
                    label="Delhi",
                    timeout=30000
                )


                print(
                    "5. City selected: Delhi",
                    flush=True
                )


                page.wait_for_timeout(
                    2000
                )


            else:

                print(
                    "5. Separate City field not found."
                )


            handle_ad(
                page,
                detection_seconds=1
            )


            # =================================================
            # SUB CITY
            #
            # IMPORTANT CHANGE:
            # Select "Delhi"
            # NOT "Delhi City"
            # =================================================

            sub_city = page.get_by_label(
                "Sub City",
                exact=True
            )


            sub_city.wait_for(
                state="visible",
                timeout=30000
            )


            # -------------------------------------------------
            # THIS IS THE IMPORTANT FIX
            # -------------------------------------------------

            sub_city.select_option(
                label="Delhi",
                timeout=30000
            )


            print(
                "6. Sub City selected: Delhi",
                flush=True
            )


            page.wait_for_timeout(
                2000
            )


            # =================================================
            # DOWNLOAD LISTENER
            # =================================================

            downloads = []


            def handle_download(download):

                downloads.append(
                    download
                )


                print(
                    f"\nDOWNLOAD EVENT DETECTED "
                    f"({len(downloads)})",
                    flush=True
                )


            page.on(
                "download",
                handle_download
            )


            # =================================================
            # PDF BUTTON
            # =================================================

            pdf_button = page.get_by_role(
                "button",
                name="⬇ PDF",
                exact=True
            )


            print(
                "7. Waiting for PDF button...",
                flush=True
            )


            click_pdf_when_ready(
                page,
                pdf_button
            )


            print(
                "8. PDF clicked.",
                flush=True
            )


            print(
                "\n======================================"
            )

            print(
                "WAITING FOR ALL NEWSPAPER PAGES"
            )

            print(
                "======================================"
            )


            # =================================================
            # PROCESSING
            # =================================================

            start_time = (
                time.monotonic()
            )


            expected_pages = None

            current_page = None

            last_progress = None

            last_progress_time = (
                time.monotonic()
            )

            processing_started = False

            processing_finished = False

            download_notice_shown = False


            while (
                time.monotonic()
                - start_time
                < DOWNLOAD_TIMEOUT_SECONDS
            ):


                if page.is_closed():

                    raise RuntimeError(
                        "The newspaper tab closed "
                        "before processing completed."
                    )


                page.wait_for_timeout(
                    1000
                )


                # ---------------------------------------------
                # CHECK AD
                # ---------------------------------------------

                handle_ad(
                    page,
                    detection_seconds=1
                )


                # ---------------------------------------------
                # READ PAGE
                # ---------------------------------------------

                try:

                    body_text = page.locator(
                        "body"
                    ).inner_text(
                        timeout=10000
                    )


                except PlaywrightError:

                    continue


                # ---------------------------------------------
                # LOOK FOR:
                #
                # Processing page 1/20
                # ---------------------------------------------

                match = re.search(
                    r"Processing\s+page\s+"
                    r"(\d+)\s*/\s*(\d+)",
                    body_text,
                    re.IGNORECASE
                )


                if match:

                    processing_started = True


                    current_page = int(
                        match.group(1)
                    )


                    expected_pages = int(
                        match.group(2)
                    )


                    progress = (
                        current_page,
                        expected_pages
                    )


                    if (
                        progress
                        != last_progress
                    ):

                        print(
                            f"Processing page "
                            f"{current_page}/"
                            f"{expected_pages}",
                            flush=True
                        )


                        last_progress = (
                            progress
                        )


                        last_progress_time = (
                            time.monotonic()
                        )


                    # -----------------------------------------
                    # ALL PAGES FINISHED
                    # -----------------------------------------

                    if (
                        expected_pages is not None
                        and current_page
                        >= expected_pages
                    ):

                        print(
                            "\nWebsite reached final page:"
                        )


                        print(
                            f"{current_page}/"
                            f"{expected_pages}"
                        )


                        processing_finished = True


                        page.wait_for_timeout(
                            5000
                        )


                        break


                # ---------------------------------------------
                # DOWNLOAD STARTED EARLY
                # ---------------------------------------------

                if (
                    len(downloads) > 0
                    and not processing_finished
                    and not download_notice_shown
                ):

                    print(
                        "\nDownload event appeared, "
                        "but we are NOT stopping yet."
                    )


                    print(
                        "Waiting for newspaper processing "
                        "to finish..."
                    )


                    download_notice_shown = True


                # ---------------------------------------------
                # FALLBACK
                # ---------------------------------------------

                if (
                    processing_started
                    and len(downloads) > 0
                    and expected_pages is not None
                    and (
                        time.monotonic()
                        - last_progress_time
                        > 20
                    )
                ):

                    print(
                        "\nProcessing message disappeared."
                    )


                    print(
                        "A download exists, so the PDF "
                        "will now be verified."
                    )


                    break


            # =================================================
            # PROCESSING CHECK
            # =================================================

            if not processing_started:

                print(
                    "\nWARNING:"
                )


                print(
                    "Could not read "
                    "'Processing page X/Y'."
                )


            # =================================================
            # WAIT FOR DOWNLOAD
            # =================================================

            print(
                "\n9. Waiting for final PDF download..."
            )


            download_wait_start = (
                time.monotonic()
            )


            while len(downloads) == 0:

                if (
                    time.monotonic()
                    - download_wait_start
                    > 120
                ):

                    raise RuntimeError(
                        "No PDF download was detected "
                        "after newspaper processing."
                    )


                page.wait_for_timeout(
                    1000
                )


            print(
                "Download detected."
            )


            print(
                "Waiting 5 seconds for any final "
                "download event..."
            )


            page.wait_for_timeout(
                5000
            )


            # Use last download
            download = downloads[-1]


            print(
                f"Total download events detected: "
                f"{len(downloads)}"
            )


            # =================================================
            # SAVE TEMPORARY PDF
            # =================================================

            print(
                "\n10. Saving downloaded PDF...",
                flush=True
            )


            try:

                download.save_as(
                    str(temporary_path)
                )


                # =============================================
                # CHECK PDF HEADER
                # =============================================

                with temporary_path.open(
                    "rb"
                ) as pdf_file:

                    header = pdf_file.read(
                        1024
                    )


                if b"%PDF-" not in header:

                    raise RuntimeError(
                        "Downloaded file is not "
                        "a valid PDF."
                    )


                # =============================================
                # CHECK ACTUAL PDF PAGE COUNT
                # =============================================

                actual_pages = (
                    get_pdf_page_count(
                        temporary_path
                    )
                )


                print(
                    "\n======================================"
                )

                print(
                    "PAGE COUNT CHECK"
                )

                print(
                    "======================================"
                )


                print(
                    "Pages reported by website:",
                    expected_pages
                )


                print(
                    "Pages actually inside PDF:",
                    actual_pages
                )


                # =============================================
                # VERIFY PAGE COUNT
                # =============================================

                if expected_pages is not None:

                    if (
                        actual_pages
                        != expected_pages
                    ):

                        raise RuntimeError(
                            "\nINCOMPLETE PDF!\n"
                            f"Website reported "
                            f"{expected_pages} pages, "
                            f"but downloaded PDF contains "
                            f"only {actual_pages} pages."
                        )


                # =============================================
                # SAVE FINAL PDF
                # =============================================

                os.replace(
                    temporary_path,
                    save_path
                )


            finally:

                if temporary_path.exists():

                    temporary_path.unlink()


            # =================================================
            # SUCCESS
            # =================================================

            print(
                "\n======================================"
            )

            print(
                "DOWNLOAD SUCCESSFUL"
            )

            print(
                "======================================"
            )


            print(
                "Website pages:",
                expected_pages
            )


            print(
                "PDF pages:",
                actual_pages
            )


            print(
                "\nSaved here:"
            )


            print(
                save_path
            )


            print(
                "\nPoornima fetcher completed successfully."
            )


        # ====================================================
        # ERROR
        # ====================================================

        except Exception as error:

            print(
                "\n======================================"
            )

            print(
                "ERROR"
            )

            print(
                "======================================"
            )


            print(
                error
            )


            if (
                browser.is_connected()
                and not page.is_closed()
            ):

                print(
                    "\nBrowser kept open "
                    "for inspection."
                )


            else:

                print(
                    "\nBrowser/page was closed."
                )


        # ====================================================
        # CLOSE
        # ====================================================

        finally:

            try:

                input(
                    "\nPress ENTER in terminal "
                    "to close browser..."
                )


            finally:

                if browser.is_connected():

                    try:

                        context.close()

                    finally:

                        browser.close()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    run()

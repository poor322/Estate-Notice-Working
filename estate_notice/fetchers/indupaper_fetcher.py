import os
from datetime import datetime

from playwright.sync_api import Playwright, sync_playwright


# =========================================================
# SETTINGS
# =========================================================

NEWSPAPER_NAME = "Hindustan Times"

# This is the option Playwright already detected on your system
SUB_CITY_VALUE = "delhi-city"

EDITION_NAME = "Delhi"

URL = "https://www.indupaper.com/hindustan-times.html"

SITE_NAME = "site1.local"


# =========================================================
# MAIN FETCHER
# =========================================================

def run(playwright: Playwright):

    print("\n======================================")
    print("ESTATE NOTICE - NEWSPAPER FETCHER")
    print("======================================")

    # -----------------------------------------------------
    # STEP 1: GET TODAY'S DATE
    # -----------------------------------------------------

    today_folder = datetime.now().strftime("%Y-%m-%d")

    # For an HTML date input
    today_for_date_input = datetime.now().strftime("%Y-%m-%d")

    print("\nToday's date:", today_folder)


    # -----------------------------------------------------
    # STEP 2: CREATE SAVE FOLDER
    # -----------------------------------------------------

    home = os.path.expanduser("~")

    save_folder = os.path.join(
        home,
        "frappe-bench",
        "sites",
        SITE_NAME,
        "private",
        "files",
        "newspapers",
        "hindustan_times",
        today_folder
    )

    os.makedirs(
        save_folder,
        exist_ok=True
    )

    save_path = os.path.join(
        save_folder,
        "hindustan_times_delhi.pdf"
    )

    print("\nPDF will be saved here:")
    print(save_path)


    # -----------------------------------------------------
    # STEP 3: OPEN BROWSER
    # -----------------------------------------------------

    print("\n1. Opening browser...")

    browser = playwright.chromium.launch(
        headless=False
    )

    context = browser.new_context(
        accept_downloads=True
    )

    page = context.new_page()


    # -----------------------------------------------------
    # STEP 4: OPEN INDUPAPER
    # -----------------------------------------------------

    print("2. Opening InduPaper...")

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    print("3. InduPaper opened")

    page.wait_for_timeout(3000)


    # -----------------------------------------------------
    # STEP 5: SET TODAY'S DATE
    # -----------------------------------------------------

    print("\n4. Trying to select today's date...")

    try:

        # First try normal HTML date field
        date_input = page.locator(
            "input[type='date']"
        )

        if date_input.count() > 0:

            date_input.first.fill(
                today_for_date_input
            )

            print(
                "5. Date selected:",
                today_for_date_input
            )

        else:

            print(
                "5. Date input not detected."
            )

            print(
                "Website's default date will be used."
            )

    except Exception as e:

        print(
            "Could not automatically set date."
        )

        print(
            "Using website default date."
        )

        print(
            "Date error:",
            e
        )


    page.wait_for_timeout(2000)


    # -----------------------------------------------------
    # STEP 6: SELECT SUB CITY
    # -----------------------------------------------------

    print(
        "\n6. Selecting Delhi City..."
    )

    sub_city = page.get_by_label(
        "Sub City"
    )

    sub_city.wait_for(
        state="attached",
        timeout=20000
    )

    sub_city.select_option(
        SUB_CITY_VALUE
    )

    print(
        "7. Delhi City selected"
    )

    # Give website time to update buttons
    page.wait_for_timeout(3000)


    # -----------------------------------------------------
    # STEP 7: FIND PDF BUTTON
    # -----------------------------------------------------

    print(
        "\n8. Looking for PDF button..."
    )

    pdf_button = page.get_by_role(
        "button",
        name="⬇ PDF"
    )

    pdf_button.wait_for(
        state="visible",
        timeout=30000
    )

    print(
        "9. PDF button found"
    )

    print(
        "PDF visible:",
        pdf_button.is_visible()
    )

    print(
        "PDF enabled:",
        pdf_button.is_enabled()
    )


    # -----------------------------------------------------
    # STEP 8: SCROLL TO PDF BUTTON
    # -----------------------------------------------------

    print(
        "\n10. Scrolling to PDF button..."
    )

    pdf_button.scroll_into_view_if_needed()

    page.wait_for_timeout(2000)

    print(
        "11. Scroll completed"
    )


    # -----------------------------------------------------
    # STEP 9: CLICK PDF AND WAIT FOR DOWNLOAD
    # -----------------------------------------------------

    print(
        "\n12. Clicking PDF..."
    )

    try:

        with page.expect_download(
            timeout=120000
        ) as download_info:

            pdf_button.click(
                timeout=30000
            )

        download = download_info.value

        print(
            "\n13. DOWNLOAD DETECTED!"
        )

        print(
            "Original filename:",
            download.suggested_filename
        )


        # -------------------------------------------------
        # STEP 10: SAVE PDF INTO FRAPPE
        # -------------------------------------------------

        download.save_as(
            save_path
        )

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
            "\nNewspaper:"
        )

        print(
            NEWSPAPER_NAME
        )

        print(
            "\nEdition:"
        )

        print(
            EDITION_NAME
        )

        print(
            "\nDate:"
        )

        print(
            today_folder
        )

        print(
            "\nSaved PDF:"
        )

        print(
            save_path
        )


        # -------------------------------------------------
        # STEP 11: RETURN FETCH INFORMATION
        # -------------------------------------------------

        result = {
            "status": "success",
            "source": NEWSPAPER_NAME,
            "edition": EDITION_NAME,
            "date": today_folder,
            "file_path": save_path
        }

        print(
            "\nFetcher Result:"
        )

        print(
            result
        )


    except Exception as e:

        print(
            "\n======================================"
        )

        print(
            "DOWNLOAD FAILED"
        )

        print(
            "======================================"
        )

        print(
            "\nError:"
        )

        print(
            e
        )


    # -----------------------------------------------------
    # STEP 12: CLOSE BROWSER
    # -----------------------------------------------------

    print(
        "\n14. Closing browser..."
    )

    context.close()

    browser.close()

    print(
        "15. Fetcher finished."
    )


# =========================================================
# START PROGRAM
# =========================================================

if __name__ == "__main__":

    with sync_playwright() as playwright:

        run(playwright)

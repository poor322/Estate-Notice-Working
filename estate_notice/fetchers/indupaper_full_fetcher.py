import os
from datetime import datetime
from playwright.sync_api import sync_playwright


URL = "https://www.indupaper.com/hindustan-times.html"


def run():

    today = datetime.now().strftime("%Y-%m-%d")

    save_folder = os.path.expanduser(
        f"~/frappe-bench/sites/site1.local/private/files/"
        f"newspapers/hindustan_times/{today}/pages"
    )

    os.makedirs(save_folder, exist_ok=True)

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(
            headless=False
        )

        context = browser.new_context()

        page = context.new_page()

        # ---------------------------------
        # 1. Open InduPaper
        # ---------------------------------

        print("1. Opening InduPaper...")

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        print("2. InduPaper opened")

        page.wait_for_timeout(3000)


        # ---------------------------------
        # 2. Set today's date
        # ---------------------------------

        date_input = page.locator(
            "input[type='date']"
        )

        if date_input.count() > 0:

            date_input.first.fill(today)

            print("3. Date selected:", today)


        # ---------------------------------
        # 3. Select Delhi City
        # ---------------------------------

        try:

            city = page.get_by_label("City")

            city.select_option(
                label="Delhi"
            )

            print("4. City selected: Delhi")

            page.wait_for_timeout(2000)

        except Exception as e:

            print("City already selected / not required")


        # ---------------------------------
        # 4. Select Delhi Sub City
        # ---------------------------------

        sub_city = page.get_by_label(
            "Sub City"
        )

        sub_city.select_option(
            "delhi-city"
        )

        print("5. Sub City selected: Delhi")

        page.wait_for_timeout(3000)


        # ---------------------------------
        # 5. Click VIEW
        # ---------------------------------

        view_button = page.get_by_role(
            "button",
            name="👁 View"
        )

        print("6. Clicking View...")

        view_button.click(
            timeout=30000
        )

        print("7. View opened")

        page.wait_for_timeout(5000)


        # ---------------------------------
        # 6. Find ALL newspaper page images
        # ---------------------------------

        page_urls = []

        previous_count = -1
        same_count = 0

        print("\nWaiting for newspaper pages...")

        for attempt in range(90):

            # Scroll the View modal
            page.evaluate(
                """
                () => {
                    const modal =
                        document.querySelector('#epaperModal');

                    if (modal) {
                        modal.scrollTop =
                            modal.scrollHeight;
                    }
                }
                """
            )

            page.wait_for_timeout(2000)

            images = page.locator(
                "#epaperModal img"
            )

            for i in range(images.count()):

                src = images.nth(i).get_attribute(
                    "src"
                )

                if not src:
                    continue

                if (
                    "epaper.hindustantimes.com" in src
                    and "/pages/" in src
                    and src not in page_urls
                ):
                    page_urls.append(src)

            print(
                "Pages detected:",
                len(page_urls)
            )

            if len(page_urls) == previous_count:

                same_count += 1

            else:

                same_count = 0

            previous_count = len(page_urls)

            # no new pages for several checks
            if same_count >= 6:
                break


        # ---------------------------------
        # 7. Show total pages
        # ---------------------------------

        print("\n==============================")
        print(
            "TOTAL PAGES FOUND:",
            len(page_urls)
        )
        print("==============================")


        # ---------------------------------
        # 8. Download every page image
        # ---------------------------------

        for number, image_url in enumerate(
            page_urls,
            start=1
        ):

            print(
                f"Downloading page "
                f"{number}/{len(page_urls)}"
            )

            response = context.request.get(
                image_url,
                timeout=60000
            )

            if not response.ok:

                print(
                    f"Page {number} failed"
                )

                continue

            image_path = os.path.join(
                save_folder,
                f"page_{number:03d}.webp"
            )

            with open(
                image_path,
                "wb"
            ) as file:

                file.write(
                    response.body()
                )

            print(
                "Saved:",
                image_path
            )


        print("\n==============================")
        print("DOWNLOAD FINISHED")
        print("==============================")

        print(
            "Pages downloaded:",
            len(page_urls)
        )

        print(
            "Saved inside:"
        )

        print(
            save_folder
        )

        input(
            "\nPress ENTER to close browser..."
        )

        context.close()
        browser.close()


if __name__ == "__main__":

    run()

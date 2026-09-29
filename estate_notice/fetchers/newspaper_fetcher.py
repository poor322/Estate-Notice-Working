import os
import urllib.request
from urllib.parse import urlparse

import frappe
from frappe.utils import today


def fetch_newspaper_page(url, source, page_number=1):
    print("Fetching newspaper page...")

    date = today()

    # Create folder inside Frappe private files
    folder = frappe.get_site_path(
        "private",
        "files",
        "newspapers",
        source.replace(" ", "_"),
        date
    )

    os.makedirs(folder, exist_ok=True)

    # Find file extension from URL
    path = urlparse(url).path
    extension = os.path.splitext(path)[1]

    if not extension:
        extension = ".html"

    filename = f"page_{page_number}{extension}"
    file_path = os.path.join(folder, filename)

    # Download page/file
    urllib.request.urlretrieve(url, file_path)

    result = {
        "source": source,
        "date": date,
        "page_number": page_number,
        "file_path": file_path,
        "status": "fetched"
    }

    print(result)

    return result

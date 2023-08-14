import re
import urllib
from datetime import datetime
from multiprocessing.pool import ThreadPool
from typing import Tuple, Optional, List
from bs4 import BeautifulSoup
import requests
from requests import RequestException
from db_manager import DBManager
from image_processor import ImageProcessor
import time
from numpy import random

MIN_ADDITIONAL_PHOTOS = 10
MAX_ADDITIONAL_PHOTOS = 20
IMDB_DOMAIN = "https://www.imdb.com"


def scrape_html(url: str) -> Optional[BeautifulSoup]:
    user_agents = [
        # Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 "
        "Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 "
        "Safari/537.3",
        "Mozilla/5.0 (Windows NT 5.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 "
        "Safari/537.36",
        # Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:53.0) Gecko/20100101 Firefox/53.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 "
        "Safari/603.3.8",
        # Safari
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/603.2.4 (KHTML, like Gecko) Version/10.1.1 "
        "Safari/603.2.4",
        # Edge
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 "
        "Safari/537.3 Edge/16.16299",
        # Internet Explorer
        "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; AS; rv:11.0) like Gecko",
        # Opera
        "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:46.0) Gecko/20100101 Firefox/46.0 OPR/36.0.2131.65"
    ]

    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "TE": "Trailers",
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # This will raise an HTTPError if the response was an HTTP error.
        return BeautifulSoup(response.text, 'html.parser')
    except RequestException as e:
        print(f"Unable to get url {url} due to {e}. Skipping...")
        return None


def process_imdb_pages(start_url: str, max_pages: int, db_manager: DBManager, image_processor: ImageProcessor):
    current_page_url = start_url
    pages_processed = 0

    with open('processed_pages.txt', 'a') as f:  # Open the file for appending
        while current_page_url and pages_processed < max_pages:
            soup = scrape_html(current_page_url)  # Get the current page's HTML
            if soup is None:
                continue

            # Calculate the range of actors for the current page
            start_range = pages_processed * 50 + 1
            end_range = start_range + 49

            # Log the range and URL to the file
            f.write(f"{pages_processed + 1}. {start_range}-{end_range}: {current_page_url}\n")

            process_imdb_list(soup, db_manager, image_processor)  # Process the current page

            next_page_button = soup.find('a', {'class': 'next-page'})
            if next_page_button:
                next_page_relative_url = next_page_button['href']
                current_page_url = urllib.parse.urljoin(start_url, next_page_relative_url)
            else:
                current_page_url = None  # No more pages

            pages_processed += 1  # Increase the number of processed pages


def process_imdb_list(soup: BeautifulSoup, db_manager: DBManager, image_processor: ImageProcessor):
    celebs_list = soup.findAll('h3', {'class': 'lister-item-header'})
    # i = 1
    for celeb in celebs_list:
        start1 = time.time()

        process_celeb(celeb, db_manager, image_processor)
        # if i==1:
        #     images_list = api_get_celeb_additional_images('nm0000607')
        #     db_manager.insert_additional_images_urls('nm0000607', images_list)
        #     i += 1
        end1 = time.time()
        print(f'single celeb scrapping took: {end1 - start1}')


def process_celeb(celeb, db_manager, image_processor=None, url_to_rescrape=None):
    try:
        if url_to_rescrape:
            url_to_page = url_to_rescrape
        else:
            link_tag = celeb.find('a')  # Find the 'a' tag
            url_to_page = IMDB_DOMAIN + link_tag['href']  # Get the 'href' attribute
    except Exception as e:
        with open('failed_celebs.txt', 'a') as f:
            f.write(f"Failed to find 'a' tag or 'href' attribute for celeb {celeb}. Error: {str(e)}\n")
        return

    try:
        celeb_page_soup = scrape_html(url_to_page)
        if celeb_page_soup is None:
            raise ValueError("Returned soup is None")
    except Exception as e:
        with open('failed_celebs.txt', 'a') as f:
            f.write(f"Failed to scrape {url_to_page}. Error: {str(e)}\n")
        return

    # Attempt to scrape info
    try:
        celeb_info = scrape_celebrity_info(celeb_page_soup, url_to_page)
        db_manager.insert_celeb(*celeb_info)
        celeb_id, celeb_name = celeb_info[0], celeb_info[1]
    except Exception as e:
        with open('failed_celebs.txt', 'a') as f:
            f.write(f"Failed to scrape or insert celeb info for {url_to_page}. Error: {str(e)}\n")
        return

    # Attempt to get the main photo
    try:
        main_photo_url = get_main_photo_url(celeb_page_soup)
        if not main_photo_url:
            print(f"No main image found for {celeb_id}, no need to scrape further.")
        else:
            db_manager.update_celeb_main_image_url(celeb_id, main_photo_url)
    except Exception as e:
        with open('failed_celebs.txt', 'a') as f:
            f.write(f"Failed to get main image for {celeb_id}. Error: {str(e)}\n")
        return  # If the main photo fails, we will not want to proceed further

    # Attempt to get the additional photos
    try:
        additional_photos_urls = get_additional_photos(celeb_page_soup, celeb_id)
        if len(additional_photos_urls) >= MIN_ADDITIONAL_PHOTOS:
            # db_manager.update_additional_images_urls(celeb_id, additional_photos_urls)
            db_manager.insert_additional_images_urls(celeb_id, additional_photos_urls)
            # image_processor.process_celebrity_images(celeb_id, main_photo_url, additional_photos_urls, db_manager)

    except Exception as e:
        with open('failed_celebs.txt', 'a') as f:
            f.write(f"Failed to process additional images for {celeb_id} or not enough photos. Error: {str(e)}\n")

    print_celeb_info(celeb_info)


def scrape_celebrity_info(soup: BeautifulSoup, url: str) -> Tuple[
        Optional[str], Optional[str], Optional[datetime], Optional[datetime], Optional[int], str]:
    # Get name
    name_tag = soup.find('h1', {'data-testid': 'hero__pageTitle'})
    name = name_tag.next.string.strip() if name_tag else None

    dob, _ = get_date_and_age(soup, 'birth-and-death-birthdate')
    dod, age = get_date_and_age(soup, 'birth-and-death-deathdate', died=True)
    if dob and not age:
        age = calculate_age(dob)

    # Get the unique IMDb ID
    match = re.search(r"nm\d{7}", url)
    imdb_id = match.group() if match else None

    return imdb_id, name, dob, dod, age, url


def get_main_photo1(soup: BeautifulSoup) -> Optional[str]:
    # Find the image tag of the actor's main image
    img_section = soup.find('section', {'class': 'ipc-page-section'})
    img_tag = img_section.find('img', {'class': 'ipc-image'}) if img_section else None
    if img_tag:
        return img_tag['src']
    else:
        return None


def get_main_photo2(soup: BeautifulSoup, celeb_name: str) -> Optional[str]:
    # Find the image tag of the actor's main image
    img_section = soup.find('section', {'class': 'ipc-page-section'})
    a_tag = img_section.find('a', {'class': 'ipc-lockup-overlay ipc-focusable'}) if img_section else None
    url_to_img_page = IMDB_DOMAIN + a_tag['href'] if a_tag else None  # Get the 'href' attribute
    img_page_soup = scrape_html(url_to_img_page)
    # img_tag = img_page_soup.find('img', {'alt': celeb_name})
    img_tag = img_page_soup.find('img', alt=lambda x: x and celeb_name in x)

    if img_tag:
        return img_tag['src']
    else:
        return None


def get_main_photo_url(soup: BeautifulSoup) -> Optional[str]:
    # Find the image tag of the actor's main image
    img_section = soup.find('section', {'class': 'ipc-page-section'})
    a_tag = img_section.find('a', {'class': 'ipc-lockup-overlay ipc-focusable'}) if img_section else None
    url_to_img_page = IMDB_DOMAIN + a_tag['href'] if a_tag else None  # Get the 'href' attribute

    return get_image_from_page(url_to_img_page)


def get_additional_photos(soup: BeautifulSoup, celeb_id: str) -> List[str]:

    additional_photos_page_url = IMDB_DOMAIN + f"/name/{celeb_id}/mediaindex/?ref_=nm_mv_sm"

    additional_soup = scrape_html(additional_photos_page_url)
    if additional_soup is None:
        return []
    else:
        div = additional_soup.find('div', {'class': 'media_index_thumb_list'})
        if div is not None:
            images_links = div.findAll('a')
        else:
            print(f'Could not find additional images page for {celeb_id}')
            return []

    # Extract URLs from the tags
    large_image_page_urls = [IMDB_DOMAIN + link['href'] for link in images_links]

    # # Extract photos URLs from each page
    # large_image_urls = [get_image_from_page(url) for url in large_image_page_urls]

    # Concurrently extract photo URLs from each page using ThreadPool
    with ThreadPool() as pool:
        large_image_urls = pool.map(get_image_from_page, large_image_page_urls)

    return large_image_urls


def get_image_from_page(url: str) -> Optional[str]:
    try:
        # Scrape the page of the individual photo
        soup = scrape_html(url)

        # Find the tag containing the URL of the full-size image
        # image_tag = soup.find('img', {'data-imag-id': 'rm3133285889-curr'})
        image_tag = soup.find(matches_format)

        # Extract the URL from the tag
        image_url = image_tag['src'] if image_tag else None

        return image_url
    except Exception as e:
        print(f"Error getting image from page {url}: {e}")
        return None


def matches_format(tag):
    # The regular expression we'll use to match the data-image-id format
    # image_id_pattern = re.compile(r"rm\d{10}-curr")
    image_id_pattern = re.compile(r"rm\d+-curr")

    # Try to get the data-image-id attribute
    data_image_id = tag.get('data-image-id')

    # If the data-image-id attribute exists and matches our pattern, return True
    if data_image_id and image_id_pattern.match(data_image_id):
        return True

    # Otherwise, return False
    return False


def get_date_and_age(soup: BeautifulSoup, div_id: str, died=False) -> Tuple[Optional[datetime], Optional[int]]:
    """
    Helper function to extract date and age (if available) from a specific div in the BeautifulSoup object.

    Parameters: soup (bs4.BeautifulSoup): The BeautifulSoup object for the webpage div_id (str): The 'data-testid'
    attribute of the div to find died (bool): A flag indicating whether the div being processed is for death date.
    Default is False (i.e., birthdate).

    Returns:
    date (datetime.date or None): The extracted date as date object. Returns None if date cannot be extracted.
    age (str or None): The extracted age if 'died' is True and age is available, otherwise returns None.
    """

    div = soup.find('div', {'data-testid': div_id})
    date, age = None, None
    if div:
        span = div.findAll('span')
        if span and len(span) > 1:
            if died:
                info_list = span[1].text.rsplit('(', 1)  # should return: ["Month Day, Year", "Age)"]
                date_str = info_list[0]
                age = int(info_list[1][:-1]) if len(info_list) > 1 else None
            else:
                date_str = span[1].string.strip() if span[1] else None

            date = convert_to_date_type(date_str)

    return date, age


def convert_to_date_type(date: str) -> Optional[datetime.date]:
    try:
        date_type = datetime.strptime(date, "%B %d, %Y").date()
        return date_type
    except ValueError as e:
        print("Error converting date:", e)
        return None


def calculate_age(date_of_birth: datetime) -> int:
    current_year = datetime.now().year
    age = current_year - date_of_birth.year
    return age


def print_celeb_info(celeb_info):
    imdb_id, name, dob, dod, age, url = celeb_info
    print("###########")
    print("id:", imdb_id)
    print("name:", name)
    print("dob:", dob)
    print("dod:", dod)
    print("age:", age)
    print("url:", url)


def rescrape_failed_pages(db_manager):
    filename = 'failed_celebs.txt'

    # Step 1: Copy original file contents to a temporary file
    with open(filename, 'r') as original_file:
        original_file_lines = original_file.readlines()
        original_file_len = len(original_file_lines)
        failed_urls_list = [line.split(" ")[3][:-1] for line in original_file_lines if "Failed to scrape" in line]
        num_pages_to_scrape = len(failed_urls_list)

    with open(filename, 'a+') as original_file:
        print("Re-scraping...")

        original_file.write("##### Re-scraping section #####")

        for url in failed_urls_list:
            process_celeb(None, db_manager, url_to_rescrape=url)

        original_file.seek(0)  # Move position back to the beginning
        new_failed_urls_list = [line.split(" ")[3][:-1] for line in original_file.readlines() if "Failed to scrape" in line]
        new_failed_urls_list_len = len(new_failed_urls_list)
        num_rescraped_pages = new_failed_urls_list_len - num_pages_to_scrape
        print(f"Successfully re-scraped {new_failed_urls_list_len - num_rescraped_pages}.")


def rescrape_failed_pages1(db_manager):
    # Keep track of lines to retain (those we couldn't scrape successfully)
    lines_to_retain = []
    filename = 'failed_celebs.txt'
    with open(filename, 'r') as file:
        lines = file.readlines()

        for line in lines:
            if "Failed to scrape" in line:
                # Extract the URL from the line
                celeb_url = line.split(" ")[3][:-1]
                # print(url)
                # soup = scrape_html(celeb_url)
                process_celeb(None, db_manager, celeb_url)

    # Rewrite the file with only the lines to retain
    # with open(filename, 'w') as file:
    #     file.writelines(lines_to_retain)


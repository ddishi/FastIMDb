import os
import numpy as np
from PIL import Image

from utils import save_main_image_to_s3, save_all_main_images, create_presigned_url, \
    create_processed_celebs_names_file
from db_manager import DBManager
from image_processor import ImageProcessor, download_image
from scrape_manager import process_imdb_list, process_imdb_pages, get_main_photo_url, get_additional_photos, \
    scrape_html, scrape_celebrity_info, rescrape_failed_pages


def load_image_as_np_array(image_path):
    # Load the image using PIL
    image = Image.open(image_path)

    # Convert the image to RGB format
    image = image.convert("RGB")

    # Convert the image to a NumPy array
    image_array = np.array(image)

    return image_array


def handle_image_upload(image_path, image_processor: ImageProcessor, db_manager: DBManager, from_server=True):
    if from_server:
        np_img = load_image_as_np_array(image_path)
    else:
        np_img = download_image(image_path)
    # matched_celebs_id = image_processor.find_nearest(np_img, 8)
    matched_celebs_id = image_processor.recognize_celeb_from_image(np_img, db_manager)
    if len(matched_celebs_id) > 0:
        recognized_celebs = []
        for i, celeb_id in enumerate(matched_celebs_id, start=1):
            if celeb_id:
                # Retrieve the celebrity's info from the database
                celeb_info = db_manager.get_celeb_info(celeb_id)
                s3_url = celeb_info[-1]
                info_list = [*celeb_info]
                info_list[-1] = create_presigned_url(image_processor.bucket_name, s3_url)
                recognized_celebs.append(info_list)
            else:
                recognized_celebs.append(None)
                print(f"No matching celebrity found for face {i}.")
                print(recognized_celebs)
        return recognized_celebs
    else:
        print("No faces detected in the uploaded image")
        return None


if __name__ == "__main__":

    # Instances for testing

    db_manager = DBManager(
        host="celebs-database-1.c4duzx241qat.eu-north-1.rds.amazonaws.com",
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database="celebs_database",
        table="Celebs2"
    )
    image_processor = ImageProcessor(bucket_name='celebs-images-bucket-2')




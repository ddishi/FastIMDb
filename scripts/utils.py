import os
from io import BytesIO
import re
import boto3
import numpy as np
from PIL import Image
from botocore.config import Config
import requests


MAX_IMAGE_SIZE = 500


def download_image(url, resize=False):
    response = requests.get(url)
    img = Image.open(BytesIO(response.content))
    if img.mode != "RGB":  # if the image is not RGB or grayscale

        img = img.convert("RGB")  # convert it to RGB

    if resize:
        # Resize the image
        img.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE), Image.ANTIALIAS)

    img_array = np.array(img)
    return img_array


def create_presigned_url(bucket_name, image_s3_url, expiration=3600):
    s3 = boto3.client('s3',
                      aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                      aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                      config=Config(signature_version='s3v4'),
                      region_name='eu-north-1',
                      )
    key = image_s3_url.split(".s3.amazonaws.com/")[-1]
    url = s3.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': bucket_name,
            'Key': key,
        }
    )
    return url


def save_all_main_images(db_manager, s3, bucket_name):
    """Save all main images to S3."""
    all_imdb_ids = db_manager.get_all_imdb_ids()

    for i, imdb_id in enumerate(all_imdb_ids):
        if i % 50 == 0:
            print(f"{i} images saved to storage.")
        celeb_info = db_manager.get_celeb_info(imdb_id)
        if celeb_info and celeb_info[6]:
            celeb_name, main_image_url = celeb_info[1], celeb_info[6]  # Extracting celeb_name and main_image_url
            save_main_image_to_s3(main_image_url, imdb_id, celeb_name, s3, bucket_name, db_manager)
        else:
            print(f"No main image found for celeb id {imdb_id}")


def sanitize_name(name):
    """Sanitize the name to be used in S3 path. Remove or replace non-alphanumeric characters."""
    sanitized_name = re.sub(r'[^a-zA-Z0-9]', '_', name)  # Replace non-alphanumeric characters with underscores
    return sanitized_name


def save_main_image_to_s3(main_image_url, celeb_id, celeb_name, s3, bucket_name, db_manager):
    """
    Download the main image and save it to S3.

    Parameters:
    - main_image_url: URL of the main image.
    - celeb_id: IMDb ID of the celebrity.
    - celeb_name: Name of the celebrity.
    - s3: S3 client.
    - bucket_name: Name of the S3 bucket.
    - db_manager: DBManager instance for updating the DB.
    """
    try:
        # Download the image as a numpy array
        main_image_np = download_image(main_image_url)

        # Convert the numpy array back to a PIL Image
        image = Image.fromarray(main_image_np)

        # Prepare the image for saving to S3 - convert it to bytes
        buffer = BytesIO()
        image.save(buffer, format="JPEG")
        buffer.seek(0)

        # Sanitize the celebrity name for S3 path
        sanitized_name = sanitize_name(celeb_name)

        # Define the path for the main image in S3
        s3_path = f"{celeb_id}_{sanitized_name}/main_image.jpg"

        # Save the image to S3
        s3.upload_fileobj(buffer, bucket_name, s3_path)

        # Optionally, update the database with the S3 URL of the main image (if needed later)
        main_image_s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_path}"
        db_manager.update_celeb_main_image_url(celeb_id, main_image_s3_url, to_s3=True)

    except Exception as e:
        print(f"Error saving main image for {celeb_id} to S3: {e}")


def string_to_encoding_main_image(encoding_str):
    # Remove brackets, newline characters, and multiple spaces, then split by spaces
    numbers_str = re.sub(r'[\[\]\n]', '', encoding_str).split()
    encoding = [float(num) for num in numbers_str]
    return encoding


def string_to_encoding_additional_image(encoding_str):
    # For additional images, split by commas
    encoding = [float(value) for value in encoding_str.split(',')]
    return encoding


def create_processed_celebs_names_file(db_manager):
    with open('saved_celebs.txt', 'r') as f:
        ids_list = f.readlines()

    with open('../data/saved_celebs_names.txt', 'a', encoding='utf-8') as f:
        for current_id in ids_list:
            current_id = current_id[:-1]  # Removing the '\n'
            celeb_data = db_manager.get_celeb_info(current_id)
            name = celeb_data[1]
            page_url = celeb_data[5]
            f.write(f"{current_id:<9} - {name:<25} - {page_url:<35}\n")

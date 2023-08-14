import pickle
from collections import Counter
from functools import partial
from multiprocessing import Pool
import boto3
import face_recognition
import numpy as np
from annoy import AnnoyIndex
from utils import create_presigned_url, download_image

MAX_IMAGES_TO_ADD = 20


class ImageProcessor:
    def __init__(self, bucket_name):
        self.s3 = boto3.client('s3')
        self.bucket_name = bucket_name
        # Fields for the Annoy index and the mapping dictionary
        self._annoy_index = None
        self._index_to_imdb = None

    ###### Main image processing related functions ######

    def process_main_images_and_save_encodings(self, db_manager):
        """
        Process all main images, compute their encodings, and save to the database.
        Parameters:
        - db_manager: Instance of DBManager to interact with the database.
        """
        # Step 1: Fetch main image S3 URLs for all celebrities
        all_celebs_ids = db_manager.get_all_imdb_ids()

        for i, imdb_id in enumerate(all_celebs_ids):
            if i % 50 == 0:
                print(f"{i} images' encodings saved to db.")

            celeb_info = db_manager.get_celeb_info(imdb_id)
            if not celeb_info or not celeb_info[7]:
                print(f"No main image s3-url found for celeb id {imdb_id}")
                continue
            main_image_s3_url = celeb_info[7]  # Extracting the main image S3 URL

            # Generate pre-signed URL
            presigned_url = create_presigned_url(self.bucket_name, main_image_s3_url)

            # Step 2: Download the main image
            image_np = download_image(presigned_url)

            # Step 3: Compute the face encoding
            main_image_encoding = face_recognition.face_encodings(image_np)

            # Step 4: Save the encoding to the database
            if main_image_encoding is not None:
                num_faces = len(main_image_encoding)
                if num_faces == 0:
                    print(f"No face detected in the main image of celeb {imdb_id}.")
                elif num_faces > 1:
                    main_image_encoding = []
                    print(f"More than 1 faces detected in the main image of celeb {imdb_id}, can't identify the "
                          f"correct face.")

                db_manager.insert_face_encoding(imdb_id, main_image_encoding, "main")
            else:
                print(f"Failed to compute encoding for main image of celeb {imdb_id}")

    ###### Additional images processing related functions ######

    def process_all_celebrity_additional_images(self, db_manager, process_remaining_ids=True):
        """
        Process additional images for all celebrities.
        Parameters:
        - db_manager: Instance of DBManager to interact with the database.
        """
        all_celebs_ids = db_manager.get_all_imdb_ids()
        processed_ids = db_manager.get_processed_celebs_ids()

        if process_remaining_ids:
            start_idx = all_celebs_ids.index(processed_ids[-1]) + 1
            ids_to_process = all_celebs_ids[start_idx:]
            already_processed_count = start_idx
        else:
            ids_to_process = all_celebs_ids
            already_processed_count = 0

        for i, imdb_id in enumerate(ids_to_process):
            print("##########################################################")
            print(
                f"Processing additional images for celebrity {i + 1 + already_processed_count}/{len(all_celebs_ids)}: {imdb_id}")
            self.process_celebrity_additional_images(db_manager, imdb_id)

    def process_celebrity_additional_images(self, db_manager, imdb_id):
        # 1. Fetch main image encoding
        main_encoding_list = db_manager.get_main_image_encodings(imdb_id)
        if not main_encoding_list:
            print(f"No encoding found for main image of celeb {imdb_id}.")
            return

        # 1.1. Convert the encoding to numpy array
        main_encoding_np = np.array(main_encoding_list)

        # 2. Retrieve additional images URLs
        additional_images_data = db_manager.get_additional_images_urls(imdb_id)
        additional_images_urls = list(additional_images_data.values())

        # Early check: If we have less than the desired minimum images, skip processing
        if len(additional_images_urls) < 10:
            print(f"Not enough additional images for celeb {imdb_id}. Skipping.")
            return

        # 3. Process additional images in batches
        BATCH_SIZE = 10
        matched_encodings = []

        for i in range(0, len(additional_images_urls), BATCH_SIZE):
            batch_urls = additional_images_urls[i:i + BATCH_SIZE]
            with Pool() as pool:
                batch_results = pool.map(partial(self.process_additional_image, main_encoding=main_encoding_np),
                                         batch_urls)

            # Filter out None results (no match)
            matched_encodings.extend([(url, enc) for (url, enc) in batch_results if enc is not None])

            # Fast reject check
            potential_matches = len(matched_encodings) + len(additional_images_urls) - (i + BATCH_SIZE)
            if potential_matches < 10:
                print(f"Can't achieve minimum matched images for celeb {imdb_id}. Skipping.")
                return

            # Check for early stopping
            if len(matched_encodings) >= 20:
                break

        # 4. Save encodings to the database, but only up to the desired number
        print(f"Adding {len(matched_encodings)} images to DB for celeb id = {imdb_id}.")
        with open('saved_celebs.txt', 'a') as f:
            f.write(f"{imdb_id}\n")
        self.save_encodings_to_db(db_manager, imdb_id, matched_encodings, additional_images_data)

    @staticmethod
    def process_additional_image(image_url, main_encoding):
        image_np = download_image(image_url)
        image_encodings = face_recognition.face_encodings(image_np)

        best_match_encoding = None

        if len(image_encodings) < 1:
            print(f"No faces found in image {image_url}.")
        else:
            distances = face_recognition.face_distance(image_encodings, main_encoding)
            min_dist_idx = np.argmin(distances)
            min_dist = distances[min_dist_idx]
            # Check if the minimum distance is within the tolerance level
            if min_dist <= 0.6:  # You can adjust the tolerance as needed
                best_match_encoding = image_encodings[min_dist_idx]
            else:
                print(f"No matches were found in {image_url}.")

        return image_url, best_match_encoding

    def save_encodings_to_db(self, db_manager, imdb_id, matched_encodings, additional_images_data):
        # Invert the dictionary for easy lookup
        url_to_id_map = {v: k for k, v in additional_images_data.items()}

        for image_url, encoding in matched_encodings:
            if encoding is not None:
                image_id = url_to_id_map.get(image_url)  # Fetching image_id using image_url
                if image_id:
                    db_manager.insert_face_encoding(imdb_id, encoding, image_type="additional", image_id=image_id)

    ###### Annoy and index map related functions ######
    def build_annoy_index_and_mapping(self, encodings_dict, vector_length=128, trees=10):
        # Initialize Annoy index with the given vector length and Euclidean distance metric
        annoy_index = AnnoyIndex(vector_length, 'euclidean')

        # Initialize a mapping dictionary to keep track of the index to IMDb ID mapping
        index_to_imdb = {}

        # Current index in Annoy
        current_index = 0

        # Loop over the encodings dictionary and add each encoding to the Annoy index
        for imdb_id, encodings in encodings_dict.items():
            for encoding in encodings:
                # Add encoding to Annoy index
                annoy_index.add_item(current_index, encoding)

                # Record the mapping between the current index and the corresponding IMDb ID
                index_to_imdb[current_index] = imdb_id

                # Increment the current index
                current_index += 1

        # Build the Annoy index with the specified number of trees
        annoy_index.build(trees)

        # Update instance fields
        self._annoy_index, self._index_to_imdb = annoy_index, index_to_imdb

    def save_annoy_index_and_mapping(self, index_path, mapping_path):
        if not self._annoy_index or not self._index_to_imdb:
            raise ValueError("Annoy index and mapping have not been built yet.")

        # Save the Annoy index to the specified path
        self._annoy_index.save(index_path)

        # Save the mapping dictionary using pickle
        with open(mapping_path, 'wb') as f:
            pickle.dump(self._index_to_imdb, f)

    def load_annoy_index_and_mapping(self, vector_length, index_path, mapping_path):
        # Load the Annoy index and mapping dictionary and update the instance fields
        self._annoy_index = AnnoyIndex(vector_length, 'euclidean')
        self._annoy_index.load(index_path)

        # Load the mapping dictionary using pickle
        with open(mapping_path, 'rb') as f:
            self._index_to_imdb = pickle.load(f)

    # Provide methods to access the Annoy index and mapping dictionary
    @property
    def annoy_index(self):
        return self._annoy_index

    @property
    def index_to_imdb(self):
        return self._index_to_imdb

    def recognize_celeb_from_image(self, image_np, db_manager):
        """Recognize the celebrity from the given image using the pre-built Annoy index."""
        # Ensure that Annoy index and mapping are available
        if not self.annoy_index or not self.index_to_imdb:
            raise ValueError("Annoy index or mapping is missing. Please load or build them first.")

        # Extract face encoding from the new image
        # image_np = download_image(image_url)
        image_encodings = face_recognition.face_encodings(image_np)
        num_faces = len(image_encodings)
        if num_faces == 0:
            print(f"No faces recognized in the image. Please try again with another image.")
            return []

        results = []

        # Loop through each detected face encoding
        for encoding in image_encodings:
            nearest_indexes = self.annoy_index.get_nns_by_vector(encoding, 15)  # Retrieve the 15 closest matches
            nearest_imdb_ids = [self.index_to_imdb[idx] for idx in nearest_indexes]
            # print(nearest_imdb_ids)

            # Use Counter to determine the most common IMDb ID
            most_common_imdb_id, appearances = Counter(nearest_imdb_ids).most_common(1)[0]
            results.append(most_common_imdb_id)

        return results

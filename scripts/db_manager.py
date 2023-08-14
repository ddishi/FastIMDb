import mysql.connector
from utils import string_to_encoding_main_image, string_to_encoding_additional_image


class DBManager:

    def __init__(self, host, user, password, database, table):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.conn = None
        self.cursor = None
        self.current_table = table

    def connect(self):
        self.conn = mysql.connector.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            database=self.database,
        )
        self.cursor = self.conn.cursor()

    def close(self):
        self.conn.close()
        self.conn = None
        self.cursor = None

    def create_celeb_table(self):
        self.connect()
        print("connected")
        self.cursor.execute(f"CREATE TABLE IF NOT EXISTS {self.current_table} ("
                            "imdb_id VARCHAR(255) PRIMARY KEY, "
                            "name VARCHAR(255), "
                            "dob DATE, "
                            "dod DATE, "
                            "age INT, "
                            "page_url VARCHAR(255), "
                            "main_image_url VARCHAR(255), "
                            "main_image_s3_url VARCHAR(255), "
                            "additional_photos_urls TEXT)"
                            )
        self.conn.commit()
        self.close()

    def insert_celeb(self, celeb_id, name, dob, dod, age, page_url):
        try:
            self.connect()
            cursor = self.conn.cursor()
            insert_query = f"""INSERT INTO {self.current_table} (imdb_id, name, dob, dod, age, page_url) 
                              VALUES (%s, %s, %s, %s, %s, %s)
                              ON DUPLICATE KEY UPDATE name = %s, dob = %s, dod = %s, age = %s, page_url = %s"""
            cursor.execute(insert_query, (celeb_id, name, dob, dod, age, page_url, name, dob, dod, age, page_url))
            self.conn.commit()
        except Exception as e:
            print(f"An error occurred while inserting data into the database: {e}")
        finally:
            self.close()

    def update_celeb_main_image_url(self, celeb_id, image_url, to_s3=False):
        try:
            self.connect()
            cursor = self.conn.cursor()
            if to_s3:
                column = "main_image_s3_url"
            else:
                column = "main_image_url"

            update_query = f"""UPDATE {self.current_table} SET {column} = %s WHERE imdb_id = %s"""
            cursor.execute(update_query, (image_url, celeb_id))
            self.conn.commit()
        except Exception as e:
            print(f"An error occurred while inserting main image url into the database: {e}")
        finally:
            self.close()

    def update_additional_images_urls(self, celeb_id, urls_list):
        try:
            self.connect()
            cursor = self.conn.cursor()
            column = "additional_images_urls"
            urls_string = ','.join(urls_list)
            update_query = f"""UPDATE {self.current_table} SET {column} = %s WHERE imdb_id = %s"""
            cursor.execute(update_query, (urls_string, celeb_id))
            self.conn.commit()
        except Exception as e:
            print(f"An error occurred while inserting additional images urls into the database: {e}")
        finally:
            self.close()

    def get_celeb_info(self, imdb_id: str):
        """
        :param imdb_id:
        :return: Tuple: (imdb_id, name, dob, dod, age, page_url, main_image_url, main_image_s3_url)
        """
        self.connect()
        self.cursor.execute(f"SELECT * FROM {self.current_table} WHERE imdb_id = %s", (imdb_id,))
        result = self.cursor.fetchone()
        self.close()
        return result

    def get_all_imdb_ids(self):
        """Fetch all IMDb IDs from the database."""
        self.connect()
        self.cursor.execute(f"SELECT imdb_id FROM {self.current_table}")
        results = self.cursor.fetchall()
        self.close()
        return [result[0] for result in results]

    ##### Celeb_Images related functions #####

    def create_images_table(self):
        self.connect()
        self.cursor.execute("CREATE TABLE IF NOT EXISTS Images ("
                            "image_id INT AUTO_INCREMENT PRIMARY KEY, "
                            "imdb_id VARCHAR(255), "
                            "image_url VARCHAR(255), "
                            "FOREIGN KEY(imdb_id) REFERENCES Celebs(imdb_id))")
        self.conn.commit()
        self.close()

    def insert_additional_images_urls(self, celeb_id, images_list):
        self.connect()
        for image in images_list:
            sql_query = ("INSERT INTO Celebs_Images (imdb_id, image_url)"
                         "VALUES (%s, %s)")
            # image is the URL, so we pass celeb_id and image to the execute function
            self.cursor.execute(sql_query, (celeb_id, image))
        self.conn.commit()
        self.close()

    def get_additional_images_urls(self, imdb_id) -> dict:
        """Fetch the additional image URLs and their respective IDs for a given celebrity based on IMDb ID."""
        self.connect()
        self.cursor.execute(f"SELECT image_id, image_url FROM Celebs_Images WHERE imdb_id = %s", (imdb_id,))
        results = self.cursor.fetchall()
        self.close()
        return {result[0]: result[1] for result in results}

    ##### Face_Encoding related functions #####

    def create_face_encodings_table(self):
        self.connect()
        self.cursor.execute(
            "CREATE TABLE Face_Encodings ("
            "    encoding_id INT AUTO_INCREMENT PRIMARY KEY, "
            "    imdb_id VARCHAR(255) NOT NULL, "
            "    encoding TEXT NOT NULL, "
            "    image_type VARCHAR(50) NOT NULL, "
            "    image_number INT DEFAULT NULL, "
            "    image_id INT, "
            "    FOREIGN KEY (imdb_id) REFERENCES Celebs2(imdb_id),"
            "    FOREIGN KEY (image_id) REFERENCES Celebs_images(image_id)"
            ")"
        )
        self.conn.commit()
        self.close()

    def insert_face_encoding(self, imdb_id, encoding, image_type, image_number=0, image_id=None):
        """
        Insert a new face encoding into the FaceEncodings table.
        For inserting main image ignore the image_number and image_id. i.e. use defaults.
        """
        self.connect()

        # Convert the numpy array encoding to a serialized format (string)
        encoding_str = ','.join(map(str, encoding))

        query = """
        INSERT INTO Face_Encodings (imdb_id, encoding, image_type, image_number, image_id)
        VALUES (%s, %s, %s, %s, %s)
        """
        self.cursor.execute(query, (imdb_id, encoding_str, image_type, image_number, image_id))
        self.conn.commit()
        self.close()

    def get_face_encodings(self, imdb_id, image_type):
        """
        Fetch the face encoding for a specified image type of a given celebrity.

        :param imdb_id: IMDb ID of the celebrity.
        :param image_type: Type of image ('main' or 'additional').
        :return: List of face encoding values for the specified image type or None if not found.
        """
        self.connect()
        query = "SELECT encoding FROM Face_Encodings WHERE imdb_id = %s AND image_type = %s"
        self.cursor.execute(query, (imdb_id, image_type))
        result = self.cursor.fetchone()
        self.close()

        if result:
            # Clean up the encoding string
            encoding_str = result[0].replace('[', '').replace(']', '').replace('\n', '').replace('  ', ' ')
            encoding_list = [float(value) for value in encoding_str.split()]
            return encoding_list
        return None

    def get_processed_celebs_ids(self):
        # Query to find imdb_id's that appear more than once (indicating additional images)
        query = """
        SELECT imdb_id
        FROM Face_Encodings
        GROUP BY imdb_id
        HAVING COUNT(imdb_id) > 1
        """
        self.connect()
        self.cursor.execute(query)
        imdb_ids_with_additional_images = [result[0] for result in self.cursor.fetchall()]
        return imdb_ids_with_additional_images

    def get_main_image_encodings(self, imdb_id):
        self.connect()
        query = "SELECT encoding FROM Face_Encodings WHERE imdb_id = %s AND image_type = 'main'"
        self.cursor.execute(query, (imdb_id,))
        result = self.cursor.fetchone()
        self.close()

        if result:
            return string_to_encoding_main_image(result[0])
        return None

    def get_additional_image_encodings(self, imdb_id):
        self.connect()
        query = "SELECT encoding FROM Face_Encodings WHERE imdb_id = %s AND image_type = 'additional'"
        self.cursor.execute(query, (imdb_id,))
        results = self.cursor.fetchall()
        self.close()

        if results:
            return [string_to_encoding_additional_image(result[0]) for result in results]
        return []

    def get_processed_celebs_all_encodings(self):
        imdb_ids_with_additional_images = self.get_processed_celebs_ids()

        imdb_id_to_encodings = {}
        for imdb_id in imdb_ids_with_additional_images:
            # Fetch main image encoding
            main_image_encoding = self.get_main_image_encodings(imdb_id)

            # Fetch additional image encodings
            encodings = self.get_additional_image_encodings(imdb_id)

            # Add the main image encoding to the beginning of the encodings list
            if main_image_encoding:
                encodings.insert(0, main_image_encoding)

            # Add the combined list of encodings (main + additional) to the dictionary
            if encodings:
                imdb_id_to_encodings[imdb_id] = encodings

        return imdb_id_to_encodings


    def get_image_count(self, celeb_id):
        # Query to find imdb_id's that appear more than once (indicating additional images)
        query = """
        SELECT COUNT(imdb_id)
        FROM Face_Encodings
        WHERE imdb_id = %s
        """

        self.connect()
        self.cursor.execute(query, (celeb_id,))
        count = self.cursor.fetchone()[0]
        return count

















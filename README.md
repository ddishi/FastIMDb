# Fast IMDb
### Final Project - 'From Idea to Reality Using AI' Course by David Kalmanson at Reichman University

-----
## Overview
Welcome to the Celeb Recognition Web App!
With our application, you can upload images or even use a webcam to recognize celebrities. Built using state-of-the-art techniques, we ensure efficient and fast recognition.
---
> ### **Notice** the available celebs for recognition - [full list](data/saved_celebs_names.txt) 
---

## Installation & Usage

- Make sure you have python installed and install the relevant imported packages from the code if needed.
- Run `server` file to start the server.
- Go to http://127.0.0.1:8000/.
- **If you encounter any troubles feel free to contact me.**

## Check out the [demo](images4README/DemoVid.mp4)!
- The tested images were took by an iphone, capturing a computer screen:

  1. [Aaron_paul.jpg](images4README/Aaron_paul.jpg)
  2. [Adam_Sandler_Jennifer_Aniston.jpg](images4README/Adam_Sandler_Jennifer_Aniston.jpg)
  3. [Derock_Ryan.jpg](images4README/Derock_Ryan.jpg)
  4. [Jason_Momoa_khal.jpg](images4README/Jason_Momoa_khal.jpg)
- Then, I captured an image using the webcam.

---

## Features
- **DataBase**: All the celebrity data was meticulously scraped from IMDb.

- **AWS RDS Database Integration**: Our app uses AWS RDS to store data across multiple tables:
  - **[Celeb2](images4README/Celeb2Table.png)**: Contains detailed information about celebrities.
  - **[Celeb_Images](images4README/Celeb_ImagesTable.png)**: Houses URLs for additional celebrity images.
  - **[Face_Encodings](images4README/Face_EncodingsTable.png)**: Contains face encodings for all processed images.


- **AWS S3 Storage**: Main images of celebrities are stored in AWS S3. We've also implemented a mechanism to generate special URLs to present these images directly from the database.


- **Performance**: For optimal performance in image similarity search, we employ the Annoy library.


- **Multiple Images**: Each celebrity is backed by 10 - 30 images in our database to ensure accurate recognition.


- **Webcam Support**: Users can utilize their webcams for real-time celebrity recognition. However, due to the downgraded resolution of webcam images, the accuracy might be slightly lower than using uploaded images.


- **Analytics**: Using _Google Analytics_ for detailed statistics and analytics about website traffic and conversions.



---
## Upcoming Features
- [ ] **AWS EC2**: Integration with EC2 will be available in the upcoming version. Stay tuned for the website url!


- [ ] **More Celebrities**: Our database is ever-growing! Stay tuned for the addition of more celebrities in the next update.
---


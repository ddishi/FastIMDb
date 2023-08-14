import requests


def actors_endpoint_api_call(celeb_id, endpoint):
    url_endpoint = f"https://online-movie-database.p.rapidapi.com/actors/{endpoint}"

    querystring = {"nconst": f"{celeb_id}"}

    api_headers = {
        "X-RapidAPI-Key": "dfeec719ecmsh49813de82f4ed67p13e4f9jsna8d8d23c8c51",
        "X-RapidAPI-Host": "online-movie-database.p.rapidapi.com"
    }

    response = requests.get(url_endpoint, headers=api_headers, params=querystring)

    return response.json()


def api_get_celeb_bio(celeb_id):

    data = actors_endpoint_api_call(celeb_id, "get-bio")

    celeb_page_url = f"https://www.imdb.com{data.get('id')}"
    name = data.get("name")
    dob = data.get("birthDate")
    dod = data.get("deathDate")
    birth_place = data.get("birthPlace")
    gender = data.get("gender")
    height_cm = data.get("heightCentimeters")
    nicknames = data.get("nicknames")
    main_image_url = data.get("image")["url"]
    print(celeb_page_url, name,dob,dod,birth_place,gender,height_cm,nicknames,main_image_url)


def api_get_celeb_additional_images(celeb_id):
    max_urls = 50
    data = actors_endpoint_api_call(celeb_id, "get-all-images")

    # Check if the 'resource' key exists and if 'images' is present in the 'resource' dictionary
    images_list = data.get('resource', {}).get('images', [])

    # Get the first 100 URLs or as many as are available
    urls_list = [item["url"] for item in images_list[:max_urls]]
    # print(urls_list)
    return urls_list


if __name__ == "__main__":
    print()
    # get_celeb_bio("nm0614165")
    # get_celeb_100_additional_images("nm5886893")

function formatDate(dateString) {
    const date = new Date(dateString);
    const options = {year: 'numeric', month: 'long', day: 'numeric'};
    return date.toLocaleDateString(undefined, options);
}

function displayRecognizedCelebrities(data) {
    const resultDiv = document.querySelector("#result");
    resultDiv.innerHTML = ""; // Clear the result div

    // Display the uploaded image and celebrity's image
    const imagesContainer = document.createElement("div");
    imagesContainer.className = "images-container";

    // Handle case where no faces detected
    if (data.celebrity_info === null) {
        const noFacesDetected = document.createElement("p");
        noFacesDetected.textContent = "No faces detected in the uploaded image";
        resultDiv.appendChild(noFacesDetected);
    } else {
        console.log(data.celebrity_info)
        // Loop over each face
        data.celebrity_info.forEach((celebInfo, index) => {
            // Handle case where face not matched
            if (celebInfo === null) {
                const unmatchedFace = document.createElement("p");
                unmatchedFace.textContent = `No matching celebrity found for face ${index + 1}.`;
                resultDiv.appendChild(unmatchedFace);
            } else {
                // Create a card for each face
                const card = document.createElement("div");
                card.className = "card";

                // Display the celebrity's image
                const celebImageContainer = document.createElement("div");
                celebImageContainer.className = "celeb-image-container";
                const celebImage = document.createElement("img");
                celebImage.src = celebInfo[6];
                celebImage.className = "celeb-image img-fluid";
                celebImage.style.maxHeight = "300px"; // Set the height of the celebrity's image to 300px
                celebImageContainer.appendChild(celebImage);
                card.appendChild(celebImageContainer);

                // Display the celebrity info as an unordered list
                const celebInfoList = document.createElement("ul");
                celebInfoList.style.color = "#000"; // Set the color of the list items

                const celebName = document.createElement("li");
                celebName.textContent = celebInfo[1];
                celebInfoList.appendChild(celebName);

                const dob = document.createElement("li");
                let date = formatDate(celebInfo[2])
                dob.textContent = `Born: ${date}`;
                celebInfoList.appendChild(dob);

                if (celebInfo[3] != null) {
                    const dod = document.createElement("li");
                    date = formatDate(celebInfo[3])
                    dob.textContent = `Died: ${date}`;
                    celebInfoList.appendChild(dod);
                }

                const celebAge = document.createElement("li");
                celebAge.textContent = "Age: " + JSON.stringify(celebInfo[4]);
                celebInfoList.appendChild(celebAge);

                const IMDBLink = document.createElement("a");
                IMDBLink.textContent = `Go to IMDb`;
                IMDBLink.href = celebInfo[5];
                IMDBLink.target = "_blank"; // Open link in a new tab

                const imdbListItem = document.createElement("li");
                imdbListItem.appendChild(IMDBLink);
                celebInfoList.appendChild(imdbListItem);

                card.appendChild(celebInfoList);

                imagesContainer.appendChild(card);

            }
        });

        // Append imagesContainer to resultDiv after loop
        resultDiv.appendChild(imagesContainer);
    }
}


navigator.getUserMedia = navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia;

var video = document.querySelector('video');
var canvas = document.querySelector('canvas');
var ctx = canvas.getContext('2d');
var localMediaStream = null;

function snapshot() {
    if (localMediaStream) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        let photo = canvas.toDataURL('image/jpeg');
        photo = photo.replace('data:image/jpeg;base64,', '');

        // Send image to the server
        fetch('/uploadImage', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({image: photo})
        })
        .then(response => response.json())
        .then(data => {
            displayRecognizedCelebrities(data);
        });
    }
}

video.addEventListener('click', snapshot, false);

navigator.getUserMedia({video: true}, function (stream) {
    video.srcObject = stream;
    localMediaStream = stream;
}, console.error);


// Handle file input change event
document.getElementById("imageFile").addEventListener("change", function(event) {
    const file = event.target.files[0];
    if (file) {
        // Create FormData object to send the file
        const formData = new FormData();
        formData.append("file", file);

        // Send the file to the server
        fetch("/uploadFile/", {
            method: "POST",
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            displayRecognizedCelebrities(data);
        })
        .catch(error => {
            console.error("Error uploading file:", error);
        });
    }
});

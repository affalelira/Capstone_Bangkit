# Machine Learning

## Project Description
This project is an implementation of a machine learning model for face verification. The model is trained using the **Faces Dataset** (Dataset Siamese.zip) and is used for our application **AJI**.

## Siamese Model File
You can download the `.h5` model file here:  
[Download siamese_model.h5](https://drive.google.com/drive/folders/1jE5OrqJcL_nFcNG4AdMi6kz7AzTzH39E?usp=drive_link)

## How to Use
1. Download the model from the link above.
2. Save the `siamese_model.h5` file in the project directory.
3. Run the following script to load the model:
   ```python
   from tensorflow.keras.models import load_model

   model = load_model("siamese_model.h5")
   print("Model loaded successfully!")

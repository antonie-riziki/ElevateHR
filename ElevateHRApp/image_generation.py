from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import base64
import os
# import streamlit as st


from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


def google_image_generator(prompt):
  response = client.models.generate_content(
      model="gemini-2.0-flash-preview-image-generation",
      contents=prompt,
      config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE']
      )
  )

  for part in response.candidates[0].content.parts:
    if part.inline_data is not None:
        image_data = part.inline_data.data
        image = Image.open(BytesIO(image_data))

        # Convert image to base64 for HTML rendering
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        return img_str
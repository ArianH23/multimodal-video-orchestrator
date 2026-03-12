from abc import ABC

from google import genai
from google.genai import types
from domain.ports.image_gen import ImageGeneratorPort


class GeminiImageAdapter(ImageGeneratorPort, ABC):
    def __init__(self, api_key, model="imagen-4.0-ultra-generate-001"):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.number_of_images = 1  # @param {type:"slider", min:1, max:4, step:1}
        self.person_generation = "ALLOW_ADULT"  # @param ['DONT_ALLOW', 'ALLOW_ADULT']
        self.aspect_ratio = "9:16"  # @param ["1:1", "3:4", "4:3", "16:9", "9:16"]

    def create_image(self, prompt, img_name):
        result = self.client.models.generate_images(
            model=self.model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=self.number_of_images,
                output_mime_type="image/png",
                person_generation=self.person_generation,
                aspect_ratio=self.aspect_ratio,
                image_size="2K"
            )
        )

        generated_image = result.generated_images[0]

        image_bytes = generated_image.image.image_bytes
        return image_bytes
        # mime_type = generated_image.image.mime_type
        #
        # ext = "." + mime_type.split('/')[-1]
        # # path = "current_analysis/" + img_name + ext
        # filename = "current_analysis/" + img_name + ext
        # with open(filename, "wb") as f:
        #     f.write(image_bytes)

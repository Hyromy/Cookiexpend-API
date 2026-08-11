import os
import uuid
from io import BytesIO
from typing import Callable, Literal, Tuple

from django.core.files.base import ContentFile
from django.db.models import Model
from django.utils import timezone
from django.utils.deconstruct import deconstructible
from PIL import Image


class ImgHelper:
    """
    A helper class for processing and saving images, providing methods for cropping, scaling, resizing,
    and normalizing images, as well as generating unique paths for uploaded images.
    """

    FOLDER = Literal["products", "categories", "gallery", "brands", "retailers"]
    SIZE = Tuple[int, int]

    class Method:
        """
        A collection of static methods for processing images, including cropping to square, scaling
        while maintaining aspect ratio, resizing to specific dimensions, and normalizing image channels.
        These methods can be used in combination to prepare images for storage and display in a consistent
        format.
        """

        @staticmethod
        def crop_to_square(image: Image.Image) -> Image.Image:
            """Crop the image to a square format, centered on the original image."""

            width, height = image.size
            min_dim = min(width, height)

            left = (width - min_dim) / 2
            top = (height - min_dim) / 2
            right = (width + min_dim) / 2
            bottom = (height + min_dim) / 2

            return image.crop((left, top, right, bottom))

        @staticmethod
        def scale(img: Image.Image, *, size: "ImgHelper.SIZE") -> Image.Image:
            """
            Scale the image to fit within the specified size, maintaining the aspect ratio. The resulting
            image will not exceed the specified dimensions.
            """

            img_copy = img.copy()
            img_copy.thumbnail(size, Image.Resampling.LANCZOS)

            return img_copy

        @staticmethod
        def resize(img: Image.Image, *, size: "ImgHelper.SIZE") -> Image.Image:
            """
            Resize the image to the specified size, ignoring the aspect ratio. The resulting image will
            be exactly the specified dimensions, but may be distorted.
            """

            return img.resize(size, Image.Resampling.LANCZOS)

        @staticmethod
        def normalize_channels(img: Image.Image) -> Image.Image:
            """
            Normalize the image channels to ensure it is in RGB format. If the image has an alpha channel
            (RGBA) or is in a palette mode (P), it will be converted to RGB. Otherwise, it will be converted
            to RGB without altering the color information.
            """

            if img.mode in ("RGBA", "P"):
                return img.convert("RGBA")
            return img.convert("RGB")

    @staticmethod
    def generate_path_in(folder_name: FOLDER) -> Callable:
        """Generate a unique path for an uploaded image, using the current date and a random token."""

        return PathGenerator(folder_name)

    @staticmethod
    def save(
        *,
        model: Model,
        field_name: str = "img",
        methods: list[Callable[[Image.Image], Image.Image]],
    ):
        """
        Process and save the image associated with the specified model instance. The image will be processed
        using the provided methods, saved in WEBP format, and the original image file will be removed
        if it exists. The model instance will be updated to reference the new image path.
        """

        file_field = getattr(model, field_name, None)

        if not file_field:
            return

        try:
            if not file_field.file:
                return
            file_field.file.seek(0)
            img_handler = Image.open(file_field.file)
        except Exception:
            return

        for processor in methods:
            img_handler = processor(img_handler)

        img_handler = ImgHelper.Method.normalize_channels(img_handler)

        buffer = BytesIO()
        img_handler.save(buffer, "WEBP", optimize=True, quality=85)
        buffer.seek(0)

        current_name = os.path.basename(file_field.name)
        new_name = os.path.splitext(current_name)[0] + ".webp"

        file_field.save(new_name, ContentFile(buffer.read()), save=False)


@deconstructible
class PathGenerator:
    def __init__(self, folder_name: str):
        self.folder_name = folder_name

    def __call__(self, instance, filename) -> str:
        ext = os.path.splitext(filename)[1]
        current_date = timezone.now().strftime("%Y%m%d")
        token = uuid.uuid4().hex[:8]
        return os.path.join(self.folder_name, f"{current_date}_{token}{ext}")

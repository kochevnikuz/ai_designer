import torch
from diffusers import StableDiffusionPipeline, StableDiffusionImg2ImgPipeline
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image, ImageOps
import os


class CarpetAIEngine:
    def __init__(self, model_id="runwayml/stable-diffusion-v1-5"):
        """
        Инициализация движка ИИ. Загружаем модель в память GPU.
        """
        print("Загрузка модели Stable Diffusion... Это может занять время.")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Основной пайплайн (Текст -> Картинка)
        self.pipe = StableDiffusionPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
        )
        self.pipe = self.pipe.to(self.device)

        # Дополнительный пайплайн (Картинка -> Картинка), переиспользуем веса
        self.pipe_img2img = StableDiffusionImg2ImgPipeline(**self.pipe.components)

        if self.device == "cuda":
            self.pipe.enable_attention_slicing()
            self.pipe_img2img.enable_attention_slicing()

        print(f"Модель успешно загружена на {self.device}")

    def _set_seamless_mode(self, enable=True):
        """Включает или выключает математику бесшовной генерации (circular padding)"""
        mode = 'circular' if enable else 'zeros'
        for module in self.pipe.unet.modules():
            if isinstance(module, torch.nn.Conv2d):
                module.padding_mode = mode
        for module in self.pipe_img2img.unet.modules():
            if isinstance(module, torch.nn.Conv2d):
                module.padding_mode = mode

    def generate_sketch(self, design_instance, strength=0.75, design_mode='standard'):
        """
        Метод генерирует эскиз ковра и сохраняет его в БД.
        """
        # 0. Подготовка персонального стиля (LoRA)
        self.pipe.unload_lora_weights()
        self.pipe_img2img.unload_lora_weights()

        attn_kwargs = None

        if design_instance.collection.lora_weights:
            lora_path = design_instance.collection.lora_weights.path
            print(f"🧠 Подключение обученного стиля (LoRA): {lora_path}")
            self.pipe.load_lora_weights(lora_path)
            self.pipe_img2img.load_lora_weights(lora_path)
            attn_kwargs = {"scale": 1.0}

        # Включение режима бесшовного раппорта (Seamless)
        if design_mode == 'seamless':
            print("🔄 Включен математический режим бесшовного рулона (Seamless)")
            self._set_seamless_mode(True)
        else:
            self._set_seamless_mode(False)

        # 1. Формируем финальный промпт
        collection_prompt = design_instance.collection.base_prompt
        user_prompt = design_instance.user_prompt

        # Если классика - просим ИИ нарисовать ТОЛЬКО четверть
        if design_mode == 'symmetry_quarter':
            user_prompt = "one quarter corner of a carpet, top left section, " + user_prompt

        negative_prompt = "3d render, perspective, room, furniture, shadows, blurry, distorted, text"
        final_prompt = f"carpet pattern design, top down view, flat texture, {collection_prompt}, {user_prompt}"

        print(f"Запуск генерации. Промпт: {final_prompt}")

        # 2. Вычисляем пропорции изображения
        width_m = float(design_instance.width_meters)
        length_m = float(design_instance.length_meters)

        base_size = 512

        if width_m > length_m:
            img_w = base_size
            img_h = int((length_m / width_m) * base_size)
        else:
            img_h = base_size
            img_w = int((width_m / length_m) * base_size)

        # Если режим симметрии, мы просим ИИ нарисовать кусок в 2 раза меньше
        if design_mode == 'symmetry_quarter':
            img_w = max(128, (img_w // 2))
            img_h = max(128, (img_h // 2))

        # Округляем до 8 для Stable Diffusion
        img_w = (img_w // 8) * 8
        img_h = (img_h // 8) * 8

        # 3. Генерация изображения (Выбор режима)
        if design_instance.source_image:
            print(f"🖼️ Режим Image-to-Image: используется загруженное фото. Сила ИИ: {strength}")
            init_image = Image.open(design_instance.source_image.path).convert("RGB")
            init_image = init_image.resize((img_w, img_h))

            image = self.pipe_img2img(
                prompt=final_prompt,
                image=init_image,
                strength=strength,
                negative_prompt=negative_prompt,
                num_inference_steps=30,
                cross_attention_kwargs=attn_kwargs
            ).images[0]
        else:
            print("📝 Режим Text-to-Image: генерация с нуля")
            image = self.pipe(
                final_prompt,
                negative_prompt=negative_prompt,
                width=img_w,
                height=img_h,
                num_inference_steps=30,
                cross_attention_kwargs=attn_kwargs
            ).images[0]

        # 4. Сборка идеальной симметрии (Если выбрана Классика)
        if design_mode == 'symmetry_quarter':
            print("🪞 Сборка идеальной симметрии 1/4...")
            right_half = ImageOps.mirror(image)
            bottom_half = ImageOps.flip(image)
            bottom_right = ImageOps.mirror(bottom_half)

            full_w = img_w * 2
            full_h = img_h * 2

            full_img = Image.new('RGB', (full_w, full_h))
            full_img.paste(image, (0, 0))  # Левый верх
            full_img.paste(right_half, (img_w, 0))  # Правый верх
            full_img.paste(bottom_half, (0, img_h))  # Левый низ
            full_img.paste(bottom_right, (img_w, img_h))  # Правый низ

            image = full_img  # Заменяем картинку на готовую симметричную

        # 5. Сохранение результата
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        file_name = f"ai_sketch_{design_instance.id}.png"

        design_instance.ai_color_image.save(file_name, ContentFile(buffer.getvalue()), save=False)
        design_instance.status = 'processing'
        design_instance.save()

        return image
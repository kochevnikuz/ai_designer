import os
import numpy as np
from PIL import Image
from scipy.spatial import KDTree
from django.conf import settings
from django.core.files.base import ContentFile
from io import BytesIO


class CarpetBMPConverter:
    def __init__(self, design_instance):
        self.design = design_instance
        self.collection = self.design.collection

        # Получаем палитру коллекции из БД, отсортированную по индексам (1-12)
        # Это критически важно, чтобы цвета встали в нужные слоты челноков
        self.palette_colors = list(self.collection.colors.order_by('color_index'))
        if not self.palette_colors:
            raise ValueError("У коллекции нет привязанных цветов в палитре!")

    def hex_to_rgb(self, hex_string):
        """Конвертирует '#RRGGBB' в кортеж (R, G, B)"""
        hex_string = hex_string.lstrip('#')
        return tuple(int(hex_string[i:i + 2], 16) for i in (0, 2, 4))

    def _calculate_target_resolution(self):
        """
        Вычисляет точное количество узлов (пикселей) для станка
        на основе размеров ковра и плотности коллекции.
        """
        # Размеры в сантиметрах
        width_cm = float(self.design.width_meters) * 100
        length_cm = float(self.design.length_meters) * 100

        # Узлов на 10 см -> Узлов на 1 см
        horiz_nodes_per_cm = self.collection.horizontal_nodes / 10.0
        vert_nodes_per_cm = self.collection.loom.vertical_nodes / 10.0

        # Итоговые пиксели (ширина x высота)
        # Горизонталь станка (уток) формирует ширину рисунка
        target_width_px = int(width_cm * horiz_nodes_per_cm)
        # Вертикаль станка (бердо) формирует длину/высоту рисунка
        target_height_px = int(length_cm * vert_nodes_per_cm)

        return target_width_px, target_height_px

    def process_and_save(self):
        """
        Главный метод: берет картинку ИИ, ресайзит,
        меняет цвета на палитру и сохраняет в Indexed BMP.
        """
        if not self.design.ai_color_image:
            raise ValueError("У дизайна нет сгенерированного ИИ эскиза.")

        print(f"Начинаем конвертацию для дизайна: {self.design.title}")

        # 1. Открываем оригинальное изображение от ИИ
        img_path = self.design.ai_color_image.path
        original_img = Image.open(img_path).convert('RGB')

        # 2. Вычисляем пиксели и делаем жесткий ресайз (NEAREST)
        target_w, target_h = self._calculate_target_resolution()
        print(f"Целевое разрешение станка: {target_w}x{target_h} узлов")

        # Используем NEAREST, чтобы избежать размытых/грязных пикселей на границах цветов
        resized_img = original_img.resize((target_w, target_h), Image.NEAREST)

        # 3. Подготовка палитры для квантования
        # Превращаем наши HEX-кода из БД в массив RGB
        target_rgb_palette = [self.hex_to_rgb(pc.hex_code) for pc in self.palette_colors]

        # Мы используем KDTree для очень быстрого поиска ближайшего цвета
        tree = KDTree(target_rgb_palette)

        # 4. Квантование (перекраска каждого пикселя в ближайший из палитры)
        print("Запуск квантования цветов (это может занять несколько секунд)...")
        # Превращаем картинку в массив numpy (формат: Высота x Ширина x 3(RGB))
        img_array = np.array(resized_img)

        # Разворачиваем в плоский список пикселей
        flat_pixels = img_array.reshape(-1, 3)

        # Ищем индексы ближайших цветов из нашей палитры для каждого пикселя
        # query возвращает (расстояния, индексы_в_палитре)
        _, indices = tree.query(flat_pixels)

        # indices - это одномерный массив (длиной Width*Height),
        # где каждое число - это индекс цвета (0-7, если 8 цветов)

        # 5. Создание 8-битного индексированного изображения (Mode 'P')
        # Создаем пустую P-картинку нужного размера
        indexed_img = Image.new('P', (target_w, target_h))

        # Вставляем туда нашу матрицу индексов (сначала вернув ей форму 2D: Высота x Ширина)
        indexed_img.putdata(indices)

        # 6. Запись правильной палитры в заголовок файла
        # Pillow ожидает плоский список: [R,G,B, R,G,B, R,G,B...] (максимум 256 * 3 = 768 значений)
        flat_palette = []
        for rgb in target_rgb_palette:
            flat_palette.extend(rgb)

        # Добиваем палитру нулями до 256 цветов (требование формата 8-bit BMP)
        while len(flat_palette) < 768:
            flat_palette.append(0)

        indexed_img.putpalette(flat_palette)

        # 7. Сохранение файла в модель Django
        buffer = BytesIO()
        # Обязательно указываем формат BMP
        indexed_img.save(buffer, format="BMP")

        file_name = f"machine_ready_{self.design.id}.bmp"

        # Сохраняем в FileField
        self.design.final_bmp_file.save(file_name, ContentFile(buffer.getvalue()), save=False)
        self.design.status = 'ready'
        self.design.save()

        print(f"Готово! BMP файл сохранен: {self.design.final_bmp_file.url}")
        return self.design.final_bmp_file.url
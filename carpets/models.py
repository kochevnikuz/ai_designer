from django.db import models
from django.core.validators import MinValueValidator


class Loom(models.Model):
    """Модель ткацкого станка."""
    name = models.CharField(max_length=100, verbose_name="Название станка (например, Van de Wiele)")
    max_width_meters = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="Максимальная ширина (м)")
    vertical_nodes = models.IntegerField(verbose_name="Вертикальные узлы (Бердо на 10 см)",
                                         help_text="Например: 32, 40, 48, 120")

    def __str__(self):
        return f"{self.name} (Бердо: {self.vertical_nodes}, Ширина: {self.max_width_meters}м)"


class Collection(models.Model):
    """Модель коллекции ковров."""
    name = models.CharField(max_length=100, verbose_name="Название коллекции")
    loom = models.ForeignKey(Loom, on_delete=models.RESTRICT, verbose_name="Привязанный станок")

    horizontal_nodes = models.IntegerField(verbose_name="Горизонтальные узлы (Уток на 10 см)")
    color_count = models.IntegerField(verbose_name="Количество цветов (6, 8, 10, 12)")

    # Скрытый промпт для ИИ, задающий стиль коллекции
    base_prompt = models.TextField(verbose_name="Базовый AI-промпт коллекции",
                                   help_text="Например: 'modern abstract art, high detail, masterpiece'")

    # НОВОЕ ПОЛЕ: Файл обучения (LoRA) для этой коллекции
    lora_weights = models.FileField(upload_to='ai_models/lora/', blank=True, null=True,
                                    verbose_name="Обученный стиль ИИ (LoRA .safetensors)",
                                    help_text="Загрузите обученную модель для этой коллекции, чтобы ИИ рисовал в вашем стиле")

    def __str__(self):
        return f"Коллекция {self.name} ({self.loom.vertical_nodes}x{self.horizontal_nodes})"


class PaletteColor(models.Model):
    """Цвета и материалы пряжи для конкретной коллекции."""
    YARN_TYPES = [
        ('PP', 'Полипропилен (PP)'),
        ('PES', 'Полиэстер (PES)'),
        ('ACR', 'Акрил (Acrylic)'),
        ('VIS', 'Вискоза / Шелк'),
    ]

    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name="colors")
    color_index = models.PositiveIntegerField(verbose_name="Номер челнока (1-12)")
    hex_code = models.CharField(max_length=7, verbose_name="HEX код цвета (#RRGGBB)")

    # Новые поля для физики ковра
    yarn_type = models.CharField(max_length=3, choices=YARN_TYPES, default='PP', verbose_name="Тип пряжи")
    is_shrink = models.BooleanField(default=False, verbose_name="Усадочная нить (High-Low эффект)")

    class Meta:
        ordering = ['color_index']
        unique_together = ['collection', 'color_index']

    def __str__(self):
        return f"Челнок {self.color_index} ({self.yarn_type}) - {self.hex_code}"


class CarpetDesign(models.Model):
    """Проект генерации ковра."""
    STATUS_CHOICES = [
        ('draft', 'Эскиз (AI)'),
        ('processing', 'Пикселизация и Цветокоррекция'),
        ('ready', 'Готов для станка (*.bmp)'),
        ('error', 'Ошибка генерации'),
    ]

    title = models.CharField(max_length=200, verbose_name="Название дизайна")
    collection = models.ForeignKey(Collection, on_delete=models.RESTRICT, verbose_name="Коллекция")

    # Габариты, которые запрашивает дизайнер
    width_meters = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="Ширина (м)")
    length_meters = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="Длина (м)")

    # Входные данные
    user_prompt = models.TextField(verbose_name="Запрос дизайнера")
    source_image = models.ImageField(upload_to='source_photos/', blank=True, null=True,
                                     verbose_name="Исходное фото (для Image-to-Image)")

    # Результаты работы ИИ
    ai_color_image = models.ImageField(upload_to='ai_results/colors/', blank=True, verbose_name="AI Эскиз (Цвет)")
    ai_depth_map = models.ImageField(upload_to='ai_results/depth/', blank=True,
                                     verbose_name="AI Карта высот (Для усадки)")
    final_bmp_file = models.FileField(upload_to='machine_bmp/', blank=True, verbose_name="Файл для станка (*.bmp)")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.width_meters > self.collection.loom.max_width_meters:
            raise ValidationError(
                f"Ширина не может превышать ширину станка ({self.collection.loom.max_width_meters}м).")
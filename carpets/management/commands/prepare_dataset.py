from django.core.management.base import BaseCommand
from PIL import Image
import os


class Command(BaseCommand):
    help = 'Нарезает большие изображения ковров на квадраты 512x512 для обучения LoRA'

    def add_arguments(self, parser):
        parser.add_argument('input_dir', type=str, help='Папка с вашими оригинальными дизайнами (jpg/png/bmp)')
        parser.add_argument('output_dir', type=str, help='Папка, куда сохранить готовый датасет (512x512 + txt)')
        parser.add_argument('trigger_word', type=str, help='Секретное слово для ИИ (например: yasham_luna_style)')

    def handle(self, *args, **options):
        input_dir = options['input_dir']
        output_dir = options['output_dir']
        trigger_word = options['trigger_word']

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp')

        count = 0
        for filename in os.listdir(input_dir):
            if not filename.lower().endswith(valid_extensions):
                continue

            filepath = os.path.join(input_dir, filename)
            try:
                img = Image.open(filepath).convert('RGB')
                w, h = img.size

                base_name = os.path.splitext(filename)[0]

                # 1. Сохраняем общую композицию (сжимаем до 512x512)
                img_resized = img.resize((512, 512), Image.LANCZOS)
                self._save_sample(img_resized, output_dir, f"{base_name}_full", trigger_word,
                                  "full carpet composition, central medallion, borders")
                count += 1

                # 2. Нарезаем детали (узоры в оригинальном качестве без сжатия)
                # Берем куски 512x512 из центра и по краям
                if w >= 512 and h >= 512:
                    # Центр
                    left = (w - 512) // 2
                    top = (h - 512) // 2
                    img_center = img.crop((left, top, left + 512, top + 512))
                    self._save_sample(img_center, output_dir, f"{base_name}_center", trigger_word,
                                      "carpet central pattern detail, intricate ornaments")
                    count += 1

                    # Левый верхний угол (бордюр)
                    img_corner = img.crop((0, 0, 512, 512))
                    self._save_sample(img_corner, output_dir, f"{base_name}_corner", trigger_word,
                                      "carpet border detail, corner pattern")
                    count += 1

                self.stdout.write(self.style.SUCCESS(f'Обработан файл: {filename}'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Ошибка с файлом {filename}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'\nГотово! Создано {count} фрагментов для обучения.'))

    def _save_sample(self, img, out_dir, name, trigger_word, description):
        """Сохраняет картинку и сопровождающий .txt файл для нее"""
        img_path = os.path.join(out_dir, f"{name}.png")
        txt_path = os.path.join(out_dir, f"{name}.txt")

        img.save(img_path)

        # Записываем промпт. ИИ выучит, что картинка связана с этим текстом.
        prompt = f"{trigger_word}, carpet pattern design, top down view, flat texture, {description}"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
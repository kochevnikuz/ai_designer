from django.core.management.base import BaseCommand
from carpets.models import CarpetDesign
from carpets.ai_generator import CarpetAIEngine
from carpets.bmp_converter import CarpetBMPConverter
import time


class Command(BaseCommand):
    help = 'Тестирование полного цикла: генерация эскиза ИИ и конвертация в BMP'

    def add_arguments(self, parser):
        # Ожидаем, что пользователь передаст ID дизайна
        parser.add_argument('design_id', type=int, help='ID дизайна (CarpetDesign) для обработки')

    def handle(self, *args, **options):
        design_id = options['design_id']

        # 1. Проверяем, существует ли такой дизайн
        try:
            design = CarpetDesign.objects.get(id=design_id)
        except CarpetDesign.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Ошибка: Дизайн с ID {design_id} не найден.'))
            return

        self.stdout.write(self.style.WARNING(f'=== Запуск полного конвейера для: "{design.title}" ==='))

        start_time = time.time()

        try:
            # 2. Шаг первый: Генерация эскиза (AI)
            self.stdout.write(self.style.NOTICE('\n[Шаг 1] Генерация эскиза нейросетью...'))
            engine = CarpetAIEngine()
            engine.generate_sketch(design)
            self.stdout.write(self.style.SUCCESS(f'Эскиз ИИ сохранен: {design.ai_color_image.url}'))

            # Обновляем объект из базы, чтобы точно получить сохраненную картинку
            design.refresh_from_db()

            # 3. Шаг второй: Конвертация в формат станка (BMP)
            self.stdout.write(self.style.NOTICE('\n[Шаг 2] Квантование цветов и перевод в BMP...'))
            converter = CarpetBMPConverter(design)
            bmp_url = converter.process_and_save()

            end_time = time.time()
            duration = round(end_time - start_time, 2)

            self.stdout.write(self.style.SUCCESS(f'\n✅ УСПЕШНО! Весь цикл завершен за {duration} сек.'))
            self.stdout.write(self.style.SUCCESS(f'Файл для станка готов к выгрузке: {bmp_url}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Критическая ошибка в процессе: {e}'))
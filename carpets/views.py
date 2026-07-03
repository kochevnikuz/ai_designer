from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Collection, CarpetDesign
from .ai_generator import CarpetAIEngine
from .bmp_converter import CarpetBMPConverter
import json

# Инициализируем движок ИИ глобально при запуске сервера,
# чтобы не грузить модель в видеокарту заново при каждом запросе.
try:
    ai_engine = CarpetAIEngine()
except Exception as e:
    print(f"Ошибка загрузки ИИ: {e}")
    ai_engine = None


def dashboard(request):
    """Отображает главную страницу интерфейса дизайнера"""
    collections = Collection.objects.all()
    return render(request, 'carpets/index.html', {'collections': collections})


@csrf_exempt
def generate_design_api(request):
    """API endpoint, который принимает данные из формы браузера и запускает ИИ"""
    if request.method == 'POST':
        try:
            # Принимаем данные через FormData (request.POST для текста и request.FILES для картинок)
            data = request.POST
            collection_id = data.get('collection_id')
            source_image = request.FILES.get('source_image')

            # Находим коллекцию
            collection = Collection.objects.get(id=collection_id)

            # Создаем новый проект в базе
            design = CarpetDesign.objects.create(
                title=data.get('title', 'Новый дизайн'),
                collection=collection,
                width_meters=data.get('width'),
                length_meters=data.get('length'),
                user_prompt=data.get('prompt'),
                source_image=source_image
            )

            # Забираем параметры ползунка и режима
            ai_strength = float(data.get('ai_strength', 75)) / 100.0
            design_mode = data.get('design_mode', 'standard')

            # 1. Запуск ИИ с учетом переданных параметров
            ai_engine.generate_sketch(design, strength=ai_strength, design_mode=design_mode)
            design.refresh_from_db()

            # 2. Конвертация в формат станка
            converter = CarpetBMPConverter(design)
            bmp_url = converter.process_and_save()

            return JsonResponse({
                'status': 'success',
                'ai_image_url': design.ai_color_image.url,
                'bmp_file_url': bmp_url,
                'design_id': design.id
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'invalid method'}, status=405)
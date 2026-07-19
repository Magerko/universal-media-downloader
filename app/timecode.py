"""Разбор и вывод меток времени для обрезки видео."""

# Поля разделяет только двоеточие: если считать «5.30» за «5:30», то «12.5»
# станет двенадцатью минутами вместо двенадцати с половиной секунд.
_DECIMAL_MARKS = (',',)


def parse_timecode(text):
    """Переводит метку времени в секунды.

    Принимает «чч:мм:сс», «мм:сс» и число секунд; точка и запятая — дробная
    часть. Пустая строка даёт None, мусор — ValueError.
    """
    if text is None:
        return None
    value = str(text).strip()
    if not value:
        return None

    # Запятая — та же дробная часть.
    for mark in _DECIMAL_MARKS:
        value = value.replace(mark, '.')

    parts = value.split(':')
    if len(parts) > 3:
        raise ValueError(f'слишком много частей в метке времени: {text!r}')
    # «1::30» допустимо, «::» — нет.
    if not any(p.strip() for p in parts):
        raise ValueError(f'в метке времени нет цифр: {text!r}')

    try:
        numbers = [float(p) if p.strip() else 0.0 for p in parts]
    except ValueError:
        raise ValueError(f'метка времени содержит не только цифры: {text!r}')

    if any(n < 0 for n in numbers):
        raise ValueError(f'отрицательное время: {text!r}')

    # Сверх шестидесяти не запрещаем: «90:00» читается однозначно.
    total = 0.0
    for number in numbers:
        total = total * 60 + number
    return total


def format_timecode(seconds):
    """Обратное преобразование — для показа в интерфейсе."""
    if seconds is None:
        return ''
    seconds = max(0, int(round(float(seconds))))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f'{hours}:{minutes:02d}:{secs:02d}'
    return f'{minutes}:{secs:02d}'


def validate_range(start, end, duration=None):
    """Проверяет пару границ. Возвращает ключ ошибки либо None.

    Длительность — если известна: выход за конец ролика ловим до загрузки.
    """
    if start is not None and end is not None and end <= start:
        return 'end_before_start'
    if duration:
        if start is not None and start >= duration:
            return 'start_after_end_of_video'
        if end is not None and end > duration + 1:
            return 'end_after_end_of_video'
    return None

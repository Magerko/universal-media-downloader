"""Разбор и вывод меток времени для обрезки видео.

Человек пишет момент времени так, как привык его видеть под плеером:
«7:40», «1:02:15», иногда просто «90». Всё это должно работать одинаково,
поэтому разбор собран в одном месте и покрыт проверками.
"""

# Разделяет поля только двоеточие. Точка и запятая — дробная часть секунд.
# Соблазн считать «5.30» за «5:30» пришлось отбросить: тогда «12.5» читалось
# бы как двенадцать минут пять секунд вместо двенадцати с половиной секунд,
# а такая ошибка молча испортит обрезку.
_DECIMAL_MARKS = (',',)


def parse_timecode(text):
    """Переводит метку времени в секунды.

    Принимает «чч:мм:сс», «мм:сс» и просто число секунд. Дробная часть
    сохраняется: у ролика с быстрой нарезкой полсекунды бывают заметны.
    Отделяется она точкой или запятой — «12.5» это двенадцать с половиной
    секунд, а не двенадцать минут пять секунд.

    Возвращает float либо None, если строка пустая. Бросает ValueError на
    том, что меткой времени не является.
    """
    if text is None:
        return None
    value = str(text).strip()
    if not value:
        return None

    # Запятую приводим к точке: в русской раскладке дробную часть привычно
    # отделять именно ей.
    for mark in _DECIMAL_MARKS:
        value = value.replace(mark, '.')

    parts = value.split(':')
    if len(parts) > 3:
        raise ValueError(f'слишком много частей в метке времени: {text!r}')
    # Пустые части внутри допустимы («1::30»), но хотя бы одна цифра нужна:
    # иначе строка «::» молча означала бы ноль.
    if not any(p.strip() for p in parts):
        raise ValueError(f'в метке времени нет цифр: {text!r}')

    try:
        numbers = [float(p) if p.strip() else 0.0 for p in parts]
    except ValueError:
        raise ValueError(f'метка времени содержит не только цифры: {text!r}')

    if any(n < 0 for n in numbers):
        raise ValueError(f'отрицательное время: {text!r}')

    # Минуты и секунды сверх шестидесяти не запрещаем: «90:00» как полтора
    # часа читается однозначно, а отказ вынудил бы считать в уме.
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
    """Проверяет пару границ. Возвращает текст ошибки либо None.

    Длительность передаётся, когда известна: выйти за конец ролика —
    самая частая ошибка, и поймать её лучше до начала загрузки, а не
    получив пустой файл.
    """
    if start is not None and end is not None and end <= start:
        return 'end_before_start'
    if duration:
        if start is not None and start >= duration:
            return 'start_after_end_of_video'
        if end is not None and end > duration + 1:
            return 'end_after_end_of_video'
    return None

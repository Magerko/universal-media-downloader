"""Готовит иконки из дизайн-системы к использованию в Qt.

Иконки приходят со `stroke="currentColor"` — это веб-соглашение, и средство
отрисовки SVG в Qt его не понимает: линии получаются чисто чёрными и на
тёмной теме почти не видны. Проверено рендером, а не на глаз.

Поэтому цвет подставляется здесь. Выбран средне-серый: у приложения две темы,
а путь к иконке в коде один, и этот тон читается и на тёмном фоне, и на
светлом. Если понадобятся отдельные наборы под темы — достаточно прогнать
скрипт дважды с разным ICON_COLOR и разложить по разным папкам.

Запуск: python tools/import_icons.py
"""
import os
import re

# Средне-серый из палитры дизайн-системы: около 5.6:1 на тёмном фоне
# и 3.4:1 на белом — читается в обеих темах.
ICON_COLOR = '#868c96'

HERE = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(os.path.dirname(HERE), 'assets', 'icons')


def apply_colour(svg: str, colour: str = ICON_COLOR) -> str:
    return re.sub(r'currentColor', colour, svg)


def write_icon(name: str, svg: str) -> str:
    os.makedirs(ICONS_DIR, exist_ok=True)
    path = os.path.join(ICONS_DIR, f'{name}.svg')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(apply_colour(svg))
    return path


if __name__ == '__main__':
    for file_name in sorted(os.listdir(ICONS_DIR)):
        if not file_name.endswith('.svg'):
            continue
        path = os.path.join(ICONS_DIR, file_name)
        with open(path, encoding='utf-8') as f:
            content = f.read()
        if 'currentColor' in content:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(apply_colour(content))
            print(f'recoloured {file_name}')
        else:
            print(f'skipped    {file_name} (already has explicit colours)')

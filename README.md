# Universal Media Downloader

<p align="center">
  <img src="assets/icon.png" alt="Logo" width="128" height="128">
</p>

<p align="center">
  <b>Универсальный загрузчик медиа</b> - десктопное приложение для скачивания видео и аудио с популярных платформ.
</p>

<p align="center">
  <a href="#возможности">Возможности</a> •
  <a href="#установка">Установка</a> •
  <a href="#требования">Требования</a> •
  <a href="#использование">Использование</a> •
  <a href="#скриншоты">Скриншоты</a>
</p>

---

## Возможности

- **Поддержка платформ**: YouTube, TikTok, Instagram, VK, RuTube, Twitch, Kick, Kinopoisk и другие
- **Выбор качества**: индивидуальные настройки для каждой платформы
- **Извлечение аудио**: конвертация в MP3 (192kbps)
- **Параллельные загрузки**: настраиваемое количество одновременных загрузок
- **История загрузок**: отслеживание всех скачанных файлов
- **Субтитры**: загрузка субтитров (EN, RU, UK)
- **Cookies**: авторизация через файл или браузер
- **Drag & Drop**: перетаскивание ссылок и .txt файлов
- **Темы**: тёмная и светлая
- **Локализация**: русский, английский, украинский
- **Автообновление**: проверка обновлений yt-dlp при запуске

## Требования

- **Python** 3.10+
- **Deno** 2.0+ (требуется для загрузки с YouTube)
- **FFmpeg** (включён в проект или системный)

### Установка Deno (обязательно для YouTube)

**Windows (PowerShell):**
```powershell
irm https://deno.land/install.ps1 | iex
```

**macOS/Linux:**
```bash
curl -fsSL https://deno.land/install.sh | sh
```

### FFmpeg

FFmpeg используется для объединения видео и аудио потоков, конвертации форматов и извлечения аудио.

**Вариант 1:** Приложение уже содержит FFmpeg в папке `assets/ffmpeg/`

**Вариант 2:** Установить системно:

**Windows:**
```powershell
winget install FFmpeg
```
или скачать с [ffmpeg.org](https://ffmpeg.org/download.html)

**macOS:**
```bash
brew install ffmpeg
```
**Linux:**
```bash
sudo apt install ffmpeg  # Debian/Ubuntu
sudo dnf install ffmpeg  # Fedora
```

## Установка

1. **Клонируйте репозиторий:**
```bash
git clone https://github.com/YOUR_USERNAME/universal-media-downloader.git
cd universal-media-downloader
```

2. **Создайте виртуальное окружение:**
```bash
python -m venv .venv
```

3. **Активируйте виртуальное окружение:**

Windows:
```bash
.venv\Scripts\activate
```

macOS/Linux:
```bash
source .venv/bin/activate
```

4. **Установите зависимости:**
```bash
pip install -r requirements.txt
```

5. **Запустите приложение:**
```bash
python main.py
```

## Использование

1. Вставьте ссылку в поле ввода и нажмите Enter или кнопку "+"
2. Настройте качество в разделе "Настройки" (опционально)
3. Нажмите "Скачать все"

### Поддерживаемые способы добавления ссылок:
- Вставка в поле ввода
- Drag & Drop ссылки или .txt файла
- Вставка из буфера обмена (кнопка "Вставить")

## Скриншоты

<p align="center">
  <img src="screenshots/main.PNG" alt="Main Screen" width="600">
</p>

<p align="center">
  <img src="screenshots/settings.PNG" alt="Settings" width="600">
</p>

## Структура проекта

```
Downloader/
├── app/                    # Основной код приложения
│   ├── main_window.py      # Главное окно
│   ├── download_manager.py # Менеджер загрузок
│   ├── download_task.py    # Модель задачи
│   ├── threads.py          # Воркеры (загрузка, превью)
│   ├── settings_tab.py     # Вкладка настроек
│   ├── history_tab.py      # Вкладка истории
│   ├── about_tab.py        # Вкладка "О программе"
│   ├── theme_manager.py    # Управление темами
│   ├── translation.py      # Система локализации
│   ├── update_checker.py   # Проверка обновлений yt-dlp
│   └── ...
├── assets/                 # Ресурсы
│   ├── ffmpeg/             # FFmpeg бинарники
│   ├── logos/              # Логотипы платформ
│   ├── en.json             # Английская локализация
│   ├── ru.json             # Русская локализация
│   └── uk.json             # Украинская локализация
├── main.py                 # Точка входа
├── requirements.txt        # Зависимости Python
└── README.md
```

## Зависимости

- **PyQt6** - GUI фреймворк
- **yt-dlp[curl-cffi]** - движок загрузки
- **requests** - HTTP клиент
- **packaging** - работа с версиями

## Известные проблемы

### YouTube не работает / ошибка "Signature solving failed"

Это происходит из-за того, что yt-dlp теперь требует JavaScript runtime для работы с YouTube.

**Решение:**
1. Установите Deno (см. раздел "Требования")
2. Перезапустите приложение

### При запуске появляется ошибка `FFmpeg не найден. Убедитесь, что он находится в папке assets/ffmpeg/bin/ffmpeg`

**Решение:**

1. Создайте нужную папку в проекте:

```bash
mkdir -p assets/ffmpeg/bin
```

2. Скопируйте FFmpeg в эту папку:

```bash
cp $(which ffmpeg) assets/ffmpeg/bin/ffmpeg
```

3. Сделайте бинарник исполняемым:

```bash
chmod +x assets/ffmpeg/bin/ffmpeg
```

После этого приложение должно запускаться без ошибки.

## Автор

**Magerko**

## Лицензия

MIT License - см. файл LICENSE для подробностей.

---

<p align="center">
  Сделано с ❤️ на Python и PyQt6
</p>

# src/iolib/serializers

Форматно-зависимый слой ввода-вывода. Каждый сериализатор умеет одно: превратить питоновскую структуру (dict / list / DataFrame) в `bytes` и обратно. Знаний о домене (что такое IRS, что такое VaR) здесь нет — это сознательно тонкая прослойка.

## Зачем это нужно

`iolib/portfolio_io.py` (`PortfolioExporter` / `PortfolioImporter`) и `iolib/results_exporter.py` (`ResultsExporter`) работают через единый интерфейс `BaseSerializer`. Это позволяет добавлять новый формат, не трогая логику сборки портфеля или отчёта: достаточно реализовать ещё один класс с методами `serialize` / `deserialize` и зарегистрировать его в `__init__.py`.

## base.py

Абстрактный базовый класс `BaseSerializer` фиксирует контракт:

| Член | Назначение |
|---|---|
| `serialize(data) -> bytes` | Превращает питоновский объект в байты для записи в файл |
| `deserialize(raw: bytes) -> Any` | Обратная операция: парсит байты в питоновский объект |
| `file_extension` (property) | Расширение файла без точки (`json`, `yaml`, `csv`, `xlsx`) |
| `mime_type` (property) | MIME-тип, используется UI при отдаче файла на скачивание через Streamlit |

Все четыре метода и свойства абстрактные, наследники обязаны их реализовать.

## Конкретные реализации

### json_serializer.py

`JsonSerializer` — стандартный JSON через `json.dumps` / `json.loads` в UTF-8. Используется как канонический формат портфелей: сохраняет вложенность и типы.

### yaml_serializer.py

`YamlSerializer` — YAML через PyYAML. Удобен, когда портфель собирают руками или ревьюят в репозитории, формат человекочитаемый и допускает комментарии.

### csv_serializer.py

`CsvSerializer` — плоское табличное представление. Для портфелей это означает «один инструмент на строку», поэтому `PortfolioImporter` опирается на `_parse_bool` / `_parse_float_or_none` / `_parse_date`, чтобы восстановить типы из строк. Для результатов расчёта (`ResultsExporter._export_csv`) формат подходит идеально: это просто таблица VaR.

### excel_serializer.py

`ExcelSerializer` — `.xlsx` через `openpyxl` и `pandas.ExcelWriter`. Используется и для портфелей, и для многолистовых результатов: `ResultsExporter._export_excel` раскладывает разные таблицы по отдельным листам книги.

## __init__.py: реестр сериализаторов

Подпакет экспортирует три объекта, через которые остальной `iolib` выбирает реализацию:

| Объект | Содержимое | Кто использует |
|---|---|---|
| `SERIALIZERS` | `dict[str, BaseSerializer]` с ключами `"json"`, `"yaml"`, `"csv"`, `"excel"` | `PortfolioExporter`, `ResultsExporter` (выбор по имени формата) |
| `FORMAT_LABELS` | Список ключей `SERIALIZERS` в стабильном порядке | UI: выпадающие списки выбора формата на странице загрузки и выгрузки |
| `EXT_TO_SERIALIZER` | `dict[ext, BaseSerializer]`, отображает расширения (`json`, `yaml`, `yml`, `csv`, `xlsx`) на инстансы | `PortfolioImporter.load` (определяет формат по расширению пути) |

Чтобы добавить новый формат, нужно создать класс-наследник `BaseSerializer`, импортировать его в `__init__.py` и дополнить `SERIALIZERS` и `EXT_TO_SERIALIZER`. Остальной код `iolib` менять не потребуется.

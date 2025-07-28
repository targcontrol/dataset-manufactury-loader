import streamlit as st
import pandas as pd
import requests
import uuid
import io
from datetime import time

# Streamlit app configuration
st.set_page_config(page_title="Dataset Uploader", layout="wide")
st.title("Создание датасетов для Производства")

# Instruction button and example table
with st.expander("Инструкция по созданию TARGControl", expanded=False):
    st.markdown("""
    ### Пример структуры Excel-таблицы
    Для корректной обработки файл должен содержать следующие столбцы:
    - **Продукция**: Название продукта (например, "Продукт А").
    - **Локация**: Строковое значение, точно совпадающее с именем локации в TARGControl (например, "Линия 1", "Линия 2", "Линия 3").
    - **Описание**: Описание продукта, например, код номенклатуры (необязательно, используется для описания датасета, если заполнено).
    - **Навыки**: Столбцы с названиями навыков, которые совпадают с данными из TARGControl (например, "Навык1", "Навык2"). Значения — целые числа или пустые ячейки.

    **Пример таблицы**:

    | Продукция   | Локация   | Описание     | Навык1 | Навык2 |
    |-------------|-----------|--------------|--------|--------|
    | Продукт А   | Линия 1   | NOM12345     | 5      | 3      |
    | Продукт Б   | Линия 2   |              | 2      | 0      |

    **Убедитесь, что**:
    - Столбцы `Продукция` и `Локация` присутствуют и заполнены.
    - Столбец `Описание` необязателен; если не заполнен, описание будет сформировано как "Датасет для [Продукция]".
    - Значения в столбце `Локация` точно совпадают с именами локаций из TARGControl.
    - Названия навыков в столбцах совпадают с названиями навыков в TARGControl.
    - Значения в столбцах навыков — целые числа или пустые ячейки.
    - Все названия должны быть в строгом соответствии с данными в TARGControl!
    """)

# Input for API token
api_token = st.text_input("Введите API Token", type="password", key="api_token")
if not api_token:
    st.warning("Пожалуйста, введите действительный API-токен для продолжения.")
    st.stop()

# File uploader for Excel file
uploaded_file = st.file_uploader("Загрузите Excel-файл", type=["xlsx"], key="file_uploader")

# API configuration
domen = 'cloud'
headers = {
    'accept': 'application/json',
    'X-API-Key': api_token,
}

# Fixed value
FORECAST_MODEL_ID = "4fd37b8e-fe68-4b51-b703-e77dbe9231be"

# Input for pattern times and number of patterns
st.subheader("Настройки шаблонов")
num_patterns = st.selectbox("Количество шаблонов", ["1 шаблон", "2 шаблона"], key="num_patterns")

st.write("Время для дневного шаблона")
col1, col2 = st.columns(2)
with col1:
    START_TIME_DAY = st.time_input("Время начала (дневной)", value=pd.to_datetime("08:00:00").time(), key="start_time_day")
with col2:
    END_TIME_DAY = st.time_input("Время окончания (дневной)", value=pd.to_datetime("20:00:00").time(), key="end_time_day")

if num_patterns == "2 шаблона":
    st.write("Время для ночного шаблона")
    col3, col4 = st.columns(2)
    with col3:
        START_TIME_NIGHT = st.time_input("Время начала (ночной)", value=pd.to_datetime("20:00:00").time(), key="start_time_night")
    with col4:
        END_TIME_NIGHT = st.time_input("Время окончания (ночной)", value=pd.to_datetime("08:00:00").time(), key="end_time_night")
else:
    START_TIME_NIGHT = None
    END_TIME_NIGHT = None

# Check if END_TIME_DAY is after START_TIME_NIGHT for 2 patterns
time_valid = True
if num_patterns == "2 шаблона" and START_TIME_NIGHT and END_TIME_DAY:
    if END_TIME_DAY > START_TIME_NIGHT:
        st.warning("Время окончания дневного шаблона не может быть позже времени начала ночного шаблона. Пожалуйста, исправьте.")
        time_valid = False

def get_locations():
    """Fetch locations from API."""
    locations = {}
    params = {'page': '0', 'size': '100'}
    try:
        response = requests.get(
            f'https://{domen}.targcontrol.com/external/api/locations',
            params=params,
            headers=headers
        )
        response.raise_for_status()
        data = response.json()['data']
        for item in data:
            locations[str(item['name'])] = item['id']
        return locations
    except requests.RequestException as e:
        st.error(f"Ошибка при получении локаций: {e}")
        return {}

def get_skills():
    """Fetch skills from API without caching."""
    skills = {}
    try:
        response = requests.get(
            f'https://{domen}.targcontrol.com/external/api/employee-skills',
            headers=headers
        )
        response.raise_for_status()
        for item in response.json():
            skills[item['name']] = item['id']
        return skills
    except requests.RequestException as e:
        st.error(f"Ошибка при получении навыков: {e}")
        return {}

def get_patterns():
    """Fetch patterns from API and return list of pattern IDs."""
    try:
        response = requests.get(
            f'https://{domen}.targcontrol.com/external/api/forecaster/pattern',
            headers=headers
        )
        response.raise_for_status()
        patterns = response.json()
        if not patterns:
            st.error("Шаблоны не найдены. Пожалуйста, создайте шаблон в веб-интерфейсе TARGControl.")
            return []
        return [pattern['id'] for pattern in patterns if not pattern['datasetId']]
    except requests.RequestException as e:
        st.error(f"Ошибка при получении шаблонов: {e}")
        return []

def get_metrics():
    """Fetch metrics from API."""
    try:
        response = requests.get(
            f'https://{domen}.targcontrol.com/external/api/forecaster/metric',
            headers=headers
        )
        response.raise_for_status()
        metrics = response.json()
        return {metric['name']: metric['id'] for metric in metrics}
    except requests.RequestException as e:
        st.error(f"Ошибка при получении метрик: {e}")
        return {}

# Fetch metrics and allow user to select one
metrics_dict = get_metrics()
if not metrics_dict:
    st.error("Метрики не найдены. Пожалуйста, создайте метрику в веб-интерфейсе TARGControl.")
    st.stop()

st.subheader("Выбор метрики")
metric_name = st.selectbox("Выберите метрику", list(metrics_dict.keys()), key="metric_select")
METRIC_ID = metrics_dict[metric_name]

# Fetch pattern IDs
PATTERN_IDS = get_patterns()
if not PATTERN_IDS:
    st.stop()

# Check if enough patterns are available
if num_patterns == "2 шаблона" and len(PATTERN_IDS) < 2:
    st.error(f"Для создания датасета с 2 шаблонами требуется как минимум 2 шаблона в TARGControl. Доступно только {len(PATTERN_IDS)} шаблона. Создайте дополнительный шаблон в веб-интерфейсе TARGControl.")
    st.stop()

def create_dataset_pattern(product_name, location_id, skills_dict, row, pattern_id, start_time, end_time):
    """Create dataset pattern with value=10 and value=20."""
    pattern_data = []
    skill_columns = [col for col in row.index if col in skills_dict and col not in ['Продукция', 'Локация', 'Описание']]

    for skill in skill_columns:
        if pd.notna(row[skill]):
            try:
                skill_value = int(float(row[skill]))
                pattern_data.append({
                    "id": str(uuid.uuid4()),
                    "skillId": skills_dict[skill],
                    "value": 10,
                    "shiftsCount": 0
                })
                pattern_data.append({
                    "id": str(uuid.uuid4()),
                    "skillId": skills_dict[skill],
                    "value": 20,
                    "shiftsCount": skill_value
                })
            except (ValueError, TypeError):
                continue

    return {
        "id": pattern_id,
        "metricId": METRIC_ID,
        "datasetId": None,
        "name": f"{product_name} - {start_time[:5]}-{end_time[:5]}",
        "startTime": start_time,
        "endTime": end_time,
        "description": f"Pattern for {product_name}",
        "skillIds": [skills_dict[skill] for skill in skill_columns if pd.notna(row[skill])],
        "patternData": pattern_data,
        "externalId": ""
    }

def create_dataset(product_name, location_id, skills_dict, row, num_patterns):
    """Create dataset for product."""
    dataset_id = str(uuid.uuid4())
    patterns = []
    start_time_day = START_TIME_DAY.strftime("%H:%M:%S")
    end_time_day = END_TIME_DAY.strftime("%H:%M:%S")

    # Use first pattern for day
    patterns.append(
        create_dataset_pattern(product_name, location_id, skills_dict, row, PATTERN_IDS[0], start_time_day, end_time_day)
    )

    # Include night pattern only if 2 patterns are selected and available
    if num_patterns == "2 шаблона" and START_TIME_NIGHT and END_TIME_NIGHT:
        start_time_night = START_TIME_NIGHT.strftime("%H:%M:%S")
        end_time_night = END_TIME_NIGHT.strftime("%H:%M:%S")
        patterns.append(
            create_dataset_pattern(product_name, location_id, skills_dict, row, PATTERN_IDS[1], start_time_night, end_time_night)
        )

    description = row.get('Описание') if pd.notna(row.get('Описание')) and str(row.get('Описание')).strip() else f"Датасет для {product_name}"

    return {
        "locationId": location_id,
        "metricId": METRIC_ID,
        "forecastModelId": FORECAST_MODEL_ID,
        "name": f"{product_name}",
        "description": description,
        "datasetPatterns": patterns,
        "tags": [product_name],
        "externalId": None
    }

def send_dataset(dataset):
    """Send dataset via API."""
    try:
        response = requests.post(
            f"https://{domen}.targcontrol.com/external/api/forecaster/dataset/save",
            headers=headers,
            json=dataset
        )
        response.raise_for_status()
        return True, f"Датасет {dataset['name']} успешно отправлен."
    except requests.RequestException as e:
        return False, f"Ошибка при отправке датасета {dataset['name']}: {e}"

def process_file(uploaded_file, num_patterns):
    """Process the uploaded Excel file."""
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Ошибка при чтении Excel-файла: {e}. Убедитесь, что файл имеет правильный формат (.xlsx).")
            return

        required_columns = ['Продукция', 'Локация']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.error(f"В файле отсутствуют обязательные столбцы: {', '.join(missing_columns)}. Проверьте структуру файла в инструкции.")
            return

        skills_dict = get_skills()
        locations_dict = get_locations()

        if locations_dict:
            st.info(f"Доступные локации из API: {', '.join(locations_dict.keys())}")
        else:
            st.error("Не удалось получить локации из API. Проверьте токен или доступность API.")
            return

        skill_columns = [col for col in df.columns if col in skills_dict and col not in ['Продукция', 'Локация', 'Описание']]
        if not skill_columns:
            st.warning("Не найдено совпадающих навыков между Excel-файлом и данными API. Проверьте названия столбцов в файле и данные API.")
        else:
            st.info(f"Найдены совпадающие навыки: {', '.join(skill_columns)}")

        total_rows = len(df)
        st.info(f"Всего продукции для создания: {total_rows} датасетов")
        progress_bar = st.progress(0)
        progress_text = st.empty()  # Placeholder for progress text
        processed_count = 0

        for idx, row in df.iterrows():
            product_name = row['Продукция']
            try:
                location_name = str(row['Локация'])
            except (ValueError, TypeError):
                st.warning(f"Некорректное значение локации в строке {idx + 2}: {row['Локация']}. Пропускаем.")
                continue

            if location_name not in locations_dict:
                st.warning(f"Локация '{location_name}' не найдена в ответе API. Проверьте доступные локации выше.")
                continue

            location_id = locations_dict[location_name]
            dataset = create_dataset(product_name, location_id, skills_dict, row, num_patterns)
            success, message = send_dataset(dataset)
            if success:
                processed_count += 1
                st.success(message)
            else:
                st.error(message)

            progress_bar.progress((idx + 1) / total_rows)
            progress_text.text(f"Обработано {processed_count} из {total_rows} датасетов")

        st.success("Обработка файла завершена!")

# Display total datasets to process if file is uploaded
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        st.info(f"Всего продукции для создания: {len(df)} датасетов")
    except Exception as e:
        st.error(f"Ошибка при чтении файла для подсчета датасетов: {e}")

if uploaded_file and api_token and time_valid and PATTERN_IDS:
    if st.button("Обработать файл", disabled=not time_valid):
        process_file(uploaded_file, num_patterns)
else:
    st.button("Обработать файл", disabled=True)
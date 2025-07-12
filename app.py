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
with st.expander("Инструкция по созданию Excel-файла", expanded=False):
    st.markdown("""
    ### Пример структуры Excel-таблицы
    Для корректной обработки файл должен содержать следующие столбцы:
    - **Продукция**: Название продукта (например, "Продукт А").
    - **Локация**: Строковое значение, точно совпадающее с именем локации в TARGControl (например, "Линия 1", "Линия 2", "Линия 3").
    - **Навыки**: Столбцы с названиями навыков, которые совпадают с данными из TARGControl (например, "Навык1", "Навык2"). Значения — целые числа или пустые ячейки.

    **Пример таблицы**:

    | Продукция   | Локация | Навык1 | Навык2 |
    |-------------|---------|--------|--------|
    | Продукт А   | Линия 1       | 5      | 3      |
    | Продукт Б   | Линия 2       | 2      | 0      |

    Убедитесь, что:
    - Столбец `Локация` содержит значения, точно совпадающие с именами локаций из TARGControl.
    - Названия навыков в столбцах совпадают с названиями навыков в TARGControl.
    - Значения в столбцах навыков — целые числа или пустые.
    
    ГЛАВНОЕ: Все названия должны быть в строгом соответствии с названиями в TARGControl!
    """)

# Input for API token
api_token = st.text_input("Введите API Token", type="password", key="api_token")
if not api_token:
    st.warning("Пожалуйста, введите действительный API-токен для продолжения.")
    st.stop()

# File uploader for Excel file
uploaded_file = st.file_uploader("Загрузите Excel-файл", type=["xlsx"], key="file_uploader")

# API configuration
domen = 'dev'
headers = {
    'accept': 'application/json',
    'X-API-Key': api_token,
}

# Fixed values
METRIC_ID = "0fc7ab83-41e2-4f51-8ea4-502e66d00a5b"
FORECAST_MODEL_ID = "4fd37b8e-fe68-4b51-b703-e77dbe9231be"
PATTERN_DAY_ID = "cf3ad7e1-b200-4f4f-a188-8f142a345d72"
PATTERN_NIGHT_ID = "5f308484-7b04-4453-a62f-588e52942a65"

# Input for pattern times and number of patterns
st.subheader("Настройки шаблонов")
num_patterns = st.selectbox("Количество шаблонов", ["1 шаблон", "2 шаблона"], key="num_patterns")

st.write("Время для дневного шаблона")
col1, col2 = st.columns(2)
with col1:
    START_TIME_DAY = st.time_input("Время начала (дневной)", value=pd.to_datetime("08:00:00").time(),
                                   key="start_time_day")
with col2:
    END_TIME_DAY = st.time_input("Время окончания (дневной)", value=pd.to_datetime("20:00:00").time(),
                                 key="end_time_day")

if num_patterns == "2 шаблона":
    st.write("Время для ночного шаблона")
    col3, col4 = st.columns(2)
    with col3:
        START_TIME_NIGHT = st.time_input("Время начала (ночной)", value=pd.to_datetime("20:00:00").time(),
                                         key="start_time_night")
    with col4:
        END_TIME_NIGHT = st.time_input("Время окончания (ночной)", value=pd.to_datetime("08:00:00").time(),
                                       key="end_time_night")
else:
    START_TIME_NIGHT = None
    END_TIME_NIGHT = None

# Check if END_TIME_DAY is after START_TIME_NIGHT for 2 patterns
time_valid = True
if num_patterns == "2 шаблона" and START_TIME_NIGHT and END_TIME_DAY:
    if END_TIME_DAY > START_TIME_NIGHT:
        st.warning(
            "Время окончания дневного шаблона не может быть позже времени начала ночного шаблона. Пожалуйста, исправьте.")
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
            locations[str(item['name'])] = item['id']  # Convert name to string for matching
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


def create_dataset_pattern(product_name, location_id, skills_dict, row, pattern_id, start_time, end_time):
    """Create dataset pattern with value=10 and value=20."""
    pattern_data = []
    # Use skills from API that match Excel columns
    skill_columns = [col for col in row.index if col in skills_dict and col != 'Продукция' and col != 'Локация']

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
    # Convert time objects to string format (HH:MM:SS)
    start_time_day = START_TIME_DAY.strftime("%H:%M:%S")
    end_time_day = END_TIME_DAY.strftime("%H:%M:%S")

    # Always include day pattern
    patterns.append(
        create_dataset_pattern(product_name, location_id, skills_dict, row, PATTERN_DAY_ID, start_time_day,
                               end_time_day)
    )

    # Include night pattern only if 2 patterns are selected
    if num_patterns == "2 шаблона" and START_TIME_NIGHT and END_TIME_NIGHT:
        start_time_night = START_TIME_NIGHT.strftime("%H:%M:%S")
        end_time_night = END_TIME_NIGHT.strftime("%H:%M:%S")
        patterns.append(
            create_dataset_pattern(product_name, location_id, skills_dict, row, PATTERN_NIGHT_ID, start_time_night,
                                   end_time_night)
        )

    return {
        "locationId": location_id,
        "metricId": METRIC_ID,
        "forecastModelId": FORECAST_MODEL_ID,
        "name": f"{product_name}",
        "description": f"Датасет для {product_name}",
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
        st.success(f"Датасет {dataset['name']} успешно отправлен.")
        return response.json()
    except requests.RequestException as e:
        st.error(f"Ошибка при отправке датасета {dataset['name']}: {e}")
        return None


def process_file(uploaded_file, num_patterns):
    """Process the uploaded Excel file."""
    if uploaded_file:
        # Read Excel file
        try:
            df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Ошибка при чтении Excel-файла: {e}. Убедитесь, что файл имеет правильный формат (.xlsx).")
            return

        # Check for required columns
        required_columns = ['Продукция', 'Локация']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.error(f"В файле отсутствуют обязательные столбцы: {', '.join(missing_columns)}. Проверьте структуру файла в инструкции.")
            return

        # Get skills and locations (always fetch fresh data)
        skills_dict = get_skills()
        locations_dict = get_locations()

        # Display available locations for debugging
        if locations_dict:
            st.info(f"Доступные локации из API: {', '.join(locations_dict.keys())}")
        else:
            st.error("Не удалось получить локации из API. Проверьте токен или доступность API.")
            return

        # Check for matching skills
        skill_columns = [col for col in df.columns if col in skills_dict and col != 'Продукция' and col != 'Локация']
        if not skill_columns:
            st.warning(
                "Не найдено совпадающих навыков между Excel-файлом и данными API. Проверьте названия столбцов в файле и данные API.")
        else:
            st.info(f"Найдены совпадающие навыки: {', '.join(skill_columns)}")

        # Process each row
        progress_bar = st.progress(0)
        total_rows = len(df)
        for idx, row in df.iterrows():
            product_name = row['Продукция']
            try:
                # Convert location to string for strict matching
                location_name = str(row['Локация'])
            except (ValueError, TypeError):
                st.warning(f"Некорректное значение локации в строке {idx + 2}: {row['Локация']}. Пропускаем.")
                continue

            # Strict matching: location_name must exactly match a key in locations_dict
            if location_name not in locations_dict:
                st.warning(f"Локация '{location_name}' не найдена в ответе API. Проверьте доступные локации выше.")
                continue

            location_id = locations_dict[location_name]
            dataset = create_dataset(product_name, location_id, skills_dict, row, num_patterns)
            send_dataset(dataset)

            # Update progress
            progress_bar.progress((idx + 1) / total_rows)

        st.success("Обработка файла завершена!")


if uploaded_file and api_token and time_valid:
    if st.button("Обработать файл", disabled=not time_valid):
        process_file(uploaded_file, num_patterns)
else:
    st.button("Обработать файл", disabled=True)
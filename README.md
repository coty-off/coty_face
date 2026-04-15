#  **ColorType Science** - Научный анализ цветотипа (CIE LCh + Michelson)

[![Docker](https://img.shields.io/badge/Docker-Compose-brightgreen?style=flat&logo=docker)](https://docker.com)
[![Celery](https://img.shields.io/badge/Celery-v5.6.3-orange?style=flat&logo=celery)](https://celeryproject.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-v0.115-blue?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-FaceParsing-purple?style=flat&logo=pytorch)](https://pytorch.org)

** Реализовано**: Face Parsing → **CIE LCh колориметрия** → **Michelson контраст** → **45 персональных оттенков**

##  **Что делает система**

1. **Сегментирует лицо** (BiSeNet): кожа, глаза, брови, волосы
2. **Анализирует 4 элемента** в CIE LCh: L*/C/h + теплота
3. **Вычисляет Michelson контраст** + цветотип (взвешенный)
4. **Генерирует палитру** 9×5=45 оттенков в L* границах пользователя

##  **НАУЧНЫЕ ОСНОВЫ (Детально)**

### **1. CIE L*a*b* → LCh (CIE 1976, ISO 11664-4)**
L* ∈ - перцептивная светлота
C = √(a²+b²) - хрома (насыщенность)
h = atan2(b*,a*) - hue (оттенок, 0-360°)

**Преимущества LCh**:
- **Перцептивно равномерная** (ΔE равномерны)
- **Hue-анализ теплоты** по колориметрическим диапазонам
- **Стандарт**: Международная комиссия по освещению (CIE)

**Диапазоны теплоты** (научно обоснованные):


Фото с раскрашенными сегментами для анализа:



<img width=50% height=50% alt="2ffba59e-e9cc-4941-ac80-4d7990e7352a_men_smart_analysis_visual" src="https://github.com/user-attachments/assets/e3f15204-792d-44fa-afd0-4b3af6c2b64d" />


Легенда оттенков внешности пользователя:



<img width="500" height="200" alt="5268bdab-15c7-4c6c-b714-9debbb966ee6_men_smart_legend_detailed" src="https://github.com/user-attachments/assets/ad82bf2a-04d6-439e-a87d-c622b1e50023" />

Палитра:
<img width="1076" height="914" alt="image" src="https://github.com/user-attachments/assets/95538cc9-c81f-41cc-a102-d9bceb6cb8b4" />



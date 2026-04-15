#  **ColorType Science** - Научный анализ цветотипа (CIE LCh + Michelson)

[![Docker](https://img.shields.io/badge/Docker-Compose-brightgreen?style=flat&logo=docker)](https://docker.com)
[![Celery](https://img.shields.io/badge/Celery-v5.6.3-orange?style=flat&logo=celery)](https://celeryproject.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-v0.115-blue?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-FaceParsing-purple?style=flat&logo=pytorch)](https://pytorch.org)

Система состоит из: Face Parsing → **CIE LCh колориметрия** → **Michelson контраст** → **45 персональных оттенков**

##  **Что делает система**

1. **Сегментирует лицо** (BiSeNet): кожа, глаза, брови, волосы
2. **Анализирует 4 элемента** в CIE LCh: L*/C/h + теплота
3. **Вычисляет Michelson контраст** + цветотип 
4. **Генерирует палитру** 9×5=45 оттенков в L* границах пользователя

##  **Основа, на что опирается приложение**

### **1. CIE L*a*b* → LCh (CIE 1976, ISO 11664-4)**
L* ∈ - перцептивная светлота
C = √(a²+b²) - хрома - насыщенность
h = atan2(b*,a*) - hue (оттенок, 0-360°)

**Преимущества LCh**:
- **Перцептивно равномерная** ΔE равномерны
- **Hue-анализ теплоты** по колориметрическим диапазонам
- **Стандарт**: Международная комиссия по освещению CIE


### **2. Контрастность Michelson **
M = (L_max - L_min) / (L_max + L_min) ∈ [0;1]
M < 0.30 → Низкая → L*raw= 
0.30≤M<0.50 → Средняя → L*raw= 
M ≥ 0.50 → Высокая → L*raw=


### **Соответствие научных источников и кода**

| **Научная основа** | **Источник** | **Параметры статьи** | **Реализация в коде** | **Функция** |
|--------------------|--------------|----------------------|-----------------------|-------------|
| **CIELCh анализ кожи** | JID (1992)<br>Reeder (2014) | L*a*b* пигментация<br>ICC=0.85-0.86 | `rgb2lab()`<br>`chroma=√(a*²+b*²)`<br>`hue_deg=atan2(b*,a*)` | `ColorAnalyzer.rgb_to_cielab_full()` |
| **Hue-диапазоны теплоты** | ICCSNT (2011)<br>Хомяков М.Ю. | KMeans+Hue классификация | `is_warm=(0<=hue<=60)∪(300<=hue<=360)`<br>`cv2.kmeans(pixels,3)` | `analyze_feature()`<br>`extract_precise_features()` |
| **L* диапазоны кожи** | ISDA (2008) | Ахроматические L* range | `L_min_user=min(L_values)`<br>`L_max_user=max(L_values)` | `detailed_4features_analysis()` |
| **Michelson контраст** | PLoS ONE (2013)<br>Frontiers (2017) | `Cf=(L_skin-L_feat)/(L_skin+L_feat)` | `michelson=(L_max-L_min)/(L_max+L_min)` | `detailed_4features_analysis()` |
| **LCh палитра** | CIELCh (ISO 11664-4) | Независимое варьирование L/C/h | `L_levels_user=clamp(raw_L, L_min_user, L_max_user)`<br>`hue_shift=±15°` | `generate_personal_palette()` |


Фото с раскрашенными сегментами для анализа:



<img width=50% height=50% alt="2ffba59e-e9cc-4941-ac80-4d7990e7352a_men_smart_analysis_visual" src="https://github.com/user-attachments/assets/e3f15204-792d-44fa-afd0-4b3af6c2b64d" />


Легенда оттенков внешности пользователя:



<img width="500" height="200" alt="5268bdab-15c7-4c6c-b714-9debbb966ee6_men_smart_legend_detailed" src="https://github.com/user-attachments/assets/ad82bf2a-04d6-439e-a87d-c622b1e50023" />

Палитра:
<img width="1076" height="914" alt="image" src="https://github.com/user-attachments/assets/95538cc9-c81f-41cc-a102-d9bceb6cb8b4" />



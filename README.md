#  **COTY** - Научный анализ цветотипа (CIE LCh + Michelson)

[![Docker](https://img.shields.io/badge/Docker-Compose-brightgreen?style=flat&logo=docker)](https://docker.com)
[![Celery](https://img.shields.io/badge/Celery-v5.6.3-orange?style=flat&logo=celery)](https://celeryproject.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-v0.115-blue?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-FaceParsing-purple?style=flat&logo=pytorch)](https://pytorch.org)

Статус всех сервисов
<img width="1527" height="147" alt="image" src="https://github.com/user-attachments/assets/1f0191c4-14ec-4ea2-ae4a-353eb4a7f8c7" />
Celery очереди живы
<img width="1917" height="453" alt="image" src="https://github.com/user-attachments/assets/a4fac967-0007-46d4-b1a4-0056ebe0a51d" />
FastAPI готов
<img width="1907" height="853" alt="image" src="https://github.com/user-attachments/assets/08a4c529-e4ac-4652-b81e-efee828cb208" />


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
- **Перцептивно равномерная** ΔE равномерны - числа лучше совпадали с тем, как человек видит разницу цветов
- **Hue-анализ теплоты** по колориметрическим диапазонам
- **Стандарт**: Международная комиссия по освещению CIE


### 2. Контрастность Michelson 
M = (L_max - L_min) / (L_max + L_min) ∈ [0;1]
M < 0.30 → Низкая → L*raw= 
0.30≤M<0.50 → Средняя → L*raw= 
M ≥ 0.50 → Высокая → L*raw=


## **Соответствие научных источников и кода**

| **Научная основа** | **Источник** | **Параметры статьи** | **Реализация в коде** | **Функция** |
|--------------------|--------------|----------------------|-----------------------|-------------|
| **CIELCh анализ кожи** | JID (1992)<br>Reeder (2014) | L*a*b* пигментация<br>ICC=0.85-0.86 | `rgb2lab()`<br>`chroma=√(a*²+b*²)`<br>`hue_deg=atan2(b*,a*)` | `ColorAnalyzer.rgb_to_cielab_full()` |
| **Hue-диапазоны теплоты** | ICCSNT (2011)<br>Хомяков М.Ю. | KMeans+Hue классификация | `is_warm=(0<=hue<=60)∪(300<=hue<=360)`<br>`cv2.kmeans(pixels,3)` | `analyze_feature()`<br>`extract_precise_features()` |
| **L* диапазоны кожи** | ISDA (2008) | Ахроматические L* range | `L_min_user=min(L_values)`<br>`L_max_user=max(L_values)` | `detailed_4features_analysis()` |
| **Michelson контраст** | PLoS ONE (2013)<br>Frontiers (2017) | `Cf=(L_skin-L_feat)/(L_skin+L_feat)` | `michelson=(L_max-L_min)/(L_max+L_min)` | `detailed_4features_analysis()` |
| **LCh палитра** | CIELCh (ISO 11664-4) | Независимое варьирование L/C/h | `L_levels_user=clamp(raw_L, L_min_user, L_max_user)`<br>`hue_shift=±15°` | `generate_personal_palette()` |


## **Библиографические источники (РИНЦ-индексированы)**

1. **Reeder A.I. et al.** "Validity and Reliability of the Munsell Soil Color Charts..." *Cancer Epidemiol Biomarkers Prev*, 2014. [PMID:25017245](https://pubmed.ncbi.nlm.nih.gov/25017245/) [elibrary.ru:25017245]
2. **Porcheron A. et al.** "Aspects of Facial Contrast Decrease with Age..." *PLoS ONE*, 2013. [DOI:10.1371/journal.pone.0057985](https://doi.org/10.1371/journal.pone.0057985) [elibrary.ru:20789123]
3. **Хомяков М.Ю.** "Классификация цвета кожи человека..." РФ публикация. [Sci-Hub поиск]
4. **Yu C. et al.** "BiSeNet: Bilateral Segmentation Network..." *ECCV*, 2018. [arXiv:1808.00897](https://arxiv.org/abs/1808.00897)

Реализация представляет собой **цифровую адаптацию колориметрических стандартов (ISO/CIE)** и **психофизических измерений контрастности**, подтвержденных эмпирическими исследованиями.


Фото с раскрашенными сегментами для анализа:



<img width=50% height=50% alt="2ffba59e-e9cc-4941-ac80-4d7990e7352a_men_smart_analysis_visual" src="https://github.com/user-attachments/assets/e3f15204-792d-44fa-afd0-4b3af6c2b64d" />

Индексная маска:


<img width="512" height="512" alt="parsing_map_on_im" src="https://github.com/user-attachments/assets/7e025c41-56ef-46ae-a298-a13e5b3fd982" />



Маска с раскрашенными сементами поверх фото:


<img width="512" height="512" alt="parsing_map_on_im" src="https://github.com/user-attachments/assets/04ecd023-f01c-42b0-be2d-6ae6a878dd5e" />


Легенда оттенков внешности пользователя:



<img width="500" height="200" alt="5268bdab-15c7-4c6c-b714-9debbb966ee6_men_smart_legend_detailed" src="https://github.com/user-attachments/assets/ad82bf2a-04d6-439e-a87d-c622b1e50023" />

Палитра:
<img width="1076" height="914" alt="image" src="https://github.com/user-attachments/assets/95538cc9-c81f-41cc-a102-d9bceb6cb8b4" />



import os
import torch
import cv2
import numpy as np
from PIL import Image
from torchvision import transforms
from model import BiSeNet

# Путь к весам (внутри контейнера)
MODEL_PATH = os.path.join("res", "cp", "79999_iter.pth")  # или model_final_diss.pth


def get_skin_mask_from_bgr(image_bgr: np.ndarray, device="cpu") -> np.ndarray:
    """
    Вход: BGR-изображение H×W×3.
    Выход: skin_mask == 1 там, где кожа; размер H×W.
    """
    net = BiSeNet(n_classes=19)
    net.to(device)
    # Загрузка весов
    net.load_state_dict(torch.load(MODEL_PATH, map_location=device))
    net.eval()

    # BGR -> RGB -> PIL -> 512×512
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    image_pil = Image.fromarray(rgb)
    image = image_pil.resize((512, 512), Image.BILINEAR)

    # Тензоризируем
    to_tensor = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ]
    )
    img_tensor = to_tensor(image).unsqueeze(0).to(device)

    # Вывод BiSeNet (19 классов, 512×512)
    with torch.no_grad():
        out = net(img_tensor)[0]
        parsing = out.squeeze(0).cpu().numpy().argmax(0)  # 512×512, 0..18

    # Номера меток для кожи; по умолчанию часто 1 (проверь документацию BiSeNet)
    skin_labels = [1]
    mask_512 = np.isin(parsing, skin_labels)  # 512×512, bool

    # Возвращаем к исходному размеру
    h, w = image_bgr.shape[:2]
    mask = cv2.resize(
        (mask_512 * 255).astype("uint8"), (w, h), interpolation=cv2.INTER_NEAREST
    )
    mask = mask.astype("bool")

    return mask
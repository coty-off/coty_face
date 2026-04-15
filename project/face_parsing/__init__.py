import os
import sys
import torch
import cv2
import numpy as np
from PIL import Image
from torchvision import transforms

# добавляем текущую папку в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MODEL_PATH = os.path.join("res", "cp", "79999_iter.pth")

def get_skin_mask_from_bgr(image_bgr: np.ndarray, device="cpu") -> np.ndarray:
    """
    Вход: BGR-изображение H×W×3.
    Выход: skin_mask == 1 там, где кожа; размер H×W.
    """
    try:
        print(f"[FACEPARSING] Loading model from: {MODEL_PATH}")
        print(f"[FACEPARSING] Current dir: {os.getcwd()}")
        print(f"[FACEPARSING] Files in dir: {os.listdir('.')}")
        
        #  Импорт модели
        from model import BiSeNet
        print("[FACEPARSING] BiSeNet imported OK")
        
        net = BiSeNet(n_classes=19)
        net.to(device)
        
        # Проверяем модель
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
        print(f"[FACEPARSING] Model exists: {MODEL_PATH}")
        
        net.load_state_dict(torch.load(MODEL_PATH, map_location=device))
        net.eval()
        print("[FACEPARSING] Model loaded OK")

        # BGR -> RGB -> PIL -> 512×512
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image_pil = Image.fromarray(rgb)
        image = image_pil.resize((512, 512), Image.BILINEAR)

        # Тензоризируем
        to_tensor = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ])
        img_tensor = to_tensor(image).unsqueeze(0).to(device)

        # Вывод BiSeNet (19 классов, 512×512)
        with torch.no_grad():
            out = net(img_tensor)[0]
            parsing = out.squeeze(0).cpu().numpy().argmax(0)  # 512×512, 0..18

        #  какие лейблы найдены?
        unique_labels = np.unique(parsing)
        print(f"[FACEPARSING] Unique labels found: {unique_labels}")
        
        # Skin labels - может быть не только 1
        skin_labels = [1, 12, 13]  # skin + возможно другие
        mask_512 = np.isin(parsing, skin_labels)
        skin_pixels_512 = np.sum(mask_512)
        print(f"[FACEPARSING] Skin pixels in 512x512: {skin_pixels_512}")

        # Возвращаем к исходному размеру
        h, w = image_bgr.shape[:2]
        mask = cv2.resize(
            (mask_512 * 255).astype("uint8"), (w, h), interpolation=cv2.INTER_NEAREST
        )
        mask = mask.astype("bool")
        skin_pixels = np.sum(mask)
        
        print(f"[FACEPARSING] Final skin pixels: {skin_pixels}")
        return mask
        
    except Exception as e:
        print(f"[FACEPARSING] ERROR: {str(e)}")
        print(f"[FACEPARSING] Traceback: {e.__traceback__}")
        # Fallback: пустая маска
        h, w = image_bgr.shape[:2]
        return np.zeros((h, w), dtype=bool)
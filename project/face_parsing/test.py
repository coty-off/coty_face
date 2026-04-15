#!/usr/bin/python
# -*- encoding: utf-8 -*-

import os
import os.path as osp
import numpy as np
from PIL import Image
import torchvision.transforms as transforms
import cv2
import argparse
import torch

from model import BiSeNet


def vis_parsing_maps(im, parsing_anno, stride, save_im=False, save_path='vis_results/parsing_map_on_im.jpg'):
    part_colors = [[255, 0, 0], [255, 85, 0], [255, 170, 0],
                   [255, 0, 85], [255, 0, 170],
                   [0, 255, 0], [85, 255, 0], [170, 255, 0],
                   [0, 255, 85], [0, 255, 170],
                   [0, 0, 255], [85, 0, 255], [170, 0, 255],
                   [0, 85, 255], [0, 170, 255],
                   [255, 255, 0], [255, 255, 85], [255, 255, 170],
                   [255, 0, 255], [255, 85, 255], [255, 170, 255],
                   [0, 255, 255], [85, 255, 255], [170, 255, 255]]

    im = np.array(im)
    vis_im = im.copy().astype(np.uint8)
    vis_parsing_anno = parsing_anno.copy().astype(np.uint8)
    vis_parsing_anno = cv2.resize(vis_parsing_anno, None, fx=stride, fy=stride, interpolation=cv2.INTER_NEAREST)
    vis_parsing_anno_color = np.zeros((vis_parsing_anno.shape[0], vis_parsing_anno.shape[1], 3)) + 255

    num_of_class = np.max(vis_parsing_anno)

    for pi in range(1, num_of_class + 1):
        index = np.where(vis_parsing_anno == pi)
        vis_parsing_anno_color[index[0], index[1], :] = part_colors[pi]

    vis_parsing_anno_color = vis_parsing_anno_color.astype(np.uint8)
    vis_im = cv2.addWeighted(cv2.cvtColor(vis_im, cv2.COLOR_RGB2BGR), 0.4, vis_parsing_anno_color, 0.6, 0)

    if save_im:
        mask_save_path = save_path.replace('.jpg', '.png')
        cv2.imwrite(mask_save_path, vis_parsing_anno)
        cv2.imwrite(save_path, vis_im, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        print(f"[VIS] Saved mask: {mask_save_path}")
        print(f"[VIS] Saved visualization: {save_path}")

    return vis_im


def process_single_image(input_path: str, output_dir: str):
    """Обрабатывает одно изображение"""
    print(f"[FACEPARSING] Processing image: {input_path}")
    os.makedirs(output_dir, exist_ok=True)

    try:
        n_classes = 19
        net = BiSeNet(n_classes=n_classes)
        device = torch.device('cpu')
        net.to(device)

        save_pth = osp.join('res/cp', '79999_iter.pth')
        if not os.path.exists(save_pth):
            raise FileNotFoundError(f"Model not found: {save_pth}")

        net.load_state_dict(torch.load(save_pth, map_location=device))
        net.eval()

        to_tensor = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ])

        img = Image.open(input_path).convert("RGB")
        image = img.resize((512, 512), Image.BILINEAR)
        img_tensor = to_tensor(image).unsqueeze(0).to(device)

        with torch.no_grad():
            out = net(img_tensor)[0]
            parsing = out.squeeze(0).cpu().numpy().argmax(0)

        print(f"[FACEPARSING] Unique labels found: {np.unique(parsing)}")

        vis_path = osp.join(output_dir, 'parsing_map_on_im.jpg')
        mask_path = osp.join(output_dir, 'parsing_map.png')

        vis_parsing_maps(image, parsing, stride=1, save_im=True, save_path=vis_path)

        print(f"[FACEPARSING]  Done. Mask: {mask_path}")
        return mask_path

    except Exception as e:
        print(f"[FACEPARSING] ❌ Error: {str(e)}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output_dir", required=True)
    args = parser.parse_args()

    mask_path = process_single_image(args.input, args.output_dir)
    print(f" Segment done. Mask saved: {mask_path}")
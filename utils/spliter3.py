import os
import time
import numpy as np
import cv2
from matplotlib import pyplot as plt
from settings import MAIN_DIR


min_x, max_x = 45,125

def char_spliter(fn):
    img = cv2.imread(fn,0)
    img = cv2.medianBlur(img, 5)
    img[img > 130] = 255
    x, y = img.shape
    split_lines = [i for i in range(y) if np.array_equal(np.ones((x, ))*255, img[:, i])]
    for i in split_lines:
        img[:, i] = 0
    # plt.imshow(img)
    # plt.show()
    # разобьем на монотонные участки
    sides, min_y, max_y = [], 0, 0
    for j in range(y):
        if j in split_lines:
            max_y = j
        else:
            if min_y == max_y:
                min_y, max_y = [j]*2
                continue
            sides.append([min_y, max_y])
            min_y, max_y = j, j
    if min_y != max_y:
        sides.append([min_y, max_y])
    # сольем близкие монотонные отрезки
    new_sides = []
    for i in range(len(sides)-1):
        if sides[i+1][0] - sides[i][1] < 10:
            new_sides.append([sides[i][0], sides[i+1][1]])
        else:
            new_sides.append([sides[i][0], sides[i][1]])
    new_sides.append([sides[-1][0], sides[-1][1]])
    #print(len(new_sides))
    sides = new_sides
    img = cv2.imread(fn, 0)
    img[img > 130] = 255

    chars = []
    for i in range(len(sides) - 1):
        x1, y1, x2, y2 = min_x, sides[i][1], max_x, sides[i + 1][0]
        x1, y1, x2, y2 = x1 + 5, y1 + 5, x2 + 5, y2 + 5
        char = img[x1:x2, y1:y2]
        chars.append(char)
    for i in range(len(chars)):
        cv2.imwrite(f'{MAIN_DIR}/captcha/symbols/{i}.jpg', chars[i])

    #img = cv2.medianBlur(img, 3)
    # for i in range(len(sides)-1):
    #     x1, y1, x2, y2 = min_x, sides[i][1],  max_x, sides[i+1][0]
    #     img[x1:x2, y1], img[x1:x2, y2], img[x1, y1:y2], img[x2, y1:y2]  = [0]*4
    # plt.imshow(img)
    # plt.show()
    chars = []
    for i in range(len(sides)-1):
        x1, y1, x2, y2 = min_x, sides[i][1],  max_x, sides[i+1][0]
        x1, y1, x2, y2 = x1+5, y1+5, x2+5, y2+5
        char = img[x1:x2, y1:y2]
        chars.append(char)
    return chars

if __name__ == '__main__':

    for fn in os.listdir('captcha')[20:]:
        name = fn.split('.')[0]
        fn = f'{MAIN_DIR}/captcha/{fn}'
        chars = char_spliter(fn)
        for i, char in enumerate(chars):
            cv2.imwrite(f'{name}_{i}.jpg', char)

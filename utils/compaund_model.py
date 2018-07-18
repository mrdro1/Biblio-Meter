import os
import traceback
import shutil
import sys, traceback, logging
#
import cv2
from matplotlib import pyplot as plt
#
import spliter3
import cnn
from settings import print_message, LOG_LEVEL

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

# >6 and [r, t]n => m

# TODO:
# Причесать код solver'а!!!
# 

model = cnn.load_pipeline()


#def load_class_dict():
#    class_dict = dict()
#    for i, class_name in enumerate(os.listdir('captcha\\tmp')):
#        # class_name = fn.split('.')[0]
#        class_dict[i] = class_name
#    return class_dict

class_dict = [s for s in "abcdefghiklmnopqrstuvwxyz"]#load_class_dict()

def del_from_temp():
    len_for_del = len(os.listdir('captcha\\tmp'))
    for fn in os.listdir('captcha\\tmp'):
        fn = f'captcha\\tmp\\{fn}'
        os.remove(fn)
    return len_for_del


def load_chars():
    for fn in os.listdir('captcha\\tmp'):
        try:
            fn = f'captcha\\tmp\\{fn}'
            x = cv2.imread(fn)
            x = cnn.add_padding(x, rgb=True)
            x.astype('float32')
            x = x / 255.
            #x = cv2.resize(x, (100, 100), interpolation=cv2.INTER_NEAREST)
            x = x.reshape((1,) + x.shape)
            yield x
        except:
            #print(traceback.format_exc())
            continue


def predict_imgs(fns):
    cc = len(fns)
    for kk, fn in enumerate(fns):
        chars = spliter3.char_spliter(fn)
        del_from_temp()
        for i in range(len(chars)):
            cv2.imwrite(f'captcha\\tmp\\{i}.jpg', chars[i])
        ans_list = []
        for char in load_chars():
            ans = class_dict[model.predict_classes(char)[0]]
            ans_list.append(ans)
        ans = ''.join(ans_list)
        shutil.copyfile(fn, f'captcha\\nn_ans\\{ans}.jpg')
        # for ans, char in zip(ans_list, chars):
        #     i = len(os.listdir('nn_ans'))
        #     cv2.imwrite(f'nn_ans\\{ans}_{i}.jpg', char)
        #print(f'{kk}/{cc}')
        # img = cv2.imread(fn)
        # plt.imshow(img)
        # plt.show()


def solve(captcha_file_name):
    logger.debug("Split captcha img '{}'.".format(captcha_file_name))
    chars = spliter3.char_spliter(captcha_file_name)
    del_from_temp()
    logger.debug("Save symbols to disk.")
    for i in range(len(chars)):
        cv2.imwrite(f'captcha\\tmp\\{i}.jpg', chars[i])
    ans_list = []
    logger.debug("Predict classes by CNN (response captcha).")
    for i, char in enumerate(load_chars()):
        ans = class_dict[model.predict_classes(char)[0]]
        ans_list.append(ans)
    answer = ''.join(ans_list)
    logger.debug("CNN answer: {}.".format(answer))
    #print_message(''.join(ans_list))
    #img = cv2.imread(captcha_file_name)
    #plt.imshow(img)
    #plt.show()
    return answer
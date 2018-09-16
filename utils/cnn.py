import os
import shutil
import random
#
import cv2
from keras.preprocessing.image import ImageDataGenerator
from keras.models import Sequential, model_from_json
from keras.layers import Conv2D, MaxPooling2D
from keras.layers import Activation, Dropout, Flatten, Dense
from keras.callbacks import TerminateOnNaN, ModelCheckpoint
#
from settings import print_message, MAIN_DIR

# 1 save models after each step
# 2 fit => labeling => check => hard mining for validation\\


def save_pipeline(model):
    BASE_DIR = '/model'
    # RNN
    model_json = model.to_json()
    with open(f"{MAIN_DIR}{BASE_DIR}\\cnn.json", "w") as json_file:
        json_file.write(model_json)
    model.save_weights(f"{MAIN_DIR}{BASE_DIR}\\cnn.h5")
    print_message("Saved CNN model to disk.")
    return 0


def load_pipeline():
    BASE_DIR = '/model'
    # CNN
    json_file = open(f'{MAIN_DIR}{BASE_DIR}/cnn.json', 'r')
    loaded_model_json = json_file.read()
    json_file.close()
    loaded_model = model_from_json(loaded_model_json)
    # loaded_model.load_weights(f'{MAIN_DIR}{BASE_DIR}/cnn.h5')
    loaded_model.load_weights(f'{MAIN_DIR}{BASE_DIR}/weights.hdf5')
    loaded_model.compile(
        loss='categorical_crossentropy',
        optimizer='rmsprop',
        metrics=['accuracy'])
    print_message("Loaded CNN model from disk.")
    return loaded_model


def create_dataset(count_img_on_class=40):
    datagen = ImageDataGenerator(
        rotation_range=20,
        width_shift_range=0.1,
        height_shift_range=0.1,
        shear_range=0.2,
        zoom_range=0.1,
        horizontal_flip=False,
        fill_mode='nearest')
    for fn in os.listdir('gold'):
        class_name = fn.split('.')[0]
        fn = f'{MAIN_DIR}\\gold\\{fn}'
        # img = load_img('data/train/cats/cat.0.jpg')  # this is a PIL image
        # img_to_array(img)  # this is a Numpy array with shape (3, 150, 150)
        x = cv2.imread(fn)
        # this is a Numpy array with shape (1, 3, 150, 150)
        x = x.reshape((1,) + x.shape)
        if not os.path.exists(f'{MAIN_DIR}\\train\\{class_name}'):
            os.mkdir(f'{MAIN_DIR}\\train\\{class_name}')
        # the .flow() command below generates batches of randomly transformed images
        # and saves the results to the `preview/` directory
        i = 0
        for batch in datagen.flow(x, batch_size=1,
                                  save_to_dir=f'{MAIN_DIR}\\train\\{class_name}', save_prefix=class_name, save_format='jpg'):
            i += 1
            if i > count_img_on_class:
                break


def create_validate():
    for dir in os.listdir('{MAIN_DIR}\\train'):
        #fns = [random.choice() for i in range(10)]
        for fn in os.listdir(f'{MAIN_DIR}\\train\\{dir}')[:10]:
            class_name = dir
            if not os.path.exists(f'{MAIN_DIR}\\validat\\{class_name}'):
                os.mkdir(f'{MAIN_DIR}\\validat\\{class_name}')
            to_fn = f'{MAIN_DIR}\\validat\\{class_name}\\{fn}'
            shutil.copyfile(f'{MAIN_DIR}\\train\\{class_name}\\{fn}', to_fn)
            os.remove(f'{MAIN_DIR}\\train\\{class_name}\\{fn}')


def add_padding(img, ts=(100, 100), rgb=False):
    if rgb:
        x, y, z = img.shape
    else:
        x, y = img.shape
    dx = ts[0] - x
    dy = ts[1] - y
    if dx < 0 or dy < 0:
        startx = x // 2 - (ts[0] // 2)
        if startx < 0:
            startx = 0
        starty = y // 2 - (ts[1] // 2)
        if starty < 0:
            starty = 0
        img = img[startx:startx + ts[0], starty:starty + ts[1]]
        if rgb:
            x, y, z = img.shape
        else:
            x, y = img.shape
        dx = ts[0] - x
        dy = ts[1] - y

    if rgb:
        WHITE = [255] * 3
    else:
        WHITE = [255]
    constant = cv2.copyMakeBorder(
        img, dx, 0, 0, dy, cv2.BORDER_CONSTANT, value=WHITE)
    return constant


def convert_ds_to_gray_scale():
    for dir in os.listdir('{MAIN_DIR}\\train'):
        for fn in os.listdir(f'{MAIN_DIR}\\train\\{dir}'):
            fn = f'{MAIN_DIR}\\train\\{dir}\\{fn}'
            # convert_to_target_size(fn)
            img = cv2.imread(fn, 0)
            img = add_padding(img)
            if img.shape != (100, 100):
                print(fn)
            #img[img == 0] = 255
            #img = cv2.medianBlur(img, 3)
            cv2.imwrite(fn, img)


def train_cnn():

    shape = [100, 100]
    model = Sequential()
    model.add(Conv2D(32, (3, 3), input_shape=(shape[0], shape[1], 3)))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))

    model.add(Conv2D(32, (3, 3)))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))

    model.add(Conv2D(64, (3, 3)))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))

    # this converts our 3D feature maps to 1D feature vectors
    model.add(Flatten())
    model.add(Dense(100))
    model.add(Activation('relu'))
    model.add(Dropout(0.25))
    model.add(Dense(25))
    model.add(Activation('sigmoid'))

    model.compile(loss='categorical_crossentropy',
                  optimizer='rmsprop',
                  metrics=['accuracy'])

    # model.predict_classes()
    batch_size = 16

    # this is the augmentation configuration we will use for training
    train_datagen = ImageDataGenerator(
        rescale=1. / 255,
        shear_range=0.2,
        zoom_range=0.2,
        horizontal_flip=False)

    # this is the augmentation configuration we will use for testing:
    # only rescaling
    test_datagen = ImageDataGenerator(rescale=1. / 255)

    # this is a generator that will read pictures found in
    # subfolers of 'data/train', and indefinitely generate
    # batches of augmented image data
    train_generator = train_datagen.flow_from_directory(
        'train',  # this is the target directory
        # all images will be resized to 150x150
        target_size=(shape[0], shape[1]),
        batch_size=batch_size,
        class_mode='categorical')  # since we use binary_crossentropy loss, we need binary labels

    # # this is a similar generator, for validation data
    validation_generator = test_datagen.flow_from_directory(
        'validat',
        target_size=(shape[0], shape[1]),
        batch_size=batch_size,
        class_mode='categorical')
    checkpointer = ModelCheckpoint(
        filepath='model/weights.hdf5',
        verbose=1,
        save_best_only=True)
    model.fit_generator(
        train_generator,
        steps_per_epoch=7326 // batch_size,
        epochs=20, callbacks=[TerminateOnNaN(), checkpointer],
        validation_data=validation_generator,
        validation_steps=250 // batch_size)
    save_pipeline(model)
    # model.save_weights('first_try.h5')


def get_count_samples(dir='train'):
    for sub_dir in os.listdir(dir):
        class_name = sub_dir
        count_samples = len(os.listdir(f'{dir}\\{sub_dir}'))
        print(class_name, count_samples)


if __name__ == '__main__':
    # create_dataset(25)
    # convert_ds_to_gray_scale()
    # create_validate()
    train_cnn()
    # get_count_samples()

import pandas as pd
import scipy.stats as stats
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
import tensorflow as tf
from tensorflow.keras import Sequential
from tensorflow.keras.layers import Flatten, Dense, Dropout, BatchNormalization
from tensorflow.keras.layers import Conv2D, MaxPool2D
from tensorflow.keras.optimizers import Adam
from sklearn.datasets import make_blobs
from sklearn.preprocessing import MinMaxScaler
from sklearn.utils import shuffle
import matplotlib.pyplot as plt
from mlxtend.plotting import plot_confusion_matrix
from sklearn.metrics import confusion_matrix
frames_list=[]

def plot_activity(activity, data):

    fig, (ax0, ax1, ax2) = plt.subplots(nrows=3, figsize=(15, 7), sharex=True)
    plot_axis(ax0, data['acc_timestamp'], data['acc_x'], 'X-Axis')
    plot_axis(ax1, data['acc_timestamp'], data['acc_y'], 'Y-Axis')
    plot_axis(ax2, data['acc_timestamp'], data['acc_z'], 'Z-Axis')
    plt.subplots_adjust(hspace=0.2)
    fig.suptitle(activity + (' Accelerometer'))
    plt.subplots_adjust(top=0.90)
    plt.show()

def plot_axis(ax, x, y, title):
    ax.plot(x, y, 'g')
    ax.set_title(title)
    ax.xaxis.set_visible(False)
    ax.set_ylim([min(y) - np.std(y), max(y) + np.std(y)])
    ax.set_xlim([min(x), max(x)])
    ax.grid(True)

    
print(tf.__version__)
file = open('Dataset.txt')
lines = file.readlines()

processedList = []

for i, line in enumerate(lines):
    try:
        line = line.split(';')
        last = line[9].split(';')[0]
        last = last.strip()
        if last == '':
            break;
        temp = [line[0], line[1], line[2], line[3], line[4], line[5], line[6], line[7],line[8], last]
        #temp = line[0]+';' +'Activity'+';' + line[1]+';'+ line[2]+';'+ line[3]+';'+ line[4]+';'+ line[5]+';'+ line[6]+';'+ line[7]+';'+last+'\n'
        processedList.append(temp)
    except:
        print('Error at line number: ', i)
        #Creaiamo un Dataframe
columns = ['user','activity','acc_timestamp', 'acc_x', 'acc_y', 'acc_z', 'gy_timestamp', 'gy_x', 'gy_y', 'gy_z']
data = pd.DataFrame(data = processedList, columns = columns)
data.head()
data['acc_x'] = data['acc_x'].astype('float')
data['acc_y'] = data['acc_y'].astype('float')
data['acc_z'] = data['acc_z'].astype('float')
data['gy_x'] = data['gy_x'].astype('float')
data['gy_y'] = data['gy_y'].astype('float')
data['gy_z'] = data['gy_z'].astype('float')
#rimuoviamo user e timestamps
df = data.drop(['user','acc_timestamp', 'gy_timestamp'], axis = 1).copy()


Walking = df[df['activity']=='Walking'].head(7519).copy()
Still = df[df['activity']=='Still'].head(7519).copy()
Running = df[df['activity']=='Running'].head(7519).copy()


balanced_data = pd.DataFrame()
balanced_data = balanced_data.append([Walking, Still, Running])

#trasformiamo le activity in labels 
label = LabelEncoder()
balanced_data['label'] = label.fit_transform(balanced_data['activity'])
balanced_data.head()


X = balanced_data[['acc_x', 'acc_y', 'acc_z', 'gy_x', 'gy_y', 'gy_z']]
y = balanced_data['label']

#x_test_copy= balanced_data[['x', 'y', 'z']]
#x_walking =x_test_copy.head(3555)

scaler = StandardScaler()
scaler.fit(X)
X=scaler.transform(X)
scaled_X = pd.DataFrame(data = X, columns = ['acc_x', 'acc_y', 'acc_z', 'gy_x', 'gy_y','gy_z'])
scaled_X['label'] = y.values
scaled_X.head()


Fs = 20
frame_size = Fs*4 # 80
hop_size = Fs*2 # 40

def get_frames(df, frame_size, hop_size):

    N_FEATURES = 6

    frames = []
    labels = []
    for i in range(0, len(df) - frame_size, hop_size):
        acc_x = df['acc_x'].values[i: i + frame_size]
        acc_y = df['acc_y'].values[i: i + frame_size]
        acc_z = df['acc_z'].values[i: i + frame_size]
        gy_x = df['gy_x'].values[i: i + frame_size]
        gy_y = df['gy_y'].values[i: i + frame_size]
        gy_z = df['gy_z'].values[i: i + frame_size]
        
        # Retrieve the most often used label in this segment
        label = stats.mode(df['label'][i: i + frame_size])[0][0]
        frames.append([acc_x, acc_y, acc_z, gy_z, gy_y, gy_z])
        labels.append(label)

    # Bring the segments into a better shape
    frames = np.asarray(frames).reshape(-1, frame_size, N_FEATURES)
    labels = np.asarray(labels)

    return frames, labels

X, y = get_frames(scaled_X, frame_size, hop_size)

X.shape, y.shape
X, y = shuffle(X, y, random_state=0)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size = 0.2, random_state = 0, stratify = y)
x_train_bf = X_train
X_train = X_train.reshape(len(X_train), 80, 6, 1)
X_test = X_test.reshape(len(X_test), 80, 6, 1)
#Creiamo il modello e aggiungiamoci i layers

model = Sequential()
model.add(Conv2D(16, (2, 2), activation = 'relu', input_shape = X_train[0].shape))
model.add(Dropout(0.1))

model.add(Conv2D(32, (2, 2), activation='relu'))
model.add(Dropout(0.2))

model.add(Flatten())

model.add(Dense(64, activation = 'relu'))
model.add(Dropout(0.5))

model.add(Dense(6, activation='softmax'))


#Comilazone del modello e test

model.compile(optimizer=Adam(learning_rate = 0.001), loss = 'sparse_categorical_crossentropy', metrics = ['accuracy'])
history = model.fit(X_train, y_train, epochs = 10, validation_data= (X_test, y_test), verbose=1)

y_pred = model.predict_classes(X_test)
mat = confusion_matrix(y_test, y_pred)
plot_confusion_matrix(conf_mat=mat, class_names=label.classes_, show_normed=False, figsize=(4,4))

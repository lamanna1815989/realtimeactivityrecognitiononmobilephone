print('Ciao')
from datetime import datetime
import socketio
import asyncio
import socketio
import nest_asyncio
from threading import Thread
from confluent_kafka import Consumer, Producer
from confluent_kafka import KafkaError, KafkaException
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
import shutup;
shutup.please()

model = tf.keras.models.load_model('saved_model/my_model')
print('model loaded')
sio = socketio.AsyncClient(ssl_verify=False)
topics = ['sensor_data']
conf = {'bootstrap.servers': 'localhost:9091,localhost:9092',
        'group.id': "my-app",
        'client.id' : "my-app",
        'enable.auto.commit': True,
        'auto.offset.reset': 'earliest'
        }

consumer = Consumer(conf)
running = True
prediction_sockets = {}
prediction_sockets_index = {}
training_sockets = {}


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
async def basic_consume_loop(consumer, topics):
            print('consumer loop stared\n')
            
            try:
                consumer.subscribe(topics)
                while running:
                    msg = consumer.poll(timeout=100.0)
                    if msg is None: continue
        
                    if msg.error():
                        if msg.error().code() == KafkaError._PARTITION_EOF:
                            # End of partition event
                            sys.stderr.write('%% %s [%d] reached end at offset %d\n' %
                                             (msg.topic(), msg.partition(), msg.offset()))
                    else:
                        #print('msg')
                        msg_process(msg)
            finally:
                # Close down consumer to commit final offsets.
                consumer.close()

def msg_process(msg):
    #[socketid, acc_time;acc_x;acc_y;acc_z;gy_time;gy_x;gy_y;gy_z] per prediction
    #[socketid,activity,acc_time;acc_x;acc_y;acc_z;gy_time;gy_x;gy_y;gy_z] per prediction
    
    tmp= msg.value().decode().split(';');
    socketid= tmp[0]
    tmp2=tmp[1:]
    if(socketid in prediction_sockets.keys()):
        prediction_sockets[socketid].append(tmp2)
    if(socketid in training_sockets.keys()):
        training_sockets[socketid].append(tmp2)
    
async def prediction_loop():
    print('prediction loop started\n')    
    while True:
        for key in list(prediction_sockets):
            try:
                if len(prediction_sockets[key])>=prediction_sockets_index[key] + 80:
                    window = prediction_sockets[key][prediction_sockets_index[key]:prediction_sockets_index[key]+80]
                    result = await make_prediction(window)
                    activit:''
                    if(result==0):
                        activit='Running'
                    elif(result==1):
                        activit='Still'
                    else:
                        activit='Walking'
                    await sio.emit('prediction',{'socketid':str(key), 'result': activit} )
                    print('Socket id: '+str(key)+' Attività: '+  str(activit)+'\n\n\n\n\n')
                    prediction_sockets_index[key]+=40
            except KeyError:
                print('')

async def make_prediction(window):
    frames=[]
    for line in window:
        frames.append([float(line[1]),float(line[2]),float(line[3]),float(line[5]),float(line[6]),float(line[7])])
    frames = np.asarray(frames).reshape(-1, 80, 6)
   
    re_frames = frames.reshape(len(frames),80,6,1)
    return model.predict_classes(re_frames)
    
connected_clients=[];
@sio.event
async def connect():
    connected=True;
    print('connected')

@sio.event
async def disconnect():
    print('disconnected')

@sio.event
async def newclientconnected(data):
    if(data[0]=='predict_activity'):
        prediction_sockets[data[1]]=[]
        prediction_sockets_index[data[1]]=0
    elif (data[0]=='training'):
        training_sockets[data[1]]=[]
        print('--------still')
    print('New client connected!' + str(data[1]) + ' activity type: ' + str(data[0])) 
    print('Prediction clients connected: ' + str(prediction_sockets.keys()) + ' Training Clients Connected: ' + str(training_sockets.keys()))

@sio.event
async def clientdisconnected(data):
    if(data[0]=='predict_activity'):
        prediction_sockets.pop(data[1])
        prediction_sockets_index.pop(data[1])
    elif (data[0]=='training'):
        training_sockets.pop(data[1])
    print('Client disconnected !' + str(data[1]))
    print('Prediction clients connected: ' + str(prediction_sockets.keys()) + ' Training Clients Connected: ' + str(training_sockets.keys()))

@sio.event
async def training_request_from_socket(data):
    print('Training request received from socket: ' + data)
    await training(data)
    
def basic_consumer_loop_NewThread():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(basic_consume_loop(consumer, topics))

def prediction_loop_NewThread():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(prediction_loop())

async def training(socketid):
    training_list = training_sockets[socketid]

    columns = ['activity','acc_timestamp', 'acc_x', 'acc_y', 'acc_z', 'gy_timestamp', 'gy_x', 'gy_y', 'gy_z']
    data = pd.DataFrame(data = training_list, columns = columns)
    data['acc_x'] = data['acc_x'].astype('float')
    data['acc_y'] = data['acc_y'].astype('float')
    data['acc_z'] = data['acc_z'].astype('float')
    data['gy_x'] = data['gy_x'].astype('float')
    data['gy_y'] = data['gy_y'].astype('float')
    data['gy_z'] = data['gy_z'].astype('float')
    df = data.drop(['acc_timestamp', 'gy_timestamp'], axis = 1).copy()
    print (len(df['activity'].value_counts().tolist()), '')
    if(len(df['activity'].value_counts().tolist())<3 or min(df['activity'].value_counts().tolist())<600):
        print('ci servono valori per tutte le classi, ed almeno 600 per ogni classe per effettuare il training')
        await sio.emit('training_res',{'socketid':str(socketid), 'msg': 'Per effettuare il training servono almeno 600 misurazioni per ogni classe, quindi 30 secondi per ciascuna attività'} )
        return;
    print(df['activity'].value_counts().tolist())
    min_value = min(df['activity'].value_counts().tolist())
    print('Training dataset on ', min_value, ' new values')
    Walking = df[df['activity']=='Walking'].head(min_value).copy()
    Still = df[df['activity']=='Still'].head(min_value).copy()
    Running = df[df['activity']=='Running'].head(min_value).copy()
    balanced_data = pd.DataFrame()
    balanced_data = balanced_data.append([Walking, Still, Running])
    label = LabelEncoder()
    balanced_data['label'] = label.fit_transform(balanced_data['activity'])
    X = balanced_data[['acc_x', 'acc_y', 'acc_z', 'gy_x', 'gy_y', 'gy_z']]
    y = balanced_data['label']
    scaler = StandardScaler()
    scaler.fit(X)
    X=scaler.transform(X)
    scaled_X = pd.DataFrame(data = X, columns = ['acc_x', 'acc_y', 'acc_z', 'gy_x', 'gy_y','gy_z'])
    scaled_X['label'] = y.values
    Fs = 20
    frame_size = Fs*4 # 80
    hop_size = Fs*2 # 40

    X, y = get_frames(scaled_X, frame_size, hop_size)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size = 0.2, random_state = 0, stratify = y)
    x_train_bf = X_train
    X_train = X_train.reshape(len(X_train), 80, 6, 1)
    X_test = X_test.reshape(len(X_test), 80, 6, 1)
    model.compile(optimizer=Adam(learning_rate = 0.0005), loss = 'sparse_categorical_crossentropy', metrics = ['accuracy'])
    history = model.fit(X_train, y_train, epochs = 10, validation_data= (X_test, y_test), verbose=1)
    await sio.emit('training_res',{'socketid':str(socketid), 'msg': 'Training completato!'} )

    await sio.emit('training_res', 'Training completato!')

    return balanced_data

             
async def main():
    await sio.connect('https://IP:PORT' + '?data=pythonclient')
    t = Thread(target=basic_consumer_loop_NewThread, args=())
    t.start()
    t2 = Thread(target= prediction_loop_NewThread, args=())
    t2.start()


    await sio.wait()
    
asyncio.run(main())


print('prova')

def shutdown():
    running = False
    

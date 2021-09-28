const express = require('express');
const app = express();
const https = require('https');
const fs = require('fs')
const path = require('path')
const { Kafka } = require("kafkajs")
const server = https.createServer({
  key: fs.readFileSync(path.join(__dirname, 'cert', 'code.key')),
  cert: fs.readFileSync(path.join(__dirname, 'cert', 'code.crt')),
},app);
const { Server } = require("socket.io");
const { type } = require('os');
const io = new Server(server, {origins: '*:*'});
const port = process.env.PORT || 3000;

// we can define the list of brokers in the cluster
const brokers = ["localhost:9092"]
const clientId = "my-app"

// initialize a new kafka client and initialize a producer from it
const kafka = new Kafka({ clientId, brokers })
const producer = kafka.producer();

const connectproduce = async () => {
	await producer.connect()
}
const produce = async (topic, msg) => {
		try {
			await producer.send({
				topic,
				messages: [
					{
						key: msg.id + ":" + topic,
						value: msg.id.toString() + ';' + msg.acc_timestamp.toString() + ";"+ msg.acc_x.toString()+";"+ msg.acc_y.toString()+";"+ msg.acc_z.toString()+';'+msg.gy_timestamp.toString() + ";"+ msg.gy_x.toString()+";"+ msg.gy_y.toString()+";"+ msg.gy_z.toString()
					},
				],
			})

		} catch (err) {
			console.error("could not write message " + err)
		}

}
const produce_train = async (topic, msg) => {
  try {
    await producer.send({
      topic,
      messages: [
        {
          key: msg.id + ":" + topic,
          value: msg.id.toString() + ';'+msg.activity.toString()+';' + msg.acc_timestamp.toString() + ";"+ msg.acc_x.toString()+";"+ msg.acc_y.toString()+";"+ msg.acc_z.toString()+';'+msg.gy_timestamp.toString() + ";"+ msg.gy_x.toString()+";"+ msg.gy_y.toString()+";"+ msg.gy_z.toString()
        },
      ],
    })

  } catch (err) {
    console.error("could not write message " + err)
  }

}

app.get('/', (req, res) => {
  res.sendFile(__dirname + "/html/home.html");
});
app.post('/edge_index', (req, res) => {
    res.sendFile(__dirname + "/html/edge_index.html");
  });
app.get('/train_model', (req, res) => {
    res.sendFile(__dirname + "/html/train_model.html");
  });
  


//gestione connessioni messaging
//connessione al producer kafka
let connectedsockets=[];
let nconnected =0;
connectproduce().then(()=>{

io.on('connection', (socket) => {//ogni connessione che riceviamo ha un socket.id diverso
  //console.log(typeof(socket.id))
  if (socket.handshake.query.data=='pythonclient'){
    console.log('python client connected')
    pythonsocketid=socket.id;
    //mettiamoci in ascolto di eventuali previsioni in ingresso
    socket.on('prediction', (msg)=>{
      io.to(msg.socketid).emit('predicted_activity', {'result' : msg.result.toString()})
        console.log('True   ', msg.socketid , '   ', typeof(msg.socketid) )
      console.log(msg.socketid, ' ', msg.result);
    });
    socket.on('training_res', (msg)=>{
      io.to(msg.socketid).emit('training_result', {'result' : msg.msg.toString()})
      console.log(msg.socketid, ' ', msg.msg);
    })
  
  }
  else {
    console.log(socket.handshake.query.data);
    data=[socket.handshake.query.data, socket.id]
    let thissocket = [socket.id];
    socket.broadcast.emit('newclientconnected', data);
    nconnected++;
    connectedsockets.push(thissocket);  
    socket.on('disconnect', () => {
      //rimuovi il socket.id
    connectedsockets = connectedsockets.filter(obj => obj[0]!=socket.id);
    nconnected--; 
    data=[socket.handshake.query.data, socket.id]
    socket.broadcast.emit('clientdisconnected', data);
    console.log('numero di socket connessi: ', nconnected.toString(), 'vettore connectedsockets: ' , connectedsockets.toString());
    console.log(socket.id.toString() + ' disconnected');
  });
    if(socket.handshake.query.data=='predict_activity'){    
    socket.on('accelerometer_gyroscope_client', (msg) => {//ora qui dobbiamo inviare alla dashboard il messaggio ricevuto + il socket id 
      let newmsg = {
        id : socket.id,
        acc_timestamp : msg.a_timestamp,
        gy_timestamp : msg.gy_timestamp,
        id : socket.id,
        acc_x : msg.a_x,
        acc_y : msg.a_y,
        acc_z : msg.a_z,
        gy_x:msg.gy_x,
        gy_y: msg.gy_y,
        gy_z: msg.gy_z
     }
     // console.log('timestampacc: ', msg.a_timestamp, ' timestamp_gy: ', msg.gy_timestamp , 'acc_x', msg.a_x, 'y', msg.a_y)
      produce("sensor_data", newmsg).then(()=>{});
  });
 }
  if(socket.handshake.query.data=='training'){
    console.log('training socket connected');
    socket.on('accelerometer_gyroscope_client_training', (msg) => { 
      let newmsg = {
        id : socket.id,
        activity: msg.activity,
        acc_timestamp : msg.a_timestamp,
        gy_timestamp : msg.gy_timestamp,
        acc_x : msg.a_x,
        acc_y : msg.a_y,
        acc_z : msg.a_z,
        gy_x:msg.gy_x,
        gy_y: msg.gy_y,
        gy_z: msg.gy_z
     }

     produce_train('sensor_data',newmsg)
     

  });
  socket.on('training_request',()=>{
    console.log('training request received from socket: ', socket.id)
    socket.broadcast.emit('training_request_from_socket', socket.id)
  })
  }

  

  }})
})


//listen serever
server.listen(port , () => {
  console.log('listening on *:' + port);
});

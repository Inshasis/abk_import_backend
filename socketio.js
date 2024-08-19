const path = require('path');
const express = require('express');
const app = express();
const server = require('http').Server(app);
const io = require('socket.io')(server);


const { get_redis_subscriber } = require('../frappe/node_utils');
const subscriber = get_redis_subscriber();

const userMap = {};
const connectedUsers = {};

app.use('/test', express.static(path.join(__dirname, './client')));

const FrappeApp = require('frappe-js-sdk').FrappeApp;

const frappe = new FrappeApp('http://salesapp.akhilaminc.com/', {
	useToken: true,
	// Pass a custom function that returns the token as a string - this could be fetched from LocalStorage or auth providers like Firebase, Auth0 etc.
	token: function () {
		return "cd85f8160843c68:5b5c8ff7858680a"
	},
	// This can be "Bearer" or "token"
	type: "token"
});

const db = frappe.db();
const call = frappe.call();


server.listen(9002, function () {
	//Add your Frappe backend's URL


	console.log('listening on *:', 9002);

	// Listen to events emmited by the clients
	io.on('connection', function (socket) {
		console.log('connection :', socket.id, socket.handshake.query.user_id);

		/** Get Rooms and join socket */
		db.getDocList('Chat Room', {
			/** Fields to be fetched */
			fields: ['name'],
			/** Filters to be applied - SQL AND operation */
			filters: [['members', 'like', "%" + socket.handshake.query.user_id + "%"]],
			/** Fetch documents as a dictionary */
			asDict: true,
		})
			.then((docs) => {
				docs.forEach((e) => socket.join(e.name));
			})
			.catch((error) => console.error(error));

		socket.emit('msgprint', {
			"message": "Sample Data Response"
		});

		socket.on('disconnect', (data) => {
			socket.leaveAll();
			socket.disconnect();
		});

		socket.on('sendMessage', async (data, ack) => {
			
			call
				.post('chat.api.message.send', data)
				.then((result) => ack(result.message))
				.catch((error) => console.error(error));
		});

		socket.on('getChatList', async (data, ack) => {

			var email = data.user;
			const searchParams = {
				email: email
			};
			call
				.get('chat.api.room.get', searchParams)
				.then((result) => ack(result.message))
				.catch((error) => console.error(error));
			// db.getDocList('Chat Room', {
			// 	/** Fields to be fetched */
			// 	fields: ['name', 'creation' , 'name as id', 'name as chat_id',                          
			//     'name as user_id',          
			//     'members',
			//     'last_message as message',
			//     'is_read',
			//     'type',
			//     'modified as time'],
			// 	/** Filters to be applied - SQL AND operation */
			// 	filters: [['members', 'like', "%"+ data.user + "%"]],
			// 	/** Sort results by field and order  */
			// 	orderBy: {
			// 	  field: 'creation',
			// 	  order: 'desc',
			// 	},
			// 	/** Fetch documents as a dictionary */
			// 	asDict: true,
			//   })
			// 	.then((docs) => {

			// 		docs.map(async (chat)=>{

			// 			var members = chat['members'].split(', ')
			// 			chat['room_name'] = email == members[1]  ? await get_full_name(
			// 				members[0]) : await get_full_name(members[1])
			// 			chat['opposite_person_email'] = members[1] == email ? members[0] : members[1]

			// 			return chat
			// 		})

			// 		ack(docs);
			// 	})
			// 	.catch((error) => console.error(error));
		});

		socket.on('getMessages', async (data, ack) => {
			console.log(data.room);
			db.getDocList('Chat Message', {
				/** Fields to be fetched */
				fields: ['name', 'creation', 'name as id', 'room as chat_id',
					'sender_email as sender_id',
					"sender as sender_name",
					'content as message',
					'creation'],
				/** Filters to be applied - SQL AND operation */
				filters: [['room', '=', data.room]],
				/** Filters to be applied - SQL OR operation */
				orFilters: [],
				/** Fetch from nth document in filtered and sorted list. Used for pagination  */
				// limit_start: 5,
				/** Number of documents to be fetched. Default is 20  */
				// limit: 10,
				/** Sort results by field and order  */
				orderBy: {
					field: 'creation',
					order: 'asc',
				},
				/** Fetch documents as a dictionary */
				asDict: true,
			})
				.then((docs) => {
					ack(docs);
				})
				.catch((error) => console.error(error));
		});
	});

});

async function get_full_name(member) {


} 

subscriber.subscribe('events');


// Listen to events emmited by frappe.publish_realtime
subscriber.on('message', function (channel, message, room) {
	console.log("MESSAGE", message);

	message = JSON.parse(message);
	if (message.room) {
		io.to(message.message.room).emit(message.event, message.message);
	} else {
		io.emit(message.event, message.message);
	}
});



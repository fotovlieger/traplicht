// WebSocket support
var targetUrl = `ws://${location.host}/ws`;
var websocket;
window.addEventListener("load", onLoad);

function onLoad() {
  initializeSocket();
}

function initializeSocket() {
  console.log("Opening WebSocket connection MicroPython Server...");
  websocket = new WebSocket(targetUrl);
  websocket.onopen = onOpen;
  websocket.onclose = onClose;
  websocket.onmessage = onMessage;
}
function onOpen(event) {
  console.log("Starting connection to WebSocket server..");
}
function onClose(event) {
  console.log("Closing connection to server..");
  setTimeout(initializeSocket, 2000);
}

function onMessage(event) {
  console.log("WebSocket message received:", event);
  const obj = JSON.parse(event.data);
  if (obj) {  updateValues(obj); }
}

function sendMessage(message) {
  console.log("WebSocket send: ", message);
  websocket.send(message);
}

function updateColor(obj, id) {
    const val = obj[id];
    const  rgb = val.split(',').map(function(num) {
      return parseInt(num);
    });
    if (rgb.length==3) {
      console.log ('upd',id, val);
      const but = document.getElementById(id);
      if (but) {
        but.jscolor.fromString(hexColor(rgb));
      }
    }
}

function updateMode(obj, id) {
    var container = document.getElementById("mode");
    var button = container.querySelector('input[value="' + obj[id] + '"]');
    if (button) {
      button.checked = true;
    }
}

function onSaveConfig() {
  var msg = {'saveConfig': 'true'};
  sendMessage(JSON.stringify(msg));
}

function onModeChanged(elt) {
  var radioButtons = elt.querySelectorAll('input[type="radio"]');
  var value = null;
  for (var i = 0; i < radioButtons.length; i++) {
    if (radioButtons[i].checked) {
      value = radioButtons[i].value;
      break;
    }
  }
  console.log (elt.id, value);
  var msg = {};
  msg[elt.id] = value;
  sendMessage(JSON.stringify(msg));
}

function hexColor(rgb) {
    return '#' + (
        ('0' + Math.round(rgb[0]).toString(16)).slice(-2) +
        ('0' + Math.round(rgb[1]).toString(16)).slice(-2) +
        ('0' + Math.round(rgb[2]).toString(16)).slice(-2)
    ).toUpperCase();
}

function onColor(but, tgt) {
  var msg = {};
  msg[tgt] = '' +
            Math.round(but.channels.r) + ',' +
			Math.round(but.channels.g) + ',' +
			Math.round(but.channels.b)
  sendMessage(JSON.stringify(msg));

  console.log (JSON.stringify(msg));
}

function updateField(obj, id) {
  if(id in obj) {
    var element = document.getElementById(id);
    console.log(id, obj[id], element);
    element.value = obj[id];
  }
}

function updateValues(obj) {
  if(obj['mode']) updateMode(obj, 'mode');
  if(obj['color']) updateColor(obj, 'color');
  
  updateField(obj, 'light');
  updateField(obj, 'mov');
  updateField(obj, 'movD');
  updateField(obj, 'on');
}

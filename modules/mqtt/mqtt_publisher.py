import paho.mqtt.client as mqtt
import json
from typing import Dict, Any, Optional, Union

class MQTTPublisher:
    """
    A class to handle connecting to an MQTT broker and publishing data.
    """
    def __init__(self, broker_host: str, broker_port: int = 1883, *, username: Optional[str] = None, password: Optional[str] = None, tls_enabled: bool = False, ca_certs: Optional[str] = None):
        """
        Initializes the MQTT client.
        :param broker_host: The IP address or hostname of the MQTT broker.
        :param broker_port: The port of the MQTT broker (default is 1883).
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish

        # Auth
        if username is not None:
            try:
                self.client.username_pw_set(username=username, password=password)
            except Exception:
                # Fallback for paho-mqtt v2 API changes
                self.client.username_pw_set(username, password)

        # TLS (optional)
        if tls_enabled:
            if ca_certs:
                self.client.tls_set(ca_certs=ca_certs)
            else:
                self.client.tls_set()  # default certs

    def _on_connect(self, client, userdata, flags, rc):
        """Callback function for when the client connects to the broker."""
        if rc == 0:
            print("Successfully connected to MQTT Broker!")
        else:
            print(f"Failed to connect, return code {rc}\n")

    def _on_disconnect(self, client, userdata, rc):
        if rc == 0:
            print("Disconnected from MQTT Broker")
        else:
            print(f"Unexpected MQTT disconnection (rc={rc})")

    def _on_publish(self, client, userdata, mid):
        # Basic notification; UI can also log when calling publish directly
        pass

    def connect(self, keepalive: int = 60) -> bool:
        """
        Connects to the MQTT broker and starts the network loop.
        Returns True on success, False on failure.
        """
        try:
            print(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}...")
            self.client.connect(self.broker_host, self.broker_port, keepalive)
            self.client.loop_start()  # Starts a background thread for the network loop
            return True
        except Exception as e:
            print(f"Could not connect to MQTT broker: {e}")
            return False

    def publish(self, topic: str, payload: Union[Dict[str, Any], str], qos: int = 0, retain: bool = False) -> bool:
        """
        Publishes a payload to a specific topic.
        - If payload is a dict, it will be converted to JSON string.
        - If payload is a string, it will be sent as-is.
        """
        try:
            # Convert dict to JSON, otherwise use string as-is
            data_to_send = json.dumps(payload) if isinstance(payload, dict) else str(payload)
            result = self.client.publish(topic, data_to_send, qos=qos, retain=retain)
            # Check if publish was successful
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"Failed to publish message to topic {topic}")
                return False
            return True
        except Exception as e:
            print(f"An error occurred during publishing: {e}")
            return False

    def disconnect(self):
        """Stops the network loop and disconnects from the broker."""
        print("Disconnecting from MQTT broker...")
        self.client.loop_stop()
        self.client.disconnect()
        print("Disconnected.")
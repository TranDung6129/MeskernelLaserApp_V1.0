import paho.mqtt.client as mqtt
import json
from typing import Dict, Any

class MQTTPublisher:
    """
    A class to handle connecting to an MQTT broker and publishing data.
    """
    def __init__(self, broker_host: str, broker_port: int = 1883):
        """
        Initializes the MQTT client.
        :param broker_host: The IP address or hostname of the MQTT broker.
        :param broker_port: The port of the MQTT broker (default is 1883).
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect

    def _on_connect(self, client, userdata, flags, rc):
        """Callback function for when the client connects to the broker."""
        if rc == 0:
            print("Successfully connected to MQTT Broker!")
        else:
            print(f"Failed to connect, return code {rc}\n")

    def connect(self) -> bool:
        """
        Connects to the MQTT broker and starts the network loop.
        Returns True on success, False on failure.
        """
        try:
            print(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}...")
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()  # Starts a background thread for the network loop
            return True
        except Exception as e:
            print(f"Could not connect to MQTT broker: {e}")
            return False

    def publish(self, topic: str, payload: Dict[str, Any]):
        """
        Publishes a payload to a specific topic.
        The payload dictionary will be converted to a JSON string.
        """
        try:
            # Convert the Python dictionary to a JSON string
            json_payload = json.dumps(payload)
            result = self.client.publish(topic, json_payload)
            # Check if publish was successful
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"Failed to publish message to topic {topic}")
        except Exception as e:
            print(f"An error occurred during publishing: {e}")

    def disconnect(self):
        """Stops the network loop and disconnects from the broker."""
        print("Disconnecting from MQTT broker...")
        self.client.loop_stop()
        self.client.disconnect()
        print("Disconnected.")
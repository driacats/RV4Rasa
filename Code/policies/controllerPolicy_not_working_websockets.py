from typing import List, Dict, Text, Optional, Any, Union, Tuple
from rasa.core.policies.policy import Policy, PolicyPrediction
from rasa.shared.nlu.interpreter import NaturalLanguageInterpreter
from rasa.shared.core.trackers import DialogueStateTracker
from rasa.shared.core.generator import TrackerWithCachedStates
from rasa.shared.core.domain import Domain
from rasa.shared.core.constants import ACTION_LISTEN_NAME
from rasa.core.featurizers.tracker_featurizers import TrackerFeaturizer
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.training.fingerprinting import Fingerprintable
from rasa.engine.storage.storage import ModelStorage
from rasa.engine.storage.resource import Resource
from rasa.engine.graph import ExecutionContext
import asyncio, websockets, re, time
from websocket import create_connection

@DefaultV1Recipe.register([DefaultV1Recipe.ComponentType.POLICY_WITHOUT_END_TO_END_SUPPORT], is_trainable=False)
class ControllerPolicy(Policy):

	user_uttered_regex = "UserUttered\((?:text): (.{1,20}), (?:intent): ([A-Z]?\w+), (?:use_text_for_featurization): ([A-Z]?\w+)\)"
	bot_uttered_regex = "BotUttered\((?:text): (.{1,20}), (?:data): {(?:\"elements\"): (.{1,20}), (?:\"quick_replies\"): (.{1,20}), (?:\"buttons\"): (.{1,20}), (?:\"attachment\"): (.{1,20}), (?:\"image\"): (.{1,20}), (?:\"custom\"): (.{1,20})}, (?:metadata): {(?:\"utter_action\"): \"(.{1,20})\", (?:\"model_id\"): \"([a-z0-9]{32})\", (?:\"assistant_id\"): \"(.{1,35})\"}\)"

	# The function __init__ initializes the class.
	# With respect to the super class it is initialized the socket client that will connect to the monitor.
	def __init__(self, cls, model_storage, resource, execution_context, error_action="utter_error_message"):
		super().__init__(cls, model_storage, resource, execution_context)
		#self.socket_client = socket.socket()
		#self.socket_client.connect(('127.0.0.1', 5002))
		self.error_action = error_action

	# The function train is called during the training phase of rasa.
	def train(self, training_trackers:List[TrackerWithCachedStates], domain:Domain, **kwargs:Any) -> Fingerprintable:
		pass

	def user_uttered_parse(self, event):
		data = re.findall(self.user_uttered_regex, event)
		if not data:
			return ""
		data = data[0]
		# data[0]: text
		# data[1]: intent
		# data[2]: use
		message = "\"UserUttered\": {"
		message += "\"text\": \"" + data[0]
		message += "\", \"intent\": \"" + data[1]
		message += "\", \"use_text_for_featurization\": \"" + data[2] + "\"},"
		return message

	def bot_uttered_parse(self, event):
		data = re.findall(self.bot_uttered_regex, event)
		if not data:
			return ""
		data = data[0]
		# data[0]: text
		# data:
		# 	data[1]: elements
		# 	data[2]: quick_replies
		# 	data[3]: buttons
		# 	data[4]: attachment
		# 	data[5]: image
		#	data[6]: custom
		# metadata:
		#	data[7]: utter_action
		#	data[8]: model_id
		#	data[9]: assistant_id
		message = "\"BotUttered\": {"
		message += "\"text\": \"" + data[0]
		message += "\", \"data\": {"
		message += "\"elements\": \"" + data[1]
		message += "\", \"quick_replies\": \"" + data[2]
		message += "\", \"buttons\": \"" + data[3]
		message += "\", \"attachment\": \"" + data[4]
		message += "\", \"image\": \"" + data[5]
		message += "\", \"custom\": \"" + data[6] + "\"}, "
		message += "\"metadata\": {"
		message += "\"utter_action\": \"" + data[7]
		message += "\", \"model_id\": \"" + data[8]
		message += "\", \"assistant_id\": \"" + data[9] + "\"}},"
		return message


	# The function build_message builds a JSON message with all the available infos.
	# TODO: Events are not included for the moment: there are issues with their format.
	# TODO: Include slots.
	def build_message(self, tracker, domain):
		message = "{\n"
		# 1. Text
		message += "\"text\": \"" + str(tracker.latest_message.text) + "\",\n"
		# 2. Intents
		message += "\"intent\": " + str(tracker.latest_message.intent).replace("\'", "\"") + ",\n"
		# 3. Entities
		message += "\"entities\": ["
		for entity in tracker.latest_message.entities:
			message += "\"" + str(entity) + "\", "
		message += "],\n"
		# 4. Events
		message += "\"events\": {"
		for event in tracker.events:
			event = str(event)
			if "UserUttered(" in event:
				m = self.user_uttered_parse(event)
				if m != "":
					message += m
				else:
					message += event.upper()
			elif "BotUttered(" in event:
				m = self.bot_uttered_parse(event)
				if m != "":
					message += m
				else:
					message += event.upper()
			else:
				message += "\"" + str(event).replace(":", "=").replace(",", ";") + "\": \"NULL\", "
		message = message[:-1]
		message += "},\n"
		# 5. Slots
		message += "\"slots\": {"
		slot_dict = tracker.current_slot_values()
		for slot in slot_dict:
			message += "\"" + str(slot) + "\": \"" + str(slot_dict[slot]) + "\",\n"
		message = message[:-2]
		message += "\n},\n"
		# 6. Latest Action Name
		message += "\"latest_action_name\": \"" + tracker.latest_action_name + "\"\n}"
		return message

	async def send_message(self, message):
		async with websockets.connect("ws://localhost:5002") as websocket:
			await websocket.send(message)
			result = await websocket.recv()
			print('[SEND] Returning result: ', result)
			## self.message_received = result
		return result

	def get_oracle_res(self, fut):
		print('Returning the oracle result that is: ', fut.result())
		return fut.result()

	# The function predict_action_probabilities is called when a message arrives to rasa and returns a prediction.
	def predict_action_probabilities(self, tracker:DialogueStateTracker, domain:Domain, **kwargs:Any) -> PolicyPrediction:
		prediction = self._default_predictions(domain)
		if not tracker.past_states(domain)[-1]['prev_action']['action_name'] == ACTION_LISTEN_NAME:
			prediction[domain.index_for_action(ACTION_LISTEN_NAME)] = 1.0
			return self._prediction(prediction)
		latest_message = self.build_message(tracker, domain)
		# self.socket_client.send(latest_message.encode())
		# oracle = self.socket_client.recv(1024).decode()
		try:
			loop = asyncio.get_running_loop()
		except RuntimeError:  # 'RuntimeError: There is no current event loop...'
			loop = None
		if loop and loop.is_running():
			print('[MAIN] Async event loop already running. Adding coroutine to the event loop.')
			task = loop.create_task(self.send_message(latest_message))
			# oracle_res = loop_event.run_until_complete(task)
			print('[MAIN] Run Until Complete')
			oracle = loop.run_until_complete(task)
			# oracle = loop.run_until_complete(self.send_message(latest_message))
			# oracle = loop.ensure_future(self.send_message(latest_message))
			# oracle = task.add_done_callback(self.get_oracle_res)
			# oracle = task.add_done_callback(lambda t: t.result())
		else:
			print('Starting new event loop')
			result = asyncio.run(self.send_message(latest_message))
		# oracle = oracle_res
		# while not self.message_received:
		# 	pass
		# oracle = self.message_received
	# 	while not oracle:
	# 		asyncio.sleep(0.5)
		print('[MAIN] Getting the oracle result')
		oracle = oracle.result()
		if "True" in oracle:
			prediction[domain.index_for_action(self.error_action)] = 1.0
			return self._prediction(prediction)

	@classmethod
	def create(cls, config: Dict[Text, Any], model_storage: ModelStorage, resource: Resource, execution_context: ExecutionContext, **kwargs:Any):
		return cls(config, model_storage, resource, execution_context)

	@classmethod
	def load(cls, config: Dict[Text, Any], model_storage: ModelStorage, resource: Resource, execution_context: ExecutionContext, **kwargs: Any):
		return cls(config, model_storage, resource, execution_context)

	def get_default_config() -> Dict[Text, Any]:
		return {"priority": 2}

	@classmethod
	def _metadata_filename(cls):
		return "controller_policy.json"

	def _metadata(self):
		return{
			"priority": self.priority
		}


class ControllerFingerprintable(Fingerprintable):
	def fingerprint(self) -> Text:
		# Implement the fingerprint method as needed
		# This method should return a string that uniquely identifies the state of the object
		return "ControllerPolicy"

from typing import List, Dict, Text, Any
from rasa.core.policies.policy import Policy, PolicyPrediction
from rasa.shared.core.trackers import DialogueStateTracker
from rasa.shared.core.generator import TrackerWithCachedStates
from rasa.shared.core.domain import Domain
from rasa.shared.core.constants import ACTION_LISTEN_NAME
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.training.fingerprinting import Fingerprintable
from rasa.engine.storage.storage import ModelStorage
from rasa.engine.storage.resource import Resource
from rasa.engine.graph import ExecutionContext
import re
from websocket import create_connection

@DefaultV1Recipe.register([DefaultV1Recipe.ComponentType.POLICY_WITHOUT_END_TO_END_SUPPORT], is_trainable=False)
class ControllerPolicy(Policy):

	user_uttered_regex = "UserUttered\((?:text): (.+), (?:intent): ([A-Z]?\w+), (?:use_text_for_featurization): ([A-Z]?\w+)\)"
	bot_uttered_regex = "BotUttered\((?:text): (.+), (?:data): {(?:\"elements\"): (.{1,20}), (?:\"quick_replies\"): (.{1,20}), (?:\"buttons\"): (.{1,20}), (?:\"attachment\"): (.{1,20}), (?:\"image\"): (.{1,20}), (?:\"custom\"): (.{1,20})}, (?:metadata): {(?:\"utter_action\"): \"(.{1,20})\", (?:\"model_id\"): \"([a-z0-9]{32})\", (?:\"assistant_id\"): \"(.{1,35})\"}\)"

	# The function __init__ initializes the class.
	# With respect to the super class it is initialized the socket client that will connect to the monitor.
	def __init__(self, cls, model_storage, resource, execution_context, error_action="utter_error_message"):
		# We call the super function
		super().__init__(cls, model_storage, resource, execution_context)
		# Set the error_action
		self.error_action = error_action
		# Create a connection to the monitor
		self.ws = create_connection("ws://localhost:5002")

	# The function train is called during the training phase of rasa.
	# In our case the monitor is deterministic, there is no training phase, so we can simply pass it.
	def train(self, training_trackers:List[TrackerWithCachedStates], domain:Domain, **kwargs:Any) -> Fingerprintable:
		pass

	# The function user_uttered_parse takes as input an Event string that contains the message of the user,
	# parses it using regex and creates a json formatted string containing the data.
	def user_uttered_parse(self, event):
		data = re.findall(self.user_uttered_regex, event)
		##  if not data:
		##  	return ""
		data = data[0]
		# data[0]: text
		# data[1]: intent
		# data[2]: use
		message = "\"UserUttered\": {"
		message += "\"text\": \"" + data[0]
		message += "\", \"intent\": \"" + data[1]
		message += "\", \"use_text_for_featurization\": \"" + data[2] + "\"},"
		return message

	# The function bot_uttered_parse takes as input an Event string that contains the message of the bot with all the data and metadata,
	# parses it using regex and creates a json formatted string containing the data.
	def bot_uttered_parse(self, event):
		data = re.findall(self.bot_uttered_regex, event)
		## if not data:
		## 	return ""
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
	# The message includes:
	# - text
	# - intents
	# - entities
	# - events
	# - slots
	# - latest_action_name
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

	# The function predict_action_probabilities is called when a message arrives to rasa and returns a prediction.
	def predict_action_probabilities(self, tracker:DialogueStateTracker, domain:Domain, **kwargs:Any) -> PolicyPrediction:
		# We start with the default predictions
		prediction = self._default_predictions(domain)
		# If the latest action of the bot was listen than it can go on.
		# These three lines prevent the function to send the message more times, without them, the server will receive
		# multiple messages for each message sent from the user on the chat.
		if not tracker.past_states(domain)[-1]['prev_action']['action_name'] == ACTION_LISTEN_NAME:
			prediction[domain.index_for_action(ACTION_LISTEN_NAME)] = 1.0
			return self._prediction(prediction)
		# We build the json string with the data of the last message
		latest_message = self.build_message(tracker, domain)
		# We send it to the monitor and wait for the answer.
		self.ws.send(latest_message)
		oracle = self.ws.recv()
		# If the monitor returns False then the message is not accepted and the action used is the error one.
		# Instead we do nothing, leaving the bot follow its routine.
		if "False" in oracle:
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

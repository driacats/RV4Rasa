from rasa.core.policies.policy import Policy
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.shared.nlu.training_data.message import Message
from rasa.shared.core.domain import Domain
from rasa.engine.storage.storage import ModelStorage
from rasa.engine.storage.resource import Resource
from rasa.engine.graph import ExecutionContext
from rasa.shared.core.trackers import DialogueStateTracker
from rasa.shared.nlu.training_data.training_data import TrainingData
from typing import List, Type, Dict, Text, Any, Optional
from rasa.engine.training.fingerprinting import Fingerprintable

# TODO: Correctly register your graph component
@DefaultV1Recipe.register(
    [DefaultV1Recipe.ComponentType.POLICY_WITHOUT_END_TO_END_SUPPORT], is_trainable=False
)
class Controller(Policy):

    def __init__(self, cls, model_storage, resource, execution_context):
        super().__init__(cls, model_storage, resource, execution_context)
    
    @classmethod
    def create(
        cls,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ):
        return cls(config, model_storage, resource, execution_context)

    @classmethod
    def load(
        cls,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
        **kwargs: Any
    ):
        return cls(config, model_storage, resource, execution_context)

    def get_default_config() -> Dict[Text, Any]:
        return {"priority": 2}

    def predict_action_probabilities(tracker: DialogueStateTracker, domain: Domain) -> List[float]:
        # implementa la logica per predire le probabilità delle azioni
        print("Prova prova")
        probabilities = tracker.latest_message.intent_resemblance
        return probabilities

    def train(self, training_data: TrainingData, **kwargs: Any) -> Fingerprintable:
        # implementa la logica per addestrare la policy sui dati di addestramento
        return training_data

    def process(message: Message, **kwargs: Any):
        metadata = message.get("metadata")
        print(metadata.get("intent"))
        print(metadata.get("example"))
        return None


class MyFingerprintable(Fingerprintable):
    def fingerprint(self) -> Text:
        # Implement the fingerprint method as needed
        # This method should return a string that uniquely identifies the state of the object
        return "my_fingerprintable"
